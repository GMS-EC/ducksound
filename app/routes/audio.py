# -*- coding: utf-8 -*-
"""
Controlador de Rutas de Audio y Multimedia - DuckSound
======================================================
Este módulo encapsula todas las funciones y endpoints relacionados con el motor de
reproducción de sonido y metadatos multimedia de la plataforma:
1. Streaming de audio compatible con cabeceras de rango HTTP 206 (Conditional Byte-Range Streaming)
   para permitir rebobinar, adelantar y cargar búferes parciales en reproductores HTML5.
2. Servidor de carátulas (Album Art) con cascada de 6 niveles (incluyendo extracción directa
   "on the fly" de metadatos incrustados APIC/Vorbis y fallback elegante en gráficos vectoriales SVG).
3. Servidor de letras (Karaoke LRC) sincronizadas.
4. Inyección del script Service Worker de la PWA desde la raíz del dominio.
"""

import os
import io
import re
import threading
import shutil
import time
from pathlib import Path
from PIL import Image

from flask import Blueprint, send_file, send_from_directory, make_response, Response, current_app
from config import Config
from app.models import db, Cancion

# Servicios de letras desacoplados
from app.services.lyrics import obtener_o_descargar_letra

# Definición del Blueprint de Audio
audio_bp = Blueprint('audio', __name__)

def resolver_ruta_fisica(original_path):
    """Resuelve la ruta física real de un archivo en disco soportando entornos Docker/Linux y Windows."""
    if not original_path:
        return None
    if os.path.exists(original_path):
        return original_path
        
    # Conversión heurística de rutas Windows montadas en volúmenes Docker/Linux
    try:
        p = original_path.replace('\\', '/')
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            alt = '/music/' + m.group(2)
            if os.path.exists(alt):
                return alt
            alt2 = str(Config.MUSIC_FOLDER / m.group(2))
            if os.path.exists(alt2):
                return alt2
    except Exception:
        pass

    # Búsqueda directa por nombre en la carpeta de música de Docker
    try:
        fname = Path(original_path).name
        direct_music = Path('/music') / fname
        if direct_music.exists():
            return str(direct_music)
        cfg_music = Config.MUSIC_FOLDER / fname
        if cfg_music.exists():
            return str(cfg_music)
    except Exception:
        pass

    # Intentar buscar como ruta relativa al directorio actual
    rel = os.path.join(os.getcwd(), original_path)
    if os.path.exists(rel):
        return rel
        
    return None


# ==============================================================================
# SECCIÓN 2: TRANSMISIÓN DE AUDIO CON CABECERAS DE RANGO (HTTP 206)
# ==============================================================================

