# -*- coding: utf-8 -*-
"""
Servicio de Descarga y Gestión de Letras (Lyrics) - DuckSound
==============================================================
Este servicio se encarga de buscar, descargar y almacenar letras de canciones (.lrc y .txt).
Utiliza una estrategia de múltiples fallbacks:
1. LRCLIB (letras sincronizadas y texto plano).
2. Lyrics.ovh (letras en texto plano).
3. Genius scraping (búsqueda y extracción del HTML).
Mantiene un caché en disco y en memoria para optimizar el rendimiento.
"""

import requests
import re
import time
import os
from pathlib import Path
from app.models import db, Cancion
from config import Config
from app.services.queue import progress_set, progress_get

# Caché en memoria para letras: {cancion_id: (timestamp, resultado)}
_lyrics_cache = {}
_LYRICS_CACHE_TTL = 3600  # 1 hora de tiempo de vida (TTL)


def _detectar_tipo_lyrics(contenido):
    """
    Detecta si el contenido de la letra está sincronizado (formato LRC) o es texto plano.
    
    Args:
        contenido (str): Contenido textual de la letra.
        
    Returns:
        str: 'lrc' si contiene marcas de tiempo, 'txt' si es texto plano.
    """
    # Patrón regex para marcas de tiempo LRC: [mm:ss.xx] o [mm:ss]
    lrc_pattern = r'\[\d{2}:\d{2}(?:\.\d{2})?\]'
    
    if re.search(lrc_pattern, contenido):
        return 'lrc'
    else:
        return 'txt'


def _crear_nombre_archivo_seguro(cancion):
    """
    Genera un nombre de archivo seguro y normalizado para almacenar la letra.
    
    Args:
        cancion (Cancion): Objeto de la base de datos que representa la canción.
        
    Returns:
        str: Nombre de archivo sanitizado.
    """
    # Sanitizar caracteres no permitidos en sistemas de archivos
    titulo_limpio = re.sub(r'[^\w\s-]', '', cancion.titulo)
    titulo_limpio = re.sub(r'[-\s]+', '_', titulo_limpio)
    
    return f"{cancion.id}_{titulo_limpio}"


