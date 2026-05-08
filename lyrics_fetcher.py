import requests
import os
import re
from pathlib import Path
from models import db, Cancion
from config import Config

# Variable global para seguimiento de progreso de descarga de letras
_lyrics_progress = {
    'active': False,
    'total': 0,
    'completed': 0,
    'downloaded': 0,
    'errors': 0,
    'current_song': '',
    'finished': False
}
import threading
_lyrics_progress_lock = threading.Lock()


def _detectar_tipo_lyrics(contenido):
    """
    Detecta si el contenido es formato LRC (con timestamps) o texto plano.
    
    Args:
        contenido (str): Contenido de la letra
        
    Returns:
        str: 'lrc' si contiene timestamps, 'txt' si es texto plano
    """
    # Patrón regex para detectar timestamps LRC: [mm:ss.xx] o [mm:ss]
    lrc_pattern = r'\[\d{2}:\d{2}(?:\.\d{2})?\]'
    
    if re.search(lrc_pattern, contenido):
        return 'lrc'
    else:
        return 'txt'


def _crear_nombre_archivo_seguro(cancion):
    """
    Crea un nombre de archivo seguro para la letra.
    
    Args:
        cancion (Cancion): Objeto canción
        
    Returns:
        str: Nombre de archivo seguro
    """
    # Limpiar el título para usarlo en el nombre del archivo
    titulo_limpio = re.sub(r'[^\w\s-]', '', cancion.titulo)
    titulo_limpio = re.sub(r'[-\s]+', '_', titulo_limpio)
    
    return f"{cancion.id}_{titulo_limpio}"


