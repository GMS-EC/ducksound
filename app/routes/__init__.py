# -*- coding: utf-8 -*-
"""
Subpaquete de Rutas / Blueprints - DuckSound
Importa y expone todos los Blueprints de la aplicación para que la fábrica create_app() los registre fácilmente.
"""
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
from app.routes.audio import audio_bp
from app.routes.main import main_bp
from app.routes.api import api_bp

# Exponer los blueprints al nivel del paquete routes
__all__ = ['auth_bp', 'admin_bp', 'audio_bp', 'main_bp', 'api_bp']
