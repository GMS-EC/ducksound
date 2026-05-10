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
from tinytag import TinyTag
from config import Config
from models import db, Artista, Album, Cancion
from metadata_fetcher import enrich_artist, enrich_all
from metadata_normalizer import normalizar_artista, normalizar_album, detectar_version, limpiar_nombre, obtener_album_base_fuzz

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}

def extraer_metadatos(ruta_archivo):
    """
    Extrae metadatos del archivo de audio usando TinyTag como fuente principal.
    Mutagen se conserva solamente para recuperar portadas embebidas.
    """
    from audio_analyzer import analyze_audio

    try:
        tag = TinyTag.get(str(ruta_archivo), image=False)
        if tag is None:
            return None

        def parse_track_num(val):
            if not val:
                return None
            try:
                return int(str(val).split('/')[0])
            except Exception:
                return None

        def extra_tag(*keys):
            extra = getattr(tag, 'extra', None) or {}
            for key in keys:
                valor = extra.get(key)
                if isinstance(valor, (list, tuple)):
                    valor = valor[0] if valor else None
                if valor:
                    return valor
            return None

        artista = getattr(tag, 'artist', None) or extra_tag('artist', 'ARTIST')
        albumartist = (
            getattr(tag, 'albumartist', None)
            or extra_tag('albumartist', 'album artist', 'album_artist', 'ALBUMARTIST', 'ALBUM ARTIST', 'TPE2')
            or artista
        )

        metadatos = {
            'titulo': getattr(tag, 'title', None) or extra_tag('title', 'TITLE'),
            'artista': artista,
            'albumartist': albumartist,
            'artista_display': artista,  # Original con colaboraciones para display
            'artista_principal': normalizar_artista(albumartist),  # Artista unificado desde albumartist
            'album': getattr(tag, 'album', None) or extra_tag('album', 'ALBUM'),
            'duracion': int(tag.duration) if getattr(tag, 'duration', None) else None,
            'ruta_imagen': None,
            'genero': getattr(tag, 'genre', None) or extra_tag('genre', 'GENRE'),
            'numero_pista': parse_track_num(getattr(tag, 'track', None) or extra_tag('tracknumber', 'TRACKNUMBER', 'TRCK')),
            'numero_disco': parse_track_num(getattr(tag, 'disc', None) or extra_tag('discnumber', 'DISCNUMBER', 'TPA')),
        }

        try:
            analisis = analyze_audio(ruta_archivo)
            if analisis:
                if analisis.get('duration'):
                    metadatos['duracion'] = int(analisis['duration'])
                if analisis.get('genero') and not metadatos['genero']:
                    metadatos['genero'] = analisis['genero']
                metadatos['audio_analysis'] = analisis
        except Exception as e:
            print(f"  ⚠ Error en análisis de audio: {e}")

        try:
            audio_file = File(ruta_archivo)
            if audio_file is not None:
                apic_tags = [
                    picture for key, picture in getattr(audio_file, 'tags', {}).items()
                    if str(key).startswith('APIC')
                ]
                if apic_tags:
                    metadatos['ruta_imagen'] = guardar_imagen_album(apic_tags[0], ruta_archivo)
                elif getattr(audio_file, 'pictures', None):
                    metadatos['ruta_imagen'] = guardar_imagen_album(audio_file.pictures[0], ruta_archivo)
        except Exception as e:
            print(f"  ⚠ Error al extraer portada embebida: {e}")

        if not metadatos.get('ruta_imagen'):
            titulo_b = metadatos.get('titulo') or Path(ruta_archivo).stem
            artista_b = metadatos.get('albumartist') or metadatos.get('artista') or ''
            album_b = metadatos.get('album') or ''
            if titulo_b and artista_b:
                print(f"  Buscando portada en internet para: {titulo_b}")
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


