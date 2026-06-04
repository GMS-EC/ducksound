# -*- coding: utf-8 -*-
"""
Módulo de Escaneo e Indexación de Biblioteca de Audio (scan_songs.py)
====================================================================

Este script es el motor principal para el descubrimiento de música de DuckSound.
Se encarga de recorrer de manera recursiva (o incremental) las carpetas de música,
extraer metadatos usando TinyTag y Mutagen, resolver y fusionar nombres de artistas y
álbumes con heurísticas avanzadas y fuzzy matching, y registrar la estructura en la base de datos.
También dispara tareas secundarias en segundo plano (vía Redis o hilos) para buscar
letras (.lrc) y descargar portadas de discos de servicios externos.
"""

import os
import sys
import re
from pathlib import Path
import requests
import urllib.parse

# Configurar la codificación UTF-8 para la salida estándar en sistemas Windows.
# Esto evita errores de UnicodeEncodeError al imprimir nombres con caracteres especiales en la consola de Windows.
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Parser de metadatos robusto (Mutagen para etiquetas complejas, TinyTag para rapidez de lectura de duración)
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from tinytag import TinyTag

# Importaciones del ecosistema DuckSound
from config import Config
from app.models import db, Artista, Album, Cancion, Favorito, HistorialEscucha, daily_mix_canciones, playlist_canciones, coleccion_canciones
from app.services.metadata import (
    enrich_artist, 
    enrich_all, 
    normalizar_artista, 
    normalizar_album, 
    detectar_version, 
    limpiar_nombre, 
    obtener_album_base_fuzz
)

# Extensiones de archivos de audio soportadas formalmente por el sistema.
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}


def extraer_metadatos(ruta_archivo):
    """
    Extrae metadatos detallados de un archivo de audio específico en disco.
    
    Esta función emplea una estrategia híbrida sumamente optimizada:
    1. Utiliza `mutagen` para extraer etiquetas textuales complejas (título, artista, álbum,
       género, pista, disco), ya que es excelente manejando variaciones de codificación (UTF-8, UTF-16, latin1).
    2. Utiliza `TinyTag` como fallback para el texto y como primera opción para la duración
       en segundos, dado que lee las cabeceras de audio a bajo nivel de manera sumamente rápida.
    3. Implementa una heurística de recuperación ante metadatos corruptos (caracteres "????").
       Si el nombre del artista parece corrupto, intenta extraer el nombre basándose en el nombre de la carpeta padre.
    4. Ejecuta un analizador de audio avanzado opcional (para obtener Nyquist, rango dinámico, RMS, etc.).

    Args:
        ruta_archivo (str o Path): La ubicación absoluta o relativa del archivo de música.

    Returns:
        dict: Un diccionario con todos los metadatos parseados, normalizados y listos para BD.
        None: Si ocurre un error fatal o el archivo no es un archivo de audio legible.
    """
    from app.services.audio_analyzer import analyze_audio
    from pathlib import Path

    def es_corrupto(texto):
        """
        Determina si una cadena de texto de metadatos parece estar corrupta o codificada erróneamente.
        Por ejemplo, cuando caracteres no admitidos en el tag original se convirtieron en '?'
        durante guardados defectuosos en otros reproductores.
        """
        if not texto: return False
        # Si el texto contiene tres '?' consecutivos o si más del 50% de sus caracteres son '?', se considera corrupto.
        if '???' in texto or (len(texto) > 0 and texto.count('?') / len(texto) > 0.5):
            return True
        return False

    def recuperar_desde_ruta(ruta):
        """
        Heurística de Fallback: Extrae el nombre del artista de la estructura de directorios del disco.
        Normalmente la estructura es: /musica/Nombre_Artista/Nombre_Album/Cancion.mp3
        """
        partes = Path(ruta).parts
        if len(partes) >= 2:
            # Tomamos la carpeta de nivel -3 (Artista) o -2 (si la estructura no incluye subcarpeta de álbum)
            return partes[-3] if len(partes) >= 3 else partes[-2]
        return None

    try:
        # Intentamos instanciar el parser principal Mutagen
        try:
            audio_file = File(str(ruta_archivo))
        except Exception as mutagen_err:
            audio_file = None
        
        def _tag_val(*keys):
            """Función interna para extraer y limpiar un valor de etiqueta desde los diccionarios de Mutagen."""
            if audio_file is None or not hasattr(audio_file, 'tags') or audio_file.tags is None:
                return None
            # Crear un mapeo case-insensitive de las claves existentes
            tags_lower = {k.lower(): k for k in audio_file.tags.keys()}
            for k in keys:
                k_lower = k.lower()
                if k_lower in tags_lower:
                    real_key = tags_lower[k_lower]
                    v = audio_file.tags[real_key]
                    if v is not None:
                        # Si es una lista o tupla, nos quedamos con el primer elemento
                        if isinstance(v, (list, tuple)):
                            v = v[0] if v else None
                        return str(v).strip() if v is not None else None
            return None
        
        def _tiny_val(attr, *extra_keys):
            """Función interna para obtener valores desde TinyTag o sus campos extra en caso de fallback."""
            if tag is None:
                return None
            val = getattr(tag, attr, None)
            if not val:
                extra = getattr(tag, 'extra', None) or {}
                for k in extra_keys:
                    v = extra.get(k)
                    if isinstance(v, (list, tuple)):
                        v = v[0] if v else None
                    if v:
                        val = v
                        break
            return val

        # 1. Intentar extracción inicial con Mutagen (ID3 estándar)
        titulo = _tag_val('TIT2', 'title') or Path(ruta_archivo).stem
        artista = _tag_val('TPE1', 'artist')
        album = _tag_val('TALB', 'album')
        genero = _tag_val('TCON', 'genre')
        track_str = _tag_val('TRCK', 'tracknumber', 'track')
        disc_str = _tag_val('TPOS', 'discnumber', 'disc')
        
        # --- APLICACIÓN DE LA HEURÍSTICA DE RECUPERACIÓN ---
        # Si el artista extraído por Mutagen viene corrupto (????), intentamos rescatarlo desde la ruta física.
        if es_corrupto(artista):
            recuperado = recuperar_desde_ruta(ruta_archivo)
            if recuperado:
                artista = recuperado
        
        # Fallback a TinyTag: Si Mutagen no devolvió nada utilizable, cargamos la cabecera mediante TinyTag
        if not artista or es_corrupto(artista) or not titulo:
            try:
                tag = TinyTag.get(str(ruta_archivo), image=False)
            except Exception:
                tag = None
            
            if tag is not None:
                if not titulo:
                    titulo = _tiny_val('title', 'TITLE') or Path(ruta_archivo).stem
                if not artista or es_corrupto(artista):
                    artista = _tiny_val('artist', 'ARTIST')
                    # Si TinyTag tampoco lo resuelve, intentamos recuperar el nombre desde el disco
                    if not artista or es_corrupto(artista):
                        artista = recuperar_desde_ruta(ruta_archivo)
                if not album:
                    album = _tiny_val('album', 'ALBUM')
                if not genero:
                    genero = _tiny_val('genre', 'GENRE')
                if not track_str:
                    t = _tiny_val('track', 'tracknumber', 'TRCK', 'TRACKNUMBER')
                    track_str = str(t) if t else None
                if not disc_str:
                    d = _tiny_val('disc', 'discnumber', 'DISCNUMBER', 'TPA')
                    disc_str = str(d) if d else None
            else:
                # Fallback de último recurso: deducir de la ruta física
                if not artista or es_corrupto(artista):
                    artista = recuperar_desde_ruta(ruta_archivo)
        
        def parse_track_num(val):
            """Parsea el número de pista/disco. Soporta formatos como '3/12' (pista 3 de 12)."""
            if not val: return None
            try: return int(str(val).split('/')[0])
            except: return None
        
        # Obtener el artista del álbum (TPE2/Album Artist), clave para evitar duplicados en discos compilatorios
        albumartist = _tag_val('TPE2', 'albumartist', 'album artist', 'album_artist', 'ALBUMARTIST', 'ALBUM ARTIST') or artista
        if es_corrupto(albumartist):
            albumartist = recuperar_desde_ruta(ruta_archivo) or artista
        # Si el título contiene un guion y el artista está definido, limpiamos el nombre del artista en el título
        if titulo and artista and ' - ' in titulo:
            partes_titulo = [p.strip() for p in titulo.split(' - ')]
            # Caso 1: "Intro - Psychonaut 4"
            if partes_titulo[-1].lower() == artista.lower() or normalizar_artista(partes_titulo[-1]) == normalizar_artista(artista):
                titulo = ' - '.join(partes_titulo[:-1])
            # Caso 2: "Psychonaut 4 - Intro"
            elif partes_titulo[0].lower() == artista.lower() or normalizar_artista(partes_titulo[0]) == normalizar_artista(artista):
                titulo = ' - '.join(partes_titulo[1:])
 
        # Construimos el diccionario de metadatos procesados
        metadatos = {
            'titulo': titulo,
            'artista': artista,
            'albumartist': albumartist,
            'artista_display': artista, # Nombre original completo tal como viene
            'artista_principal': normalizar_artista(albumartist), # Artista principal para agrupación única
            'album': album,
            'duracion': None,
            'ruta_imagen': None,
            'genero': genero,
            'numero_pista': parse_track_num(track_str),
            'numero_disco': parse_track_num(disc_str),
        }
        
        # Extraer la duración precisa de TinyTag (si está disponible)
        try:
            tiny = TinyTag.get(str(ruta_archivo), image=False)
            if tiny and tiny.duration:
                metadatos['duracion'] = int(tiny.duration)
        except:
            pass
        
        # Ejecutar análisis electroacústico de audio si el analizador está disponible (calcula RMS, rango dinámico, etc.)
        try:
            analisis = analyze_audio(ruta_archivo)
            if analisis:
                metadatos['analisis'] = analisis
        except:
            pass
            
        return metadatos
    except Exception as e:
        import logging
        logging.error(f"Error extrayendo metadatos de {ruta_archivo}: {e}")
        return None


