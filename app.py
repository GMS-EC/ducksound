# -*- coding: utf-8 -*-
"""
Punto de Entrada de DuckSound
===========================
Este archivo es el punto de entrada oficial para iniciar la aplicación Flask.
Expone las instancias globales 'app' y 'db' para permitir el inicio continuo
mediante Gunicorn, Waitress, Docker y los scripts de migración heredados.
"""

import os
from app import app, db

# Comentarios en español para futuras tareas de mantenimiento
# -----------------------------------------------------------
# Si ejecutas este archivo directamente en tu entorno local (python app.py),
# se iniciará el servidor web Flask en modo depuración (debug=True).
# En producción, Gunicorn utilizará la variable 'app' expuesta aquí.

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8604))
    print(f"🎵 Iniciando DuckSound en el puerto {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
