# -*- coding: utf-8 -*-
"""
Inicialización del Paquete de la Aplicación Flask (DuckSound).
Implementa el patrón de Fábrica de Aplicaciones (Application Factory) mediante `create_app()`.
"""
import os
import sys
import secrets
from flask import Flask, session, redirect, url_for, request, jsonify
from flask_compress import Compress
from config import Config
from app.models import db, Usuario

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
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Inicialización de extensiones
    db.init_app(app)
    compress.init_app(app)

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

    # 3. Interceptores de Seguridad y Encabezados HTTP globales
    @app.after_request
    def add_security_headers(response):
        """Añade cabeceras estándar de protección contra ataques XSS y clickjacking."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.before_request
    def require_login():
        """
        Escudo global: Intercepta todas las peticiones entrantes.
        Si la sesión de usuario no está activa y el recurso es privado, deniega el acceso.
        """
        # Se incluye tanto 'main.index' como 'index' y 'auth.login' para evitar bucles de redirección
        allowed_endpoints = ['auth.login', 'static', 'index', 'main.index']
        
        if request.method == 'OPTIONS':
            return
            
        # Si no hay sesión activa y el endpoint es privado
        if request.endpoint and request.endpoint not in allowed_endpoints and 'user_id' not in session:
            # Peticiones AJAX / API
            if request.path.startswith('/api/') or request.path.startswith('/admin/'):
                return jsonify({'error': 'Acceso denegado: Inicia sesión primero'}), 401
                
            # Respuestas planas de audio, letras y carátulas (previene fugas de HTML a reproductores)
            if request.path.startswith('/audio/') or request.path.startswith('/album-art/') or request.path.startswith('/lyrics/'):
                return "Acceso denegado", 401
                
            # Redireccionar a la página de login
            return redirect(url_for('auth.login'))

    @app.before_request
    def csrf_protect():
        """
        Protección básica CSRF para solicitudes basadas en formularios estándar (POST/PUT/DELETE).
        Exime de manera controlada los endpoints de APIs asíncronas y administración remota autorizada.
        """
        if request.method not in ["GET", "HEAD", "OPTIONS", "TRACE"]:
            # Eximir APIs y administración
            if request.path.startswith('/api/') or request.path.startswith('/admin/'):
                return
            
            token = session.get('_csrf_token')
            if not token:
                return jsonify({'error': 'Falta el token CSRF en la sesión'}), 403
                
            req_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
            if not req_token and request.is_json:
                req_token = request.json.get('csrf_token')
                
            if not req_token or req_token != token:
                return jsonify({'error': 'Token CSRF inválido o faltante'}), 403

    def generate_csrf_token():
        """Genera un token CSRF seguro en formato hexadecimal para la sesión actual."""
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(32)
        return session['_csrf_token']

    # Registrar el generador de token CSRF en el motor de plantillas Jinja2
    app.jinja_env.globals['csrf_token'] = generate_csrf_token

    # Proxy inteligente para url_for en Jinja para asegurar compatibilidad de plantillas monolíticas antiguas sin namespace
    original_url_for = app.jinja_env.globals.get('url_for')
    if original_url_for:
        def smart_url_for(endpoint, **values):
            try:
                return original_url_for(endpoint, **values)
            except Exception:
                # Si el endpoint tiene un namespace antiguo o incorrecto (ej: 'browse.explore'),
                # extraemos solo el nombre de la función ('explore') para intentar resolverlo.
                func_name = endpoint.split('.')[-1]
                for prefix in ['main', 'audio', 'api', 'auth', 'admin']:
                    try:
                        return original_url_for(f"{prefix}.{func_name}", **values)
                    except Exception:
                        pass
                raise
        app.jinja_env.globals['url_for'] = smart_url_for

    @app.context_processor
    def inject_user_info():
        """Inyecta información básica de sesión del usuario en todas las plantillas Jinja2."""
        user_info = {
            'usuario_autenticado': session.get('nombre_usuario'),
            'user_id': session.get('user_id'),
            'app_version': Config.APP_VERSION
        }
        if session.get('user_id'):
            user_obj = db.session.get(Usuario, session['user_id'])
            user_info['es_admin'] = user_obj.is_admin() if user_obj else False
        else:
            user_info['es_admin'] = False
        return user_info

    # 4. Registro centralizado de Blueprints
    from app.routes import auth_bp, admin_bp, audio_bp, main_bp, api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    return app


# Instancia por defecto expuesta a nivel de paquete
# Esto permite hacer 'from app import app, db' manteniendo total compatibilidad.
app = create_app()
