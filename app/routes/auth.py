# -*- coding: utf-8 -*-
"""
Rutas de Autenticación - DuckSound
Maneja el ciclo de vida de la sesión del usuario (login, logout, redirecciones iniciales).
"""
from flask import Blueprint, render_template, request, redirect, url_for, session
from app.models import db, Usuario

# Definición del Blueprint de Autenticación
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Controlador para el inicio de sesión de usuarios.
    Soporta peticiones GET (renderiza el formulario) y POST (valida credenciales).
    """
    if request.method == 'POST':
        nombre_usuario = request.form.get('nombre_usuario')
        password = request.form.get('password')
        
        # Buscar usuario por nombre en la base de datos
        usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
        
        # Verificar contraseña usando el método seguro hasheado del modelo
        if usuario and usuario.check_password(password):
            session['user_id'] = usuario.id
            session['nombre_usuario'] = usuario.nombre_usuario
            return redirect(url_for('main.dashboard'))
        else:
            return render_template('login.html', error='Credenciales inválidas')
    
    # Redirigir al dashboard si ya tiene una sesión activa
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
        
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual limpiando el almacenamiento de sesión de Flask
    y redirigiendo a la pantalla de login.
    """
    session.clear()
    return redirect(url_for('auth.login'))
