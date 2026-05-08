import os
import sys
import re
from pathlib import Path
import requests
import urllib.parse

# Configurar UTF-8 para la salida en Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from config import Config
from models import db, Artista, Album, Cancion
from datetime import datetime
from metadata_fetcher import enrich_artist, enrich_all
from metadata_normalizer import normalizar_artista, normalizar_titulo, normalizar_album, detectar_version, limpiar_nombre

# Extensiones de audio soportadas
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}

def extraer_metadatos(ruta_archivo):
    """
    Extrae metadatos del archivo de audio usando mutagen.
    Retorna un diccionario con titulo, artista, album, duracion, genero y ruta_imagen.
    También ejecuta el análisis de calidad de audio.
    """
    from audio_analyzer import analyze_audio

    try:
        audio_file = File(ruta_archivo)
        
        if audio_file is None:
            return None
        
        metadatos = {
            'titulo': None,
            'artista': None,
            'album': None,
            'duracion': None,
            'ruta_imagen': None,
            'genero': None
        }
        
        # Extraer duración
        if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
            metadatos['duracion'] = int(audio_file.info.length)
        
        # Ejecutar análisis de calidad de audio (lo combina con extracción de género y más)
        try:
            analisis = analyze_audio(ruta_archivo)
            if analisis:
                # Actualizar duración con valor más preciso de librosa
                if analisis.get('duration'):
                    metadatos['duracion'] = int(analisis['duration'])
                if analisis.get('genero') and not metadatos['genero']:
                    metadatos['genero'] = analisis['genero']
                metadatos['audio_analysis'] = analisis
        except Exception as e:
            print(f"  ⚠ Error en análisis de audio: {e}")
        
        def parse_track_num(val):
            if not val: return None
            try:
                # Puede ser '01/12' o '1'
                return int(str(val).split('/')[0])
            except:
                return None

        # Extraer metadatos según el tipo de archivo
        if isinstance(audio_file, MP3):
            metadatos['titulo'] = audio_file.get('TIT2', [None])[0]
            metadatos['artista'] = audio_file.get('TPE1', [None])[0]
            metadatos['album'] = audio_file.get('TALB', [None])[0]
            metadatos['genero'] = audio_file.get('TCON', [None])[0]
            
            # Número de pista
            metadatos['numero_pista'] = parse_track_num(audio_file.get('TRCK', [None])[0])

            # Extraer imagen del álbum
            apic_tags = [tag for key, tag in getattr(audio_file, 'tags', {}).items() if key.startswith('APIC')]
            if apic_tags:
                metadatos['ruta_imagen'] = guardar_imagen_album(apic_tags[0], ruta_archivo)
            elif getattr(audio_file, 'pictures', None):
                metadatos['ruta_imagen'] = guardar_imagen_album(audio_file.pictures[0], ruta_archivo)
        elif isinstance(audio_file, FLAC):
            metadatos['titulo'] = audio_file.get('TITLE', [None])[0]
            metadatos['artista'] = audio_file.get('ARTIST', [None])[0]
            metadatos['album'] = audio_file.get('ALBUM', [None])[0]
            metadatos['genero'] = audio_file.get('GENRE', [None])[0]
            metadatos['numero_pista'] = parse_track_num(audio_file.get('TRACKNUMBER', [None])[0])
            # Extraer imagen del álbum
            if audio_file.pictures:
                metadatos['ruta_imagen'] = guardar_imagen_album(audio_file.pictures[0], ruta_archivo)
        elif isinstance(audio_file, WAVE):
            # WAV no tiene metadatos estándar, intentar extraer de comentarios
            if hasattr(audio_file, 'tags'):
                metadatos['titulo'] = audio_file.tags.get('TITLE', [None])[0] if audio_file.tags else None
                metadatos['artista'] = audio_file.tags.get('ARTIST', [None])[0] if audio_file.tags else None
                metadatos['genero'] = audio_file.tags.get('GENRE', [None])[0] if audio_file.tags else None
                metadatos['album'] = audio_file.tags.get('ALBUM', [None])[0] if audio_file.tags else None
                metadatos['numero_pista'] = parse_track_num(audio_file.tags.get('TRACKNUMBER', [None])[0] if audio_file.tags else None)
        else:
            # Para otros formatos, intentar genérico
            if hasattr(audio_file, 'tags') and audio_file.tags:
                metadatos['titulo'] = audio_file.tags.get('title', [None])[0]
                metadatos['artista'] = audio_file.tags.get('artist', [None])[0]
                metadatos['album'] = audio_file.tags.get('album', [None])[0]
                metadatos['numero_pista'] = parse_track_num(audio_file.tags.get('tracknumber', [None])[0])
                # Extraer imagen genérica
                apic_tags = [tag for key, tag in getattr(audio_file, 'tags', {}).items() if key.startswith('APIC')]
                if apic_tags:
                    metadatos['ruta_imagen'] = guardar_imagen_album(apic_tags[0], ruta_archivo)
                elif getattr(audio_file, 'pictures', None):
                    metadatos['ruta_imagen'] = guardar_imagen_album(audio_file.pictures[0], ruta_archivo)
        if not metadatos.get('ruta_imagen'):
            # Intentar fallback desde iTunes API
            titulo_b = metadatos.get('titulo') or Path(ruta_archivo).stem
            artista_b = metadatos.get('artista', '')
            album_b = metadatos.get('album', '')
            if titulo_b and artista_b:
                print(f"  🔍 Buscando portada en internet para: {titulo_b}")
                cover_url = fetch_cover_from_itunes(artista_b, album_b, titulo_b)
                if cover_url:
                    ruta_img = descargar_y_guardar_portada(cover_url, ruta_archivo)
                    if ruta_img:
                        metadatos['ruta_imagen'] = ruta_img
                        print(f"  ✅ Portada descargada desde internet.")

        return metadatos
    except Exception as e:
        print(f"  ⚠ Error al leer metadatos: {e}")
        return None