def extraer_metadatos_paralelo(archivos, progress_callback=None, stage='processing', percent_start=0, percent_end=100):
    """
    Extrae metadatos para una lista de archivos utilizando un ThreadPoolExecutor en paralelo.
    Esta función es puramente de lectura de disco y procesamiento matemático, por lo que es
    completamente segura y libre de condiciones de carrera con la base de datos SQL.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os
    
    total = len(archivos)
    if total == 0:
        return {}
        
    resultados = {}
    # Limitar el número de hilos trabajadores para evitar sobrecargar la CPU del host
    max_workers = min(6, os.cpu_count() or 4)
    
    def emit_progress(payload):
        if not progress_callback:
            return
        try:
            progress_callback(payload)
        except Exception:
            pass
            
    print(f"🚀 Iniciando extracción de metadatos en paralelo con {max_workers} trabajadores para {total} archivos...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Encolar la extracción de metadatos para cada archivo
        futures = {executor.submit(extraer_metadatos, archivo): archivo for archivo in archivos}
        
        for idx, future in enumerate(as_completed(futures), start=1):
            archivo = futures[future]
            try:
                meta = future.result()
                if meta:
                    resultados[str(archivo)] = meta
            except Exception as e:
                import logging
                logging.error(f"⚠️ Error extrayendo metadatos en hilo para {archivo.name}: {e}")
                
            percent = int(percent_start + ((idx / total) * (percent_end - percent_start)))
            emit_progress({
                'stage': stage,
                'message': f'Analizando audio ({idx}/{total}): {archivo.name}',
                'current_file': archivo.name,
                'processed': idx,
                'total': total,
                'percent': percent
            })
            
    return resultados


def obtener_o_crear_artista(nombre, enriquecer=False, mbid=None):
    """
    Busca un artista en la base de datos o lo crea si no existe.
    
    Implementa una cascada de resolución de identidad muy robusta de 5 niveles para evitar duplicados:
    1. Búsqueda directa por MusicBrainz ID (MBID) si se proporciona.
    2. Búsqueda exacta case-insensitive y normalizada del nombre.
    3. Consulta externa a la API de MusicBrainz para unificar nombres usando el estándar mundial.
    4. Emparejamiento difuso ("Fuzzy matching" >= 80%) contra artistas existentes sin MBID.
    5. Creación del artista en BD, aplicando romanización (Unidecode) para nombres no latinos
       si no hay datos en MusicBrainz.

    Args:
        nombre (str): Nombre del artista extraído de los tags del archivo.
        enriquecer (bool, opcional): Indica si se debe forzar el enriquecimiento de metadatos (por defecto False).
        mbid (str, opcional): MusicBrainz ID del artista si ya se conoce.

    Returns:
        Artista: El objeto de modelo Artista encontrado o creado.
    """
    if not nombre:
        return None
    
    # --- LIMPIEZA DE ARRAYS EN CADENA ---
    # Algunos reproductores guardan etiquetas múltiples en formatos tipo "['Artista']".
    # Esta sub-heurística limpia corchetes y comillas sobrantes para extraer la cadena real.
    if isinstance(nombre, (list, tuple)):
        nombre = nombre[0] if nombre else "Unknown Artist"
    elif isinstance(nombre, str) and nombre.startswith('[') and nombre.endswith(']'):
        cleaned = nombre[1:-1].strip()
        if (cleaned.startswith("'") and cleaned.endswith("'")) or (cleaned.startswith('"') and cleaned.endswith('"')):
            cleaned = cleaned[1:-1]
        nombre = cleaned
    
    from app.services.metadata import normalizar_artista
    nombre_norm = normalizar_artista(nombre) or nombre
    
    from app.models import db, Artista
    from sqlalchemy import func
    from rapidfuzz import fuzz
    UMBRAL_FUZZY = 80
    
    # --- NIVEL 1: BÚSQUEDA POR MUSICBRAINZ ID ---
    if mbid:
        artista_obj = Artista.query.filter_by(musicbrainz_id=mbid).first()
        if artista_obj:
            return artista_obj
    
    # --- NIVEL 2: BÚSQUEDA EXACTA NORMALIZADA EN BD ---
    # Se eliminan espacios en blanco laterales y se compara en minúsculas en SQL.
    artista_obj = Artista.query.filter(
        func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()
    ).first()
    if artista_obj:
        return artista_obj
    
    # --- NIVEL 3: BÚSQUEDA EN LA API DE MUSICBRAINZ ---
    # Si no está en BD, intentamos consultar a la API de MusicBrainz para ver si hay un nombre canónico/sort_name.
    from app.services.metadata import buscar_artista
    mb_result = buscar_artista(nombre)
    if mb_result:
        mb_nombre_raw = mb_result['nombre']
        mb_sort = mb_result['sort_name']
        # El nombre normalizado prefiere el sort_name (ej: "Matsubara, Miki" en lugar de caracteres japoneses si aplica)
        mb_nombre_norm = normalizar_artista(mb_sort if mb_sort and mb_sort != mb_nombre_raw else mb_nombre_raw)
        
        # Buscar nuevamente en base de datos usando el MBID retornado por la API
        artista_obj = Artista.query.filter_by(musicbrainz_id=mb_result['mbid']).first()
        if artista_obj:
            return artista_obj
        
        # Buscar por el nombre normalizado obtenido de MusicBrainz
        if mb_nombre_norm:
            artista_obj = Artista.query.filter(
                func.lower(func.trim(Artista.nombre_normalizado)) == mb_nombre_norm.lower().strip()
            ).first()
            if artista_obj:
                return artista_obj
        
        mb_result['nombre_norm'] = mb_nombre_norm
    
    # --- NIVEL 4: FUZZY MATCHING (EMPAREJAMIENTO DIFUSO) ---
    # Si no tiene MBID en la BD local, comparamos similitud léxica mediante token_set_ratio.
    # Esto une automáticamente variaciones de tipeo o puntuación menores.
    mejor_ratio = 0
    mejor_artista = None
    for a in Artista.query.filter(Artista.musicbrainz_id.is_(None)).all():
        ratio = fuzz.token_set_ratio(nombre_norm.lower(), a.nombre.lower())
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_artista = a
    if mejor_ratio >= UMBRAL_FUZZY and mejor_artista:
        return mejor_artista
    
    # --- NIVEL 5: CREACIÓN DE NUEVO REGISTRO ---
    mb_norm_name = mb_result.get('nombre_norm') if mb_result else None
    if mb_norm_name:
        final_norm = mb_norm_name
    else:
        from app.services.metadata import _es_latino
        # Romanizar caracteres no latinos (ej: cirílico, kanji) a texto latino legible con unidecode
        if not _es_latino(nombre_norm):
            from unidecode import unidecode
            final_norm = normalizar_artista(unidecode(nombre_norm))
        else:
            final_norm = nombre_norm
    
    try:
        artista_obj = Artista(
            nombre=nombre,
            nombre_normalizado=final_norm,
            musicbrainz_id=mb_result['mbid'] if mb_result else None
        )
        db.session.add(artista_obj)
        db.session.flush()
        return artista_obj
    except Exception:
        db.session.rollback()
        # Fallback de último recurso si falló el insert por colisión concurrente (Unique constraint)
        return Artista.query.filter(
            func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()
        ).first()

    # =========================================================================
    # NOTA DE INTEGRIDAD DE CÓDIGO (DEAD CODE / DUPLICADOS INALCANZABLES):
    # Los bloques de código que figuran a continuación son remanentes duplicados
    # de fusiones de commits anteriores en el repositorio del usuario. 
    # Dado que el bloque try-except anterior garantiza un retorno del flujo
    # (retorna el objeto creado o el consultado en el except), el siguiente código
    # es técnicamente inaccesible. Se conserva 100% idéntico para evitar 
    # cualquier alteración funcional o lógica del script original.
    # =========================================================================
    if artista_obj:
        return artista_obj
    
    # 3. Buscar en MusicBrainz API
    from app.services.metadata import buscar_artista
    mb_result = buscar_artista(nombre_norm_busqueda)
    if mb_result:
        mb_nombre_raw = mb_result['nombre']
        mb_sort = mb_result['sort_name']
        mb_nombre_norm = normalizar_artista(mb_sort if mb_sort and mb_sort != mb_nombre_raw else mb_nombre_raw)
        
        artista_obj = Artista.query.filter_by(musicbrainz_id=mb_result['mbid']).first()
        if artista_obj:
            return artista_obj
        
        if mb_nombre_norm:
            artista_obj = Artista.query.filter(
                func.lower(func.trim(Artista.nombre_normalizado)) == mb_nombre_norm.lower().strip()
            ).first()
            if artista_obj:
                return artista_obj
        
        mb_result['nombre_norm'] = mb_nombre_norm
    
    mejor_ratio = 0
    mejor_artista = None
    for a in Artista.query.filter(Artista.musicbrainz_id.is_(None)).all():
        ratio = fuzz.token_set_ratio(nombre_norm.lower(), a.nombre.lower())
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_artista = a
    if mejor_ratio >= UMBRAL_FUZZY and mejor_artista:
        return mejor_artista
    
    mb_norm_name = mb_result.get('nombre_norm') if mb_result else None
    if mb_norm_name:
        final_norm = mb_norm_name
    else:
        from app.services.metadata import _es_latino
        if not _es_latino(nombre_norm):
            from unidecode import unidecode
            final_norm = normalizar_artista(unidecode(nombre_norm))
        else:
            final_norm = nombre_norm
    
    try:
        artista_obj = Artista(
            nombre=nombre,
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

    artista_obj = Artista.query.filter(
        func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()
    ).first()
    if artista_obj:
        return artista_obj

    from app.services.metadata import buscar_artista
    mb_result = buscar_artista(nombre_norm)
    if mb_result:
        mb_nombre_raw = mb_result['nombre']
        mb_sort = mb_result['sort_name']
        mb_nombre_norm = normalizar_artista(mb_sort if mb_sort and mb_sort != mb_nombre_raw else mb_nombre_raw)
        
        artista_obj = Artista.query.filter_by(musicbrainz_id=mb_result['mbid']).first()
        if artista_obj:
            return artista_obj
        
        if mb_nombre_norm:
            artista_obj = Artista.query.filter(
                func.lower(func.trim(Artista.nombre_normalizado)) == mb_nombre_norm.lower().strip()
            ).first()
            if artista_obj:
                return artista_obj
        
        mb_result['nombre_norm'] = mb_nombre_norm

    mejor_ratio = 0
    mejor_artista = None
    for a in Artista.query.filter(Artista.musicbrainz_id.is_(None)).all():
        ratio = fuzz.token_set_ratio(nombre_norm.lower(), a.nombre.lower())
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor_artista = a
    if mejor_ratio >= UMBRAL_FUZZY and mejor_artista:
        return mejor_artista

    mb_norm_name = mb_result.get('nombre_norm') if mb_result else None
    if mb_norm_name:
        final_norm = mb_norm_name
    else:
        from app.services.metadata import _es_latino
        if not _es_latino(nombre_norm):
            from unidecode import unidecode
            final_norm = normalizar_artista(unidecode(nombre_norm))
        else:
            final_norm = nombre_norm

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
    """
    Busca un álbum específico en la base de datos o lo crea si no existe.

    Implementa una estrategia de resolución robusta en 4 etapas:
    1. Búsqueda directa por MusicBrainz ID (MBID) si se proporciona.
    2. Búsqueda por título normalizado del álbum y ID del artista principal.
       Utiliza `detectar_version` para separar remasters, versiones en vivo o aniversario
       (ej. "Discovery (2014 Remaster)" -> "Discovery"), normaliza el título y utiliza
       un match difuso contra los álbumes existentes del artista.
    3. Consulta a la API externa de MusicBrainz usando el MBID del artista para obtener
       los datos de lanzamiento oficiales y canonicalizar el álbum.
    4. Creación del álbum en la base de datos si no fue encontrado.

    Args:
        album (str): Nombre del álbum extraído de los tags del archivo.
        albumartist (str): Nombre del artista del álbum.
        mbid (str, opcional): MusicBrainz ID del álbum si ya se conoce.

    Returns:
        Album: El objeto del modelo Album encontrado o creado, o None si faltan datos esenciales.
    """
    if not album or not albumartist:
        return None

    # Primero resolvemos u obtenemos el Artista del Álbum para asociarlo correctamente.
    album_artista_obj = obtener_o_crear_artista(albumartist)
    if not album_artista_obj:
        return None

    # --- ETAPA 1: BÚSQUEDA DIRECTA POR MBID ---
    if mbid:
        album_obj = Album.query.filter_by(musicbrainz_id=mbid).first()
        if album_obj:
            return album_obj

    # --- ETAPA 2: NORMALIZACIÓN Y BÚSQUEDA DIFUSA LOCAL ---
    # Detectamos y separamos sufijos como "(Remastered)", "(Live)", "(Deluxe Edition)"
    album_base, _ = detectar_version(album)
    # Normalizamos el título base para evitar diferencias de mayúsculas/minúsculas y caracteres raros
    album_final = normalizar_album(album_base or album)
    if not album_final:
        return None

    # Obtenemos todos los álbumes del artista en la BD y buscamos coincidencia difusa (fuzzy)
    albumes_artista = Album.query.filter_by(artista_id=album_artista_obj.id).all()
    album_obj = obtener_album_base_fuzz(album_final, albumes_artista)
    if album_obj:
        return album_obj

    # --- ETAPA 3: BÚSQUEDA EXTERNA EN MUSICBRAINZ ---
    if album_artista_obj.musicbrainz_id:
        from app.services.metadata import buscar_album
        mb_album = buscar_album(album, album_artista_obj.musicbrainz_id)
        if mb_album and not mbid:
            # Buscar si el álbum de MusicBrainz ya existe en la base de datos local
            album_obj = Album.query.filter_by(musicbrainz_id=mb_album['mbid']).first()
            if album_obj:
                return album_obj
            mbid = mb_album['mbid']

    # --- ETAPA 4: CREACIÓN DE NUEVO ÁLBUM ---
    album_obj = Album(titulo=album_final, artista_id=album_artista_obj.id, musicbrainz_id=mbid)
    try:
        db.session.add(album_obj)
        db.session.flush()
        return album_obj
    except Exception:
        db.session.rollback()
        # Fallback de último recurso: si hubo error por concurrencia al insertar, buscamos el álbum de nuevo
        albumes_artista = Album.query.filter_by(artista_id=album_artista_obj.id).all()
        album_obj = obtener_album_base_fuzz(album_final, albumes_artista)
        return album_obj

    # =========================================================================
    # NOTA DE INTEGRIDAD DE CÓDIGO (DEAD CODE / DUPLICADOS INALCANZABLES):
    # El bloque try-except anterior garantiza retornar siempre el álbum.
    # Por lo tanto, el siguiente bloque es inalcanzable, pero se mantiene intacto 
    # de acuerdo con la política de cero modificaciones lógicas del código original.
    # =========================================================================
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
    """
    Realiza una depuración y limpieza en cascada en la base de datos.
    Elimina registros de Álbumes que ya no tienen canciones asociadas,
    y luego elimina registros de Artistas que no posean álbumes ni canciones.
    
    Returns:
        tuple: (albumes_eliminados, artistas_eliminados) con el conteo de registros purgados.
    """
    albumes_eliminados = 0
    artistas_eliminados = 0

    # 1. Depurar álbumes huérfanos
    for album in Album.query.all():
        if not album.canciones:
            db.session.delete(album)
            albumes_eliminados += 1

    # Sincronizamos cambios parciales en la sesión para reflejar la posible desasociación de álbumes en artistas.
    db.session.flush()

    # 2. Depurar artistas huérfanos (que no tengan ni canciones sueltas ni álbumes registrados)
    for artista in Artista.query.all():
        if not artista.canciones and not artista.albums:
            db.session.delete(artista)
            artistas_eliminados += 1

    return albumes_eliminados, artistas_eliminados


def normalizar_biblioteca(progress_callback=None, percent_start=90, percent_end=99):
    """
    Unifica artistas y álbumes duplicados de forma recursiva aplicando las reglas canónicas de DuckSound.
    
    Esta función es sumamente importante para mantener la salud de la biblioteca:
    1. Recorre todos los artistas de la base de datos, normaliza su nombre léxicamente.
    2. Si el nombre normalizado coincide con otro artista ya existente de menor ID,
       transfiere todas las canciones y álbumes al artista canónico y elimina el registro redundante (fusión).
    3. Si el nombre normalizado difiere del nombre actual pero no colisiona, actualiza el nombre visible (renombrado).
    4. Repite un proceso similar para los álbumes pertenecientes a cada artista, fusionando álbumes
       que tengan el mismo título normalizado o que coincidan difusamente (remasters, ediciones especiales).
    5. Dispara una purga final de entidades vacías tras las fusiones y consolida los cambios con un commit.

    Args:
        progress_callback (callable, opcional): Callback de progreso para reportar el porcentaje en tiempo real.
        percent_start (int): Porcentaje inicial del proceso en el pipeline de escaneo global.
        percent_end (int): Porcentaje final estimado.

    Returns:
        dict: Un diccionario resumen con las estadísticas detalladas del proceso de unificación.
    """
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

    # --- FASE A: NORMALIZACIÓN Y FUSIÓN DE ARTISTAS ---
    from sqlalchemy import func
    eliminados = set()
    for idx, artista in enumerate(artistas, start=1):
        if artista.id in eliminados:
            continue

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

        # Buscar si ya existe otro artista registrado con ese mismo nombre normalizado.
        # Hacemos comparación case-insensitive y eliminando espacios laterales sobre nombre y nombre_normalizado
        artista_existente = Artista.query.filter(
            (func.lower(func.trim(Artista.nombre_normalizado)) == nombre_norm.lower().strip()) |
            (func.lower(func.trim(Artista.nombre)) == nombre_norm.lower().strip()),
            Artista.id != artista.id
        ).order_by(Artista.id).first()

        if artista_existente:
            # Determinar cuál es el artista canónico (destino) y cuál se fusionará (origen).
            # Priorizamos al que tenga MusicBrainz ID, luego al que tenga más metadatos (foto/biografía), 
            # y finalmente al ID más bajo.
            def obtener_puntaje(a):
                p = 0
                if a.musicbrainz_id:
                    p += 1000
                if a.foto_url:
                    p += 100
                if a.biografia:
                    p += 10
                p -= a.id * 0.0001
                return p
                
            p_existente = obtener_puntaje(artista_existente)
            p_actual = obtener_puntaje(artista)
            
            if p_existente >= p_actual:
                destino = artista_existente
                origen = artista
            else:
                destino = artista
                origen = artista_existente
            
            # Reasignar todas las relaciones en la base de datos
            from app.services.metadata import actualizar_tags_disco
            for cancion in list(origen.canciones):
                cancion.artista_id = destino.id
                if cancion.ruta_archivo_audio:
                    try:
                        actualizar_tags_disco(cancion.ruta_archivo_audio, artista=destino.nombre)
                    except Exception as e:
                        print(f"⚠️ Error actualizando tag de artista en fusión: {e}")
            for album in list(origen.albums):
                album.artista_id = destino.id
                
            # Conservar metadatos valiosos del origen si el destino carecía de ellos
            if not destino.musicbrainz_id and origen.musicbrainz_id:
                destino.musicbrainz_id = origen.musicbrainz_id
            if not destino.foto_url and origen.foto_url:
                destino.foto_url = origen.foto_url
            if not destino.biografia and origen.biografia:
                destino.biografia = origen.biografia
            
            db.session.delete(origen)
            eliminados.add(origen.id)
            resumen['artistas_fusionados'] += 1
        elif nombre_norm != artista.nombre:
            from app.services.metadata import actualizar_tags_disco
            for cancion in artista.canciones:
                if cancion.ruta_archivo_audio:
                    try:
                        actualizar_tags_disco(cancion.ruta_archivo_audio, artista=nombre_norm)
                    except Exception as e:
                        print(f"⚠️ Error actualizando tag de artista en renombrado: {e}")
            artista.nombre = nombre_norm
            resumen['artistas_renombrados'] += 1

    db.session.flush()

    # --- FASE B: NORMALIZACIÓN Y FUSIÓN DE ÁLBUMES POR ARTISTA ---
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

            # Renombrar si difiere del título físico
            if titulo_norm and titulo_norm != album.titulo:
                from app.services.metadata import actualizar_tags_disco
                for cancion in album.canciones:
                    if cancion.ruta_archivo_audio:
                        try:
                            actualizar_tags_disco(cancion.ruta_archivo_audio, album=titulo_norm)
                        except Exception as e:
                            print(f"⚠️ Error actualizando tag de álbum en renombrado: {e}")
                album.titulo = titulo_norm
                resumen['albumes_renombrados'] += 1

            # Buscar si el álbum normalizado coincide con otro del mismo artista
            album_existente = obtener_album_base_fuzz(titulo_norm or album.titulo, albumes_base)
            if album_existente and album_existente.id != album.id:
                # Traspasar canciones al álbum destino/canónico
                from app.services.metadata import actualizar_tags_disco
                for cancion in list(album.canciones):
                    cancion.album_id = album_existente.id
                    if cancion.ruta_archivo_audio:
                        try:
                            actualizar_tags_disco(cancion.ruta_archivo_audio, album=album_existente.titulo)
                        except Exception as e:
                            print(f"⚠️ Error actualizando tag de álbum en fusión: {e}")
                # Traspasar metadatos ricos (portada y año) si el destino no los tenía
                if not album_existente.portada_url and album.portada_url:
                    album_existente.portada_url = album.portada_url
                if not album_existente.anio and album.anio:
                    album_existente.anio = album.anio
                
                db.session.delete(album)
                resumen['albumes_fusionados'] += 1
            else:
                albumes_base.append(album)

    # --- FASE C: PURGAR REGISTROS VACÍOS Y HACER COMMIT ---
    eliminados = limpiar_entidades_vacias()
    resumen['albumes_eliminados'], resumen['artistas_eliminados'] = eliminados
    db.session.commit()

    emit({'stage': 'normalizing', 'message': 'Normalizacion de metadatos finalizada', 'percent': percent_end})
    return resumen


def guardar_imagen_album(picture, ruta_audio, album_artist=None, album_name=None):
    """
    Guarda la imagen de la carátula integrada en un archivo de música en el directorio del servidor.
    
    Genera un hash MD5 único basado en el nombre del artista, del álbum y el archivo
    para evitar colisiones de nombre, y guarda los datos binarios como JPG o PNG.

    Args:
        picture (mutagen.id3.APIC / tinytag): El objeto contenedor de imagen con bytes y tipo mime.
        ruta_audio (str): Ruta del archivo original (usado como semilla del hash).
        album_artist (str, opcional): Nombre del artista para singularizar el hash.
        album_name (str, opcional): Nombre del álbum.

    Returns:
        str: Ruta relativa en disco de la imagen guardada.
        None: Si la operación falla.
    """
    try:
        import hashlib
        carpeta_album_art = Config.ALBUM_ART_FOLDER
        carpeta_album_art.mkdir(exist_ok=True)
        
        # Generar un identificador único en formato hash
        nombre_base = Path(ruta_audio).stem
        unique = f"{album_artist or ''}/{album_name or ''}/{nombre_base}"
        hash_str = hashlib.md5(unique.encode('utf-8')).hexdigest()[:12]
        extension = '.jpg' if picture.mime == 'image/jpeg' else '.png'
        ruta_imagen = carpeta_album_art / f"{hash_str}{extension}"
        
        # Escribir los bytes del búfer al archivo en disco
        with open(ruta_imagen, 'wb') as f:
            f.write(picture.data)
        
        return str(ruta_imagen)
    except Exception as e:
        print(f"  ⚠ Error al guardar imagen del álbum: {e}")
        return None


def descargar_y_guardar_portada(url, ruta_audio, album_artist=None, album_name=None):
    """
    Descarga una imagen de portada desde una URL externa HTTP y la guarda localmente.

    Args:
        url (str): Enlace de descarga directa de la imagen de arte.
        ruta_audio (str): Ruta del archivo de audio para calcular el hash de guardado.
        album_artist (str, opcional): Nombre del artista del álbum.
        album_name (str, opcional): Nombre del álbum.

    Returns:
        str: Ruta local en disco de la carátula descargada.
        None: Si la red falla o la URL no es válida.
    """
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            # Emulamos un objeto picture compatible con guardar_imagen_album
            class FakePicture:
                def __init__(self, data, mime):
                    self.data = data
                    self.mime = mime
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            picture = FakePicture(resp.content, content_type)
            return guardar_imagen_album(picture, ruta_audio, album_artist, album_name)
    except Exception:
        pass
    return None


def fetch_cover_from_itunes(artist, album, song_title):
    """
    Busca portadas en alta resolución (600x600) consultando la iTunes Search API pública.

    Args:
        artist (str): Artista de búsqueda.
        album (str): Álbum de búsqueda.
        song_title (str): Título de la canción en caso de no tener álbum.

    Returns:
        str: URL HTTP de la imagen en alta resolución si es encontrada.
        None: Si la búsqueda externa no da resultados o falla la conexión.
    """
    import urllib.parse
    # Construimos la query combinando artista + álbum, o artista + título si el álbum no existe
    query = f"{artist} {album}" if album else f"{artist} {song_title}"
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&media=music&entity=album&limit=1"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('resultCount', 0) > 0:
                artwork_url = data['results'][0].get('artworkUrl100')
                if artwork_url:
                    # iTunes por defecto retorna miniatura 100x100bb.
                    # La reemplazamos por '600x600bb' para obtener excelente calidad en el reproductor.
                    return artwork_url.replace('100x100bb', '600x600bb')
    except Exception:
        pass
    return None


def limpiar_nombre_archivo(nombre_archivo):
    """
    Limpia el nombre físico de un archivo de audio para inferir artista y título.
    Útil como fallback de último recurso cuando el archivo carece de cualquier etiqueta de metadatos.
    
    Espera patrones comunes como:
      "Miki Matsubara - Stay With Me.mp3" -> Título: "Stay With Me", Artista: "Miki Matsubara"
      "Stay With Me.mp3"                  -> Título: "Stay With Me", Artista: None

    Args:
        nombre_archivo (str): Nombre del archivo (incluyendo extensión).

    Returns:
        tuple: (titulo_inferido, artista_inferido)
    """
    # Removemos la extensión del archivo
    nombre_sin_ext = Path(nombre_archivo).stem
    # Match con separador estándar guion rodeado de espacios
    match = re.match(r'^(.+?)\s*-\s*(.+)$', nombre_sin_ext, re.IGNORECASE)
    if match:
        return match.group(2).strip(), match.group(1).strip()  # (titulo, artista)
    
    # Si no tiene separador, asumimos que todo el nombre del archivo es el título
    return nombre_sin_ext.strip(), None


def inferir_metadatos_desde_ruta(ruta_archivo, carpeta_base_audio):
    """
    Infiere el artista y el álbum examinando la jerarquía de subdirectorios.
    Esto compensa la carencia absoluta de tags internos de metadatos en bibliotecas estructuradas.
    
    Ejemplos de mapeo:
      Artist/song.mp3              → artista='Artist', album=None
      Artist/Album/song.mp3        → artista='Artist', album='Album'
      Genre/Artist/Album/song.mp3  → artista='Artist', album='Album'
      Artist/CD 1/song.mp3         → artista='Artist', album=None (ignora subcarpeta CD)

    Args:
        ruta_archivo (str o Path): Ubicación física del archivo de música.
        carpeta_base_audio (str o Path): Carpeta raíz de música configurada en la aplicación.

    Returns:
        tuple: (artista_inferido, album_inferido) con valores inferidos o None.
    """
    import re
    try:
        # Calculamos la ruta relativa respecto a la carpeta raíz para analizar solo los directorios de interés
        rel_path = Path(ruta_archivo).resolve().relative_to(Path(carpeta_base_audio).resolve())
        parts = list(rel_path.parts)
        if len(parts) < 2:
            return None, None
        
        # Filtramos el nombre del archivo
        dirs = parts[:-1]
        
        # Omitimos carpetas del tipo "CD 1", "CD 2", "Disc 1" que distorsionan la jerarquía lógica
        filtered_dirs = []
        for dir_name in dirs:
            if re.match(r'^(CD|Disc)\s*\d+$', dir_name, re.IGNORECASE):
                continue
            filtered_dirs.append(dir_name)
        
        if len(filtered_dirs) == 1:
            dir_name = filtered_dirs[0]
            if ' - ' in dir_name:
                partes_dir = dir_name.split(' - ', 1)
                return partes_dir[0].strip(), partes_dir[1].strip()
            # Estructura: Artista/Cancion.mp3
            return dir_name, None
        elif len(filtered_dirs) >= 2:
            # Estructura: .../Artista/Album/Cancion.mp3
            return filtered_dirs[-2], filtered_dirs[-1]
    except Exception:
        pass
    return None, None


def buscar_archivo_lrc(ruta_audio, carpeta_lyrics, cancion_id=None):
    """
    Busca un archivo de letra temporizada (.lrc) que corresponda a un tema musical específico.
    
    Aplica 4 estrategias en cascada para encontrar archivos .lrc locales:
    1. Busca en la misma carpeta física donde está el archivo de audio con idéntico nombre base.
    2. Busca en la carpeta global de letras (`Config.LYRICS_FOLDER`) con el mismo nombre base.
    3. Busca en la carpeta global de letras buscando archivos prefijados con el ID de base de datos de la canción.
    4. Realiza una búsqueda flexible case-insensitive para salvar diferencias de mayúsculas/minúsculas.

    Args:
        ruta_audio (str o Path): Ruta de audio original.
        carpeta_lyrics (Path): Ruta del directorio global de lyrics.
        cancion_id (int, opcional): ID interno de la base de datos de la canción para búsqueda exacta por ID.

    Returns:
        str: Ruta absoluta en disco del archivo .lrc si se localiza.
        None: Si no existe letra local para esta canción.
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
    
    # Estrategia 3: Buscar por ID de canción en BD si está disponible
    if cancion_id:
        # Busca patrones tipo "123_*.lrc"
        for lrc_file in Config.LYRICS_FOLDER.glob(f"{cancion_id}_*.lrc"):
            if lrc_file.exists():
                return str(lrc_file)
    
    # Estrategia 4: Búsqueda flexible (case-insensitive)
    for lrc_file in Config.LYRICS_FOLDER.glob("*.lrc"):
        if lrc_file.stem.lower() == nombre_base.lower():
            return str(lrc_file)
    
    return None


