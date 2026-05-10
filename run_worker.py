"""
Worker de Redis RQ para tareas background.
Ejecutar como: python run_worker.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_queue import get_connection
from rq import Worker, Queue

if __name__ == '__main__':
    conn = get_connection()
    queues = ['ducksound']
    worker = Worker(queues, connection=conn)
    print("🎵 DuckSound Worker iniciado. Escuchando cola:", queues)
    worker.work()
