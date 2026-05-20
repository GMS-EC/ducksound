# -*- coding: utf-8 -*-
"""
Controlador de Rutas de Audio y Multimedia - DuckSound
======================================================
Este módulo encapsula todas las funciones y endpoints relacionados con el motor de
reproducción de sonido y metadatos multimedia de la plataforma:
1. Iframe contenedor persistente para blindar el AudioContext.
2. Streaming de audio compatible con cabeceras de rango HTTP 206 (Conditional Byte-Range Streaming)
   para permitir rebobinar, adelantar y cargar búferes parciales en reproductores HTML5.
3. Servidor de carátulas (Album Art) con cascada de 6 niveles (incluyendo extracción directa
   "on the fly" de metadatos incrustados APIC/Vorbis y fallback elegante en gráficos vectoriales SVG).
4. Servidor de letras (Karaoke LRC) sincronizadas.
5. Inyección del script Service Worker de la PWA desde la raíz del dominio.
"""

import os
import io
import re
from pathlib import Path

from flask import Blueprint, render_template, send_file, send_from_directory, make_response, Response, current_app
from config import Config
from app.models import db, Cancion

# Servicios de letras desacoplados
from app.services.lyrics import obtener_o_descargar_letra

# Definición del Blueprint de Audio
audio_bp = Blueprint('audio', __name__)


# ==============================================================================
# SECCIÓN 1: VISTA DEL CONTENEDOR PERSISTENTE (PLAYER FRAME)
# ==============================================================================

@audio_bp.route('/player_frame')
def player_frame():
    """
    Sirve el marco iframe dedicado del reproductor para aislar y blindar el AudioContext.
    Evita cortes de sonido durante la navegación SPA del usuario.
    """
    return render_template('player_frame.html')


# ==============================================================================
# SECCIÓN 2: TRANSMISIÓN DE AUDIO CON CABECERAS DE RANGO (HTTP 206)
# ==============================================================================

