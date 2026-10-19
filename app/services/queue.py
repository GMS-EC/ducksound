# -*- coding: utf-8 -*-
"""
Servicio de Cola de Tareas en Segundo Plano - DuckSound
======================================================
Permite ejecutar tareas pesadas de escaneo, transcodificación y enriquecimiento
en segundo plano.
- Modo Ultra-Ligero (por defecto si no hay Redis): Utiliza un ThreadPoolExecutor en memoria.
- Modo Distribuido: Utiliza Redis y RQ si Redis está activo.
"""
import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Configuración de conexiones de Redis desde variables de entorno
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'auto').lower()

# Prefijos para claves dentro de Redis
REDIS_SCAN_PREFIX = 'ducksound:scan:'
REDIS_ACTIVE_KEY = 'ducksound:scan:active_id'
REDIS_PROGRESS_PREFIX = 'ducksound:progress:'

_conn = None
_queue = None
_redis_available = None

# Almacenamiento en memoria para modo ultra-ligero sin Redis
_mem_lock = threading.Lock()
_mem_tasks = {}
_mem_active_scan_id = None
_mem_progress = {}
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='ducksound_bg')


def is_redis_available():
    """Comprueba si Redis está disponible para su uso."""
    global _redis_available
    if REDIS_ENABLED in ('false', '0', 'no', 'none'):
        return False
    if _redis_available is not None:
        return _redis_available
    try:
        import redis
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                             socket_connect_timeout=1, socket_timeout=2)
        client.ping()
        _redis_available = True
    except Exception:
        _redis_available = False
    return _redis_available


def get_connection():
    """Inicializa y retorna la conexión con Redis si está disponible."""
    global _conn
    if not is_redis_available():
        return None
    if _conn is None:
        import redis
        _conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                            socket_connect_timeout=3, socket_timeout=5,
                            retry_on_timeout=True)
    return _conn


def get_queue():
    """Retorna la cola de tareas asíncronas de RQ para DuckSound si Redis está disponible."""
    global _queue
    if not is_redis_available():
        return None
    if _queue is None:
        from rq import Queue
        _queue = Queue('ducksound', connection=get_connection(), default_timeout=3600)
    return _queue


def enqueue(func, *args, **kwargs):
    """
    Agrega una tarea a la cola:
    - Si Redis está disponible, encola en RQ.
    - Si no hay Redis (Modo Ultra-Ligero), ejecuta asíncronamente en el ThreadPoolExecutor.
    """
    if is_redis_available():
        try:
            q = get_queue()
            if q:
                return q.enqueue(func, *args, **kwargs)
        except Exception:
            pass
    # Modo local en segundo plano (ThreadPool)
    return _executor.submit(func, *args, **kwargs)


# ==========================================================
# 📊 CONTROL DE ESTADOS DE ESCANEO DE CANCIONES
# ==========================================================

def scan_task_set(task_id, data):
    """Guarda el estado e información de avance de una tarea de escaneo."""
    data['updated_at'] = time.time()
    if is_redis_available():
        try:
            get_connection().setex(f'{REDIS_SCAN_PREFIX}{task_id}', 7200, json.dumps(data))
            return
        except Exception:
            pass
    with _mem_lock:
        _mem_tasks[str(task_id)] = data.copy()


def scan_task_get(task_id):
    """Obtiene el diccionario de estado de una tarea de escaneo."""
    if is_redis_available():
        try:
            raw = get_connection().get(f'{REDIS_SCAN_PREFIX}{task_id}')
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    with _mem_lock:
        data = _mem_tasks.get(str(task_id))
        return data.copy() if data else None


def scan_task_delete(task_id):
    """Elimina la información de rastreo de una tarea de escaneo."""
    if is_redis_available():
        try:
            get_connection().delete(f'{REDIS_SCAN_PREFIX}{task_id}')
        except Exception:
            pass
    with _mem_lock:
        _mem_tasks.pop(str(task_id), None)


def scan_set_active(task_id):
    """Registra cuál es el ID del escaneo en ejecución activa en este instante."""
    global _mem_active_scan_id
    if is_redis_available():
        try:
            if task_id:
                get_connection().set(REDIS_ACTIVE_KEY, task_id, ex=7200)
            else:
                get_connection().delete(REDIS_ACTIVE_KEY)
            return
        except Exception:
            pass
    with _mem_lock:
        _mem_active_scan_id = str(task_id) if task_id else None