def obtener_o_descargar_letra(cancion_id):
    """
    Recupera la letra de una canción buscando primero en disco y caché local,
    y si no existe, la descarga utilizando proveedores externos en cascada.
    
    Args:
        cancion_id (int): Identificador único de la canción.
        
    Returns:
        dict or None: Diccionario con {'tipo': 'lrc'|'txt', 'letra': 'contenido'} o None si no se halló.
    """
    try:
        # Consultar la canción en la base de datos
        cancion = db.session.get(Cancion, cancion_id)
        if not cancion:
            return None
        
        # 0. Buscar en el caché en memoria
        if cancion_id in _lyrics_cache:
            cached_time, cached_result = _lyrics_cache[cancion_id]
            if time.time() - cached_time < _LYRICS_CACHE_TTL:
                return cached_result
        
        # 1. Buscar en disco usando la ruta almacenada
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
                    print(f"Error leyendo archivo de letra local {ruta_lrc}: {e}")
                    # Si falla la lectura, procedemos a re-descargar
        
        # 1.5. Lógica de rescate: si no tiene ruta pero el archivo existe físicamente en disco
        if not cancion.ruta_archivo_lrc or not Path(cancion.ruta_archivo_lrc).exists():
            from app.services.scanner import buscar_archivo_lrc
            
            # Buscar el archivo .lrc en el directorio de letras
            ruta_lrc_rescate = buscar_archivo_lrc(cancion.ruta_archivo_audio, Config.LYRICS_FOLDER, cancion.id)
            if ruta_lrc_rescate:
                try:
                    with open(ruta_lrc_rescate, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    # Guardamos la ruta válida encontrada en la base de datos
                    cancion.ruta_archivo_lrc = ruta_lrc_rescate
                    db.session.commit()
                    
                    tipo = _detectar_tipo_lyrics(contenido)
                    print(f"🔄 Letra local rescatada de disco: {Path(ruta_lrc_rescate).name}")
                    resultado = {"tipo": tipo, "letra": contenido}
                    _lyrics_cache[cancion_id] = (time.time(), resultado)
                    return resultado
                except (IOError, UnicodeDecodeError) as e:
                    print(f"Error leyendo archivo rescatado {ruta_lrc_rescate}: {e}")
        
        # 2. Intentar descarga desde la API principal: LRCLIB
        if not all([cancion.titulo, cancion.artista_obj, cancion.duracion]):
            print(f"Faltan campos requeridos para buscar letras en APIs para cancion {cancion_id}")
            return None
        
        # Parámetros obligatorios para la consulta exacta en LRCLIB
        params = {
            'track_name': cancion.titulo,
            'artist_name': cancion.artista_obj.nombre,
            'duration': int(cancion.duracion)
        }
        
        if cancion.album_obj and cancion.album_obj.titulo:
            params['album_name'] = cancion.album_obj.titulo
        
        headers = {'User-Agent': 'DuckSound/1.0.1 (app_music)'}
        
        try:
            response = requests.get('https://lrclib.net/api/get', params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                letra_contenido = None
                tipo_letra = 'txt'
                
                # Priorizar letras sincronizadas (syncedLyrics)
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
                print(f"Error de API LRCLIB para canción {cancion_id}: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"Timeout en LRCLIB para canción {cancion_id}")
        except requests.exceptions.RequestException as e:
            print(f"Error de red en LRCLIB para canción {cancion_id}: {e}")
        except Exception as e:
            print(f"Error inesperado en LRCLIB para canción {cancion_id}: {e}")
        
        # 3. Primer Fallback: Lyrics.ovh (Servicio gratuito y rápido, texto plano)
        titulo = cancion.titulo
        artista = cancion.artista_obj.nombre if cancion.artista_obj else ''
        
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
                print(f"Error en Fallback Lyrics.ovh para canción {cancion_id}: {e}")
        
        # 4. Segundo Fallback: Web Scraping a Genius.com
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
                                    # Intentar aislar los contenedores de letras conocidos
                                    match = re.search(r'<div class="lyrics"[^>]*>(.*?)</div>\s*</div>', page.text, re.DOTALL)
                                    if not match:
                                        match = re.search(r'<div data-lyrics-container[^>]*>(.*?)</div>', page.text, re.DOTALL)
                                    if match:
                                        html_lyrics = match.group(1)
                                        # Limpiar etiquetas HTML básicas y espaciados
                                        letra_limpia = re.sub(r'<br\s*/?>', '\n', html_lyrics)
                                        letra_limpia = re.sub(r'<[^>]+>', '', letra_limpia)
                                        letra_limpia = re.sub(r'\n{3,}', '\n\n', letra_limpia).strip()
                                        if letra_limpia:
                                            return _guardar_letra(cancion, letra_limpia, 'txt', cancion_id)
                                break  # Detenerse tras procesar el primer resultado más coincidente
            except Exception as e:
                print(f"Error en Fallback Genius para canción {cancion_id}: {e}")
        
        return None
        
    except Exception as e:
        print(f"Error general en obtener_o_descargar_letra para canción {cancion_id}: {e}")
        return None


def _guardar_letra(cancion, letra_contenido, tipo_letra, cancion_id):
    """
    Función auxiliar para guardar físicamente el contenido de la letra en disco,
    registrar la ruta en la base de datos y actualizar el caché de memoria.
    """
    try:
        nombre_archivo = _crear_nombre_archivo_seguro(cancion)
        extension = '.lrc' if tipo_letra == 'lrc' else '.txt'
        ruta_archivo = Config.LYRICS_FOLDER / f"{nombre_archivo}{extension}"
        
        # Asegurar la existencia del directorio destino
        Config.LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)
        
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(letra_contenido)
            
        cancion.ruta_archivo_lrc = str(ruta_archivo)
        db.session.commit()
        
        resultado = {"tipo": tipo_letra, "letra": letra_contenido}
        _lyrics_cache[cancion_id] = (time.time(), resultado)
        return resultado
    except Exception as e:
        print(f"Error al guardar archivo físico de letra: {e}")
        return None


def descargar_letras_segundo_plano(batch_size=10):
    """
    Wrapper de ejecución para descargas masivas asíncronas de letras en segundo plano.
    Instancia una aplicación Flask temporal con app_context para interactuar con la BD.
    """
    from app import create_app
    app = create_app()
    
    with app.app_context():
        _descargar_letras_impl(batch_size)


def _descargar_letras_impl(batch_size):
    """
    Implementación interna del hilo asíncrono para descargar en lote todas las
    letras faltantes en la biblioteca local.
    """
    print("=" * 60)
    print("🎤 INICIANDO DESCARGA DE LETRAS EN SEGUNDO PLANO (MODULAR)")
    print("=" * 60)
    
    # Obtener todas las canciones sin archivo de letra registrado o con referencias rotas
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
    
    # Filtrar solo aquellas cuyas rutas en disco realmente no existan físicamente
    canciones_sin_letra = [c for c in canciones_sin_letra if not c.ruta_archivo_lrc or not os.path.exists(c.ruta_archivo_lrc)]
    
    if not canciones_sin_letra:
        print("✅ Todas las canciones ya tienen letras locales indexadas correctamente.")
        progress_set('lyrics', {'active': False, 'finished': True})
        return
    
    print(f"📊 Canciones sin letras identificadas: {len(canciones_sin_letra)}")
    print(f"🔄 Iniciando descarga controlada en lotes de {batch_size}...\n")
    
    def set_progress(**kw):
        data = progress_get('lyrics') or {}
        data.update(kw)
        progress_set('lyrics', data)
    
    # Registrar el estado inicial del progreso en Redis
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
            nombre_artista = cancion.artista_obj.nombre if cancion.artista_obj else 'Artista Desconocido'
            song_str = f"{cancion.titulo} - {nombre_artista}"
            print(f"[{idx}/{len(canciones_sin_letra)}] 🔍 Buscando: {song_str}")
            
            set_progress(current_song=song_str, completed=idx - 1)
            
            resultado = obtener_o_descargar_letra(cancion.id)
            if resultado:
                print("  ✅ Letra obtenida y sincronizada.")
                descargadas += 1
                set_progress(downloaded=descargadas)
            else:
                print("  ⚠️ Letra no encontrada en ningún proveedor.")
                errores += 1
                set_progress(errors=errores)
            
            # Pausa de cortesía para evitar penalizaciones o rate limit en los servidores externos
            if idx % batch_size == 0:
                print("  ⏸️ Pausa breve entre lotes...")
                time.sleep(2)
                
        except Exception as e:
            print(f"  ❌ Error inesperado procesando letra de canción {cancion.id}: {e}")
            errores += 1
            set_progress(errors=errores)
    
    print("\n" + "=" * 60)
    print("✅ DESCARGA MASIVA FINALIZADA")
    print(f"   Descargadas con éxito: {descargadas}")
    print(f"   No resueltas / Errores: {errores}")
    print("=" * 60)
    
    progress_set('lyrics', {
        'active': False,
        'finished': True,
        'completed': len(canciones_sin_letra),
        'current_song': 'Completado con éxito'
    })