def obtener_o_crear_artista(nombre, enriquecer=False, mbid=None):
    if not nombre:
        return None

    nombre_norm = normalizar_artista(nombre)
    if not nombre_norm:
        return None
    
    from sqlalchemy import func
    from rapidfuzz import fuzz
    UMBRAL_FUZZY = 80

    # 1. Buscar por musicbrainz_id si se proporcionó (desde metadatos del archivo)
    if mbid:
        artista_obj = Artista.query.filter_by(musicbrainz_id=mbid).first()
        if artista_obj:
            return artista_obj

    # 2. Buscar por nombre_normalizado
    artista_obj = Artista.query.filter(
        func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()
    ).first()
    if artista_obj:
        return artista_obj

    # 3. Buscar en MusicBrainz API
    from musicbrainz_client import buscar_artista
    mb_result = buscar_artista(nombre_norm)
    if mb_result:
        # Usar sort_name como nombre_normalizado (romanizado si es diferente)
        mb_nombre_raw = mb_result['nombre']
        mb_sort = mb_result['sort_name']
        mb_nombre_norm = normalizar_artista(mb_sort if mb_sort and mb_sort != mb_nombre_raw else mb_nombre_raw)
        
        # Buscar por MBID en BD
        artista_obj = Artista.query.filter_by(musicbrainz_id=mb_result['mbid']).first()
        if artista_obj:
            return artista_obj
        
        # Buscar por nombre_normalizado de MusicBrainz
        if mb_nombre_norm:
            artista_obj = Artista.query.filter(
                func.lower(func.trim(Artista.nombre_normalizado)) == mb_nombre_norm.lower().strip()
            ).first()
            if artista_obj:
                return artista_obj
        
        # Actualizar mb_result con el normalized name correcto
        mb_result['nombre_norm'] = mb_nombre_norm

    # 4. Fuzzy matching contra artistas existentes que NO tengan MBID
    mejor_ratio = 0
    mejor_artista = None
    for a in Artista.query.filter(Artista.musicbrainz_id.is_(None)).all():
        ratio = fuzz.token_set_ratio(nombre_norm.lower(), a.nombre.lower())
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_artista = a
    if mejor_ratio >= UMBRAL_FUZZY and mejor_artista:
        return mejor_artista

    # 5. Crear nuevo artista
    # Usar sort_name de MusicBrainz como nombre_normalizado si existe (romanización)
    mb_norm_name = mb_result.get('nombre_norm') if mb_result else None
    final_norm = mb_norm_name or nombre_norm
    try:
        artista_obj = Artista(
            nombre=nombre_norm,
            nombre_normalizado=final_norm,
            musicbrainz_id=mb_result['mbid'] if mb_result else None
        )
        db.session.add(artista_obj)
        db.session.flush()
        return artista_obj
    except Exception:
        db.session.rollback()
        artista_obj = Artista.query.filter(
            func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()
        ).first()
        return artista_obj


def obtener_o_crear_album(album, albumartist, mbid=None):
    if not album or not albumartist:
        return None

    album_artista_obj = obtener_o_crear_artista(albumartist)
    if not album_artista_obj:
        return None

    # 1. Buscar por musicbrainz_id
    if mbid:
        album_obj = Album.query.filter_by(musicbrainz_id=mbid).first()
        if album_obj:
            return album_obj

    # 2. Buscar por título normalizado + artista
    album_base, _ = detectar_version(album)
    album_final = normalizar_album(album_base or album)
    if not album_final:
        return None

    albumes_artista = Album.query.filter_by(artista_id=album_artista_obj.id).all()
    album_obj = obtener_album_base_fuzz(album_final, albumes_artista)
    if album_obj:
        return album_obj

    # 3. Consultar MusicBrainz si el artista tiene MBID
    if album_artista_obj.musicbrainz_id:
        from musicbrainz_client import buscar_album
        mb_album = buscar_album(album, album_artista_obj.musicbrainz_id)
        if mb_album and not mbid:
            album_obj = Album.query.filter_by(musicbrainz_id=mb_album['mbid']).first()
            if album_obj:
                return album_obj
            mbid = mb_album['mbid']

    # 4. Crear nuevo álbum
    album_obj = Album(titulo=album_final, artista_id=album_artista_obj.id, musicbrainz_id=mbid)
    try:
        db.session.add(album_obj)
        db.session.flush()
        return album_obj
    except Exception:
        db.session.rollback()
        albumes_artista = Album.query.filter_by(artista_id=album_artista_obj.id).all()
        album_obj = obtener_album_base_fuzz(album_final, albumes_artista)
        return album_obj

    album_obj = Album(titulo=album_final, artista_id=album_artista_obj.id)
    try:
        db.session.add(album_obj)
        db.session.flush()
        return album_obj
    except Exception:
        db.session.rollback()
        # Si falló por unique constraint, buscar de nuevo
        albumes_artista = Album.query.filter_by(artista_id=album_artista_obj.id).all()
        album_obj = obtener_album_base_fuzz(album_final, albumes_artista)
        return album_obj


