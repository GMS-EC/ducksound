# -*- coding: utf-8 -*-
"""
Servicio de Transcodificación Inteligente de Audio - DuckSound
=============================================================
Este servicio se encarga de convertir archivos de audio de alta fidelidad (FLAC, WAV)
a formato MP3 de alta calidad (320kbps) al vuelo o en segundo plano.

Implementa medidas de seguridad industrial para proteger los recursos de CPU:
1. Semáforo Global: Limita el número de transcodificaciones simultáneas activas (máx. 4).
2. Bloqueos por Canción: Evita que dos peticiones simultáneas del mismo tema disparen dos ffmpeg en paralelo.
3. Transcodificación Atómica: Escribe en un archivo temporal (.tmp) y renombra sólo al finalizar con éxito.
4. Comando FFMPEG de Prioridad Mínima: Usa 'nice -n 19' y '-threads 1' para no penalizar a Gunicorn/PostgreSQL.
"""

import os
import subprocess
import threading
import logging
from pathlib import Path
from config import Config
from app.models import db, Cancion

logger = logging.getLogger(__name__)

# Semáforo global para limitar el uso de CPU de ffmpeg (máximo 4 conversiones concurrentes)
CPU_SEMAPHORE = threading.Semaphore(4)

# Diccionario de bloqueos por canción para evitar procesamiento duplicado del mismo ID
_song_locks = {}
_master_lock = threading.Lock()


def _get_song_lock(cancion_id):
    """Retorna un objeto Lock único y persistente para un ID de canción específico."""
    with _master_lock:
        if cancion_id not in _song_locks:
            _song_locks[cancion_id] = threading.Lock()
        return _song_locks[cancion_id]


def obtener_ruta_cache(cancion_id, calidad='high'):
    """Retorna la ubicación esperada del archivo transcodificado en la caché según la calidad."""
    suffix = "320k"
    if calidad == 'standard':
        suffix = "192k"
    elif calidad == 'saver':
        suffix = "96k"
    return Config.TRANSCODE_CACHE_FOLDER / f"{cancion_id}_{suffix}.mp3"


def transcodificar_cancion(cancion_id, calidad='high', forzar=False):
    """
    Transcodifica un archivo de alta fidelidad a MP3 (320k/192k/96k) de manera atómica y segura.
    
    Args:
        cancion_id (int): ID de la canción en la base de datos.
        calidad (str): Calidad destino ('high', 'standard', 'saver').
        forzar (bool): Si es True, ignora la caché existente y vuelve a procesar.
        
    Returns:
        str: Ruta al archivo MP3 transcodificado y cacheado, o None si falla.
    """
    # 1. Obtener la canción de la base de datos
    # Si estamos en un hilo secundario sin contexto, se asume que el contexto ya está activo
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        logger.error(f"[Transcoder] Canción ID {cancion_id} no encontrada en la base de datos.")
        return None

    original_path = cancion.ruta_archivo_audio
    if not original_path or not os.path.exists(original_path):
        # Intentar ruta alternativa de Docker si la original no existe físicamente
        alt_path = original_path.replace('\\\\', '/').replace(':/', ':/')
        import re
        m = re.match(r'^([A-Za-z]):/(.*)', alt_path)
        if m:
            alt_path = '/music/' + m.group(2)
        if os.path.exists(alt_path):
            original_path = alt_path
        else:
            logger.error(f"[Transcoder] Archivo original no encontrado en disco: {original_path}")
            return None

    # Determinar si el archivo original ya es un formato compatible que NO requiere transcodificación
    ext = Path(original_path).suffix.lower()
    if ext in ['.mp3', '.m4a']:
        # Ya es un formato de alta compresión nativo, no requiere transcodificación
        return original_path

    # Determinar el bitrate y sufijo a partir de la calidad solicitada
    bitrate = '320k'
    suffix = '320k'
    if calidad == 'standard':
        bitrate = '192k'
        suffix = '192k'
    elif calidad == 'saver':
        bitrate = '96k'
        suffix = '96k'

    ruta_final = obtener_ruta_cache(cancion_id, calidad=calidad)
    
    # 2. Si ya está en caché y no forzamos, retornar de inmediato (Cero CPU)
    if not forzar and ruta_final.exists() and ruta_final.stat().st_size > 0:
        return str(ruta_final)

    # 3. Adquirir el bloqueo específico de esta canción
    lock = _get_song_lock(cancion_id)
    with lock:
        # Volver a comprobar la caché dentro del bloqueo por si otro hilo la completó en la espera
        if not forzar and ruta_final.exists() and ruta_final.stat().st_size > 0:
            return str(ruta_final)

        # 4. Adquirir un slot en el semáforo global de CPU
        logger.info(f"[Transcoder] Canción ID {cancion_id} entra a cola de transcodificación (calidad: {calidad}).")
        with CPU_SEMAPHORE:
            logger.info(f"[Transcoder] Iniciando transcodificación de {original_path} -> {ruta_final} ({bitrate})")
            
            ruta_temporal = Config.TRANSCODE_CACHE_FOLDER / f"{cancion_id}_{suffix}.mp3.tmp"
            if ruta_temporal.exists():
                try:
                    ruta_temporal.unlink()
                except Exception:
                    pass

            # Comando FFMPEG ultra-optimizado:
            # - nice -n 19: Prioridad mínima a nivel de kernel de Linux.
            # - threads 1: Evita que ffmpeg consuma más de un núcleo.
            # - c:a libmp3lame -b:a [bitrate]: Codificación MP3 estéreo con el bitrate deseado.
            cmd = [
                'nice', '-n', '19',
                'ffmpeg', '-y',
                '-i', str(original_path),
                '-c:a', 'libmp3lame',
                '-b:a', bitrate,
                '-f', 'mp3',
                '-threads', '1',
                str(ruta_temporal)
            ]

            try:
                # Ejecutar el subproceso bloqueante (es sumamente rápido: ~1s para una canción normal)
                resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                
                # Reemplazo atómico para evitar archivos corruptos en accesos concurrentes
                if ruta_temporal.exists() and ruta_temporal.stat().st_size > 0:
                    ruta_temporal.rename(ruta_final)
                    logger.info(f"[Transcoder] Transcodificación exitosa de ID {cancion_id} ({calidad}) finalizada.")
                    return str(ruta_final)
                else:
                    raise RuntimeError("El archivo resultante de ffmpeg está vacío o no se creó.")
                    
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode('utf-8', errors='ignore')
                logger.error(f"[Transcoder] Error de ffmpeg transcodificando ID {cancion_id} a {calidad}: {err_msg}")
            except Exception as ex:
                logger.error(f"[Transcoder] Excepción general transcodificando ID {cancion_id} a {calidad}: {ex}")
            finally:
                # Limpieza de archivo temporal si quedó residual por fallo
                if ruta_temporal.exists():
                    try:
                        ruta_temporal.unlink()
                    except Exception:
                        pass
                        
    return None


