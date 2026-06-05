# -*- coding: utf-8 -*-
"""
Rutas de Autenticación - DuckSound
Maneja el ciclo de vida de la sesión del usuario (login, logout, redirecciones iniciales).
Registra sesiones activas con información del dispositivo para gestión remota.
"""
import secrets
from datetime import datetime
from flask import Blueprint, request, session, current_app, jsonify
from app.models import db, Usuario, SesionActiva

# Definición del Blueprint de Autenticación
auth_bp = Blueprint('auth', __name__)


def _parse_user_agent(ua_string):
    """
    Extrae navegador, sistema operativo y tipo de dispositivo desde un User-Agent.
    Implementación ligera sin dependencias externas.
    """
    ua = ua_string or ''
    ua_lower = ua.lower()

    # Detectar navegador
    navegador = 'Desconocido'
    if 'edg/' in ua_lower or 'edge/' in ua_lower:
        navegador = 'Microsoft Edge'
    elif 'opr/' in ua_lower or 'opera' in ua_lower:
        navegador = 'Opera'
    elif 'chrome/' in ua_lower and 'safari/' in ua_lower:
        navegador = 'Chrome'
    elif 'firefox/' in ua_lower:
        navegador = 'Firefox'
    elif 'safari/' in ua_lower and 'chrome/' not in ua_lower:
        navegador = 'Safari'
    elif 'msie' in ua_lower or 'trident/' in ua_lower:
        navegador = 'Internet Explorer'

    # Detectar sistema operativo
    sistema = 'Desconocido'
    if 'windows nt 10' in ua_lower:
        sistema = 'Windows 10/11'
    elif 'windows nt' in ua_lower:
        sistema = 'Windows'
    elif 'mac os x' in ua_lower:
        sistema = 'macOS'
    elif 'android' in ua_lower:
        sistema = 'Android'
    elif 'iphone' in ua_lower or 'ipad' in ua_lower:
        sistema = 'iOS'
    elif 'linux' in ua_lower:
        sistema = 'Linux'
    elif 'chromeos' in ua_lower or 'cros' in ua_lower:
        sistema = 'Chrome OS'

    # Detectar tipo de dispositivo
    dispositivo = 'Escritorio'
    if 'mobile' in ua_lower or 'iphone' in ua_lower or 'android' in ua_lower:
        if 'tablet' in ua_lower or 'ipad' in ua_lower:
            dispositivo = 'Tablet'
        else:
            dispositivo = 'Móvil'
    elif 'ipad' in ua_lower or 'tablet' in ua_lower:
        dispositivo = 'Tablet'

    return navegador, sistema, dispositivo


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Controlador para el inicio de sesión de usuarios (JSON API).
    Valida credenciales y devuelve información del usuario.
    """
    data = request.get_json(silent=True) or {}
    nombre_usuario = data.get('nombre_usuario')
    password = data.get('password')

    if not nombre_usuario or not password:
        return jsonify({'error': 'nombre_usuario y password son requeridos'}), 400
    
    # Buscar usuario por nombre en la base de datos
    usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
    
    # Verificar contraseña usando el método seguro hasheado del modelo
    if usuario and usuario.check_password(password):
        # Generar un token único para esta sesión
        session_token = secrets.token_hex(32)
        
        # Parsear información del dispositivo desde el User-Agent
        ua_string = request.headers.get('User-Agent', '')
        navegador, sistema, dispositivo = _parse_user_agent(ua_string)
        
        # Obtener IP del cliente (compatible con proxies reversos)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        # Registrar la sesión activa en la base de datos
        nueva_sesion = SesionActiva(
            usuario_id=usuario.id,
            session_token=session_token,
            navegador=navegador,
            sistema=sistema,
            dispositivo=dispositivo,
            ip_address=ip_address
        )
        db.session.add(nueva_sesion)
        db.session.commit()
        
        # Cachear la sesión en Redis para validación rápida en before_request
        from app.services.queue import get_connection
        try:
            r = get_connection()
            r.setex(f"ducksound:session:{session_token}", 3600, usuario.id)
        except Exception as e:
            current_app.logger.warning(f"[Session Cache] Error guardando en Redis: {e}")
        
        # Configurar la sesión de Flask
        session['user_id'] = usuario.id
        session['nombre_usuario'] = usuario.nombre_usuario
        session['session_token'] = session_token
        
        return jsonify({
            'success': True,
            'user': usuario.to_dict(),
            'session_token': session_token
        }), 200
    else:
        return jsonify({'error': 'Credenciales inválidas'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Cierra la sesión del usuario actual (JSON API).
    """
    # Eliminar el registro de sesión activa de la base de datos
    token = session.get('session_token')
    if token:
        sesion_activa = SesionActiva.query.filter_by(session_token=token).first()
        if sesion_activa:
            db.session.delete(sesion_activa)
            db.session.commit()
            
            # Eliminar la sesión de la caché de Redis
            from app.services.queue import get_connection
            try:
                r = get_connection()
                r.delete(f"ducksound:session:{token}")
            except Exception as e:
                current_app.logger.error(f"Error eliminando sesión de Redis: {e}")
    
    session.clear()
    return jsonify({'success': True}), 200