def invalidar_cache_redis():
    """
    Busca todas las claves en Redis que coincidan con 'ducksound:cache:*' y las elimina
    para invalidar la caché de consultas AJAX (búsquedas, recomendaciones) tras un escaneo exitoso.
    """
    try:
        from app.services.queue import get_connection
        r = get_connection()
        claves = r.keys('ducksound:cache:*')
        if claves:
            r.delete(*claves)
            print(f"🧹 [Cache Redis] Se eliminaron {len(claves)} claves de caché de consultas AJAX.")
        else:
            print("🧹 [Cache Redis] No hay claves de caché de consultas AJAX para invalidar.")
    except Exception as e:
        print(f"⚠️ [Cache Redis] Error al invalidar la caché de Redis: {e}")


def escanear_carpeta_audio(progress_callback=None):
    """
    Realiza un escaneo completo y profundo de la carpeta de audio configurada.
    
    Este pipeline realiza las siguientes fases críticas:
    1. Fase de Purgado de Huérfanos: Busca y elimina de la base de datos todas las canciones
       cuyos archivos físicos ya no existan en el disco. Limpia también artistas y álbumes vacíos.
    2. Fase de Descubrimiento de Archivos: Recorre de forma recursiva todas las subcarpetas del
       directorio de música para listar archivos de audio legibles.
    3. Fase de Indexación Batch: Procesa cada archivo detectado:
       - Si ya existe en la BD por ruta exacta, actualiza sus letras locales (.lrc) y la omite.
       - Si se movió o renombró el directorio, detecta el cambio por nombre de archivo stem y corrige la ruta en BD.
       - Extrae metadatos (mutagen/tinytag/heurísticas).
       - Crea relaciones únicas normalizadas de Artistas y Álbumes.
       - Genera el registro de Cancion con estadísticas electroacústicas ricas (RMS, DR, Nyquist, etc.).
       - Realiza commits transaccionales por bloques (batch de 50 temas) para máxima velocidad de inserción.
    4. Fase de Normalización Global: Ejecuta unificación masiva de artistas y álbumes duplicados.
    5. Fase de Enriquecimiento Externo: Consulta APIs externas para rescatar portadas, biografías y años faltantes.
    6. Fase de Encolamiento Asíncrono: Envía tareas a la cola de Redis (letras y MBIDs faltantes).

    Args:
        progress_callback (callable, opcional): Función callback para notificar el estado del progreso en tiempo real al frontend.

    Returns:
        dict: Un diccionario resumen con estadísticas precisas del escaneo (canciones añadidas, omitidas, etc.).
    """
    def emit_progress(payload):
        """Envía el estado de progreso al callback del frontend de manera segura."""
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
    
    # Validar que la carpeta de música exista físicamente
    if not carpeta_audio.exists():
        print(f"La carpeta de audio no existe: {carpeta_audio}")
        emit_progress({'stage': 'error', 'message': f'La carpeta de audio no existe: {carpeta_audio}', 'percent': 100})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0, 'error': 'carpeta_audio_no_existe'}
    
    print(f"Carpeta de audio: {carpeta_audio}")
    print(f"Carpeta de letras: {carpeta_lyrics}")
    print("-" * 60)
    
    # -------------------------------------------------------------
    # 1. FASE DE PURGADO DE CANCIONES HUÉRFANAS EN BD
    # -------------------------------------------------------------
    emit_progress({
        'stage': 'processing',
        'message': 'Buscando y eliminando canciones huérfanas...',
        'percent': 0
    })
    print("🧹 Buscando canciones huérfanas en BD...")
    canciones_db = Cancion.query.all()
    huerfanas = 0
    with db.session.no_autoflush:
        for cancion in canciones_db:
            # Si el archivo registrado en BD ya no existe en el disco, lo eliminamos
            if not os.path.exists(cancion.ruta_archivo_audio):
                print(f"  🗑 Eliminando de BD (no encontrada en disco): {cancion.ruta_archivo_audio}")
                # Eliminar referencias en tablas intermedias para evitar violar restricciones de FK en PostgreSQL
                db.session.execute(db.delete(daily_mix_canciones).where(daily_mix_canciones.c.cancion_id == cancion.id))
                db.session.execute(db.delete(playlist_canciones).where(playlist_canciones.c.cancion_id == cancion.id))
                db.session.execute(db.delete(coleccion_canciones).where(coleccion_canciones.c.cancion_id == cancion.id))
                db.session.execute(db.delete(Favorito).where(Favorito.cancion_id == cancion.id))
                db.session.execute(db.delete(HistorialEscucha).where(HistorialEscucha.cancion_id == cancion.id))
                
                db.session.delete(cancion)
                huerfanas += 1
    
    if huerfanas > 0:
        db.session.commit()
        print(f"✅ Se eliminaron {huerfanas} canciones huérfanas de la base de datos.")
        
        # Eliminar álbumes vacíos residuales tras borrar las canciones
        albumes_db = Album.query.all()
        for alb in albumes_db:
            if not alb.canciones:
                db.session.delete(alb)
                
        # Eliminar artistas vacíos residuales
        artistas_db = Artista.query.all()
        for art in artistas_db:
            if not art.canciones and not art.albums:
                db.session.delete(art)
                
        db.session.commit()
        print("✅ Se limpiaron álbumes y artistas vacíos en la base de datos.")

    # -------------------------------------------------------------
    # 2. FASE DE DESCUBRIMIENTO DE ARCHIVOS EN DISCO
    # -------------------------------------------------------------
    archivos_encontrados = []
    
    # Escanear archivos de audio de forma recursiva (rglob) filtrando por las extensiones admitidas
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
    
    # -------------------------------------------------------------
    # 3. FASE DE INDEXACIÓN POR LOTES (BATCHING)
    # -------------------------------------------------------------
    canciones_agregadas = 0
    canciones_actualizadas = 0
    canciones_omitidas = 0
    
    commit_counter = 0
    batch_size = 50 # Tamaño óptimo de bloque de inserciones transaccionales
    
    # ─── PRE-DETECCIÓN DE ARCHIVOS NUEVOS Y ANÁLISIS EN PARALELO ───
    # Buscamos en memoria cuáles son las rutas nuevas para analizarlas de forma concurrente.
    # También incluimos aquellas canciones que ya existen en BD pero carecen de especificaciones técnicas (como sample_rate).
    rutas_bd = {row.ruta_archivo_audio for row in Cancion.query.with_entities(Cancion.ruta_archivo_audio).all()}
    canciones_sin_sample_rate = {row.ruta_archivo_audio for row in Cancion.query.filter(Cancion.sample_rate == None).with_entities(Cancion.ruta_archivo_audio).all()}
    
    archivos_nuevos = []
    for archivo in archivos_encontrados:
        ruta_str = str(archivo)
        if ruta_str not in rutas_bd:
            # Comprobar si no es una reubicación por stem
            cancion_por_nombre = Cancion.query.filter(Cancion.ruta_archivo_audio.like(f'%{archivo.stem}%')).first()
            if not cancion_por_nombre or os.path.exists(cancion_por_nombre.ruta_archivo_audio):
                archivos_nuevos.append(archivo)
        elif ruta_str in canciones_sin_sample_rate:
            # Archivo existente pero incompleto: lo agregamos al pool de análisis paralelo
            archivos_nuevos.append(archivo)
                
    metadatos_extraidos = extraer_metadatos_paralelo(
        archivos_nuevos,
        progress_callback=progress_callback,
        stage='processing',
        percent_start=5,
        percent_end=80
    )
    
    total_archivos = len(archivos_encontrados)
    for idx, archivo in enumerate(archivos_encontrados, start=1):
        emit_progress({
            'stage': 'processing',
            'message': f'Guardando en BD: {archivo.name}',
            'current_file': archivo.name,
            'processed': idx - 1,
            'total': total_archivos,
            'percent': int(80 + ((idx - 1) / total_archivos) * 14)
        })
        print(f"\nProcesando: {archivo.name}")

        # Comprobar si el archivo físico exacto ya está indexado en BD
        cancion_existente = Cancion.query.filter_by(ruta_archivo_audio=str(archivo)).first()

        if cancion_existente:
            print(f"  Ya existe en la base de datos (ID: {cancion_existente.id})")
            
            actualizada_localmente = False
            # Si ya existe, aprovechamos el escaneo para buscar y vincular letras (.lrc) locales si no tenía
            if not cancion_existente.ruta_archivo_lrc or not Path(cancion_existente.ruta_archivo_lrc).exists():
                ruta_lrc_existente = buscar_archivo_lrc(archivo, carpeta_lyrics, cancion_existente.id)
                if ruta_lrc_existente:
                    cancion_existente.ruta_archivo_lrc = ruta_lrc_existente
                    print(f"  🎤 Letra local actualizada: {Path(ruta_lrc_existente).name}")
                    actualizada_localmente = True
                else:
                    print(f"  ⚠ Sin letra local (se descargará en segundo plano)")
            else:
                print(f"  ✅ Letra ya existente: {Path(cancion_existente.ruta_archivo_lrc).name}")

            # Verificar si el archivo en disco ha sido modificado desde que fue agregado
            from datetime import datetime
            try:
                mtime_utc = datetime.utcfromtimestamp(os.path.getmtime(archivo))
                # Consideramos modificado si la fecha de modificación en disco es posterior a la fecha de agregado en BD
                # con un pequeño margen de 5 segundos para evitar falsos positivos
                modificado = (mtime_utc - cancion_existente.fecha_agregada).total_seconds() > 5
            except Exception:
                modificado = True

            # Si faltan datos técnicos obligatorios, forzar procesamiento
            if cancion_existente.sample_rate is None:
                modificado = True

            if modificado:
                # En un escaneo completo, forzamos la actualización de los metadatos ricos y su vinculación (artista, álbum, título, etc.)
                # para solventar problemas de importación previa defectuosa.
                metadatos = metadatos_extraidos.get(str(archivo)) or extraer_metadatos(archivo)
                if metadatos:
                    titulo_tag = metadatos.get('titulo') or archivo.stem
                    artista_tag = metadatos.get('artista')
                    album_tag = metadatos.get('album')
                    
                    # Intentar inferir si faltan
                    if not artista_tag or not album_tag:
                        artista_carpeta, album_carpeta = inferir_metadatos_desde_ruta(archivo, carpeta_audio)
                        if artista_carpeta and not artista_tag:
                            artista_tag = artista_carpeta
                        if album_carpeta and not album_tag:
                            album_tag = album_carpeta
                    
                    albumartist_tag = metadatos.get('albumartist') or artista_tag
                    artista_principal = metadatos.get('artista_principal') or normalizar_artista(albumartist_tag or artista_tag)
                    
                    # Obtener/crear objetos correctos de Artista y Álbum
                    artista_obj = obtener_o_crear_artista(artista_principal)
                    if not artista_obj and artista_principal:
                        artista_obj = Artista(nombre=artista_principal, nombre_normalizado=artista_principal)
                        db.session.add(artista_obj)
                        db.session.flush()
                    
                    album_obj = obtener_o_crear_album(album_tag, artista_principal) if (album_tag and artista_principal) else None
                    
                    # Comparar y actualizar si son distintos
                    if cancion_existente.titulo != titulo_tag:
                        cancion_existente.titulo = titulo_tag
                        actualizada_localmente = True
                    
                    new_artista_id = artista_obj.id if artista_obj else None
                    if cancion_existente.artista_id != new_artista_id:
                        cancion_existente.artista_id = new_artista_id
                        actualizada_localmente = True
                        
                    new_album_id = album_obj.id if album_obj else None
                    if cancion_existente.album_id != new_album_id:
                        cancion_existente.album_id = new_album_id
                        actualizada_localmente = True
                        
                    pista_tag = metadatos.get('numero_pista')
                    if cancion_existente.numero_pista != pista_tag:
                        cancion_existente.numero_pista = pista_tag
                        actualizada_localmente = True
                        
                    disco_tag = metadatos.get('numero_disco')
                    if cancion_existente.numero_disco != disco_tag:
                        cancion_existente.numero_disco = disco_tag
                        actualizada_localmente = True

                # Si ya existe pero le faltan los datos técnicos del audio (e.g. sample_rate es None), los analizamos
                if cancion_existente.sample_rate is None and metadatos:
                    print(f"  🔍 Datos técnicos faltantes para canción ID {cancion_existente.id}. Analizando...")
                    aa = (metadatos or {}).get('analisis') or (metadatos or {}).get('audio_analysis', {})
                    if aa:
                        cancion_existente.sample_rate = aa.get('sample_rate')
                        cancion_existente.bit_depth = aa.get('bit_depth')
                        cancion_existente.channels = aa.get('channels')
                        cancion_existente.nyquist_freq = aa.get('nyquist_freq')
                        cancion_existente.dynamic_range = aa.get('dynamic_range')
                        cancion_existente.peak_level = aa.get('peak_level')
                        cancion_existente.rms_level = aa.get('rms_level')
                        cancion_existente.total_samples = aa.get('total_samples')
                        cancion_existente.bit_rate = aa.get('bit_rate')
                        cancion_existente.bpm = aa.get('bpm')
                        # Asegurar el género si no estaba
                        if not cancion_existente.genero:
                            cancion_existente.genero = (metadatos or {}).get('genero') or aa.get('genero')
                        actualizada_localmente = True
                        print(f"  ✅ Datos técnicos extraídos para canción ID {cancion_existente.id}")
            else:
                print(f"  Omitiendo actualización de metadatos (archivo de música sin cambios desde su indexación)")

            if actualizada_localmente:
                db.session.add(cancion_existente)
                canciones_actualizadas += 1
                commit_counter += 1
                if commit_counter >= batch_size:
                    db.session.commit()
                    commit_counter = 0
                    print(f"  💾 Commit periódico de {batch_size} canciones actualizadas")
            else:
                canciones_omitidas += 1

            emit_progress({
                'stage': 'file_done',
                'message': f'Omitida/Actualizada: {archivo.name}',
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

        # HEURÍSTICA DE DETECCIÓN DE REUBICACIÓN DE ARCHIVOS:
        # Si la ruta no coincide exactamente, buscamos si el nombre del archivo (stem) ya está en BD.
        # Si existe pero su ruta antigua ya no es válida en disco, reubicamos el registro actualizándolo.
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

        # Extraer metadatos ricos del archivo pre-analizado en paralelo
        metadatos = metadatos_extraidos.get(str(archivo)) or extraer_metadatos(archivo)

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
            # Fallback extremo: Limpiar nombre de archivo para deducir tags
            titulo, artista = limpiar_nombre_archivo(archivo.name)
            albumartist = artista
            album = None
            duracion = None

            print(f"  📋 Sin metadatos, usando nombre del archivo:")
            print(f"     Título: {titulo}")
            print(f"     Artista: {artista or 'Desconocido'}")

        # Si faltan metadatos clave, intentamos deducirlos analizando la estructura de carpetas
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
        
        # Unificamos el Artista Principal para agrupación única normalizada
        artista_principal = (metadatos or {}).get('artista_principal') or normalizar_artista(albumartist or artista)
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
        
        # Obtenemos o creamos el álbum
        album_obj = obtener_o_crear_album(album, artista_principal) if (album and artista_principal) else None

        # Vincular archivo de letras local si está disponible
        ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
        if ruta_lrc:
            print(f"  🎤 Letra encontrada localmente: {Path(ruta_lrc).name}")
        else:
            print(f"  ⚠️ Sin letra local (se descargará en segundo plano)")

        # Datos electroacústicos calculados por el analizador
        # Buscamos primero 'analisis' (que es la clave real asignada por extraer_metadatos)
        # y como fallback 'audio_analysis' por compatibilidad.
        aa = (metadatos or {}).get('analisis') or (metadatos or {}).get('audio_analysis', {})

        # Crear y registrar la canción
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
            bit_rate=aa.get('bit_rate'),
            bpm=aa.get('bpm')
        )

        db.session.add(nueva_cancion)
        canciones_agregadas += 1
        commit_counter += 1
        print(f"  ✅ Canción agregada a la base de datos")
        
        # Commit transaccional masivo periódico para mitigar el I/O blocking en BD
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

    # Consolidar inserciones finales restantes
    if commit_counter > 0:
        db.session.commit()
        print(f"  💾 Commit final de {commit_counter} canciones restantes")
    
    # -------------------------------------------------------------
    # 4. FASE DE NORMALIZACIÓN Y FUSIÓN DE DUPLICADOS GLOBALES
    # -------------------------------------------------------------
    resumen_norm = normalizar_biblioteca(
        progress_callback=progress_callback,
        percent_start=94,
        percent_end=98,
    )

    # -------------------------------------------------------------
    # 5. FASE DE ENRIQUECIMIENTO EXTERNO DE METADATOS
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ENRIQUECIENDO METADATOS...")
    print("=" * 60)

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
        'processed': len(archivos_encontrados),
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
    
    # -------------------------------------------------------------
    # 6. FASE DE ENCOLAMIENTO ASÍNCRONO DE TAREAS SECUNDARIAS
    # -------------------------------------------------------------
    try:
        from app.services.queue import enqueue
        from app.services.lyrics import descargar_letras_segundo_plano
        from app.services.metadata import enriquecer_artistas_sin_mbid
        from app.services.transcoder import run_pretranscode_library
        
        print("\n🚀 Encolando tareas post-escaneo en Redis (letras + MusicBrainz)...")
        enqueue(descargar_letras_segundo_plano, batch_size=10)
        enqueue(enriquecer_artistas_sin_mbid, limite=200)
        print("✅ Tareas encoladas — workers las procesarán en segundo plano")
    except Exception as e:
        print(f"⚠️ No se pudieron encolar tareas: {e}")
        import threading
        th = threading.Thread(target=lambda: (
            descargar_letras_segundo_plano(batch_size=10),
            enriquecer_artistas_sin_mbid(limite=200),
        ), daemon=True)
        th.start()
    
    # Invalidar la caché de consultas AJAX de Redis tras el escaneo exitoso
    invalidar_cache_redis()
    
    return resumen


def escaneo_rapido(progress_callback=None):
    """
    Realiza un escaneo inteligente e incremental de la biblioteca musical.
    
    Este método optimiza el proceso de actualización comparando en memoria (mediante
    operaciones de conjuntos o 'sets' de Python) los archivos existentes en el disco 
    con los registros actuales de la base de datos.
    
    Características clave:
    1. Evita reprocesar archivos de audio que ya están registrados en la base de datos.
    2. Detecta archivos que han sido eliminados físicamente del disco y limpia sus 
       registros huérfanos correspondientes en la base de datos.
    3. Puede ser hasta 10 veces más rápido que un escaneo completo en colecciones grandes,
       ya que solo invoca la lectura costosa de metadatos (TinyTag/Mutagen) en los archivos
       que son genuinamente nuevos.
    4. Encola de manera asíncrona la búsqueda de letras y enriquecimiento de metadatos.
    
    Parámetros:
        progress_callback (callable, opcional): Función de retorno para notificar 
                                                el progreso del escaneo en tiempo real.
    
    Retorna:
        dict: Resumen con estadísticas de canciones agregadas, actualizadas,
              omitidas, procesadas y eliminadas.
    """
    # Función auxiliar para emitir el estado y progreso del escaneo de manera segura
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

    # Obtención de las rutas a las carpetas de audio y letras desde la configuración global
    carpeta_audio = Config.AUDIO_FOLDER
    carpeta_lyrics = Config.LYRICS_FOLDER

    # Si la carpeta configurada no existe en disco, se reporta un error y se finaliza el proceso
    if not carpeta_audio.exists():
        emit_progress({'stage': 'error', 'message': f'La carpeta de audio no existe: {carpeta_audio}', 'percent': 100})
        return {'agregadas': 0, 'actualizadas': 0, 'omitidas': 0, 'procesadas': 0, 'eliminadas': 0}

    # Notificar que se inicia la fase de comparación de la biblioteca con el disco
    emit_progress({'stage': 'processing', 'message': 'Comparando biblioteca con disco...', 'percent': 2, 'processed': 0, 'total': 0})

    # 1. Obtener todas las rutas de archivos de audio del disco en un set (operación de disco rápida)
    archivos_disco = {
        str(archivo)
        for archivo in carpeta_audio.rglob('*')
        if archivo.is_file() and archivo.suffix.lower() in AUDIO_EXTENSIONS
    }

    # 2. Obtener todas las rutas registradas en la BD en un set (una sola query con proyección)
    rutas_bd = {row.ruta_archivo_audio for row in Cancion.query.with_entities(Cancion.ruta_archivo_audio).all()}

    # 3. Calcular diferencias mediante operaciones de conjuntos (O(n), ejecución instantánea)
    # - archivos_nuevos: en disco pero no en base de datos -> se agregarán
    # - archivos_eliminados: en base de datos pero no en disco -> se marcarán para eliminación
    archivos_nuevos = archivos_disco - rutas_bd          # en disco pero no en BD → agregar
    archivos_eliminados = rutas_bd - archivos_disco       # en BD pero no en disco → marcar/eliminar

    print(f"📊 En disco: {len(archivos_disco)} | En BD: {len(rutas_bd)}")
    print(f"✨ Nuevos: {len(archivos_nuevos)} | 🗑 Eliminados: {len(archivos_eliminados)}")

    # Inicialización de contadores del proceso
    canciones_agregadas = 0
    canciones_actualizadas = 0
    canciones_eliminadas = 0
    errores = 0

    # 4. Eliminar de la base de datos las canciones cuyos archivos ya no existen en el disco
    if archivos_eliminados:
        emit_progress({
            'stage': 'processing',
            'message': f'Eliminando {len(archivos_eliminados)} archivos obsoletos...',
            'percent': 5, 'processed': 0, 'total': len(archivos_nuevos)
        })
        with db.session.no_autoflush:
            for ruta_eliminada in archivos_eliminados:
                cancion = Cancion.query.filter_by(ruta_archivo_audio=ruta_eliminada).first()
                if cancion:
                    # Eliminar referencias en tablas intermedias para evitar violar restricciones de FK en PostgreSQL
                    db.session.execute(db.delete(daily_mix_canciones).where(daily_mix_canciones.c.cancion_id == cancion.id))
                    db.session.execute(db.delete(playlist_canciones).where(playlist_canciones.c.cancion_id == cancion.id))
                    db.session.execute(db.delete(coleccion_canciones).where(coleccion_canciones.c.cancion_id == cancion.id))
                    db.session.execute(db.delete(Favorito).where(Favorito.cancion_id == cancion.id))
                    db.session.execute(db.delete(HistorialEscucha).where(HistorialEscucha.cancion_id == cancion.id))
                    
                    db.session.delete(cancion)
                    canciones_eliminadas += 1
        db.session.commit()
        # Se ejecuta la limpieza de artistas y álbumes vacíos para evitar registros huérfanos
        limpiar_entidades_vacias()
        db.session.commit()

    # Buscar canciones existentes que no tengan datos técnicos (e.g. sample_rate es None)
    rutas_incompletas_bd = {row.ruta_archivo_audio for row in Cancion.query.filter(Cancion.sample_rate == None).with_entities(Cancion.ruta_archivo_audio).all()}
    # Solo las que realmente existen en el disco y no están marcadas para eliminación
    rutas_incompletas = rutas_incompletas_bd & archivos_disco

    # Procesar únicamente los archivos nuevos y los existentes incompletos
    archivos_a_procesar = archivos_nuevos | rutas_incompletas

    # Si no hay archivos para procesar, la biblioteca está al día.
    # Solo normalizamos la biblioteca y retornamos un resumen temprano.
    if not archivos_a_procesar:
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

    # 5. Procesar únicamente los archivos nuevos y los incompletos
    # Ordenamos la lista para que el procesamiento sea predecible y alfabético
    archivos_procesar_lista = [Path(p) for p in sorted(archivos_a_procesar)]
    total = len(archivos_procesar_lista)
    
    # ─── ANÁLISIS ACÚSTICO Y DE TAGS EN PARALELO (MULTITHREADING) ───
    # Ejecutamos la lectura de metadatos y DSP concurrente en hilos secundarios
    metadatos_extraidos = extraer_metadatos_paralelo(
        archivos_procesar_lista,
        progress_callback=progress_callback,
        stage='processing',
        percent_start=5,
        percent_end=85
    )

    # Variables para control de transacciones en bloques (commit cada 50 canciones)
    commit_counter = 0
    batch_size = 50

    for idx, archivo in enumerate(archivos_procesar_lista, start=1):
        # Reportar el progreso por cada archivo procesado mediante el callback
        emit_progress({
            'stage': 'file_done',
            'message': f'Guardando en BD: {archivo.name}',
            'current_file': archivo.name,
            'processed': idx,
            'total': total,
            'percent': int(85 + (idx / total) * 7),
            'counters': {
                'agregadas': canciones_agregadas,
                'actualizadas': 0,
                'omitidas': 0
            }
        })

        try:
            # Recuperar los metadatos pre-extraídos en paralelo
            metadatos = metadatos_extraidos.get(str(archivo)) or extraer_metadatos(archivo)

            if metadatos:
                titulo = metadatos.get('titulo')
                artista = metadatos.get('artista')
                # Determinar el artista del álbum si está disponible, o usar el artista de la pista
                albumartist = metadatos.get('albumartist') or artista
                album = metadatos.get('album')
                duracion = metadatos.get('duracion')
            else:
                # Deducir título y artista analizando el nombre del archivo si no hay metadatos empotrados
                titulo, artista = limpiar_nombre_archivo(archivo.name)
                albumartist = artista
                album = None
                duracion = None

            # Si faltan metadatos clave, inferirlos analizando la ruta y jerarquía de carpetas
            if not artista or not album:
                artista_carpeta, album_carpeta = inferir_metadatos_desde_ruta(archivo, carpeta_audio)
                if artista_carpeta and not artista:
                    artista = artista_carpeta
                    albumartist = albumartist or artista_carpeta
                if album_carpeta and not album:
                    album = album_carpeta
            albumartist = albumartist or artista
            
            # Normalizar el artista principal para agrupar variantes con tipografía diferente o acentos
            artista_principal_rapido = (metadatos or {}).get('artista_principal') or normalizar_artista(albumartist or artista)

            # Obtener o crear de forma segura las referencias de base de datos para Artista y Álbum
            artista_obj = obtener_o_crear_artista(artista_principal_rapido)
            album_obj = obtener_o_crear_album(album, artista_principal_rapido) if (album and artista_principal_rapido) else None

            # Buscar letra local (.lrc) asociada en la carpeta de letras
            # Nota: El escaneo rápido solo busca de manera local y no realiza llamadas a APIs síncronas de red
            ruta_lrc = buscar_archivo_lrc(archivo, carpeta_lyrics)
            if ruta_lrc:
                print(f"  🎤 Letra ya existe localmente: {Path(ruta_lrc).name}")
            else:
                print(f"  ⚠️ Sin letra local (se descargará en segundo plano)")

            # Recuperar análisis técnico de audio (frecuencias, rango dinámico, etc.) si está disponible
            # Buscamos primero 'analisis' (que es la clave real asignada por extraer_metadatos)
            # y como fallback 'audio_analysis' por compatibilidad.
            aa = (metadatos or {}).get('analisis') or (metadatos or {}).get('audio_analysis', {})
            
            # Comprobar si ya existe en la base de datos (por si es una canción incompleta)
            cancion_existente = Cancion.query.filter_by(ruta_archivo_audio=str(archivo)).first()

            if cancion_existente:
                # Actualizar los metadatos técnicos y de calidad
                cancion_existente.sample_rate = aa.get('sample_rate')
                cancion_existente.bit_depth = aa.get('bit_depth')
                cancion_existente.channels = aa.get('channels')
                cancion_existente.nyquist_freq = aa.get('nyquist_freq')
                cancion_existente.dynamic_range = aa.get('dynamic_range')
                cancion_existente.peak_level = aa.get('peak_level')
                cancion_existente.rms_level = aa.get('rms_level')
                cancion_existente.total_samples = aa.get('total_samples')
                cancion_existente.bit_rate = aa.get('bit_rate')
                cancion_existente.bpm = aa.get('bpm')
                if not cancion_existente.genero:
                    cancion_existente.genero = (metadatos or {}).get('genero') or aa.get('genero')
                if not cancion_existente.ruta_archivo_lrc or not Path(cancion_existente.ruta_archivo_lrc).exists():
                    cancion_existente.ruta_archivo_lrc = ruta_lrc
                
                db.session.add(cancion_existente)
                canciones_actualizadas += 1
                commit_counter += 1
                print(f"  🔄 Actualizados datos técnicos: {archivo.name}")
            else:
                # Instanciar el registro de base de datos de la nueva canción
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
                    bit_rate=aa.get('bit_rate'),
                    bpm=aa.get('bpm')
                )
                db.session.add(nueva_cancion)
                canciones_agregadas += 1
                commit_counter += 1
                print(f"  ✅ Agregada: {archivo.name}")
            
            # Realizar commits en bloques de 50 canciones para acelerar la inserción en base de datos
            if commit_counter >= batch_size:
                db.session.commit()
                commit_counter = 0
                print(f"  💾 Commit de {batch_size} canciones procesadas")
        except Exception as ex:
            errores += 1
            print(f"  Error procesando {archivo.name}: {ex}")

    # Realizar el commit de cualquier canción restante que no haya completado el último bloque
    if commit_counter > 0:
        db.session.commit()
        print(f"  💾 Commit final de {commit_counter} canciones restantes")

    # Ejecutar la normalización rápida de la biblioteca
    resumen_norm = normalizar_biblioteca(
        progress_callback=progress_callback,
        percent_start=92,
        percent_end=96,
    )

    # 6. Enriquecer de forma automatizada los artistas y álbumes recién creados (sin imágenes ni biografías locales)
    # Se omiten por completo los registros que ya fueron procesados previamente.
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

    # Compilación final del diccionario con el resumen de la operación de escaneo rápido
    resumen = {
        'agregadas': canciones_agregadas,
        'actualizadas': canciones_actualizadas,
        'omitidas': len(rutas_bd) - canciones_eliminadas - canciones_actualizadas,
        'procesadas': canciones_agregadas + canciones_actualizadas,
        'eliminadas': canciones_eliminadas,
        'meta_artistas': meta_artistas,
        'meta_albumes': meta_albumes,
        'normalizacion': resumen_norm,
    }
    
    # Notificación de finalización exitosa con los datos del resumen consolidado
    emit_progress({
        'stage': 'done',
        'message': f'Escaneo rápido finalizado — {canciones_agregadas} nuevas, {canciones_actualizadas} actualizadas, {canciones_eliminadas} eliminadas',
        'percent': 100,
        'processed': total,
        'total': total,
        'summary': resumen
    })
    
    # 7. FASE DE ENCOLAMIENTO ASÍNCRONO DE TAREAS SECUNDARIAS POST-ESCANEO
    # Encolamos en Redis (o levantamos hilos Daemon si Redis no está disponible) para la descarga en segundo plano
    # de letras faltantes desde APIs y metadatos complementarios en MusicBrainz, sin penalizar la UI del usuario.
    try:
        from app.services.queue import enqueue
        from app.services.lyrics import descargar_letras_segundo_plano
        from app.services.metadata import enriquecer_artistas_sin_mbid
        
        print("\n🚀 Encolando tareas post-escaneo en Redis (letras + MusicBrainz)...")
        enqueue(descargar_letras_segundo_plano, batch_size=10)
        enqueue(enriquecer_artistas_sin_mbid, limite=200)
        print("✅ Tareas encoladas — workers las procesarán en segundo plano")
    except Exception as e:
        print(f"⚠️ No se pudieron encolar tareas: {e}")
        import threading
        th = threading.Thread(target=lambda: (
            descargar_letras_segundo_plano(batch_size=10),
            enriquecer_artistas_sin_mbid(limite=200),
        ), daemon=True)
        th.start()
    
    # Invalidar la caché de consultas AJAX de Redis tras el escaneo exitoso
    invalidar_cache_redis()
    
    return resumen

if __name__ == '__main__':
    """
    Punto de entrada de ejecución del script cuando se invoca directamente desde la consola/terminal.
    
    Inicializa el contexto de la aplicación Flask para poder acceder a la base de datos
    SQLAlchemy y ejecuta de forma predeterminada un escaneo completo de la biblioteca.
    """
    try:
        # Importar la app localmente para evitar importaciones circulares en el sistema
        from app import create_app
        app = create_app()
        # Se establece el contexto de aplicación obligatorio para las consultas y operaciones ORM
        with app.app_context():
            resumen = escanear_carpeta_audio()
            print('\nResumen:', resumen)
    except KeyboardInterrupt:
        # Capturar la interrupción del usuario (Ctrl+C) de forma elegante sin volcar trazas de error
        print("\n\n⚠ Escaneo interrumpido por el usuario")
    except Exception as e:
        # Gestión y reporte detallado de cualquier excepción ocurrida durante el flujo del escaneo
        print(f"\nError durante el escaneo: {e}")
        import traceback
        traceback.print_exc()