def scan_get_active():
    """Retorna el ID y el diccionario de estado del escaneo activo en ejecución."""
    global _mem_active_scan_id
    if is_redis_available():
        try:
            raw = get_connection().get(REDIS_ACTIVE_KEY)
            if raw:
                tid = raw.decode()
                task = scan_task_get(tid)
                if task:
                    return tid, task
                get_connection().delete(REDIS_ACTIVE_KEY)
        except Exception:
            pass
    with _mem_lock:
        if _mem_active_scan_id:
            task = _mem_tasks.get(_mem_active_scan_id)
            if task:
                return _mem_active_scan_id, task.copy()
            _mem_active_scan_id = None
    return None, None


# ==========================================================
# 📈 CONTROL DE PROGRESOS GENERALES (Lyrics, MusicBrainz)
# ==========================================================

def progress_set(key, data, ttl=7200):
    """Registra datos de progreso genéricos (ej. 'lyrics', 'mb')."""
    if is_redis_available():
        try:
            get_connection().setex(f'{REDIS_PROGRESS_PREFIX}{key}', ttl, json.dumps(data))
            return
        except Exception:
            pass
    with _mem_lock:
        _mem_progress[key] = data.copy()


def progress_get(key):
    """Recupera la estructura de progreso genérico."""
    if is_redis_available():
        try:
            raw = get_connection().get(f'{REDIS_PROGRESS_PREFIX}{key}')
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    with _mem_lock:
        data = _mem_progress.get(key)
        return data.copy() if data else None


def progress_update(key, **kwargs):
    """Actualiza de forma atómica campos específicos del progreso."""
    data = progress_get(key) or {}
    data.update(kwargs)
    progress_set(key, data)


# ==========================================================
# ⚙️ FUNCIONES RUNNER QUE CORREN EN SEGUNDO PLANO
# ==========================================================

def _progress_wrapper(current_task_id):
    """Retorna un callback que actualiza el estado de la tarea de escaneo."""
    def _progress(payload):
        t = scan_task_get(current_task_id) or {}
        t.update({
            'percent': payload.get('percent', t.get('percent', 0)),
            'message': payload.get('message', t.get('message', '')),
            'processed': payload.get('processed', t.get('processed', 0)),
            'total': payload.get('total', t.get('total', 0)),
        })
        if payload.get('current_file'):
            t['current_file'] = payload.get('current_file')
        if payload.get('summary'):
            t['summary'] = payload.get('summary')
        
        stage = payload.get('stage')
        if stage == 'done':
            t['status'] = 'done'
        elif stage == 'enriching':
            t['status'] = 'enriching'
        elif stage == 'error':
            t['status'] = 'error'
            t['error'] = payload.get('message') or 'Error'
        
        scan_task_set(current_task_id, t)
    return _progress


def run_full_scan(task_id):
    """Ejecuta un escaneo completo de la carpeta de audio."""
    from app import create_app
    from app.services.scanner import escanear_carpeta_audio

    app = create_app()
    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            resumen = escanear_carpeta_audio(progress_callback=progress)
            t = scan_task_get(task_id) or {}
            t['status'] = 'done'
            t['percent'] = 100
            t['summary'] = resumen
            t['message'] = 'Escaneo finalizado'
            scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id) or {}
            t['status'] = 'error'
            t['error'] = str(ex)
            t['message'] = f'Error: {ex}'
            scan_task_set(task_id, t)
        finally:
            scan_set_active(None)


def run_quick_scan(task_id):
    """Ejecuta un escaneo rápido."""
    from app import create_app
    from app.services.scanner import escaneo_rapido

    app = create_app()
    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            resumen = escaneo_rapido(progress_callback=progress)
            t = scan_task_get(task_id) or {}
            t['status'] = 'done'
            t['percent'] = 100
            t['summary'] = resumen
            t['message'] = 'Escaneo rápido finalizado'
            scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id) or {}
            t['status'] = 'error'
            t['error'] = str(ex)
            t['message'] = f'Error: {ex}'
            scan_task_set(task_id, t)
        finally:
            scan_set_active(None)


def run_generate_daily_mixes(usuario_id):
    """Ejecuta la generación de mixes diarios en segundo plano."""
    from app import create_app
    from app.services.recommender import generate_daily_mixes_for_user

    app = create_app()
    with app.app_context():
        try:
            generate_daily_mixes_for_user(usuario_id)
        except Exception as e:
            app.logger.error(f"[Daily Mixes] Error al generar mixes en segundo plano: {e}")
