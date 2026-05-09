#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para generar daily mixes para todos los usuarios
Ejecutar este script para generar daily mixes si no aparecen en el dashboard
"""

from app import app, db
from models import DailyMix, Usuario
from datetime import date
import sys

def generate_daily_mixes_for_user(usuario_id):
    """Genera daily mixes para un usuario específico"""
    with app.app_context():
        from app import _generate_daily_mixes
        
        today = date.today()
        existing_mixes = DailyMix.query.filter_by(usuario_id=usuario_id, fecha=today).all()
        
        if existing_mixes:
            print(f"El usuario {usuario_id} ya tiene {len(existing_mixes)} mixes para hoy")
            return
        
        print(f"Generando daily mixes para el usuario {usuario_id}...")
        _generate_daily_mixes(usuario_id)
        
        new_mixes = DailyMix.query.filter_by(usuario_id=usuario_id, fecha=today).all()
        print(f"Se generaron {len(new_mixes)} daily mixes para el usuario {usuario_id}")

def generate_daily_mixes_for_all_users():
    """Genera daily mixes para todos los usuarios"""
    with app.app_context():
        usuarios = Usuario.query.all()
        
        for usuario in usuarios:
            print(f"\nProcesando usuario: {usuario.nombre} (ID: {usuario.id})")
            generate_daily_mixes_for_user(usuario.id)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        usuario_id = int(sys.argv[1])
        generate_daily_mixes_for_user(usuario_id)
    else:
        generate_daily_mixes_for_all_users()
    
    print("\n¡Proceso completado!")
