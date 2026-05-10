"""
Tareas RQ para ejecución en workers background.
Estas funciones se ejecutan en procesos separados (workers de RQ).
"""
from task_queue import scan_task_get, scan_task_set, scan_set_active


def _progress_wrapper(current_task_id):
    """Crea un callback de progreso que escribe en Redis."""
    def _progress(payload):
        t = scan_task_get(current_task_id)
        if not t:
            return
        t.update({
            'percent': payload.get('percent', t.get('percent', 0)),
            'message': payload.get('message', t.get('message', '')),
            'processed': payload.get('processed', t.get('processed', 0)),
            'total': payload.get('total', t.get('total', 0)),
        })
        if payload.get('current_file'):
            t['current_file'] = payload.get('current_file')
        if payload.get('summary'):
            t['summary'] = payload.get('summary')
        stage = payload.get('stage')
        if stage == 'done':
            t['status'] = 'done'
        elif stage == 'enriching':
            t['status'] = 'enriching'
        elif stage == 'error':
            t['status'] = 'error'
            t['error'] = payload.get('message') or 'Error'
        scan_task_set(current_task_id, t)
    return _progress


def run_full_scan(task_id):
    """Ejecuta un escaneo completo. Llamado por RQ worker."""
    from app import app
    from scan_songs import escanear_carpeta_audio

    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            resumen = escanear_carpeta_audio(progress_callback=progress)
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'done'
                t['percent'] = 100
                t['summary'] = resumen
                t['message'] = 'Escaneo finalizado'
                scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'error'
                t['error'] = str(ex)
                t['message'] = f'Error: {ex}'
                scan_task_set(task_id, t)
        finally:
            scan_set_active(None)


def run_quick_scan(task_id):
    """Ejecuta un escaneo rápido. Llamado por RQ worker."""
    from app import app
    from scan_songs import escaneo_rapido

    with app.app_context():
        progress = _progress_wrapper(task_id)
        try:
            resumen = escaneo_rapido(progress_callback=progress)
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'done'
                t['percent'] = 100
                t['summary'] = resumen
                t['message'] = 'Escaneo rápido finalizado'
                scan_task_set(task_id, t)
        except Exception as ex:
            t = scan_task_get(task_id)
            if t:
                t['status'] = 'error'
                t['error'] = str(ex)
                t['message'] = f'Error: {ex}'
                scan_task_set(task_id, t)
        finally:
            scan_set_active(None)
