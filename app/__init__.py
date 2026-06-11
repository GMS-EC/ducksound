# -*- coding: utf-8 -*-
"""
Inicialización del Paquete de la Aplicación Flask (DuckSound).
Implementa el patrón de Fábrica de Aplicaciones (Application Factory) mediante `create_app()`.
"""
import os
import sys
import secrets
from datetime import datetime, timedelta
from flask import Flask, session, redirect, url_for, request, jsonify, current_app, abort
from flask_compress import Compress
from flask_cors import CORS
from config import Config
from app.models import db, Usuario, SesionActiva

# Habilitar soporte UTF-8 para la salida en consola en entornos de desarrollo Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Instanciamos los componentes Flask que se vincularán dinámicamente en create_app
compress = Compress()


def create_app(config_class=Config):
    """
    Fábrica de la Aplicación (Application Factory).
    Crea, configura e inicializa una instancia de la aplicación Flask.
    
    Args:
        config_class: Clase o módulo de configuración (por defecto Config de config.py).
    
    Returns:
        Flask: Instancia completamente configurada de la aplicación Flask.
    """
    app = Flask(__name__, static_folder='../frontend/dist', static_url_path='/')
    app.config.from_object(config_class)

    # 1. Inicialización de extensiones
    db.init_app(app)
    compress.init_app(app)
    
    # CORS: permitir que el frontend (React en :5173) acceda a la API
    CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

    # 2. Creación automática de esquemas de base de datos
    with app.app_context():
        db.create_all()
        
        # Migración de base de datos para la columna 'audio_quality'
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                # Comprobar si la columna existe (funciona para Postgres y SQLite)
                columnas = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='usuarios' AND column_name='audio_quality'"
                )).fetchall()
                if not columnas:
                    try:
                        conn.execute(text("ALTER TABLE usuarios ADD COLUMN audio_quality VARCHAR(20) NOT NULL DEFAULT 'lossless'"))
                        conn.commit()
                        print("✅ [DuckSound] Columna 'audio_quality' agregada exitosamente a la tabla usuarios.")
                    except Exception as sqle:
                        if "duplicate column" in str(sqle).lower() or "already exists" in str(sqle).lower():
                            pass
                        else:
                            raise sqle
                else:
                    print("✅ [DuckSound] La columna 'audio_quality' ya existe en la tabla usuarios.")
        except Exception as e:
            print(f"⚠️ [DuckSound] Error en migración de base de datos para 'audio_quality': {e}")
        
        # Crear un usuario administrador inicial por defecto si la base de datos está vacía
        try:
            if Usuario.query.count() == 0:
                admin_user = Usuario(
                    nombre_usuario='ducksound',
                    role='admin'
                )
                admin_user.set_password('ducksound')  # Contraseña por defecto
                db.session.add(admin_user)
                db.session.commit()
                print("⚠️ [DuckSound] Usuario administrador inicial creado: ducksound / ducksound")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ [DuckSound] No se pudo comprobar/crear usuario inicial: {e}")

        # Limpiar archivos de transcodificación antiguos al iniciar
        try:
            from app.services.transcoder import limpiar_cache_transcodificacion
            limpiar_cache_transcodificacion()
        except Exception as e:
            print(f"⚠️ [DuckSound] Error limpiando caché de transcodificación: {e}")

        # Limpiar sesiones expiradas al iniciar
        try:
            from app.services.session_manager import limpiar_sesiones_expiradas
            exito, msg = limpiar_sesiones_expiradas()
            if exito:
                print(f"✅ [DuckSound] {msg}")
        except Exception as e:
            print(f"⚠️ [DuckSound] Error limpiando sesiones: {e}")

    # 3. Interceptores de Seguridad y Encabezados HTTP globales
    @app.errorhandler(403)
    def forbidden_error(e):
        return jsonify({'error': 'Forbidden', 'message': 'Acceso denegado'}), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return jsonify({'error': 'Not Found', 'message': 'El recurso solicitado no existe'}), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({'error': 'Internal Server Error', 'message': 'Ocurrió un error inesperado en el servidor'}), 500

    @app.route('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='img/favicon.png'))

    @app.after_request
    def add_security_headers(response):
        """Añade cabeceras estándar de protección contra ataques XSS y clickjacking."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.before_request
    def serve_spa():
        """
        Interviene antes de require_login y de la ejecución de rutas.
        Si la petición es GET, acepta 'text/html' y no se refiere a rutas
        especiales de medios/API directas, sirve directamente la SPA (index.html).
        """
        if request.method in ('GET', 'HEAD') and 'text/html' in request.headers.get('Accept', ''):
            if (request.path.startswith('/audio/') or 
                request.path.startswith('/album-art/') or 
                request.path.startswith('/lyrics/') or
                request.path.startswith('/api/')):
                return None
            
            try:
                return app.send_static_file('index.html')
            except Exception:
                abort(404)

    @app.before_request
    def require_login():
        """
        Escudo global: Intercepta todas las peticiones entrantes.
        Si la sesión de usuario no está activa y el recurso es privado, deniega el acceso.
        Valida además que la sesión no haya sido revocada remotamente.
        """
        # Se incluye catch_all para permitir cargar el index de la SPA sin redirección infinita
        allowed_endpoints = ['auth.login', 'static', 'favicon', 'index', 'catch_all']
        
        if request.method == 'OPTIONS':
            return
            
        # Si no hay sesión activa y el endpoint es privado
        if request.endpoint and request.endpoint not in allowed_endpoints and 'user_id' not in session:
            # Respuestas planas de audio, letras y carátulas (previene fugas de HTML a reproductores)
            if request.path.startswith('/audio/') or request.path.startswith('/album-art/') or request.path.startswith('/lyrics/'):
                return "Acceso denegado", 401
                
            return jsonify({'error': 'Acceso denegado: Inicia sesión primero'}), 401
        
        # Validar que la sesión no haya sido revocada remotamente
        if 'user_id' in session and request.endpoint and request.endpoint not in allowed_endpoints:
            token = session.get('session_token')
            if token:
                # 1. Intentar validación rápida vía Redis
                from app.services.queue import get_connection
                try:
                    r = get_connection()
                    cached_user_id = r.get(f"ducksound:session:{token}")
                    if cached_user_id:
                        # Sesión válida y cacheada
                        pass
                    else:
                        # 2. Fallback a DB si no está en caché
                        sesion_db = SesionActiva.query.filter_by(session_token=token).first()
                        if not sesion_db:
                            # La sesión fue revocada
                            session.clear()
                            return jsonify({'error': 'Sesión revocada'}), 401
                        
                        # Actualizar caché para futuras peticiones
                        r.setex(f"ducksound:session:{token}", 3600, sesion_db.usuario_id)
                except Exception as e:
                    # En caso de error de Redis, fallamos hacia la DB para no bloquear al usuario
                    sesion_db = SesionActiva.query.filter_by(session_token=token).first()
                    if not sesion_db:
                        session.clear()
                        return jsonify({'error': 'Sesión revocada'}), 401
                
                # Actualizar última actividad cada 5 minutos para no saturar la DB
                ahora = datetime.utcnow()
                # Solo intentamos actualizar si ya tenemos el objeto sesion_db o si ha pasado tiempo
                # Para evitar el UnboundLocalError, primero nos aseguramos de tener el objeto si queremos actualizarlo
                try:
                    if 'sesion_db' not in locals():
                        sesion_db = SesionActiva.query.filter_by(session_token=token).first()
                    
                    if sesion_db and (not sesion_db.ultima_actividad or (ahora - sesion_db.ultima_actividad) > timedelta(minutes=5)):
                        sesion_db.ultima_actividad = ahora
                        db.session.commit()
                except Exception as e:
                    current_app.logger.warning(f"[Session Activity] Error actualizando actividad: {e}")


    @app.before_request
    def csrf_protect():
        """
        Protección básica CSRF para solicitudes basadas en formularios estándar (POST/PUT/DELETE).
        Exime de manera controlada los endpoints de APIs asíncronas y administración remota autorizada.
        """
        if request.method not in ["GET", "HEAD", "OPTIONS", "TRACE"]:
            # Eximir APIs y administración
            if request.path.startswith('/api/') or request.path.startswith('/admin/') or request.path == '/login':
                return
            
            token = session.get('_csrf_token')
            if not token:
                return jsonify({'error': 'Falta el token CSRF en la sesión'}), 403
                
            req_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
            if not req_token and request.is_json:
                req_token = request.json.get('csrf_token')
                
            if not req_token or req_token != token:
                return jsonify({'error': 'Token CSRF inválido o faltante'}), 403



    # 4. Registro centralizado de Blueprints
    from app.routes import auth_bp, admin_bp, audio_bp, main_bp, api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        # Evitar capturar rutas de la API, audio, admin o ficheros estáticos de assets
        if path.startswith('api/') or path.startswith('audio/') or path.startswith('admin/') or path.startswith('login') or path.startswith('logout') or path.startswith('album-art/') or path.startswith('lyrics/'):
            abort(404)
        try:
            return app.send_static_file('index.html')
        except Exception:
            abort(404)

    return app


# Instancia por defecto expuesta a nivel de paquete
# Esto permite hacer 'from app import app, db' manteniendo total compatibilidad.
app = create_app()