def guardar_imagen_album(picture, ruta_audio):
    """
    Guarda la imagen del álbum en la carpeta media/album_art.
    Retorna la ruta de la imagen guardada o None.
    """
    try:
        # Usar ALBUM_ART_FOLDER del config (escribe en ubicación persistente)
        carpeta_album_art = Config.ALBUM_ART_FOLDER
        carpeta_album_art.mkdir(exist_ok=True)
        
        # Generar nombre de archivo basado en el nombre del audio
        nombre_base = Path(ruta_audio).stem
        extension = '.jpg' if picture.mime == 'image/jpeg' else '.png'
        ruta_imagen = carpeta_album_art / f"{nombre_base}{extension}"
        
        # Guardar la imagen
        with open(ruta_imagen, 'wb') as f:
            f.write(picture.data)
        
        return str(ruta_imagen)
    except Exception as e:
        print(f"  ⚠ Error al guardar imagen del álbum: {e}")
        return None

def descargar_y_guardar_portada(url, ruta_audio):
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            class FakePicture:
                def __init__(self, data, mime):
                    self.data = data
                    self.mime = mime
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            picture = FakePicture(resp.content, content_type)
            return guardar_imagen_album(picture, ruta_audio)
    except Exception:
        pass
    return None

def fetch_cover_from_itunes(artist, album, song_title):
    import urllib.parse
    query = f"{artist} {album}" if album else f"{artist} {song_title}"
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&media=music&entity=album&limit=1"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('resultCount', 0) > 0:
                artwork_url = data['results'][0].get('artworkUrl100')
                if artwork_url:
                    # Request high-res 600x600 instead of 100x100
                    return artwork_url.replace('100x100bb', '600x600bb')
    except Exception:
        pass
    return None

