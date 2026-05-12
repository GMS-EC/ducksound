import requests
import re
import time
from pathlib import Path
from models import db, Cancion
from config import Config

# Caché en memoria para letras: {cancion_id: (timestamp, resultado)}
_lyrics_cache = {}
_LYRICS_CACHE_TTL = 3600  # 1 hora

# Progreso de descarga de letras vía Redis
from task_queue import progress_set, progress_get


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
        
        # Paso 0: Verificar caché en memoria
        if cancion_id in _lyrics_cache:
            cached_time, cached_result = _lyrics_cache[cancion_id]
            if time.time() - cached_time < _LYRICS_CACHE_TTL:
                return cached_result
        
        # Paso 1: Verificar caché local (archivo en disco)
        if cancion.ruta_archivo_lrc:
            ruta_lrc = Path(cancion.ruta_archivo_lrc)
            if ruta_lrc.exists():
                try:
                    with open(ruta_lrc, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    tipo = _detectar_tipo_lyrics(contenido)
                    resultado = {"tipo": tipo, "letra": contenido}
                    _lyrics_cache[cancion_id] = (time.time(), resultado)
                    return resultado
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
                    resultado = {"tipo": tipo, "letra": contenido}
                    _lyrics_cache[cancion_id] = (time.time(), resultado)
                    return resultado
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
                    return _guardar_letra(cancion, letra_contenido, tipo_letra, cancion_id)
            
            elif response.status_code == 404:
                print(f"No se encontró letra para canción {cancion_id} en LRCLIB")
            else:
                print(f"Error en API LRCLIB para canción {cancion_id}: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"Timeout LRCLIB para canción {cancion_id}")
        except requests.exceptions.RequestException as e:
            print(f"Error de red LRCLIB para canción {cancion_id}: {e}")
        except Exception as e:
            print(f"Error inesperado LRCLIB para canción {cancion_id}: {e}")
        
        # === PASO 4: FALLBACKS si LRCLIB no encontró nada ===
        titulo = cancion.titulo
        artista = cancion.artista_obj.nombre if cancion.artista_obj else ''
        
        # Fallback 1: Lyrics.ovh (API gratuita, texto plano)
        if titulo and artista:
            try:
                ovh_url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(artista)}/{requests.utils.quote(titulo)}"
                ovh_resp = requests.get(ovh_url, timeout=10)
                if ovh_resp.status_code == 200:
                    ovh_data = ovh_resp.json()
                    if ovh_data.get('lyrics'):
                        letra = ovh_data['lyrics'].strip()
                        if letra:
                            return _guardar_letra(cancion, letra, 'txt', cancion_id)
            except Exception as e:
                print(f"Error Lyrics.ovh para {cancion_id}: {e}")
        
        # Fallback 2: Genius scraping (solo si tenemos nombre de artista y título)
        if titulo and artista:
            try:
                import urllib.parse
                query = f"{artista} {titulo}"
                search_url = f"https://genius.com/api/search/song?q={urllib.parse.quote(query)}"
                genius_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0'}
                g_resp = requests.get(search_url, headers=genius_headers, timeout=10)
                if g_resp.status_code == 200:
                    g_data = g_resp.json()
                    hits = g_data.get('response', {}).get('sections', [])
                    for section in hits:
                        for hit in section.get('hits', []):
                            result = hit.get('result', {})
                            song_url = result.get('url', '')
                            if song_url:
                                page = requests.get(song_url, headers=genius_headers, timeout=10)
                                if page.status_code == 200:
                                    import re
                                    # Buscar el contenedor de letras en el HTML de Genius
                                    match = re.search(r'<div class="lyrics"[^>]*>(.*?)</div>\s*</div>', page.text, re.DOTALL)
                                    if not match:
                                        match = re.search(r'<div data-lyrics-container[^>]*>(.*?)</div>', page.text, re.DOTALL)
                                    if match:
                                        html_lyrics = match.group(1)
                                        # Limpiar HTML básico
                                        letra_limpia = re.sub(r'<br\s*/?>', '\n', html_lyrics)
                                        letra_limpia = re.sub(r'<[^>]+>', '', letra_limpia)
                                        letra_limpia = re.sub(r'\n{3,}', '\n\n', letra_limpia).strip()
                                        if letra_limpia:
                                            return _guardar_letra(cancion, letra_limpia, 'txt', cancion_id)
                                break  # Solo intentar el primer resultado
            except Exception as e:
                print(f"Error Genius para {cancion_id}: {e}")
        return None
        
    except Exception as e:
        print(f"Error en obtener_o_descargar_letra para canción {cancion_id}: {e}")
        return None


def _guardar_letra(cancion, letra_contenido, tipo_letra, cancion_id):
    """Guarda la letra en disco y actualiza la BD."""
    try:
        nombre_archivo = _crear_nombre_archivo_seguro(cancion)
        extension = '.lrc' if tipo_letra == 'lrc' else '.txt'
        ruta_archivo = Config.LYRICS_FOLDER / f"{nombre_archivo}{extension}"
        Config.LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(letra_contenido)
        cancion.ruta_archivo_lrc = str(ruta_archivo)
        db.session.commit()
        resultado = {"tipo": tipo_letra, "letra": letra_contenido}
        _lyrics_cache[cancion_id] = (time.time(), resultado)
        return resultado
    except Exception as e:
        print(f"Error al guardar letra: {e}")
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
    from task_queue import progress_set
    
    print("=" * 60)
    print("🎤 DESCARGANDO LETRAS EN SEGUNDO PLANO")
    print("=" * 60)
    
    # Obtener canciones sin letra o con ruta inválida
    from models import Cancion
    import os
    
    canciones_sin_letra = Cancion.query.filter(
        db.or_(
            Cancion.ruta_archivo_lrc.is_(None),
            Cancion.ruta_archivo_lrc == '',
            Cancion.ruta_archivo_lrc.notin_(
                db.session.query(Cancion.ruta_archivo_lrc).filter(
                    Cancion.ruta_archivo_lrc.isnot(None),
                    Cancion.ruta_archivo_lrc != ''
                ).all()
            )
        )
    ).all()
    
    # Filtrar los que realmente no existen en disco
    canciones_sin_letra = [c for c in canciones_sin_letra if not c.ruta_archivo_lrc or not os.path.exists(c.ruta_archivo_lrc)]
    
    if not canciones_sin_letra:
        print("✅ Todas las canciones ya tienen letra local")
        progress_set('lyrics', {'active': False, 'finished': True})
        return
    
    print(f"📊 Canciones sin letra: {len(canciones_sin_letra)}")
    print(f"🔄 Iniciando descarga en lotes de {batch_size}...\n")
    
    def set_progress(**kw):
        data = progress_get('lyrics') or {}
        data.update(kw)
        progress_set('lyrics', data)
    
    # Inicializar progreso
    progress_set('lyrics', {
        'active': True,
        'total': len(canciones_sin_letra),
        'completed': 0,
        'downloaded': 0,
        'errors': 0,
        'current_song': '',
        'finished': False
    })
    
    descargadas = 0
    errores = 0
    
    for idx, cancion in enumerate(canciones_sin_letra, start=1):
        try:
            song_str = f"{cancion.titulo} - {cancion.artista_obj.nombre if cancion.artista_obj else '?'}"
            print(f"[{idx}/{len(canciones_sin_letra)}] 🔍 {song_str}")
            
            set_progress(current_song=song_str, completed=idx - 1)
            
            resultado = obtener_o_descargar_letra(cancion.id)
            
            if resultado:
                print(f"  ✅ Letra obtenida")
                descargadas += 1
                set_progress(downloaded=descargadas)
            else:
                print(f"  ⚠️ No se encontró letra")
                errores += 1
                set_progress(errors=errores)
            
            if idx % batch_size == 0:
                print(f"  ⏸️ Pausa breve... (lote completado)")
                time.sleep(2)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errores += 1
            set_progress(errors=errores)
    
    print("\n" + "="*60)
    print(f"✅ DESCARGA COMPLETADA")
    print(f"   ✅ Descargadas: {descargadas}")
    print(f"   ⚠️ Errores: {errores}")
    print("="*60)
    
    progress_set('lyrics', {
        'active': False,
        'finished': True,
        'completed': len(canciones_sin_letra),
        'current_song': 'Completado'
    })