@audio_bp.route('/audio/<int:cancion_id>')
def servir_audio(cancion_id):
    """
    Transmite el archivo de audio correspondiente a una canción, utilizando
    caché local y streaming al vuelo para evitar latencias de FUSE/Rclone.
    """
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return "Canción no encontrada", 404
        
    original_path = cancion.ruta_archivo_audio
    resolved_path = resolver_ruta_fisica(original_path)
    
    if not resolved_path:
        current_app.logger.error(f"[Audio Server] Archivo no encontrado para id={cancion_id}. Ruta original: {original_path}")
        return "Archivo de audio no encontrado", 404

    def _mime_for(p):
        """Devuelve el MIME type correcto en base a la extensión del archivo de audio."""
        ext = Path(p).suffix.lower()
        return {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg'
        }.get(ext, 'audio/mpeg')

    # ─── PREFERENCIA DE CALIDAD DE AUDIO DEL USUARIO Y TRANSCODIFICACIÓN ───
    from flask import session
    usuario_id = session.get('user_id')
    calidad = 'lossless'
    if usuario_id:
        from app.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        if usuario:
            calidad = usuario.audio_quality or 'lossless'

    ext_original = Path(resolved_path).suffix.lower()
    requires_transcode = (calidad != 'lossless') and (ext_original in ['.flac', '.wav', '.ogg'])

    if requires_transcode:
        # --- CASO 1: TRANSCODIFICACIÓN A MP3 (CON SOPORTE DE RANGOS) ---
        from app.services.transcoder import obtener_ruta_cache, transcodificar_cancion
        
        ruta_final = obtener_ruta_cache(cancion_id, calidad=calidad)
        if not (ruta_final.exists() and ruta_final.stat().st_size > 0):
            current_app.logger.info(f"[Audio Server] Transcodificando al vuelo ID {cancion_id} a calidad {calidad}...")
            transcodificar_cancion(cancion_id, calidad)
            
        if ruta_final.exists() and ruta_final.stat().st_size > 0:
            current_app.logger.info(f"[Audio Server] Sirviendo versión transcodificada ({calidad}) con rangos: {ruta_final}")
            resp = send_file(str(ruta_final), mimetype='audio/mpeg', conditional=True, max_age=86400)
            resp.headers['Accept-Ranges'] = 'bytes'
            return resp
        else:
            current_app.logger.warning(f"[Audio Server] Falló la transcodificación para ID {cancion_id}. Sirviendo original con rangos.")
            resp = send_file(resolved_path, mimetype=_mime_for(resolved_path), conditional=True, max_age=86400)
            resp.headers['Accept-Ranges'] = 'bytes'
            return resp

    else:
        # --- CASO 2: SERVIR ORIGINAL DIRECTAMENTE CON SOPORTE COMPLETO HTTP 206 BYTE-RANGE ---
        # send_file con conditional=True gestiona nativamente cabeceras Range, Content-Range, 206 Partial Content y seeking
        resp = send_file(
            resolved_path,
            mimetype=_mime_for(resolved_path),
            conditional=True,
            max_age=86400
        )
        resp.headers['Accept-Ranges'] = 'bytes'
        return resp



# ==============================================================================
# SECCIÓN 3: SERVIDOR DE LETRAS SINCRONIZADAS (KARAOKE LRC)
# ==============================================================================