def limpiar_nombre_archivo(nombre_archivo):
    """
    Limpia el nombre del archivo para extraer título y artista si no hay metadatos.
    Formato esperado: "Artista - Titulo.ext" o "Titulo.ext"
    """
    # Remover extensión
    nombre_sin_ext = Path(nombre_archivo).stem
    match = re.match(r'^(.+?)\s*-\s*(.+)$', nombre_sin_ext, re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()  # titulo, artista
    
    # Si no coincide, usar todo como título
    return nombre_sin_ext.strip(), None

def inferir_metadatos_desde_ruta(ruta_archivo, carpeta_base_audio):
    """
    Infiere artista y álbum desde la estructura de subcarpetas cuando no hay metadatos ID3.
    
    Ejemplos:
      Artist/song.mp3              → artista='Artist', album=None
      Artist/Album/song.mp3        → artista='Artist', album='Album'
      Genre/Artist/Album/song.mp3  → artista='Artist', album='Album'
      song.mp3                     → artista=None, album=None
    """
    try:
        rel_path = Path(ruta_archivo).resolve().relative_to(Path(carpeta_base_audio).resolve())
        parts = list(rel_path.parts)
        # parts incluye el nombre del archivo al final
        if len(parts) < 2:
            return None, None  # Sin subcarpetas
        # Quitamos el nombre del archivo, solo nos quedamos con los directorios
        dirs = parts[:-1]
        if len(dirs) == 1:
            # Artist/song.mp3
            return dirs[0], None
        elif len(dirs) >= 2:
            # Artist/Album/song.mp3 → tomamos útlimo como album, penúltimo como artista
            return dirs[-2], dirs[-1]
    except Exception:
        pass
    return None, None


def buscar_archivo_lrc(ruta_audio, carpeta_lyrics):
    """
    Busca un archivo .lrc correspondiente al archivo de audio.
    Busca con el mismo nombre base (sin extensión).
    """
    nombre_base = Path(ruta_audio).stem
    ruta_lrc = carpeta_lyrics / f"{nombre_base}.lrc"
    
    if ruta_lrc.exists():
        return str(ruta_lrc)
    
    return None

def descargar_letra_lrc(cancion: str, artista: str, ruta_archivo: str):
    """
    Busca y descarga una letra sincronizada usando la API pública de LRCLIB.
    """
    print(f"  🔍 Buscando letra: '{cancion}' de '{artista}'...")

    # Preparamos la URL para la API
    base_url = "https://lrclib.net/api/search"
    query = f"?track_name={urllib.parse.quote(cancion)}&artist_name={urllib.parse.quote(artista)}"
    url_completa = base_url + query

    try:
        # Hacemos la petición a la API
        respuesta = requests.get(url_completa)
        respuesta.raise_for_status()

        datos = respuesta.json()

        # Comprobar si encontramos resultados
        if not datos:
            print(f"  ❌ No se encontró la canción en la base de datos.")
            return False

        # Tomamos el primer resultado que tenga letra sincronizada (syncedLyrics)
        resultado_ideal = None
        for track in datos:
            if track.get('syncedLyrics'):
                resultado_ideal = track
                break

        if not resultado_ideal:
            print(f"  ❌ Se encontró la canción, pero no tiene letra sincronizada.")
            return False

        letra_sincronizada = resultado_ideal['syncedLyrics']

        # Guardar el archivo
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(letra_sincronizada)

        print(f"  ✅ Letra descargada y guardada: {Path(ruta_archivo).name}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error al conectar con la API: {e}")
        return False

def escanear_carpeta_audio(progress_callback=None):
    """
    Escanea la carpeta de audio y agrega las canciones a la base de datos.
    """
    def emit_progress(payload):
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:
            pass

    print("=" * 60)
    print("🎵 ESCANEANDO CARPETA DE AUDIO 🎵")
    print("=" * 60)
    
    carpeta_audio = Config.AUDIO_FOLDER
    carpeta_lyrics = Config.LYRICS_FOLDER
    
    if not carpeta_audio.exists():
        print(f"❌ La carpeta de audio no existe: {carpeta_audio}")
        emit_progress({'stage': 'error', 'message': f'La carpeta de audio no existe: {carpeta_audio}', 'percent': 100})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0, 'error': 'carpeta_audio_no_existe'}
    
    print(f"📁 Carpeta de audio: {carpeta_audio}")
    print(f"📁 Carpeta de letras: {carpeta_lyrics}")
    print("-" * 60)
    
    # -------------------------------------------------------------
    # Limpieza primero: borrar de la BD lo que ya no existe físicamente
    # -------------------------------------------------------------
    emit_progress({
        'stage': 'processing',
        'message': 'Buscando y eliminando canciones huérfanas...',
        'percent': 0
    })
    print("🧹 Buscando canciones huérfanas en BD...")
    canciones_db = Cancion.query.all()
    huerfanas = 0
    for cancion in canciones_db:
        if not os.path.exists(cancion.ruta_archivo_audio):
            print(f"  🗑 Eliminando de BD (no encontrada en disco): {cancion.ruta_archivo_audio}")
            db.session.delete(cancion)
            huerfanas += 1
    
    if huerfanas > 0:
        db.session.commit()
        print(f"✅ Se eliminaron {huerfanas} canciones huérfanas de la base de datos.")
        
        # Limpiar álbumes vacíos
        albumes_db = Album.query.all()
        for alb in albumes_db:
            if not alb.canciones:
                db.session.delete(alb)
                
        # Limpiar artistas vacíos
        artistas_db = Artista.query.all()
        for art in artistas_db:
            if not art.canciones and not art.albums:
                db.session.delete(art)
                
        db.session.commit()
        print("✅ Se limpiaron álbumes y artistas vacíos en la base de datos.")

    archivos_encontrados = []
    
    # Escanear archivos de audio recursivamente en todas las subcarpetas
    for archivo in carpeta_audio.rglob('*'):
        if archivo.is_file() and archivo.suffix.lower() in AUDIO_EXTENSIONS:
            archivos_encontrados.append(archivo)
    
    if not archivos_encontrados:
        print("❌ No se encontraron archivos de audio en la carpeta.")
        emit_progress({'stage': 'done', 'message': 'No se encontraron archivos de audio.', 'percent': 100, 'processed': 0, 'total': 0})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0}
    
    print(f"✅ Se encontraron {len(archivos_encontrados)} archivos de audio")
    print("-" * 60)
    emit_progress({
        'stage': 'scan_started',
        'message': f'Se encontraron {len(archivos_encontrados)} archivos para procesar',
        'percent': 0,
        'processed': 0,
        'total': len(archivos_encontrados)
    })
    
    # Procesar cada archivo
    canciones_agregadas = 0
    canciones_actualizadas = 0
    canciones_omitidas = 0
    
    # Se asume que el llamador (CLI o la ruta Flask) ejecuta esto dentro
    # del contexto de aplicación apropiado. No creamos un nuevo
    # app.app_context() aquí para evitar importaciones circulares.
    total_archivos = len(archivos_encontrados)
    for idx, archivo in enumerate(archivos_encontrados, start=1):
        emit_progress({
            'stage': 'processing',
            'message': f'Procesando {archivo.name}',
            'current_file': archivo.name,
            'processed': idx - 1,
            'total': total_archivos,
            'percent': int(((idx - 1) / total_archivos) * 100)
        })
        print(f"\n📝 Procesando: {archivo.name}")

        # Verificar si ya existe en la base de datos por ruta exacta
        cancion_existente = Cancion.query.filter_by(ruta_archivo_audio=str(archivo)).first()

        if cancion_existente:
            print(f"  ⏭ Ya existe en la base de datos (ID: {cancion_existente.id})")
            canciones_omitidas += 1
            emit_progress({
                'stage': 'file_done',
                'message': f'Omitida (ya existía): {archivo.name}',
                'current_file': archivo.name,
                'processed': idx,
                'total': total_archivos,
                'percent': int((idx / total_archivos) * 100),
                'counters': {
                    'agregadas': canciones_agregadas,
                    'actualizadas': canciones_actualizadas,
                    'omitidas': canciones_omitidas
                }
            })
            continue

        # Si la ruta NO coincide, verificar si la canción ya existe por nombre de archivo
        # (para reparar rutas que cambiaron de ubicación)
        cancion_por_nombre = Cancion.query.filter(
            Cancion.ruta_archivo_audio.like(f'%{archivo.stem}%')
        ).first()
        if cancion_por_nombre:
            ruta_antigua = cancion_por_nombre.ruta_archivo_audio
            if not os.path.exists(ruta_antigua):
                print(f"  🔧 Ruta antigua no existe. Actualizando ruta para canción ID {cancion_por_nombre.id}")
                print(f"     Antigua: {ruta_antigua}")
                print(f"     Nueva:   {str(archivo)}")
                cancion_por_nombre.ruta_archivo_audio = str(archivo)
                db.session.add(cancion_por_nombre)
                canciones_actualizadas += 1
                emit_progress({
                    'stage': 'file_done',
                    'message': f'Actualizada ruta: {archivo.name}',
                    'current_file': archivo.name,
                    'processed': idx,
                    'total': total_archivos,
                    'percent': int((idx / total_archivos) * 100),
                    'counters': {
                        'agregadas': canciones_agregadas,
                        'actualizadas': canciones_actualizadas,
                        'omitidas': canciones_omitidas
                    }
                })
                continue

        # Extraer metadatos
        metadatos = extraer_metadatos(archivo)

        if metadatos:
            titulo = metadatos['titulo']
            artista = metadatos['artista']
            album = metadatos['album']
            duracion = metadatos['duracion']

            print(f"  📋 Metadatos encontrados:")
            print(f"     Título: {titulo}")
            print(f"     Artista: {artista}")
            print(f"     Álbum: {album}")
            print(f"     Duración: {duracion}s")
        else:
            # Usar nombre del archivo como fallback
            titulo, artista = limpiar_nombre_archivo(archivo.name)
            album = None
            duracion = None

            print(f"  📋 Sin metadatos, usando nombre del archivo:")
            print(f"     Título: {titulo}")
            print(f"     Artista: {artista or 'Desconocido'}")

        # Si faltan artista o álbum, intentar inferirlos desde la estructura de carpetas
        if not artista or not album:
            artista_carpeta, album_carpeta = inferir_metadatos_desde_ruta(archivo, carpeta_audio)
            if artista_carpeta and not artista:
                artista = artista_carpeta
                print(f"  📁 Artista inferido desde carpeta: {artista}")
            if album_carpeta and not album:
                album = album_carpeta
                print(f"  📁 Álbum inferido desde carpeta: {album}")

        artista_obj = None
        if artista:
            artista_norm = normalizar_artista(artista)
            artista_obj = Artista.query.filter_by(nombre=artista_norm).first()
        if not artista_obj and artista:
            artista_obj = Artista(nombre=artista_norm or artista)
            db.session.add(artista_obj)
            db.session.flush()
            # Auto-enriquecer metadatos del nuevo artista desde APIs públicas
            try:
                enrich_artist(artista_obj, commit=False)
                print(f"  🌐 Metadatos automáticos obtenidos para: {artista_norm or artista}")
            except Exception as e:
                print(f"  ⚠ No se pudieron obtener metadatos automáticos: {e}")

        album_obj = None
        album_base, album_version = detectar_version(album)
        album_final = normalizar_album(album_base or album)
        if album_final and artista_obj:
            album_obj = Album.query.filter_by(titulo=album_final, artista_id=artista_obj.id).first()
        if not album_obj and album_final and artista_obj:
            album_obj = Album(titulo=album_final, artista_id=artista_obj.id)
            db.session.add(album_obj)
            db.session.flush()

        # Buscar archivo LRC correspondiente
        ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
        if ruta_lrc:
            print(f"  🎤 Letra encontrada: {Path(ruta_lrc).name}")
        else:
            print(f"  ⚠ Sin letra sincronizada local")
            # Intentar descargar letra automáticamente
            nombre_base = Path(archivo).stem
            ruta_lrc_destino = carpeta_lyrics / f"{nombre_base}.lrc"
            if descargar_letra_lrc(titulo or archivo.stem, artista or 'Desconocido', str(ruta_lrc_destino)):
                ruta_lrc = str(ruta_lrc_destino)

        # Extraer análisis de audio de metadatos
        aa = (metadatos or {}).get('audio_analysis', {})

        # Crear nueva canción
        nueva_cancion = Cancion(
            titulo=titulo or archivo.stem,
            artista_id=artista_obj.id if artista_obj else None,
            album_id=album_obj.id if album_obj else None,
            duracion=duracion or aa.get('duration'),
            ruta_archivo_audio=str(archivo),
            ruta_archivo_lrc=ruta_lrc,
            ruta_imagen_album=metadatos.get('ruta_imagen') if metadatos else None,
            numero_pista=(metadatos or {}).get('numero_pista'),
            genero=(metadatos or {}).get('genero') or aa.get('genero'),
            sample_rate=aa.get('sample_rate'),
            bit_depth=aa.get('bit_depth'),
            channels=aa.get('channels'),
            nyquist_freq=aa.get('nyquist_freq'),
            dynamic_range=aa.get('dynamic_range'),
            peak_level=aa.get('peak_level'),
            rms_level=aa.get('rms_level'),
            total_samples=aa.get('total_samples'),
            bit_rate=aa.get('bit_rate')
        )

        db.session.add(nueva_cancion)
        canciones_agregadas += 1
        print(f"  ✅ Canción agregada a la base de datos")
        emit_progress({
            'stage': 'file_done',
            'message': f'Agregada: {archivo.name}',
            'current_file': archivo.name,
            'processed': idx,
            'total': total_archivos,
            'percent': int((idx / total_archivos) * 100),
            'counters': {
                'agregadas': canciones_agregadas,
                'actualizadas': canciones_actualizadas,
                'omitidas': canciones_omitidas
            }
        })

    # Guardar cambios fuera del bucle
    db.session.commit()

    # Auto-enriquecer metadatos de artistas y álbumes
    print("\n" + "=" * 60)
    print("🌐 ENRIQUECIENDO METADATOS...")
    print("=" * 60)

    # Notificar al frontend que comenzó la fase de enriquecimiento
    emit_progress({
        'stage': 'enriching',
        'message': 'Enriqueciendo metadatos de artistas y álbumes...',
        'current_file': 'Enriqueciendo metadatos...',
        'processed': total_archivos,
        'total': total_archivos,
        'percent': 99,
        'counters': {
            'agregadas': canciones_agregadas,
            'actualizadas': canciones_actualizadas,
            'omitidas': canciones_omitidas
        }
    })

    try:
        res_meta = enrich_all(commit=True)
        print(f"   Artistas enriquecidos: {res_meta['artistas'][0]}/{res_meta['artistas'][1]}")
        print(f"   Álbumes enriquecidos:  {res_meta['albumes'][0]}/{res_meta['albumes'][1]}")
    except Exception as e:
        print(f"   ⚠ Error al enriquecer metadatos: {e}")
        res_meta = {'artistas': (0, 0), 'albumes': (0, 0)}

    print("\n" + "=" * 60)
    print("📊 RESUMEN DEL ESCANEO")
    print("=" * 60)
    print(f"✅ Canciones agregadas: {canciones_agregadas}")
    print(f"🔄 Canciones actualizadas: {canciones_actualizadas}")
    print(f"⏭ Canciones omitidas (ya existían): {canciones_omitidas}")
    print(f"📁 Total procesadas: {len(archivos_encontrados)}")
    if res_meta['artistas'][0] > 0 or res_meta['albumes'][0] > 0:
        print(f"🌐 Metadatos enriquecidos:")
        print(f"   Artistas: {res_meta['artistas'][0]} · Álbumes: {res_meta['albumes'][0]}")
    print("=" * 60)

    # Devolver resumen para uso por llamadas programáticas (ej. ruta web)
    try:
        meta_artistas = res_meta['artistas'][0]
        meta_albumes = res_meta['albumes'][0]
    except Exception:
        meta_artistas = 0
        meta_albumes = 0
    resumen = {
        'agregadas': canciones_agregadas,
        'actualizadas': canciones_actualizadas,
        'omitidas': canciones_omitidas,
        'procesadas': len(archivos_encontrados),
        'meta_artistas': meta_artistas,
        'meta_albumes': meta_albumes,
    }
    emit_progress({
        'stage': 'done',
        'message': 'Escaneo finalizado',
        'percent': 100,
        'processed': len(archivos_encontrados),
        'total': len(archivos_encontrados),
        'summary': resumen
    })
    return resumen


