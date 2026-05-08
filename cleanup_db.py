#!/usr/bin/env python
from app import app
from models import db, Usuario
from werkzeug.security import generate_password_hash

with app.app_context():
    # Delete all users
    Usuario.query.delete()
    db.session.commit()
    
    # Create admin user
    admin = Usuario(nombre_usuario='admin', role='admin')
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    print('Usuario admin creado correctamente')
