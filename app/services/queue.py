# -*- coding: utf-8 -*-
"""
Servicio de Cola de Tareas en Segundo Plano - DuckSound
Wrapper para interactuar con Redis RQ (Redis Queue), gestionar tareas de escaneo
e indexación asíncrona, y rastrear el porcentaje de progreso mediante claves persistentes en Redis.
"""
import os
import json
import time
import redis
from rq import Queue

# Configuración de conexiones de Redis desde variables de entorno
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Prefijos para claves dentro de Redis
REDIS_SCAN_PREFIX = 'ducksound:scan:'
REDIS_ACTIVE_KEY = 'ducksound:scan:active_id'
REDIS_PROGRESS_PREFIX = 'ducksound:progress:'

_conn = None
_queue = None


def get_connection():
    """Inicializa y retorna la conexión persistente con el servidor de Redis."""
    global _conn
    if _conn is None:
        _conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                            socket_connect_timeout=5, socket_timeout=10,
                            retry_on_timeout=True)
    return _conn


def get_queue():
    """Retorna la cola de tareas asíncronas de RQ para DuckSound."""
    global _queue
    if _queue is None:
        _queue = Queue('ducksound', connection=get_connection(), default_timeout=3600)
    return _queue


def enqueue(func, *args, **kwargs):
    """Agrega una función a la cola de tareas de Redis RQ para ejecución en un worker separado."""
    q = get_queue()
    return q.enqueue(func, *args, **kwargs)


# ==========================================================
# 📊 CONTROL DE ESTADOS DE ESCANEO DE CANCIONES (Redis)
# ==========================================================

def _r():
    """Helper simple para obtener la conexión activa de Redis."""
    return get_connection()


def scan_task_set(task_id, data):
    """Guarda el estado e información de avance de una tarea de escaneo con un TTL de 2 horas."""
    data['updated_at'] = time.time()
    _r().setex(f'{REDIS_SCAN_PREFIX}{task_id}', 7200, json.dumps(data))


def scan_task_get(task_id):
    """Obtiene el diccionario de estado de una tarea de escaneo guardada en Redis."""
    raw = _r().get(f'{REDIS_SCAN_PREFIX}{task_id}')
    if raw:
        return json.loads(raw)
    return None


def scan_task_delete(task_id):
    """Elimina la información de rastreo de una tarea de escaneo en Redis."""
    _r().delete(f'{REDIS_SCAN_PREFIX}{task_id}')


def scan_set_active(task_id):
    """Registra cuál es el ID del escaneo en ejecución activa en este instante."""
    if task_id:
        _r().set(REDIS_ACTIVE_KEY, task_id, ex=7200)
    else:
        _r().delete(REDIS_ACTIVE_KEY)


def scan_get_active():
    """
    Retorna el ID y el diccionario de estado del escaneo activo en ejecución.
    Si la tarea expiró en Redis, limpia el puntero de activo de forma segura.
    """
    raw = _r().get(REDIS_ACTIVE_KEY)
    if raw:
        tid = raw.decode()
        task = scan_task_get(tid)
        if task:
            return tid, task
        # Limpieza por consistencia
        _r().delete(REDIS_ACTIVE_KEY)
    return None, None


# ==========================================================
# 📈 CONTROL DE PROGRESOS GENERALES (Lyrics, MusicBrainz)
# ==========================================================

def progress_set(key, data, ttl=7200):
    """Registra datos de progreso genéricos (ej. 'lyrics', 'mb') con un tiempo de expiración."""
    _r().setex(f'{REDIS_PROGRESS_PREFIX}{key}', ttl, json.dumps(data))


def progress_get(key):
    """Recupera la estructura de progreso genérico desde Redis."""
    raw = _r().get(f'{REDIS_PROGRESS_PREFIX}{key}')
    if raw:
        return json.loads(raw)
    return None


def progress_update(key, **kwargs):
    """Actualiza de forma atómica campos específicos del progreso."""
    data = progress_get(key) or {}
    data.update(kwargs)
    progress_set(key, data)


# ==========================================================
# ⚙️ FUNCIONES RUNNER QUE CORREN EN EL WORKER DE RQ
# ==========================================================

def _progress_wrapper(current_task_id):
    """
    Retorna una función callback que traduce payloads del escáner en
    actualizaciones de progreso dentro de la base de datos clave-valor Redis.
    """
    def _progress(payload):
        t = scan_task_get(current_task_id)
        if not t:
            return
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
    """
    Ejecuta un escaneo completo de la carpeta de audio indexando archivos nuevos
    y analizando la acústica de las canciones. Corre dentro del proceso del worker.
    """
    from app import create_app
    from app.services.scanner import AudioScanner

    app = create_app()
    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            scanner = AudioScanner()
            resumen = scanner.escanear_carpeta_audio(progress_callback=progress)
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'done'
                t['percent'] = 100
                t['summary'] = resumen
                t['message'] = 'Escaneo finalizado'
                scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'error'
                t['error'] = str(ex)
                t['message'] = f'Error: {ex}'
                scan_task_set(task_id, t)
        finally:
            scan_set_active(None)


def run_quick_scan(task_id):
    """
    Ejecuta un escaneo rápido (comparando marcas de tiempo de archivos en disco).
    Evita reprocesar archivos estables acelerando el inicio. Corre dentro del worker.
    """
    from app import create_app
    from app.services.scanner import AudioScanner

    app = create_app()
    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            scanner = AudioScanner()
            resumen = scanner.escaneo_rapido(progress_callback=progress)
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'done'
                t['percent'] = 100
                t['summary'] = resumen
                t['message'] = 'Escaneo rápido finalizado'
                scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'error'
                t['error'] = str(ex)
                t['message'] = f'Error: {ex}'
                scan_task_set(task_id, t)
        finally:
            scan_set_active(None)
