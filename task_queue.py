"""
Queue de tareas asíncronas usando Redis + RQ.
Procesa escaneos, descarga de letras y enriquecimiento MusicBrainz en workers separados.
"""
import os
import redis
from rq import Queue

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

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
