# -*- coding: utf-8 -*-
"""
Gestor de Sesiones - DuckSound
Proporciona utilidades para la limpieza y mantenimiento de sesiones activas.
"""
from datetime import datetime, timedelta
from app.models import db, SesionActiva

def limpiar_sesiones_expiradas(dias=30):
    """
    Elimina registros de SesionActiva que no han tenido actividad en los últimos 'dias'.
    Evita que la tabla crezca indefinidamente.
    """
    try:
        limite = datetime.utcnow() - timedelta(days=dias)
        sesiones_viejas = SesionActiva.query.filter(SesionActiva.ultima_actividad < limite).all()
        cantidad = len(sesiones_viejas)
        
        if cantidad > 0:
            for s in sesiones_viejas:
                db.session.delete(s)
            db.session.commit()
            return True, f"Se eliminaron {cantidad} sesiones expiradas."
        return False, "No se encontraron sesiones expiradas."
    except Exception as e:
        db.session.rollback()
        return False, f"Error limpiando sesiones: {e}"