def pretranscodificar_canciones_async(canciones_ids, calidad='high'):
    """
    Encola la transcodificación asíncrona de una lista de canciones en la cola de Redis RQ.
    Esto permite calentar el caché silenciosamente durante la indexación.
    """
    from app.services.queue import enqueue
    for cid in canciones_ids:
        enqueue(run_background_transcode, cid, calidad)


def run_background_transcode(cancion_id, calidad='high'):
    """
    Función de entrada para el worker de RQ.
    Inicializa el contexto de la aplicación de Flask y ejecuta la transcodificación.
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            transcodificar_cancion(cancion_id, calidad=calidad)
        except Exception as e:
            logger.error(f"[Transcoder Worker] Error transcodificando ID {cancion_id} ({calidad}) en background: {e}")


def pretranscodificar_biblioteca(calidad='high'):
    """
    Busca todas las canciones de formatos sin compresión nativa (FLAC, WAV, OGG)
    en la base de datos que aún no tengan caché de transcodificación, y encola
    su procesamiento individual en segundo plano.
    """
    from app.services.queue import enqueue
    canciones = Cancion.query.all()
    encoladas = 0
    
    for cancion in canciones:
        ext = Path(cancion.ruta_archivo_audio).suffix.lower()
        if ext in ['.flac', '.wav', '.ogg']:
            ruta_cache = obtener_ruta_cache(cancion.id, calidad=calidad)
            if not ruta_cache.exists():
                enqueue(run_background_transcode, cancion.id, calidad)
                encoladas += 1
                
    logger.info(f"[Transcoder] Tarea de escaneo de caché finalizada. Encoladas {encoladas} canciones para transcodificación asíncrona ({calidad}).")
    return encoladas


def run_pretranscode_library(calidad='high'):
    """Runner de RQ para ejecutar pretranscodificar_biblioteca dentro del contexto de Flask."""
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            pretranscodificar_biblioteca(calidad=calidad)
        except Exception as e:
            logger.error(f"[Transcoder Worker] Error al pretranscodificar biblioteca en background ({calidad}): {e}")


def limpiar_cache_transcodificacion(max_age_horas=24):
    """
    Elimina archivos del caché de transcodificación que no se hayan usado en más de `max_age_horas`.
    Esto evita que el disco se llene con archivos transcodificados de canciones que ya no se escuchan.
    """
    import time
    ahora = time.time()
    max_age_segundos = max_age_horas * 3600
    eliminados = 0
    for archivo in Config.TRANSCODE_CACHE_FOLDER.iterdir():
        if archivo.suffix in ('.mp3', '.tmp'):
            try:
                tiempo_mod = archivo.stat().st_mtime
                if ahora - tiempo_mod > max_age_segundos:
                    archivo.unlink()
                    eliminados += 1
            except Exception as e:
                logger.error(f"[Transcoder] Error limpiando archivo {archivo}: {e}")
    if eliminados:
        logger.info(f"[Transcoder] Limpieza completada: {eliminados} archivos eliminados del caché.")
    return eliminados