def limpiar_entidades_vacias():
    albumes_eliminados = 0
    artistas_eliminados = 0

    for album in Album.query.all():
        if not album.canciones:
            db.session.delete(album)
            albumes_eliminados += 1

    db.session.flush()

    for artista in Artista.query.all():
        if not artista.canciones and not artista.albums:
            db.session.delete(artista)
            artistas_eliminados += 1

    return albumes_eliminados, artistas_eliminados


def normalizar_biblioteca(progress_callback=None, percent_start=90, percent_end=99):
    """Unifica artistas y albumes duplicados usando las reglas normalizadas actuales."""
    def emit(payload):
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:
            pass

    resumen = {
        'artistas_renombrados': 0,
        'artistas_fusionados': 0,
        'albumes_renombrados': 0,
        'albumes_fusionados': 0,
        'albumes_eliminados': 0,
        'artistas_eliminados': 0,
    }

    emit({'stage': 'normalizing', 'message': 'Normalizando artistas...', 'percent': percent_start})
    artistas = Artista.query.order_by(Artista.id).all()
    total_artistas = max(len(artistas), 1)
    mid_percent = percent_start + int((percent_end - percent_start) * 0.45)

    for idx, artista in enumerate(artistas, start=1):
        nombre_norm = normalizar_artista(artista.nombre)
        emit({
            'stage': 'normalizing',
            'message': f'Normalizando artista: {artista.nombre}',
            'processed': idx,
            'total': len(artistas),
            'percent': percent_start + int((idx / total_artistas) * max(mid_percent - percent_start, 1)),
        })

        if not nombre_norm:
            continue

        artista_existente = Artista.query.filter(
            Artista.nombre == nombre_norm,
            Artista.id != artista.id
        ).order_by(Artista.id).first()

        if artista_existente:
            destino = artista_existente if artista_existente.id < artista.id else artista
            origen = artista if destino.id == artista_existente.id else artista_existente
            for cancion in list(origen.canciones):
                cancion.artista_id = destino.id
            for album in list(origen.albums):
                album.artista_id = destino.id
            db.session.delete(origen)
            resumen['artistas_fusionados'] += 1
        elif nombre_norm != artista.nombre:
            artista.nombre = nombre_norm
            resumen['artistas_renombrados'] += 1

    db.session.flush()

    emit({'stage': 'normalizing', 'message': 'Normalizando albumes...', 'percent': mid_percent})
    artistas = Artista.query.order_by(Artista.id).all()
    total_albumes = max(Album.query.count(), 1)
    albumes_vistos = 0

    for artista in artistas:
        albumes_artista = Album.query.filter_by(artista_id=artista.id).order_by(Album.id).all()
        albumes_base = []

        for album in albumes_artista:
            albumes_vistos += 1
            titulo_norm = normalizar_album(album.titulo)
            emit({
                'stage': 'normalizing',
                'message': f'Normalizando album: {album.titulo}',
                'processed': albumes_vistos,
                'total': total_albumes,
                'percent': mid_percent + int((albumes_vistos / total_albumes) * max(percent_end - mid_percent, 1)),
            })

            if titulo_norm and titulo_norm != album.titulo:
                album.titulo = titulo_norm
                resumen['albumes_renombrados'] += 1

            album_existente = obtener_album_base_fuzz(titulo_norm or album.titulo, albumes_base)
            if album_existente and album_existente.id != album.id:
                for cancion in list(album.canciones):
                    cancion.album_id = album_existente.id
                if not album_existente.portada_url and album.portada_url:
                    album_existente.portada_url = album.portada_url
                if not album_existente.anio and album.anio:
                    album_existente.anio = album.anio
                db.session.delete(album)
                resumen['albumes_fusionados'] += 1
            else:
                albumes_base.append(album)

    eliminados = limpiar_entidades_vacias()
    resumen['albumes_eliminados'], resumen['artistas_eliminados'] = eliminados
    db.session.commit()

    emit({'stage': 'normalizing', 'message': 'Normalizacion de metadatos finalizada', 'percent': percent_end})
    return resumen


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
      Artist/CD 1/song.mp3        → artista='Artist', album=None (ignorar carpeta de disco)
      Artist/Disc 2/song.mp3      → artista='Artist', album=None (ignorar carpeta de disco)
      song.mp3                     → artista=None, album=None
    """
    import re
    try:
        rel_path = Path(ruta_archivo).resolve().relative_to(Path(carpeta_base_audio).resolve())
        parts = list(rel_path.parts)
        # parts incluye el nombre del archivo al final
        if len(parts) < 2:
            return None, None  # Sin subcarpetas
        # Quitamos el nombre del archivo, solo nos quedamos con los directorios
        dirs = parts[:-1]
        
        # Verificar si alguna carpeta es de disco (CD/Disc) y omitirla
        filtered_dirs = []
        for dir_name in dirs:
            if re.match(r'^(CD|Disc)\s*\d+$', dir_name, re.IGNORECASE):
                continue  # Ignorar carpetas de disco
            filtered_dirs.append(dir_name)
        
        if len(filtered_dirs) == 1:
            # Artist/song.mp3
            return filtered_dirs[0], None
        elif len(filtered_dirs) >= 2:
            # Artist/Album/song.mp3 → tomamos último como album, penúltimo como artista
            return filtered_dirs[-2], filtered_dirs[-1]
    except Exception:
        pass
    return None, None


def buscar_archivo_lrc(ruta_audio, carpeta_lyrics, cancion_id=None):
    """
    Busca un archivo .lrc correspondiente al archivo de audio.
    Estrategias de búsqueda:
    1. Mismo nombre base en carpeta de la canción
    2. Mismo nombre base en Config.LYRICS_FOLDER
    3. Basado en ID de canción en Config.LYRICS_FOLDER
    """
    from config import Config
    import os
    
    nombre_base = Path(ruta_audio).stem
    ruta_audio_path = Path(ruta_audio)
    
    # Estrategia 1: Buscar en la misma carpeta que el audio
    ruta_lrc_local = ruta_audio_path.parent / f"{nombre_base}.lrc"
    if ruta_lrc_local.exists():
        return str(ruta_lrc_local)
    
    # Estrategia 2: Buscar en LYRICS_FOLDER por nombre base
    ruta_lrc_lyrics = carpeta_lyrics / f"{nombre_base}.lrc"
    if ruta_lrc_lyrics.exists():
        return str(ruta_lrc_lyrics)
    
    # Estrategia 3: Buscar por ID de canción si está disponible
    if cancion_id:
        # Buscar archivos que comiencen con el ID
        for lrc_file in Config.LYRICS_FOLDER.glob(f"{cancion_id}_*.lrc"):
            if lrc_file.exists():
                return str(lrc_file)
    
    # Estrategia 4: Búsqueda flexible (case-insensitive y variaciones)
    # Buscar en LYRICS_FOLDER con variaciones del nombre
    for lrc_file in Config.LYRICS_FOLDER.glob("*.lrc"):
        if lrc_file.stem.lower() == nombre_base.lower():
            return str(lrc_file)
    
    return None

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
        print(f"La carpeta de audio no existe: {carpeta_audio}")
        emit_progress({'stage': 'error', 'message': f'La carpeta de audio no existe: {carpeta_audio}', 'percent': 100})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0, 'error': 'carpeta_audio_no_existe'}
    
    print(f"Carpeta de audio: {carpeta_audio}")
    print(f"Carpeta de letras: {carpeta_lyrics}")
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
        print("No se encontraron archivos de audio en la carpeta.")
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
    
    # Contador para commits en bloque cada 50 canciones
    commit_counter = 0
    batch_size = 50
    
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
        print(f"\nProcesando: {archivo.name}")

        # Verificar si ya existe en la base de datos por ruta exacta
        cancion_existente = Cancion.query.filter_by(ruta_archivo_audio=str(archivo)).first()

        if cancion_existente:
            print(f"  Ya existe en la base de datos (ID: {cancion_existente.id})")
            
            # ESCANEO COMPLETO: Buscar letra localmente (NO descargar de API para mantener rapidez)
            if not cancion_existente.ruta_archivo_lrc or not Path(cancion_existente.ruta_archivo_lrc).exists():
                ruta_lrc_existente = buscar_archivo_lrc(archivo, carpeta_lyrics, cancion_existente.id)
                if ruta_lrc_existente:
                    cancion_existente.ruta_archivo_lrc = ruta_lrc_existente
                    print(f"  🎤 Letra local actualizada: {Path(ruta_lrc_existente).name}")
                    canciones_actualizadas += 1
                else:
                    print(f"  ⚠ Sin letra local (se descargará en segundo plano)")
            else:
                print(f"  ✅ Letra ya existente: {Path(cancion_existente.ruta_archivo_lrc).name}")
            
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
            albumartist = metadatos.get('albumartist') or artista
            album = metadatos['album']
            duracion = metadatos['duracion']

            print(f"  📋 Metadatos encontrados:")
            print(f"     Título: {titulo}")
            print(f"     Artista: {artista}")
            print(f"     Album: {album}")
            print(f"     Duración: {duracion}s")
        else:
            # Usar nombre del archivo como fallback
            titulo, artista = limpiar_nombre_archivo(archivo.name)
            albumartist = artista
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
                albumartist = albumartist or artista_carpeta
                print(f"  Artista inferido desde carpeta: {artista}")
            if album_carpeta and not album:
                album = album_carpeta
                print(f"  Album inferido desde carpeta: {album}")

        albumartist = albumartist or artista
        
        # Usar artista_principal (desde albumartist) como único artista
        artista_principal = (metadatos or {}).get('artista_principal') or normalizar_artista(albumartist or artista)
        # artista_display conserva el original con colaboraciones
        artista_display = (metadatos or {}).get('artista_display') or artista
        
        artista_obj = obtener_o_crear_artista(artista_principal)
        if not artista_obj and artista_principal:
            artista_obj = Artista(nombre=artista_principal, nombre_normalizado=artista_principal)
            db.session.add(artista_obj)
            db.session.flush()
            try:
                enrich_artist(artista_obj, commit=False)
                print(f"  Metadatos automaticos obtenidos para: {artista_principal}")
            except Exception as e:
                print(f"  ⚠ No se pudieron obtener metadatos automáticos: {e}")
        
        # Álbum: único camino, usando albumartist
        album_obj = obtener_o_crear_album(album, artista_principal) if (album and artista_principal) else None

        # Buscar archivo LRC correspondiente (solo local para rapidez)
        ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
        if ruta_lrc:
            print(f"  🎤 Letra encontrada localmente: {Path(ruta_lrc).name}")
        else:
            print(f"  ⚠️ Sin letra local (se descargará en segundo plano)")

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
            numero_disco=(metadatos or {}).get('numero_disco'),
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
        commit_counter += 1
        print(f"  ✅ Canción agregada a la base de datos")
        
        # Hacer commit cada 100 canciones
        if commit_counter >= batch_size:
            db.session.commit()
            commit_counter = 0
            print(f"  💾 Commit de {batch_size} canciones procesadas")
        
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

    # Commit final para cualquier canción restante
    if commit_counter > 0:
        db.session.commit()
        print(f"  💾 Commit final de {commit_counter} canciones restantes")
    resumen_norm = normalizar_biblioteca(
        progress_callback=progress_callback,
        percent_start=94,
        percent_end=98,
    )

    # Auto-enriquecer metadatos de artistas y álbumes
    print("\n" + "=" * 60)
    print("ENRIQUECIENDO METADATOS...")
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
        print(f"   Albumes enriquecidos:  {res_meta['albumes'][0]}/{res_meta['albumes'][1]}")
    except Exception as e:
        print(f"   ⚠ Error al enriquecer metadatos: {e}")
        res_meta = {'artistas': (0, 0), 'albumes': (0, 0)}

    print("\n" + "=" * 60)
    print("📊 RESUMEN DEL ESCANEO")
    print("=" * 60)
    print(f"✅ Canciones agregadas: {canciones_agregadas}")
    print(f"🔄 Canciones actualizadas: {canciones_actualizadas}")
    print(f"Canciones omitidas (ya existian): {canciones_omitidas}")
    print(f"Total procesadas: {len(archivos_encontrados)}")
    if res_meta['artistas'][0] > 0 or res_meta['albumes'][0] > 0:
        print("Metadatos enriquecidos:")
        print(f"   Artistas: {res_meta['artistas'][0]} - Albumes: {res_meta['albumes'][0]}")
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
        'normalizacion': resumen_norm,
    }
    emit_progress({
        'stage': 'done',
        'message': 'Escaneo finalizado',
        'percent': 100,
        'processed': len(archivos_encontrados),
        'total': len(archivos_encontrados),
        'summary': resumen
    })
    
    # Encolar tareas post-escaneo en Redis (workers los procesan sin bloquear la app)
    try:
        from task_queue import enqueue
        from lyrics_fetcher import descargar_letras_segundo_plano
        from musicbrainz_client import enriquecer_artistas_sin_mbid
        
        print("\n🚀 Encolando tareas post-escaneo en Redis (letras + MusicBrainz)...")
        enqueue(descargar_letras_segundo_plano, batch_size=10)
        enqueue(enriquecer_artistas_sin_mbid, limite=200)
        print("✅ Tareas encoladas — workers las procesarán en segundo plano")
    except Exception as e:
        print(f"⚠️ No se pudieron encolar tareas: {e}")
        # Fallback: ejecutar en hilo
        import threading
        th = threading.Thread(target=lambda: (
            descargar_letras_segundo_plano(batch_size=10),
            enriquecer_artistas_sin_mbid(limite=200)
        ), daemon=True)
        th.start()
    
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
    print("ESCANEO RAPIDO (INCREMENTAL)")
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

    # 4. Eliminar de la biblioteca las canciones cuyos archivos ya no existen.
    if archivos_eliminados:
        emit_progress({
            'stage': 'processing',
            'message': f'Detectando {len(archivos_eliminados)} archivos eliminados...',
            'percent': 5, 'processed': 0, 'total': len(archivos_nuevos)
        })
        for ruta_eliminada in archivos_eliminados:
            cancion = Cancion.query.filter_by(ruta_archivo_audio=ruta_eliminada).first()
            if cancion:
                db.session.delete(cancion)
                canciones_eliminadas += 1
                print(f"  Eliminada de BD: {Path(ruta_eliminada).name}")
        db.session.commit()
        limpiar_entidades_vacias()
        db.session.commit()

    if not archivos_nuevos:
        resumen_norm = normalizar_biblioteca(
            progress_callback=progress_callback,
            percent_start=90,
            percent_end=99,
        )
        emit_progress({
            'stage': 'done',
            'message': f'Sin cambios — biblioteca al día. ({canciones_eliminadas} eliminadas)',
            'percent': 100, 'processed': 0, 'total': 0,
            'summary': {'agregadas': 0, 'actualizadas': 0, 'omitidas': len(rutas_bd) - canciones_eliminadas,
                        'procesadas': 0, 'eliminadas': canciones_eliminadas,
                        'meta_artistas': 0, 'meta_albumes': 0,
                        'normalizacion': resumen_norm}
        })
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': len(rutas_bd) - canciones_eliminadas,
                'procesadas': 0, 'eliminadas': canciones_eliminadas, 'meta_artistas': 0, 'meta_albumes': 0,
                'normalizacion': resumen_norm}

    # 5. Procesar solo los archivos nuevos (misma lógica que el escaneo completo)
    archivos_nuevos_lista = [Path(p) for p in sorted(archivos_nuevos)]
    total = len(archivos_nuevos_lista)

    # Contador para commits en bloque cada 50 canciones
    commit_counter = 0
    batch_size = 50

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
                albumartist = metadatos.get('albumartist') or artista
                album = metadatos.get('album')
                duracion = metadatos.get('duracion')
            else:
                titulo, artista = limpiar_nombre_archivo(archivo.name)
                albumartist = artista
                album = None
                duracion = None

            if not artista or not album:
                artista_carpeta, album_carpeta = inferir_metadatos_desde_ruta(archivo, carpeta_audio)
                if artista_carpeta and not artista:
                    artista = artista_carpeta
                    albumartist = albumartist or artista_carpeta
                if album_carpeta and not album:
                    album = album_carpeta
            albumartist = albumartist or artista
            
            # Artista principal desde albumartist (unificado)
            artista_principal_rapido = (metadatos or {}).get('artista_principal') or normalizar_artista(albumartist or artista)

            artista_obj = obtener_o_crear_artista(artista_principal_rapido)
            album_obj = obtener_o_crear_album(album, artista_principal_rapido) if (album and artista_principal_rapido) else None

            # Solo búsqueda local (escaneo rápido no descarga de API)
            ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
            if ruta_lrc:
                print(f"  🎤 Letra ya existe localmente: {Path(ruta_lrc).name}")
            else:
                print(f"  ⚠️ Sin letra local (se descargará en segundo plano)")

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
                numero_disco=(metadatos or {}).get('numero_disco'),
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
            commit_counter += 1
            print(f"  ✅ Agregada: {archivo.name}")
            
            # Hacer commit cada 100 canciones
            if commit_counter >= batch_size:
                db.session.commit()
                commit_counter = 0
                print(f"  💾 Commit de {batch_size} canciones procesadas")
        except Exception as ex:
            errores += 1
            print(f"  Error procesando {archivo.name}: {ex}")

    # Commit final para cualquier canción restante
    if commit_counter > 0:
        db.session.commit()
        print(f"  💾 Commit final de {commit_counter} canciones restantes")

    resumen_norm = normalizar_biblioteca(
        progress_callback=progress_callback,
        percent_start=92,
        percent_end=96,
    )

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
        'normalizacion': resumen_norm,
    }
    emit_progress({
        'stage': 'done',
        'message': f'Escaneo rápido finalizado — {canciones_agregadas} nuevas, {canciones_eliminadas} eliminadas',
        'percent': 100,
        'processed': total,
        'total': total,
        'summary': resumen
    })
    
    # Encolar tareas post-escaneo en Redis (workers los procesan sin bloquear la app)
    try:
        from task_queue import enqueue
        from lyrics_fetcher import descargar_letras_segundo_plano
        from musicbrainz_client import enriquecer_artistas_sin_mbid
        
        print("\n🚀 Encolando tareas post-escaneo en Redis (letras + MusicBrainz)...")
        enqueue(descargar_letras_segundo_plano, batch_size=10)
        enqueue(enriquecer_artistas_sin_mbid, limite=200)
        print("✅ Tareas encoladas — workers las procesarán en segundo plano")
    except Exception as e:
        print(f"⚠️ No se pudieron encolar tareas: {e}")
        import threading
        th = threading.Thread(target=lambda: (
            descargar_letras_segundo_plano(batch_size=10),
            enriquecer_artistas_sin_mbid(limite=200)
        ), daemon=True)
        th.start()
    
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
        print(f"\nError durante el escaneo: {e}")
        import traceback
        traceback.print_exc()