@audio_bp.route('/audio/<int:cancion_id>')
def servir_audio(cancion_id):
    """
    Transmite el archivo de audio físico correspondiente a una canción.
    
    > [!IMPORTANT]
    > **Streaming Seekable de Alto Rendimiento:**
    > Utiliza `conditional=True` en `send_file` para indicarle a Flask/Waitress que procese
    > y responda nativamente con rangos parciales HTTP 206. Esto permite a los reproductores
    > HTML5 pausar, retroceder y adelantar de forma instantánea sin descargar todo el archivo.
    """
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return "Canción no encontrada", 404
        
    original_path = cancion.ruta_archivo_audio
    tried_paths = [original_path]

    # ─── PREFERENCIA DE CALIDAD DE AUDIO DEL USUARIO Y TRANSCODIFICACIÓN ───
    from flask import session
    usuario_id = session.get('user_id')
    calidad = 'lossless'
    if usuario_id:
        from app.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        if usuario:
            calidad = usuario.audio_quality or 'lossless'

    ext_original = Path(original_path).suffix.lower()
    
    if calidad == 'lossless':
        current_app.logger.info(f"[Audio Server] Calidad configurada: Hi-Res Lossless. Transmisión original sin pérdidas (bit-perfect) para ID {cancion_id}.")
    else:
        # Si la canción es un formato pesado sin compresión nativa (FLAC, WAV, OGG), transcodificar al bitrate elegido
        if ext_original in ['.flac', '.wav', '.ogg']:
            current_app.logger.info(f"[Audio Server] Formato de alta fidelidad {ext_original} detectado para ID {cancion_id}. Calidad elegida: {calidad}. Verificando transcodificación...")
            try:
                from app.services.transcoder import transcodificar_cancion
                ruta_transcodificada = transcodificar_cancion(cancion_id, calidad=calidad)
                if ruta_transcodificada and os.path.exists(ruta_transcodificada):
                    current_app.logger.info(f"[Audio Server] Sirviendo versión transcodificada ({calidad}) desde caché: {ruta_transcodificada}")
                    return send_file(ruta_transcodificada, mimetype='audio/mpeg', conditional=True, max_age=86400)
                else:
                    current_app.logger.warning(f"[Audio Server] Falló la transcodificación de ID {cancion_id} a {calidad}. Utilizando fallback original.")
            except Exception as e:
                current_app.logger.error(f"[Audio Server] Error en servicio de transcodificación: {e}")

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

    # 1. Intentar servir por la ruta exacta registrada directamente en disco
    if os.path.exists(original_path):
        current_app.logger.debug(f"[Audio Server] Sirviendo ruta física original: {original_path}")
        return send_file(original_path, mimetype=_mime_for(original_path), conditional=True, max_age=86400)

    # 2. Conversión Heurística de rutas Windows montadas en volúmenes Docker/Linux
    try:
        p = original_path.replace('\\\\', '/').replace(':/', ':/')
        # Detectar patrones del estilo 'G:/Musica/cancion.mp3' para mapearlas a '/music/'
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            rest = m.group(2)
            alt = '/music/' + rest
            tried_paths.append(alt)
            if os.path.exists(alt):
                current_app.logger.debug(f"[Audio Server] Sirviendo ruta mapeada Docker: {alt}")
                return send_file(alt, mimetype=_mime_for(alt), conditional=True, max_age=86400)
    except Exception as e:
        current_app.logger.error(f"[Audio Server] Error al mapear ruta Windows-Docker: {e}")

    # 3. Intentar como ruta relativa en el directorio de trabajo local de la app
    rel = os.path.join(os.getcwd(), original_path)
    tried_paths.append(rel)
    if os.path.exists(rel):
        current_app.logger.debug(f"[Audio Server] Sirviendo ruta relativa: {rel}")
        return send_file(rel, mimetype=_mime_for(rel), conditional=True, max_age=86400)

    current_app.logger.error(f"[Audio Server] Archivo no encontrado para id={cancion_id}. Intentos: {tried_paths}")
    return "Archivo de audio no encontrado", 404


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
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    
    # Fallback físico directo si el scraping falló
    original_path = cancion.ruta_archivo_lrc
    tried_paths = [original_path]

    if original_path and os.path.exists(original_path):
        return send_file(original_path, mimetype='text/plain', max_age=3600)

    # Conversión de rutas Windows a volúmenes Docker
    try:
        if original_path:
            p = original_path.replace('\\\\', '/').replace(':/', ':/')
            m = re.match(r'^([A-Za-z]):/(.*)', p)
            if m:
                alt = '/music/' + m.group(2)
                tried_paths.append(alt)
                if os.path.exists(alt):
                    return send_file(alt, mimetype='text/plain')
    except Exception as e:
        current_app.logger.error(f"[Lyrics Server] Error al mapear ruta física LRC: {e}")

    # Intentar buscar bajo ruta relativa
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        return send_file(rel, mimetype='text/plain')

    current_app.logger.warning(f"[Lyrics Server] Letras no encontradas para id={cancion_id}. Intentos: {tried_paths}")
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


