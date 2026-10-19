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
    Evita que la tabla crezca indefinidamente mediante una consulta de eliminación atómica directa.
    """
    try:
        limite = datetime.utcnow() - timedelta(days=dias)
        cantidad = SesionActiva.query.filter(SesionActiva.ultima_actividad < limite).delete(synchronize_session=False)
        db.session.commit()
        if cantidad > 0:
            return True, f"Se eliminaron {cantidad} sesiones expiradas."
        return False, "No se encontraron sesiones expiradas."
    except Exception as e:
        db.session.rollback()
        return False, f"Error limpiando sesiones: {e}"