def obtener_o_descargar_letra(cancion_id):
    """
    Obtiene la letra de una canción desde caché local o la descarga desde LRCLIB API.
    
    Args:
        cancion_id (int): ID de la canción
        
    Returns:
        dict or None: Diccionario {'tipo': 'lrc'|'txt', 'letra': 'contenido'} o None si no se encuentra
    """
    try:
        # Obtener el objeto Cancion desde la base de datos
        cancion = Cancion.query.get(cancion_id)
        if not cancion:
            return None
        
        # Paso 1: Verificar caché local
        if cancion.ruta_archivo_lrc:
            ruta_lrc = Path(cancion.ruta_archivo_lrc)
            if ruta_lrc.exists():
                try:
                    with open(ruta_lrc, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    tipo = _detectar_tipo_lyrics(contenido)
                    return {"tipo": tipo, "letra": contenido}
                except (IOError, UnicodeDecodeError) as e:
                    print(f"Error leyendo archivo local {ruta_lrc}: {e}")
                    # Continuar con búsqueda de rescate si el archivo local no se puede leer
        
        # Paso 1.5: Lógica de rescate - buscar en disco duro si BD es None o archivo no existe
        if not cancion.ruta_archivo_lrc or not Path(cancion.ruta_archivo_lrc).exists():
            # Importar la función robusta de búsqueda
            from scan_songs import buscar_archivo_lrc
            
            # Buscar letra local usando la función mejorada
            ruta_lrc_rescate = buscar_archivo_lrc(cancion.ruta_archivo_audio, Config.LYRICS_FOLDER, cancion.id)
            if ruta_lrc_rescate:
                try:
                    with open(ruta_lrc_rescate, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    # Actualizar la BD con la ruta encontrada
                    cancion.ruta_archivo_lrc = ruta_lrc_rescate
                    db.session.commit()
                    
                    tipo = _detectar_tipo_lyrics(contenido)
                    print(f"🔄 Letra rescatada del disco: {Path(ruta_lrc_rescate).name}")
                    return {"tipo": tipo, "letra": contenido}
                except (IOError, UnicodeDecodeError) as e:
                    print(f"Error leyendo archivo rescatado {ruta_lrc_rescate}: {e}")
                    # Continuar con la API si el archivo rescatado no se puede leer
        
        # Paso 2: Llamar a API LRCLIB
        if not all([cancion.titulo, cancion.artista_obj, cancion.duracion]):
            print(f"Faltan datos requeridos para buscar letra de canción {cancion_id}")
            return None
        
        # Preparar parámetros para la API
        params = {
            'track_name': cancion.titulo,
            'artist_name': cancion.artista_obj.nombre,
            'duration': int(cancion.duracion)  # Convertir a segundos exactos
        }
        
        # Añadir album_name si está disponible
        if cancion.album_obj and cancion.album_obj.titulo:
            params['album_name'] = cancion.album_obj.titulo
        
        headers = {
            'User-Agent': 'DuckSound/1.0.1 (app_music)'
        }
        
        try:
            response = requests.get(
                'https://lrclib.net/api/get',
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Paso 3: Procesar respuesta y guardar
                letra_contenido = None
                tipo_letra = 'txt'
                
                # Priorizar syncedLyrics sobre plainLyrics
                if data.get('syncedLyrics'):
                    letra_contenido = data['syncedLyrics']
                    tipo_letra = 'lrc'
                elif data.get('plainLyrics'):
                    letra_contenido = data['plainLyrics']
                    tipo_letra = 'txt'
                
                if letra_contenido:
                    # Crear archivo de letra
                    nombre_archivo = _crear_nombre_archivo_seguro(cancion)
                    extension = '.lrc' if tipo_letra == 'lrc' else '.txt'
                    ruta_archivo = Config.LYRICS_FOLDER / f"{nombre_archivo}{extension}"
                    
                    # Asegurar que el directorio exista
                    Config.LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)
                    
                    # Escribir archivo
                    with open(ruta_archivo, 'w', encoding='utf-8') as f:
                        f.write(letra_contenido)
                    
                    # Actualizar base de datos
                    cancion.ruta_archivo_lrc = str(ruta_archivo)
                    db.session.commit()
                    
                    return {"tipo": tipo_letra, "letra": letra_contenido}
            
            elif response.status_code == 404:
                print(f"No se encontró letra para canción {cancion_id}")
                return None
            else:
                print(f"Error en API LRCLIB para canción {cancion_id}: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"Timeout buscando letra para canción {cancion_id}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error de red buscando letra para canción {cancion_id}: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado buscando letra para canción {cancion_id}: {e}")
            return None
            
    except Exception as e:
        print(f"Error en obtener_o_descargar_letra para canción {cancion_id}: {e}")
        return None


def descargar_letras_segundo_plano(batch_size=10):
    """
    Descarga letras para todas las canciones que no tengan letra local.
    Diseñado para ejecutarse en segundo plano (thread).
    Procesa en lotes para no saturar la API.
    """
    import time
    from app import app
    
    # Ejecutar dentro del contexto de la aplicación
    with app.app_context():
        _descargar_letras_impl(batch_size)

def _descargar_letras_impl(batch_size):
    """Implementación real, ejecutada dentro del contexto de la app."""
    from models import Cancion, db
    import time
    
    global _lyrics_progress
    
    print("=" * 60)
    print("🎤 DESCARGANDO LETRAS EN SEGUNDO PLANO")
    print("=" * 60)
    
    # Obtener canciones sin letra o con ruta inválida
    canciones_sin_letra = []
    todas_canciones = Cancion.query.all()
    
    for c in todas_canciones:
        if not c.ruta_archivo_lrc or not Path(c.ruta_archivo_lrc).exists():
            canciones_sin_letra.append(c)
    
    if not canciones_sin_letra:
        print("✅ Todas las canciones ya tienen letra local")
        with _lyrics_progress_lock:
            _lyrics_progress['active'] = False
            _lyrics_progress['finished'] = True
        return
    
    print(f"📊 Canciones sin letra: {len(canciones_sin_letra)}")
    print(f"🔄 Iniciando descarga en lotes de {batch_size}...\n")
    
    # Inicializar progreso
    with _lyrics_progress_lock:
        _lyrics_progress['active'] = True
        _lyrics_progress['total'] = len(canciones_sin_letra)
        _lyrics_progress['completed'] = 0
        _lyrics_progress['downloaded'] = 0
        _lyrics_progress['errors'] = 0
        _lyrics_progress['current_song'] = ''
        _lyrics_progress['finished'] = False
    
    descargadas = 0
    errores = 0
    
    for idx, cancion in enumerate(canciones_sin_letra, start=1):
        try:
            print(f"[{idx}/{len(canciones_sin_letra)}] 🔍 {cancion.titulo} - {cancion.artista_obj.nombre if cancion.artista_obj else '?'}")
            
            # Actualizar progreso
            with _lyrics_progress_lock:
                _lyrics_progress['current_song'] = f"{cancion.titulo} - {cancion.artista_obj.nombre if cancion.artista_obj else '?'}"
                _lyrics_progress['completed'] = idx - 1
            
            resultado = obtener_o_descargar_letra(cancion.id)
            
            if resultado:
                print(f"  ✅ Letra obtenida")
                descargadas += 1
                with _lyrics_progress_lock:
                    _lyrics_progress['downloaded'] = descargadas
            else:
                print(f"  ⚠️ No se encontró letra")
                errores += 1
                with _lyrics_progress_lock:
                    _lyrics_progress['errors'] = errores
            
            # Pausa pequeña para no saturar la API
            if idx % batch_size == 0:
                print(f"  ⏸️ Pausa breve... (lote completado)")
                time.sleep(2)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errores += 1
            with _lyrics_progress_lock:
                _lyrics_progress['errors'] = errores
    
    print("\n" + "="*60)
    print(f"✅ DESCARGA COMPLETADA")
    print(f"   ✅ Descargadas: {descargadas}")
    print(f"   ⚠️ Errores: {errores}")
    print("="*60)
    
    # Marcar como finalizado
    with _lyrics_progress_lock:
        _lyrics_progress['active'] = False
        _lyrics_progress['finished'] = True
        _lyrics_progress['completed'] = len(canciones_sin_letra)
        _lyrics_progress['current_song'] = 'Completado'
