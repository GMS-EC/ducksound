# -*- coding: utf-8 -*-
"""
Worker de Redis RQ para DuckSound
===============================
Este script se encarga de ejecutar y procesar las tareas en segundo plano.
Utiliza Redis y el framework RQ (Redis Queue) para procesar colas de trabajo.
"""

import os
import sys

# Comentarios en español para futuras tareas de mantenimiento
# -----------------------------------------------------------
# Agregamos el directorio raíz del proyecto al sys.path para asegurar que
# todas las importaciones relativas y absolutas del paquete 'app' funcionen
# correctamente dentro del proceso secundario del worker de Docker o local.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.queue import get_connection
from rq import Worker

if __name__ == '__main__':
    conn = get_connection()
    queues = ['ducksound']
    
    # Creamos e iniciamos el worker de RQ conectado al Redis de DuckSound
    worker = Worker(queues, connection=conn)
    print(f"🎵 [DuckSound Worker] Iniciado con éxito. Escuchando cola: {queues}")
    worker.work()