def escaneo_rapido(progress_callback=None):
    """
    Escaneo inteligente e incremental.
    - Solo procesa archivos que NO están ya en la base de datos.
    - Detecta archivos eliminados del disco y los marca.
    - Hasta 10x más rápido que el escaneo completo en bibliotecas grandes.
    """
    def emit_progress(payload):
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:
            pass

    print("=" * 60)
    print("⚡ ESCANEO RÁPIDO (INCREMENTAL)")
    print("=" * 60)

    carpeta_audio = Config.AUDIO_FOLDER
    carpeta_lyrics = Config.LYRICS_FOLDER

    if not carpeta_audio.exists():
        emit_progress({'stage': 'error', 'message': f'La carpeta de audio no existe: {carpeta_audio}', 'percent': 100})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0, 'eliminadas': 0}

    emit_progress({'stage': 'processing', 'message': 'Comparando biblioteca con disco...', 'percent': 2, 'processed': 0, 'total': 0})

    # 1. Obtener todas las rutas del disco en un set (operación de disco, rápida)
    archivos_disco = {
        str(archivo)
        for archivo in carpeta_audio.rglob('*')
        if archivo.is_file() and archivo.suffix.lower() in AUDIO_EXTENSIONS
    }

    # 2. Obtener todas las rutas registradas en la BD en un set (una sola query)
    rutas_bd = {row.ruta_archivo_audio for row in Cancion.query.with_entities(Cancion.ruta_archivo_audio).all()}

    # 3. Calcular diferencias mediante operaciones de conjuntos (O(n), instantáneo)
    archivos_nuevos = archivos_disco - rutas_bd          # en disco pero no en BD → agregar
    archivos_eliminados = rutas_bd - archivos_disco       # en BD pero no en disco → marcar/eliminar

    print(f"📊 En disco: {len(archivos_disco)} | En BD: {len(rutas_bd)}")
    print(f"✨ Nuevos: {len(archivos_nuevos)} | 🗑 Eliminados: {len(archivos_eliminados)}")

    canciones_agregadas = 0
    canciones_eliminadas = 0
    errores = 0

    # 4. Marcar canciones eliminadas (no las borramos de BD para no perder historial)
    if archivos_eliminados:
        emit_progress({
            'stage': 'processing',
            'message': f'Detectando {len(archivos_eliminados)} archivos eliminados...',
            'percent': 5, 'processed': 0, 'total': len(archivos_nuevos)
        })
        for ruta_eliminada in archivos_eliminados:
            cancion = Cancion.query.filter_by(ruta_archivo_audio=ruta_eliminada).first()
            if cancion:
                # Marcamos con un prefijo para indicar que el archivo ya no existe
                if not cancion.ruta_archivo_audio.startswith('[ELIMINADO]'):
                    cancion.ruta_archivo_audio = '[ELIMINADO] ' + cancion.ruta_archivo_audio
                    db.session.add(cancion)
                    canciones_eliminadas += 1
                    print(f"  🗑 Marcada como eliminada: {Path(ruta_eliminada).name}")
        db.session.commit()

    if not archivos_nuevos:
        emit_progress({
            'stage': 'done',
            'message': f'Sin cambios — biblioteca al día. ({canciones_eliminadas} eliminadas)',
            'percent': 100, 'processed': 0, 'total': 0,
            'summary': {'agregadas': 0, 'actualizadas': 0, 'omitidas': len(rutas_bd),
                        'procesadas': 0, 'eliminadas': canciones_eliminadas,
                        'meta_artistas': 0, 'meta_albumes': 0}
        })
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': len(rutas_bd),
                'procesadas': 0, 'eliminadas': canciones_eliminadas, 'meta_artistas': 0, 'meta_albumes': 0}

    # 5. Procesar solo los archivos nuevos (misma lógica que el escaneo completo)
    archivos_nuevos_lista = [Path(p) for p in sorted(archivos_nuevos)]
    total = len(archivos_nuevos_lista)

    for idx, archivo in enumerate(archivos_nuevos_lista, start=1):
        emit_progress({
            'stage': 'processing',
            'message': f'Nuevo: {archivo.name}',
            'current_file': archivo.name,
            'processed': idx - 1,
            'total': total,
            'percent': int(5 + ((idx - 1) / total) * 90)
        })

        try:
            metadatos = extraer_metadatos(archivo)

            if metadatos:
                titulo = metadatos.get('titulo')
                artista = metadatos.get('artista')
                album = metadatos.get('album')
                duracion = metadatos.get('duracion')
            else:
                titulo, artista = limpiar_nombre_archivo(archivo.name)
                album = None
                duracion = None

            if not artista or not album:
                artista_carpeta, album_carpeta = inferir_metadatos_desde_ruta(archivo, carpeta_audio)
                if artista_carpeta and not artista:
                    artista = artista_carpeta
                if album_carpeta and not album:
                    album = album_carpeta

            artista_obj = None
            if artista:
                from metadata_normalizer import normalizar_artista
                artista_norm = normalizar_artista(artista)
                artista_obj = Artista.query.filter_by(nombre=artista_norm).first()
                if not artista_obj:
                    artista_obj = Artista(nombre=artista_norm or artista)
                    db.session.add(artista_obj)
                    db.session.flush()
                    try:
                        enrich_artist(artista_obj, commit=False)
                    except Exception:
                        pass

            album_obj = None
            from metadata_normalizer import detectar_version, normalizar_album
            album_base, _ = detectar_version(album)
            album_final = normalizar_album(album_base or album)
            if album_final and artista_obj:
                album_obj = Album.query.filter_by(titulo=album_final, artista_id=artista_obj.id).first()
                if not album_obj:
                    album_obj = Album(titulo=album_final, artista_id=artista_obj.id)
                    db.session.add(album_obj)
                    db.session.flush()

            ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
            if not ruta_lrc:
                nombre_base = Path(archivo).stem
                ruta_lrc_destino = carpeta_lyrics / f"{nombre_base}.lrc"
                if descargar_letra_lrc(titulo or archivo.stem, artista or 'Desconocido', str(ruta_lrc_destino)):
                    ruta_lrc = str(ruta_lrc_destino)

            aa = (metadatos or {}).get('audio_analysis', {})
            nueva_cancion = Cancion(
                titulo=titulo or archivo.stem,
                artista_id=artista_obj.id if artista_obj else None,
                album_id=album_obj.id if album_obj else None,
                duracion=duracion or aa.get('duration'),
                ruta_archivo_audio=str(archivo),
                ruta_archivo_lrc=ruta_lrc,
                ruta_imagen_album=metadatos.get('ruta_imagen') if metadatos else None,
                numero_pista=(metadatos or {}).get('numero_pista'),
                genero=(metadatos or {}).get('genero') or aa.get('genero'),
                sample_rate=aa.get('sample_rate'),
                bit_depth=aa.get('bit_depth'),
                channels=aa.get('channels'),
                nyquist_freq=aa.get('nyquist_freq'),
                dynamic_range=aa.get('dynamic_range'),
                peak_level=aa.get('peak_level'),
                rms_level=aa.get('rms_level'),
                total_samples=aa.get('total_samples'),
                bit_rate=aa.get('bit_rate')
            )
            db.session.add(nueva_cancion)
            canciones_agregadas += 1
            print(f"  ✅ Agregada: {archivo.name}")
        except Exception as ex:
            errores += 1
            print(f"  ❌ Error procesando {archivo.name}: {ex}")

    db.session.commit()

    # 6. Enriquecer solo artistas y álbumes sin foto/bio (los ya enriquecidos se omiten)
    emit_progress({
        'stage': 'enriching',
        'message': 'Enriqueciendo metadatos de artistas/álbumes nuevos...',
        'processed': total, 'total': total, 'percent': 97
    })
    try:
        res_meta = enrich_all(commit=True)
        meta_artistas = res_meta['artistas'][0]
        meta_albumes = res_meta['albumes'][0]
    except Exception as e:
        print(f"  ⚠ Error enriquecimiento: {e}")
        meta_artistas = 0
        meta_albumes = 0

    resumen = {
        'agregadas': canciones_agregadas,
        'actualizadas': 0,
        'omitidas': len(rutas_bd) - canciones_eliminadas,
        'procesadas': canciones_agregadas,
        'eliminadas': canciones_eliminadas,
        'meta_artistas': meta_artistas,
        'meta_albumes': meta_albumes,
    }
    emit_progress({
        'stage': 'done',
        'message': f'Escaneo rápido finalizado — {canciones_agregadas} nuevas, {canciones_eliminadas} eliminadas',
        'percent': 100,
        'processed': total,
        'total': total,
        'summary': resumen
    })
    return resumen

if __name__ == '__main__':
    try:
        # Importar la app localmente para evitar importaciones circulares
        from app import app
        with app.app_context():
            resumen = escanear_carpeta_audio()
            print('\nResumen:', resumen)
    except KeyboardInterrupt:
        print("\n\n⚠ Escaneo interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error durante el escaneo: {e}")
        import traceback
        traceback.print_exc()
