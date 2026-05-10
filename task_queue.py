"""
Queue de tareas asíncronas usando Redis + RQ.
Procesa escaneos, descarga de letras y enriquecimiento MusicBrainz en workers separados.
"""
import json
import time
import os
import redis
from rq import Queue

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_SCAN_PREFIX = 'ducksound:scan:'
REDIS_ACTIVE_KEY = 'ducksound:scan:active_id'

_conn = None
_queue = None


def get_connection():
    global _conn
    if _conn is None:
        _conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                            socket_connect_timeout=5, socket_timeout=10,
                            retry_on_timeout=True)
    return _conn


def get_queue():
    global _queue
    if _queue is None:
        _queue = Queue('ducksound', connection=get_connection(), default_timeout=3600)
    return _queue


def enqueue(func, *args, **kwargs):
    """Encola una función para ejecución en worker background."""
    q = get_queue()
    return q.enqueue(func, *args, **kwargs)


# === Scan task tracking via Redis ===

def _r():
    return get_connection()


def scan_task_set(task_id, data):
    """Guarda el estado de una tarea de escaneo en Redis."""
    data['updated_at'] = time.time()
    _r().setex(f'{REDIS_SCAN_PREFIX}{task_id}', 7200, json.dumps(data))  # TTL 2h


def scan_task_get(task_id):
    """Obtiene el estado de una tarea de escaneo."""
    raw = _r().get(f'{REDIS_SCAN_PREFIX}{task_id}')
    if raw:
        return json.loads(raw)
    return None


def scan_task_delete(task_id):
    """Elimina una tarea de escaneo."""
    _r().delete(f'{REDIS_SCAN_PREFIX}{task_id}')


def scan_set_active(task_id):
    """Marca una tarea como activa."""
    if task_id:
        _r().set(REDIS_ACTIVE_KEY, task_id, ex=7200)
    else:
        _r().delete(REDIS_ACTIVE_KEY)


def scan_get_active():
    """Obtiene la tarea activa actual."""
    raw = _r().get(REDIS_ACTIVE_KEY)
    if raw:
        tid = raw.decode()
        task = scan_task_get(tid)
        if task:
            return tid, task
        # Tarea activa pero expirada — limpiar
        _r().delete(REDIS_ACTIVE_KEY)
    return None, None


def scan_cleanup_old():
    """Limpia tareas expiradas — Redis las maneja con TTL."""
    pass


# === Progress tracking via Redis (letras, MB, etc) ===

REDIS_PROGRESS_PREFIX = 'ducksound:progress:'


def progress_set(key, data, ttl=7200):
    """Guarda progreso en Redis (ej: 'lyrics', 'mb')."""
    _r().setex(f'{REDIS_PROGRESS_PREFIX}{key}', ttl, json.dumps(data))


def progress_get(key):
    """Obtiene progreso de Redis."""
    raw = _r().get(f'{REDIS_PROGRESS_PREFIX}{key}')
    if raw:
        return json.loads(raw)
    return None


def progress_update(key, **kwargs):
    """Actualiza campos específicos del progreso existente."""
    data = progress_get(key) or {}
    data.update(kwargs)
    progress_set(key, data)