@audio_bp.route('/lyrics/<int:cancion_id>')
def servir_lyrics(cancion_id):
    """
    Sirve las letras LRC sincronizadas para el reproductor de karaoke.
    Si no existen localmente, realiza una petición de descarga asíncrona automatizada al servicio.
    """
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return "Canción no encontrada", 404

    # Intentar obtener la letra descargada o realizar scraping dinámico
    resultado = obtener_o_descargar_letra(cancion_id)
    
    if resultado and resultado.get('letra'):
        # Servir el texto plano con codificación UTF-8 explícita
        response = make_response(Response(resultado['letra'], mimetype='text/plain; charset=utf-8'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    
    # Fallback físico directo si el scraping falló
    if cancion.ruta_archivo_lrc:
        resolved_lrc = resolver_ruta_fisica(cancion.ruta_archivo_lrc)
        if resolved_lrc and os.path.exists(resolved_lrc):
            return send_file(resolved_lrc, mimetype='text/plain', max_age=0)

    current_app.logger.warning(f"[Lyrics Server] Letras no encontradas para id={cancion_id}.")
    return "Archivo de letras no encontrado", 404


# ==============================================================================
# SECCIÓN 4: SERVIDOR DE CARÁTULAS DE ÁLBUM (ALBUM ART) CON CASCADA DE FALLBACKS
# ==============================================================================

def _extract_cover_from_file(audio_path):
    """
    Auxiliar binario que extrae portadas incrustadas directamente dentro del archivo de audio.
    Soporta APIC en MP3 (ID3v2) y pictures en FLAC (Vorbis Comments).
    """
    if not audio_path or not os.path.exists(audio_path):
        return None
    try:
        from mutagen import File as MFile
        af = MFile(audio_path)
        if af is None:
            return None
        # FLAC y OGG
        if hasattr(af, 'pictures') and af.pictures:
            return af.pictures[0].data
        # MP3 ID3 APIC
        if hasattr(af, 'tags') and af.tags is not None:
            apic = af.tags.getall('APIC')
            if apic:
                return apic[0].data
    except Exception:
        pass
    return None


def _generate_thumbnail(img_source, size_name):
    """
    Genera una miniatura optimizada en formato WebP.
    img_source puede ser una ruta (str) o datos binarios (bytes).
    """
    sizes = {
        'small': 100,
        'medium': 300,
        'large': 600
    }
    target_size = sizes.get(size_name, 300)
    
    try:
        if isinstance(img_source, bytes):
            img = Image.open(io.BytesIO(img_source))
        else:
            img = Image.open(img_source)
            
        # Convertir a RGB si es necesario (para evitar errores con PNG/WebP transparencia al guardar JPEG/WebP)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Recorte cuadrado centrado (Crop to square)
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) / 2
        top = (height - min_dim) / 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        
        # Redimensionar
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        
        # Definir ruta de salida en el cache de miniaturas
        # Usamos un hash o simplemente el ID si lo tuviéramos, pero aquí pasamos el source.
        # Para simplificar, la función que llama manejará el nombre del archivo.
        return img
    except Exception as e:
        current_app.logger.error(f"[Art Server] Error generando miniatura: {e}")
        return None

@audio_bp.route('/album-art/<int:cancion_id>')
def servir_album_art(cancion_id):
    """
    Endpoint robusto de portadas de álbumes con optimización de miniaturas.
    """
    from flask import request
    size_name = request.args.get('size', 'medium') # default: medium
    
    # 1. Verificar si ya existe la miniatura en caché
    thumbnail_filename = f"thumb_{size_name}_{cancion_id}.webp"
    thumbnail_path = Config.THUMBNAILS_FOLDER / thumbnail_filename
    
    if thumbnail_path.exists():
        if thumbnail_path.stat().st_size > 0:
            resp = send_file(str(thumbnail_path), mimetype='image/webp')
            resp.headers['Cache-Control'] = 'public, max-age=86400, stale-while-revalidate=604800'
            return resp
        else:
            try:
                thumbnail_path.unlink()
            except Exception:
                pass

    # 4. Fallback visual total (SVG)
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
        <rect width="300" height="300" fill="#2a2a33" rx="12"/>
        <circle cx="150" cy="150" r="70" fill="none" stroke="#9ca3af" stroke-width="2" opacity="0.3"/>
        <text x="150" y="172" font-size="90" text-anchor="middle" fill="#9ca3af" font-family="sans-serif" opacity="0.5">&#9835;</text>
    </svg>'''

    # 2. Buscar la imagen original usando la cascada de niveles
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return placeholder_svg, 200, {'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=3600'}

    original_path = cancion.ruta_imagen_album
    img_source = None
    
    # --- Cascada de búsqueda ---
    # Nivel 0: Si el álbum tiene portada_url asociada (Deezer o ruta local)
    if cancion.album_obj and cancion.album_obj.portada_url:
        portada = cancion.album_obj.portada_url
        if portada.startswith(('http://', 'https://')):
            try:
                import requests as _requests
                resp_req = _requests.get(portada, timeout=5)
                if resp_req.ok:
                    img_source = resp_req.content
            except Exception as e:
                current_app.logger.error(f"[Art Server] Error descargando portada de album {portada}: {e}")
        elif os.path.exists(portada):
            img_source = portada

    if not img_source and original_path:
        resolved_art = resolver_ruta_fisica(original_path)
        if resolved_art and os.path.exists(resolved_art):
            img_source = resolved_art
        else:
            alt_path = Config.ALBUM_ART_FOLDER / Path(original_path).name
            if alt_path.exists():
                img_source = str(alt_path)

    # Nivel 2: Búsqueda heurística inteligente en la carpeta física del audio
    if not img_source and cancion.ruta_archivo_audio:
        resolved_audio = resolver_ruta_fisica(cancion.ruta_archivo_audio)
        if resolved_audio:
            from app.services.coverart import find_cover_in_audio_dir
            best_folder_cover = find_cover_in_audio_dir(resolved_audio)
            if best_folder_cover and os.path.exists(best_folder_cover):
                img_source = best_folder_cover

    # Nivel final: Extracción binaria incrustada como último recurso
    if not img_source and cancion.ruta_archivo_audio:
        resolved_audio = resolver_ruta_fisica(cancion.ruta_archivo_audio)
        if resolved_audio:
            img_source = _extract_cover_from_file(resolved_audio)

    # 3. Generar la miniatura si encontramos una fuente
    if img_source:
        img = _generate_thumbnail(img_source, size_name)
        if img:
            img.save(thumbnail_path, 'WEBP', quality=80)
            resp = send_file(str(thumbnail_path), mimetype='image/webp')
            resp.headers['Cache-Control'] = 'public, max-age=86400, stale-while-revalidate=604800'
            return resp

    return placeholder_svg, 200, {'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=3600'}


# ==============================================================================
# SECCIÓN 4.5: PORTADAS DINÁMICAS PARA DAILY MIXES
# ==============================================================================

def _generar_portada_daily_mix(mix_id, mix_nombre, fecha):
    """
    Genera una portada dinámica con gradientes y patrones para un Daily Mix.
    Cambia diariamente porque usa la fecha como semilla.
    """
    import hashlib
    from PIL import Image, ImageDraw
    
    paletas = {
        'Morning Vibes': [(255, 179, 71), (255, 107, 53), (200, 50, 30)],
        'Afternoon Chill': [(71, 181, 255), (53, 107, 255), (30, 50, 200)],
        'Night Beats': [(180, 71, 255), (107, 53, 200), (50, 30, 150)],
    }
    
    colores = paletas.get(mix_nombre, [(100, 100, 100), (50, 50, 50), (30, 30, 30)])
    seed_str = f"{mix_id}_{fecha}"
    semilla = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    
    size = 300
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    
    # Gradiente diagonal
    for y in range(size):
        t = y / size
        r = int(colores[0][0] * (1 - t) + colores[2][0] * t)
        g = int(colores[0][1] * (1 - t) + colores[2][1] * t)
        b = int(colores[0][2] * (1 - t) + colores[2][2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    # Capa de círculos decorativos con transparencia
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    import random
    rng = random.Random(semilla)
    for _ in range(20):
        cx = rng.randint(0, size)
        cy = rng.randint(0, size)
        cr = rng.randint(15, 60)
        alpha = rng.randint(20, 50)
        draw_overlay.ellipse(
            [cx - cr, cy - cr, cx + cr, cy + cr],
            fill=(255, 255, 255, alpha)
        )
    
    # Círculo central
    draw_overlay.ellipse([40, 40, size - 40, size - 40], outline=(255, 255, 255, 60), width=2)
    
    # Combinar
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    
    return img


@audio_bp.route('/daily-mix-cover/<int:mix_id>')
def servir_portada_daily_mix(mix_id):
    """
    Genera y sirve una portada visual dinámica para un Daily Mix.
    Cambia automáticamente cada día (basado en la fecha del mix).
    """
    from app.models import DailyMix
    from datetime import date
    import hashlib
    
    mix = db.session.get(DailyMix, mix_id)
    if not mix:
        # Fallback SVG
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
            <rect width="300" height="300" fill="#2a2a33" rx="12"/>
            <text x="150" y="172" font-size="60" text-anchor="middle" fill="#9ca3af" font-family="sans-serif">&#9835;</text>
        </svg>''', 200, {'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=3600'}
    
    fecha_str = mix.fecha.isoformat() if mix.fecha else date.today().isoformat()
    cache_dir = Path(Config.DATA_DIR) / 'daily_mix_covers' if hasattr(Config, 'DATA_DIR') else Config.THUMBNAILS_FOLDER / 'daily_mix_covers'
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    seed_key = f"{mix_id}_{fecha_str}"
    hash_name = hashlib.md5(seed_key.encode()).hexdigest()[:16]
    cache_path = cache_dir / f"{hash_name}.webp"
    
    if cache_path.exists():
        return send_file(str(cache_path), mimetype='image/webp', max_age=86400)
    
    img = _generar_portada_daily_mix(mix_id, mix.nombre, fecha_str)
    img.save(str(cache_path), 'WEBP', quality=85)
    
    return send_file(str(cache_path), mimetype='image/webp', max_age=86400)

@audio_bp.route('/service-worker.js')
def service_worker():
    """
    Sirve el archivo Service Worker de la PWA.
    Es mandatorio servirlo en la raíz ('/') para cumplir con el estándar W3C
    y permitir la interceptación de solicitudes en todo el dominio web.
    Desactiva las cabeceras HTTP de caché para forzar al navegador a verificar actualizaciones.
    """
    response = make_response(send_from_directory(current_app.static_folder, 'service-worker.js', mimetype='application/javascript'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