@audio_bp.route('/album-art/<int:cancion_id>')
def servir_album_art(cancion_id):
    """
    Endpoint robusto de portadas de álbumes.
    Implementa una búsqueda en cascada de 6 niveles con fallback elegante a un gráfico SVG.
    """
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return "Canción no encontrada", 404

    original_path = cancion.ruta_imagen_album
    tried_paths = [original_path]

    def _image_mime_for(p):
        """Asigna cabeceras MIME de imagen idóneas."""
        ext = Path(p).suffix.lower()
        return {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }.get(ext, 'image/jpeg')

    # 1. Intentar ruta física original registrada
    if original_path and os.path.exists(original_path):
        return send_file(original_path, mimetype=_image_mime_for(original_path), max_age=86400)

    # 2. Carpeta centralizada de carátulas (ALBUM_ART_FOLDER)
    if original_path:
        alt_name = Path(original_path).name
        alt_path = Config.ALBUM_ART_FOLDER / alt_name
        tried_paths.append(str(alt_path))
        if alt_path.exists():
            return send_file(str(alt_path), mimetype=_image_mime_for(str(alt_path)))

    # 3. Carpeta clásica de archivos multimedia del proyecto
    if hasattr(Config, 'MEDIA_FOLDER') and original_path:
        old_path = Path(str(Config.MEDIA_FOLDER)) / 'album_art' / Path(original_path).name
        tried_paths.append(str(old_path))
        if old_path.exists():
            return send_file(str(old_path), mimetype=_image_mime_for(str(old_path)))

    # 4. Volumen docker legacy '/music/album_art/'
    if original_path:
        docker_legacy = Path('/music/album_art') / Path(original_path).name
        tried_paths.append(str(docker_legacy))
        if docker_legacy.exists():
            return send_file(str(docker_legacy), mimetype=_image_mime_for(str(docker_legacy)))

    # 5. Mapeo de sistemas Windows/Docker
    try:
        if original_path:
            p = original_path.replace('\\\\', '/').replace(':/', ':/')
            m = re.match(r'^([A-Za-z]):/(.*)', p)
            if m:
                alt = '/music/' + m.group(2)
                tried_paths.append(alt)
                if os.path.exists(alt):
                    return send_file(alt, mimetype=_image_mime_for(alt))
    except Exception as e:
        current_app.logger.error(f"[Art Server] Error al mapear carátula Windows-Docker: {e}")

    # 6. Intentar ruta relativa local
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        return send_file(rel, mimetype=_image_mime_for(rel))

    # 7. EXTRACCIÓN BINARIA: Extraer carátula incrustada al vuelo en el archivo físico
    img_data = _extract_cover_from_file(cancion.ruta_archivo_audio)
    if img_data is None and cancion.ruta_archivo_audio:
        # Reintentar la extracción mapeando la ruta de audio en Docker si fuese necesario
        p = cancion.ruta_archivo_audio.replace('\\\\', '/').replace(':/', ':/')
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            alt = '/music/' + m.group(2)
            tried_paths.append(f"audio_fallback:{alt}")
            img_data = _extract_cover_from_file(alt)
            
    if img_data:
        current_app.logger.debug(f"[Art Server] Portada extraída con éxito de tags ID3/APIC para: {cancion.titulo}")
        return send_file(io.BytesIO(img_data), mimetype='image/jpeg')

    # Fallback visual total: Servidor de marcador SVG vectorial moderno
    current_app.logger.warning(f"[Art Server] Portada no encontrada para id={cancion_id}. Serviendo SVG. Intentos: {tried_paths}")
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
        <rect width="300" height="300" fill="#2a2a33" rx="12"/>
        <circle cx="150" cy="150" r="70" fill="none" stroke="#9ca3af" stroke-width="2" opacity="0.3"/>
        <text x="150" y="172" font-size="90" text-anchor="middle" fill="#9ca3af" font-family="sans-serif" opacity="0.5">&#9835;</text>
    </svg>'''
    return placeholder_svg, 200, {'Content-Type': 'image/svg+xml'}


# ==============================================================================
# SECCIÓN 5: SERVICE WORKER DE LA PWA (SERVIR EN LA RAÍZ)
# ==============================================================================

@audio_bp.route('/service-worker.js')
def service_worker():
    """
    Sirve el archivo Service Worker de la PWA.
    Es mandatorio servirlo en la raíz ('/') para cumplir con el estándar W3C
    y permitir la interceptación de solicitudes en todo el dominio web.
    Desactiva las cabeceras HTTP de caché para forzar al navegador a verificar actualizaciones.
    """
    response = make_response(send_from_directory('static/js', 'service-worker.js', mimetype='application/javascript'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
