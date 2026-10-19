# -*- coding: utf-8 -*-
"""
Controlador de Rutas de API JSON (AJAX) - DuckSound
===================================================
Este módulo unifica todos los endpoints auxiliares y de servicios RESTful que alimentan
la aplicación de una sola página (SPA) y los scripts del frontend en el navegador:
1. Búsqueda predictiva y normalizada global (motor de búsqueda rápida).
2. Listados de canciones y álbumes filtrados por artistas para la navegación ágil.
3. Consultas de metadatos acústicos avanzados (BPM, Dynamic Range, Nyquist, RMS).
4. Motor de recomendación de canciones similares acústicamente y artistas relacionados.
5. Control y CRUD de colecciones/playlists de usuarios (creación, adición de tracks/álbumes/artistas).
6. Control de Favoritos ("Me gusta") con interruptores atómicos (toggle).
7. Registro en tiempo real de audiciones en el historial (HistorialEscucha) con respeto de privacidad.
8. Consulta de avance de tareas asíncronas en segundo plano (Redis RQ wrapper para barras de carga).
9. Perfil de configuración de usuario (preferencias, apodo, password, tracking).
10. Traducción dinámica de letras mediante APIs libres con fallback automático.
"""

import time
import re
import secrets
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, jsonify, request, session, url_for, current_app, Response
from sqlalchemy import func, desc
from app.models import db, Usuario, Artista, Album, Playlist, Cancion, Favorito, Coleccion, DailyMix, HistorialEscucha, SesionActiva, AlbumGuardado
from app.services.queue import get_connection as get_redis_connection
import json

# Importaciones de servicios desacoplados
from app.services.lyrics import obtener_o_descargar_letra
from app.services.recommender import get_similar_songs
from app.services.queue import progress_get
from app.services.metadata import get_mb_progress
from app.services.color import extraer_colores_imagen
from app.services.events import event_bus
from app.services.silence import detect_silence_padding
from app.services.tagger import read_audio_tags, write_audio_tags

# Definición del Blueprint de API
api_bp = Blueprint('api', __name__)


# ==============================================================================
# SECCIÓN 0: TOKEN CSRF PARA PROTECCIÓN DE FORMULARIOS
# ==============================================================================

@api_bp.route('/api/csrf-token')
def csrf_token():
    """Expone el token CSRF actual para que el frontend lo incluya en peticiones POST."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return jsonify({'csrf_token': session['_csrf_token']})


# ==============================================================================
# SECCIÓN 1: MOTOR DE BÚSQUEDA NORMALIZADA E INSTANTÁNEA
# ==============================================================================

@api_bp.route('/api/search', methods=['GET'])
def api_search():
    """
    Endpoint principal del motor de búsqueda global con RapidFuzz y caché de Redis.
    Aplica concordancia difusa (Fuzzy Matching con scoring WRatio), tolerancia a errores tipográficos,
    e insensibilidad a mayúsculas y acentos en canciones, artistas y álbumes.
    Calcula el 'top_result' (Mejor Resultado estilo Spotify) para destacar el elemento principal.
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'top_result': None, 'songs': [], 'artists': [], 'albums': []})

    # Intentar obtener la respuesta desde la caché de Redis
    cache_key = f"ducksound:cache:search:fuzzy:{q.lower()}"
    try:
        r = get_redis_connection()
        if r:
            cached_data = r.get(cache_key)
            if cached_data:
                return Response(cached_data, mimetype='application/json')
    except Exception as e:
        current_app.logger.warning(f"[Cache Search] Error leyendo de Redis: {e}")

    from rapidfuzz import fuzz
    from app.services.parsers import normalize_search_text
    
    q_norm = normalize_search_text(q)
    term = f'%{q}%'

    # 1. BÚSQUEDA DE CANCIONES (Piscina Inteligente de Candidatos + Scoring)
    # Direct matches by title, artist, album, plus popular pool
    candidate_songs = {}
    
    for s in Cancion.query.filter(Cancion.titulo.ilike(term)).limit(40).all():
        candidate_songs[s.id] = s
    for s in Cancion.query.join(Artista).filter(Artista.nombre.ilike(term)).limit(40).all():
        candidate_songs[s.id] = s
    for s in Cancion.query.join(Album).filter(Album.titulo.ilike(term)).limit(40).all():
        candidate_songs[s.id] = s
    for s in Cancion.query.order_by(Cancion.play_count.desc(), Cancion.id.desc()).limit(150).all():
        if s.id not in candidate_songs and len(candidate_songs) < 250:
            candidate_songs[s.id] = s

    scored_songs = []
    for s in candidate_songs.values():
        t_norm = normalize_search_text(s.titulo)
        comb_norm = normalize_search_text(f"{s.artista_obj.nombre} {s.titulo}" if s.artista_obj else s.titulo)
        score = max(fuzz.WRatio(q_norm, t_norm), fuzz.WRatio(q_norm, comb_norm))
        if q.lower() in (s.titulo or '').lower():
            score = max(score, 88.0)
        if score >= 60:
            scored_songs.append((score, s))

    scored_songs.sort(key=lambda x: (x[0], x[1].play_count or 0), reverse=True)
    top_songs = [s for _, s in scored_songs[:10]]

    # 2. BÚSQUEDA DE ARTISTAS (Fuzzy & Scoring)
    all_artists = Artista.query.all()
    scored_artists = []
    for a in all_artists:
        a_norm = normalize_search_text(a.nombre)
        score = fuzz.WRatio(q_norm, a_norm)
        if q.lower() in a.nombre.lower():
            score = max(score, 90.0)
        if score >= 60:
            scored_artists.append((score, a))

    scored_artists.sort(key=lambda x: x[0], reverse=True)
    top_artists = [a for _, a in scored_artists[:6]]

    # 3. BÚSQUEDA DE ÁLBUMES (Fuzzy & Scoring)
    all_albums = Album.query.all()
    scored_albums = []
    for al in all_albums:
        al_norm = normalize_search_text(al.titulo)
        al_comb = normalize_search_text(f"{al.artista.nombre} {al.titulo}" if al.artista else al.titulo)
        score = max(fuzz.WRatio(q_norm, al_norm), fuzz.WRatio(q_norm, al_comb))
        if q.lower() in al.titulo.lower():
            score = max(score, 90.0)
        if score >= 60:
            scored_albums.append((score, al))

    scored_albums.sort(key=lambda x: x[0], reverse=True)
    top_albums = [al for _, al in scored_albums[:6]]

    # 4. DETERMINACIÓN DEL "TOP RESULT"
    # Jerarquía en empates: Artista > Álbum > Canción
    best_cand = None
    best_score = 0.0

    if scored_artists:
        a_score, a_obj = scored_artists[0]
        if a_score >= 65 and a_score >= best_score:
            best_score = a_score
            best_cand = {
                'type': 'artist',
                'id': a_obj.id,
                'nombre': a_obj.nombre,
                'foto': a_obj.foto_url or '',
                'score': round(a_score, 1)
            }

    if scored_albums:
        al_score, al_obj = scored_albums[0]
        # Si el álbum supera al artista por al menos 5 puntos o no hay artista
        if al_score >= 65 and (best_cand is None or al_score > best_score + 5.0):
            best_score = al_score
            first_song_id = al_obj.canciones[0].id if al_obj.canciones else None
            cover_url = url_for('audio.servir_album_art', cancion_id=first_song_id) if first_song_id else None
            best_cand = {
                'type': 'album',
                'id': al_obj.id,
                'titulo': al_obj.titulo,
                'artista': al_obj.artista.nombre if al_obj.artista else None,
                'cover': cover_url,
                'score': round(al_score, 1)
            }

    if scored_songs:
        s_score, s_obj = scored_songs[0]
        # Si la canción supera significativamente al candidato previo
        if s_score >= 70 and (best_cand is None or s_score > best_score + 8.0):
            best_cand = {
                'type': 'song',
                'id': s_obj.id,
                'titulo': s_obj.titulo,
                'artista': s_obj.artista_obj.nombre if s_obj.artista_obj else None,
                'audio': url_for('audio.servir_audio', cancion_id=s_obj.id),
                'cover': url_for('audio.servir_album_art', cancion_id=s_obj.id),
                'lyrics': url_for('audio.servir_lyrics', cancion_id=s_obj.id),
                'score': round(s_score, 1)
            }

    response_data = {
        'top_result': best_cand,
        'songs': [{
            'id': s.id,
            'titulo': s.titulo,
            'artista': s.artista_obj.nombre if s.artista_obj else None,
            'audio': url_for('audio.servir_audio', cancion_id=s.id),
            'cover': url_for('audio.servir_album_art', cancion_id=s.id),
            'lyrics': url_for('audio.servir_lyrics', cancion_id=s.id),
        } for s in top_songs],
        'artists': [{
            'id': a.id,
            'nombre': a.nombre,
            'foto': a.foto_url or '',
        } for a in top_artists],
        'albums': [{
            'id': al.id,
            'titulo': al.titulo,
            'artista': al.artista.nombre if al.artista else None,
        } for al in top_albums],
    }

    try:
        r = get_redis_connection()
        if r:
            r.setex(cache_key, 300, json.dumps(response_data))
    except Exception as e:
        current_app.logger.warning(f"[Cache Search] Error escribiendo en Redis: {e}")

    return jsonify(response_data)


def _seconds_to_time_string(seconds: int) -> str:
    """Convierte segundos a una representación humana concisa."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours} hr{'s' if hours > 1 else ''}, {minutes} min{'s' if minutes > 1 else ''}" if minutes > 0 else f"{hours} hr{'s' if hours > 1 else ''}"
    if minutes > 0:
        return f"{minutes} min{'s' if minutes > 1 else ''}"
    return f"{seconds % 60} seg"


@api_bp.route('/api/stats', methods=['GET'])
def api_stats():
    """
    Endpoint de estadísticas de escucha dinámicas por ventana de tiempo.
    Soporta los parámetros de consulta: period=week|month|day|all (por defecto 'all').
    """
    from datetime import datetime, timedelta
    from app.models import HistorialEscucha

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'No autorizado'}), 401

    period = request.args.get('period', 'all').lower()
    now = datetime.utcnow()
    start_date = None

    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'day':
        start_date = now - timedelta(days=1)

    # 1. Total plays y skips
    q_base = HistorialEscucha.query.filter(HistorialEscucha.usuario_id == user_id)
    if start_date:
        q_base = q_base.filter(HistorialEscucha.reproducido_en >= start_date)

    total_plays = q_base.filter(HistorialEscucha.skip == False).count()
    total_skips = q_base.filter(HistorialEscucha.skip == True).count()

    # 2. Top canciones en el período
    top_songs_q = db.session.query(
        Cancion, func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.skip == False
    )
    if start_date:
        top_songs_q = top_songs_q.filter(HistorialEscucha.reproducido_en >= start_date)
    top_songs = top_songs_q.group_by(Cancion).order_by(desc('plays')).limit(10).all()

    # 3. Top artistas en el período
    top_artists_q = db.session.query(
        Artista.id, Artista.nombre, Artista.foto_url, func.count(HistorialEscucha.id).label('plays')
    ).select_from(HistorialEscucha)\
     .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
     .join(Artista, Cancion.artista_id == Artista.id)\
     .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False)
    if start_date:
        top_artists_q = top_artists_q.filter(HistorialEscucha.reproducido_en >= start_date)
    top_artists = top_artists_q.group_by(Artista.id, Artista.nombre, Artista.foto_url).order_by(desc('plays')).limit(8).all()

    # 4. Duración acumulada
    dur_q = db.session.query(func.sum(Cancion.duracion))\
        .join(HistorialEscucha)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False, Cancion.duracion.isnot(None))
    if start_date:
        dur_q = dur_q.filter(HistorialEscucha.reproducido_en >= start_date)
    total_seconds = int(dur_q.scalar() or 0)

    return jsonify({
        'period': period,
        'total_plays': total_plays,
        'total_skips': total_skips,
        'total_seconds': total_seconds,
        'total_hours': round(total_seconds / 3600.0, 1),
        'time_string': _seconds_to_time_string(total_seconds),
        'top_songs': [{
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else None,
            'cover': url_for('audio.servir_album_art', cancion_id=c.id),
            'audio': url_for('audio.servir_audio', cancion_id=c.id),
            'plays': plays
        } for c, plays in top_songs],
        'top_artists': [{
            'id': a_id,
            'nombre': a_nombre,
            'foto': a_foto or '',
            'plays': plays
        } for a_id, a_nombre, a_foto, plays in top_artists]
    })



# ==============================================================================
# SECCIÓN 2: APIS DEL CATÁLOGO DE CANCIONES Y ÁLBUMES
# ==============================================================================

@api_bp.route('/api/canciones')
def api_canciones():
    """
    Retorna la lista de canciones indexadas en formato JSON.
    Soporta parámetros de consulta opcionales 'limit' y 'offset' para paginación.
    Devuelve {'total': N, 'data': [...]} cuando se usa paginación.
    """
    try:
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        
        query = Cancion.query.order_by(Cancion.titulo)
        
        # Calcular total si hay paginación
        if limit is not None or offset is not None:
            total = query.count()
            
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            
            canciones = query.all()
            return jsonify({'total': total, 'data': [c.to_dict() for c in canciones]})
        
        # Sin paginación: devuelve lista plana (compatibilidad hacia atrás)
        canciones = query.all()
        return jsonify([c.to_dict() for c in canciones])
    except Exception as e:
        current_app.logger.error(f"[API Canciones] Error en paginación: {e}")
        return jsonify([]), 500


@api_bp.route('/api/cancion/<int:cancion_id>')
def api_cancion(cancion_id):
    """Retorna los metadatos serializados de una única canción."""
    cancion = Cancion.query.get_or_404(cancion_id)
    return jsonify(cancion.to_dict())


@api_bp.route('/api/artist/<int:artist_id>/albums', methods=['GET'])
def api_albums_by_artist(artist_id):
    """Retorna los álbumes oficiales asociados a un artista."""
    artista = Artista.query.get_or_404(artist_id)
    albums = Album.query.filter_by(artista_id=artista.id).order_by(Album.anio.desc()).all()
    result = []
    for a in albums:
        result.append({
            'id': a.id,
            'titulo': a.titulo,
            'anio': a.anio,
            'portada_url': a.portada_url,
            'artista_id': a.artista_id
        })
    return jsonify(result)


@api_bp.route('/api/artist/<int:artist_id>/canciones', methods=['GET'])
def api_songs_by_artist(artist_id):
    """
    Retorna la lista jerárquica de canciones de un artista para el reproductor SPA,
    clasificándolas cronológicamente por disco y luego por número de pista física.
    """
    artista = Artista.query.get_or_404(artist_id)
    songs = Cancion.query.filter_by(artista_id=artista.id).all()
    
    albums_dict = {}
    for s in songs:
        album_id = s.album_id if s.album_id is not None else 0
        if album_id not in albums_dict:
            albums_dict[album_id] = {
                'album': s.album_obj,
                'songs': []
            }
        albums_dict[album_id]['songs'].append(s)
    
    def sort_album_key(item):
        album = item[1]['album']
        if album and hasattr(album, 'anio') and album.anio:
            return (album.anio, album.id or 0)
        return (9999, item[0])
    
    albums_ordenados = sorted(albums_dict.items(), key=sort_album_key)
    
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
    result = []
    for album_id, album_data in albums_ordenados:
        album = album_data['album']
        album_songs = album_data['songs']
        
        discos_dict = {}
        for s in album_songs:
            disc_num = s.numero_disco if s.numero_disco is not None else 1
            if disc_num not in discos_dict:
                discos_dict[disc_num] = []
            discos_dict[disc_num].append(s)
        
        discos_ordenados = sorted(discos_dict.items())
        for disc_num, canciones_disco in discos_ordenados:
            canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
            for c in canciones_ordenadas:
                result.append({
                    'id': c.id,
                    'titulo': c.titulo,
                    'artista': artista.nombre,
                    'album': album.titulo if album else 'Desconocido',
                    'audio': url_for('audio.servir_audio', cancion_id=c.id),
                    'cover': url_for('audio.servir_album_art', cancion_id=c.id, size='small'),
                    'lyrics': url_for('audio.servir_lyrics', cancion_id=c.id),
                    'numero_pista': c.numero_pista,
                    'numero_disco': c.numero_disco
                })
    
    return jsonify(result)


@api_bp.route('/api/album/<int:album_id>/canciones', methods=['GET'])
def api_songs_by_album(album_id):
    """Retorna la lista ordenada de canciones contenidas en un álbum específico."""
    album = Album.query.get_or_404(album_id)
    songs = Cancion.query.filter_by(album_id=album.id).all()
    
    discos_dict = {}
    for s in songs:
        disc_num = s.numero_disco if s.numero_disco is not None else 1
        if disc_num not in discos_dict:
            discos_dict[disc_num] = []
        discos_dict[disc_num].append(s)
    
    discos_ordenados = sorted(discos_dict.items())
    
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
    result = []
    for disc_num, canciones_disco in discos_ordenados:
        canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
        for c in canciones_ordenadas:
            result.append({
                'id': c.id,
                'titulo': c.titulo,
                'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
                'audio': url_for('audio.servir_audio', cancion_id=c.id),
                'cover': url_for('audio.servir_album_art', cancion_id=c.id),
                'lyrics': url_for('audio.servir_lyrics', cancion_id=c.id),
                'numero_pista': c.numero_pista,
                'numero_disco': c.numero_disco
            })
    
    return jsonify(result)


# ==============================================================================
# SECCIÓN 3: ENDPOINTS DE RECOMENDACIÓN DIARIA Y MIXES
# ==============================================================================

@api_bp.route('/api/daily-mix/<int:mix_id>/songs', methods=['GET'])
def api_daily_mix_songs(mix_id):
    """Devuelve la cola de reproducción del Mix Diario solicitado."""
    mix = DailyMix.query.get_or_404(mix_id)
    if mix.usuario_id != session.get('user_id'):
        return jsonify({'error': 'Acceso denegado'}), 403
        
    canciones = [
        {
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
            'audio': url_for('audio.servir_audio', cancion_id=c.id),
            'cover': url_for('audio.servir_album_art', cancion_id=c.id),
            'lyrics': url_for('audio.servir_lyrics', cancion_id=c.id)
        }
        for c in mix.canciones
    ]
    return jsonify(canciones)


# ==============================================================================
# SECCIÓN 4: CONSULTA DE ESPECIFICACIONES TÉCNICAS ACÚSTICAS (AUDIO INFO)
# ==============================================================================

@api_bp.route('/api/audio-info/<int:cancion_id>', methods=['GET'])
def api_audio_info(cancion_id):
    """Retorna detalles acústicos y de resolución física (BPM, Dynamic Range, RMS) de una canción."""
    c = db.session.get(Cancion, cancion_id)
    if not c:
        return jsonify({'error': 'Not found'}), 404
        
    return jsonify({
        'id': c.id,
        'titulo': c.titulo,
        'sample_rate': c.sample_rate,
        'bit_depth': c.bit_depth,
        'channels': c.channels,
        'duration': c.duracion,
        'nyquist_freq': c.nyquist_freq,
        'dynamic_range': c.dynamic_range,
        'peak_level': c.peak_level,
        'rms_level': c.rms_level,
        'total_samples': c.total_samples,
        'bit_rate': c.bit_rate,
        'genero': c.genero,
        'bpm': c.bpm
    })


# ==============================================================================
# SECCIÓN 5: MOTORES DE RECOMENDACIÓN ACÚSTICA (SIMILITUD Y ARTISTAS RELACIONADOS)
# ==============================================================================

@api_bp.route('/api/similares/<int:cancion_id>', methods=['GET'])
def api_similares(cancion_id):
    """
    Retorna pistas recomendadas acústicamente similares con caché de Redis.
    Utiliza el motor de cálculo matemático de embeddings y vecinos.
    """
    cache_key = f"ducksound:cache:similares:{cancion_id}"
    try:
        r = get_redis_connection()
        cached_data = r.get(cache_key)
        if cached_data:
            return Response(cached_data, mimetype='application/json')
    except Exception as e:
        current_app.logger.warning(f"[Cache Similares] Error leyendo de Redis: {e}")

    try:
        similares = get_similar_songs(cancion_id, top_k=10)
        
        # Guardar en caché con TTL de 1 hora (3600 segundos)
        try:
            r = get_redis_connection()
            r.setex(cache_key, 3600, json.dumps(similares))
        except Exception as ec:
            current_app.logger.warning(f"[Cache Similares] Error escribiendo en Redis: {ec}")
            
        return jsonify(similares)
    except Exception as e:
        current_app.logger.error(f"Error calculando canciones similares: {e}")
        return jsonify([]), 200


@api_bp.route('/api/related/artists/<int:artist_id>')
def related_artists(artist_id):
    """
    Motor de recomendaciones de Artistas Similares con caché de Redis.
    Aplica una cascada inteligente de 4 estrategias:
    1. Género Compartido: Artistas con canciones del mismo género.
    2. Colaboraciones o Compilaciones: Artistas que comparten álbumes.
    3. Perfil Acústico Simétrico: Compara promedios de BPM, sonoridad RMS y Dynamic Range de sus tracks.
    4. Fallback: Recomienda los artistas más populares en volumen.
    """
    cache_key = f"ducksound:cache:related_artists:{artist_id}"
    try:
        r = get_redis_connection()
        cached_data = r.get(cache_key)
        if cached_data:
            return Response(cached_data, mimetype='application/json')
    except Exception as e:
        current_app.logger.warning(f"[Cache Related Artists] Error leyendo de Redis: {e}")

    artist = db.session.get(Artista, artist_id)
    if not artist:
        return jsonify({'error': 'Artista no encontrado'}), 404
        
    related_ids = set()
    related = []
    limit = 4

    # ESTRATEGIA 1: Coincidencia por género musical idéntico
    genres = db.session.query(Cancion.genero).filter(
        Cancion.artista_id == artist_id, Cancion.genero.isnot(None)
    ).distinct().all()
    genre_list = [g[0] for g in genres if g[0]]

    if genre_list:
        genre_matches = db.session.query(Artista).join(Cancion).filter(
            Cancion.genero.in_(genre_list),
            Artista.id != artist_id
        ).distinct().all()
        for a in genre_matches:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)

    # ESTRATEGIA 2: Álbumes en común o compilaciones cruzadas
    if len(related) < limit:
        album_ids = db.session.query(Album.id).filter(Album.artista_id == artist_id).subquery()
        same_album_artists = db.session.query(Artista).join(Album).join(Cancion).filter(
            Album.id.in_(db.session.query(Cancion.album_id).filter(
                Cancion.album_id.in_(album_ids),
                Cancion.artista_id != artist_id
            )),
            Artista.id != artist_id
        ).distinct().all()
        for a in same_album_artists:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)
                if len(related) >= limit:
                    break

    # ESTRATEGIA 3: Perfil acústico similar (BPM, rango dinámico, volumen RMS promedio)
    if len(related) < limit:
        avg_profile = db.session.query(
            db.func.avg(Cancion.bpm),
            db.func.avg(Cancion.dynamic_range),
            db.func.avg(Cancion.rms_level)
        ).filter(Cancion.artista_id == artist_id).first()

        if avg_profile and avg_profile[0] is not None:
            bpm, dyn, rms = avg_profile
            tolerance_bpm = 20
            tolerance_dyn = 5
            
            acoustic_matches = db.session.query(
                Artista,
                db.func.count(Cancion.id).label('song_count')
            ).join(Cancion).filter(
                Cancion.bpm.between(bpm - tolerance_bpm, bpm + tolerance_bpm),
                Cancion.dynamic_range.between(dyn - tolerance_dyn, dyn + tolerance_dyn),
                Artista.id != artist_id
            ).group_by(Artista.id).order_by(db.func.count(Cancion.id).desc()).limit(limit).all()

            for a, _ in acoustic_matches:
                if a.id not in related_ids:
                    related_ids.add(a.id)
                    related.append(a)
                    if len(related) >= limit:
                        break

    # ESTRATEGIA 4: Fallback de popularidad
    if len(related) < limit:
        popular = db.session.query(Artista).join(Cancion).filter(
            Artista.id != artist_id
        ).group_by(Artista.id).order_by(
            db.func.count(Cancion.id).desc()
        ).limit(limit - len(related)).all()
        for a in popular:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)
                if len(related) >= limit:
                    break

    response_payload = [{
        'id': a.id,
        'nombre': a.nombre,
        'nombre_normalizado': a.nombre_normalizado,
        'foto': a.foto_url or '',
        'album_count': len(a.albums)
    } for a in related[:limit]]

    # Guardar en caché con TTL de 1 hora (3600 segundos)
    try:
        r = get_redis_connection()
        r.setex(cache_key, 3600, json.dumps(response_payload))
    except Exception as e:
        current_app.logger.warning(f"[Cache Related Artists] Error escribiendo en Redis: {e}")

    return jsonify(response_payload)


# ==============================================================================
# SECCIÓN 6: SERVICIO DE LETRAS SINCRONIZADAS LRC
# ==============================================================================

@api_bp.route('/api/cancion/<int:cancion_id>/lyrics', methods=['GET'])
def api_cancion_lyrics(cancion_id):
    """
    Retorna la letra sincronizada y formateada en JSON desde la caché de letras.
    Peticiona descarga en segundo plano automática si no se ha indexado aún.
    """
    try:
        resultado = obtener_o_descargar_letra(cancion_id)
        if resultado:
            return jsonify(resultado), 200
        else:
            return jsonify({'error': 'Letra no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error en api_cancion_lyrics: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500


@api_bp.route('/api/album/<int:album_id>/color', methods=['GET'])
@api_bp.route('/api/album/<int:album_id>/colors', methods=['GET'])
def api_album_color(album_id):
    """Retorna la paleta de color ambiental de un álbum (dominante, acento y gradiente)."""
    from pathlib import Path
    from config import Config
    from app.models import Album
    from app.services.color import extraer_colores_imagen, _color_por_defecto
    album = db.session.get(Album, album_id)
    if not album:
        return jsonify(_color_por_defecto()), 200

    img_path = album.portada_url
    if not img_path or not Path(img_path).exists():
        # Buscar en miniaturas de sus canciones
        for c in album.canciones:
            thumb = Config.THUMBNAILS_FOLDER / f"thumb_small_{c.id}.webp"
            if thumb.exists():
                img_path = str(thumb)
                break

    return jsonify(extraer_colores_imagen(img_path)), 200


@api_bp.route('/api/cancion/<int:cancion_id>/color', methods=['GET'])
@api_bp.route('/api/song/<int:cancion_id>/colors', methods=['GET'])
def api_cancion_color(cancion_id):
    """Retorna la paleta de color ambiental asociada a una canción."""
    from pathlib import Path
    from config import Config
    from app.models import Cancion
    from app.services.color import extraer_colores_imagen, _color_por_defecto
    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return jsonify(_color_por_defecto()), 200

    img_path = cancion.ruta_imagen_album or (cancion.album_obj.portada_url if cancion.album_obj else None)
    if not img_path or not Path(img_path).exists():
        thumb = Config.THUMBNAILS_FOLDER / f"thumb_small_{cancion.id}.webp"
        if thumb.exists():
            img_path = str(thumb)

    return jsonify(extraer_colores_imagen(img_path)), 200

# ==============================================================================
# SECCIÓN 6.5: SMART MIXES & RECIPES (TOP STREAMED, RECENT, RADIOS)
# ==============================================================================

@api_bp.route('/api/cancion/<int:cancion_id>/radio', methods=['GET'])
@api_bp.route('/api/mixes/radio/<int:cancion_id>', methods=['GET'])
def api_cancion_radio(cancion_id):
    """
    Genera una lista de reproducción inteligente tipo 'Radio' a partir de la canción base,
    usando similitud acústica híbrida (BPM, dynamic range, RMS) y compatibilidad de género/artista.
    """
    from app.services.recipes import get_radio_mix
    limit = request.args.get('limit', 25, type=int)
    resultado = get_radio_mix(cancion_id, limit=limit)
    if not resultado:
        return jsonify({'error': 'Canción no encontrada o sin recomendaciones'}), 404
    return jsonify(resultado), 200


@api_bp.route('/api/mixes/top', methods=['GET'])
@api_bp.route('/api/songs/top', methods=['GET'])
def api_mixes_top():
    """
    Retorna la mezcla de canciones más reproducidas (Top Streamed).
    Prioriza el historial del usuario autenticado si existe sesión.
    """
    from app.services.recipes import get_top_mix
    user_id = session.get('user_id')
    limit = request.args.get('limit', 25, type=int)
    resultado = get_top_mix(user_id=user_id, limit=limit)
    return jsonify(resultado), 200


@api_bp.route('/api/mixes/recent', methods=['GET'])
@api_bp.route('/api/songs/recent', methods=['GET'])
def api_mixes_recent():
    """
    Retorna la mezcla de adiciones recientes o canciones escuchadas recientemente.
    """
    from app.services.recipes import get_recent_mix
    user_id = session.get('user_id')
    limit = request.args.get('limit', 25, type=int)
    resultado = get_recent_mix(user_id=user_id, limit=limit)
    return jsonify(resultado), 200


@api_bp.route('/api/mixes/artist/<int:artista_id>', methods=['GET'])
def api_mixes_artist(artista_id):
    """
    Genera una estación de radio centrada en un artista y artistas con afinidad estilística.
    """
    from app.services.recipes import get_artist_radio
    limit = request.args.get('limit', 25, type=int)
    resultado = get_artist_radio(artista_id, limit=limit)
    if not resultado:
        return jsonify({'error': 'Artista no encontrado'}), 404
    return jsonify(resultado), 200


@api_bp.route('/api/mixes', methods=['GET'])
def api_mixes_overview():
    """
    Retorna el catálogo o resumen de todas las mezclas inteligentes disponibles para el usuario.
    """
    from app.services.recipes import get_smart_mixes_overview
    user_id = session.get('user_id')
    overview = get_smart_mixes_overview(user_id=user_id)
    return jsonify(overview), 200


# ==============================================================================
# SECCIÓN 7: API DE COLECCIONES (PLAYLISTS PERSONALIZADAS DE USUARIO)
# ==============================================================================

@api_bp.route('/api/colecciones/crear', methods=['POST'])
def api_colecciones_crear():
    """Crea una nueva colección o playlist para el usuario actual."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify({'error': 'No auth'}), 401
    
    if request.is_json:
        data = request.get_json()
        nombre = data.get('nombre', '').strip()
        descripcion = data.get('descripcion', '').strip()
    else:
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
            
    c = Coleccion(nombre=nombre, descripcion=descripcion or None, usuario_id=usuario_id)
    db.session.add(c)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'ok': True, 'id': c.id, 'nombre': c.nombre})
    return redirect(url_for('main.coleccion_detail', coleccion_id=c.id))


@api_bp.route('/api/coleccion-lista', methods=['GET'])
def api_coleccion_lista():
    """Retorna una lista simplificada de playlists pertenecientes al usuario actual."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([])
    cols = Coleccion.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([{'id': c.id, 'nombre': c.nombre} for c in cols])


@api_bp.route('/api/colecciones/<int:coleccion_id>/add-album/<int:album_id>', methods=['POST'])
def api_coleccion_add_album(coleccion_id, album_id):
    """Añade todas las canciones de un álbum completo a una playlist."""
    usuario_id = session.get('user_id')
    c = Coleccion.query.get_or_404(coleccion_id)
    if c.usuario_id != usuario_id:
        return jsonify({'error': 'Forbidden'}), 403
        
    a = Album.query.get_or_404(album_id)
    for song in a.canciones:
      if song not in c.canciones:
        c.canciones.append(song)
    db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/api/colecciones/<int:coleccion_id>/add-artist/<int:artist_id>', methods=['POST'])
def api_coleccion_add_artist(coleccion_id, artist_id):
    """Vincula un artista a una playlist del usuario."""
    usuario_id = session.get('user_id')
    c = Coleccion.query.get_or_404(coleccion_id)
    if c.usuario_id != usuario_id:
        return jsonify({'error': 'Forbidden'}), 403
        
    a = Artista.query.get_or_404(artist_id)
    if a not in c.artistas:
        c.artistas.append(a)
        db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/api/colecciones/<int:coleccion_id>/add-cancion/<int:cancion_id>', methods=['POST'])
def api_coleccion_add_cancion(coleccion_id, cancion_id):
    """Añade una única canción a una playlist."""
    usuario_id = session.get('user_id')
    c = Coleccion.query.get_or_404(coleccion_id)
    if c.usuario_id != usuario_id:
        return jsonify({'error': 'Forbidden'}), 403
        
    song = Cancion.query.get_or_404(cancion_id)
    if song not in c.canciones:
        c.canciones.append(song)
        db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/api/playlist/<int:playlist_id>/songs', methods=['GET'])
def api_songs_by_playlist(playlist_id):
    """API para obtener las canciones de una playlist."""
    playlist = Playlist.query.get_or_404(playlist_id)
    canciones = [c.to_dict() for c in playlist.canciones]
    return jsonify(canciones)


# ==============================================================================
# SECCIÓN 8: API DE FAVORITOS ("ME GUSTA")
# ==============================================================================

@api_bp.route('/api/favoritos', methods=['GET'])
def api_favoritos_list():
    """Retorna la lista de IDs de canciones marcadas como favoritas del usuario."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([]), 200
    favoritos = Favorito.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([f.cancion_id for f in favoritos])


@api_bp.route('/api/favoritos/toggle/<int:cancion_id>', methods=['POST'])
def api_favoritos_toggle(cancion_id):
    """Alterna (agrega o elimina) el estado favorito de una canción."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify({'error': 'No autenticado'}), 401

    fav = Favorito.query.filter_by(usuario_id=usuario_id, cancion_id=cancion_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'liked': False})
    else:
        fav = Favorito(usuario_id=usuario_id, cancion_id=cancion_id)
        db.session.add(fav)
        db.session.commit()
        return jsonify({'liked': True})


@api_bp.route('/api/favoritos/canciones', methods=['GET'])
def api_favoritos_canciones():
    """Retorna diccionarios de datos de las canciones favoritas del usuario actual."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([]), 200

    canciones = Cancion.query.join(
        Favorito, Favorito.cancion_id == Cancion.id
    ).filter(
        Favorito.usuario_id == usuario_id
    ).order_by(Favorito.fecha_agregado.desc()).all()

    return jsonify([c.to_dict() for c in canciones])


# ==============================================================================
# SECCIÓN 9: BIBLIOTECA DE ÁLBUMES GUARDADOS
# ==============================================================================

@api_bp.route('/api/biblioteca/albums', methods=['GET'])
def api_biblioteca_albums():
    """Retorna la lista de álbumes guardados en la biblioteca del usuario."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([]), 200

    guardados = AlbumGuardado.query.filter_by(usuario_id=usuario_id)\
        .order_by(AlbumGuardado.fecha_agregado.desc()).all()

    result = []
    for g in guardados:
        al = db.session.get(Album, g.album_id)
        if al:
            artista_nombre = al.artista.nombre if al.artista else None
            artista_id = al.artista_id
            # Usa el ID de la primera canción del álbum para servir la portada
            primera_cancion = al.canciones[0] if al.canciones else None
            result.append({
                'id': al.id,
                'titulo': al.titulo,
                'anio': al.anio,
                'artista': artista_nombre,
                'artista_id': artista_id,
                'cancion_id': primera_cancion.id if primera_cancion else None,
                'fecha_guardado': g.fecha_agregado.isoformat() if g.fecha_agregado else None,
            })
    return jsonify(result)


@api_bp.route('/api/biblioteca/albums/<int:album_id>/toggle', methods=['POST'])
def api_biblioteca_album_toggle(album_id):
    """Guarda o elimina un álbum de la biblioteca del usuario."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify({'error': 'No autenticado'}), 401

    guardado = AlbumGuardado.query.filter_by(usuario_id=usuario_id, album_id=album_id).first()
    if guardado:
        db.session.delete(guardado)
        db.session.commit()
        return jsonify({'saved': False})
    else:
        nuevo = AlbumGuardado(usuario_id=usuario_id, album_id=album_id)
        db.session.add(nuevo)
        db.session.commit()
        return jsonify({'saved': True})


@api_bp.route('/api/biblioteca/albums/<int:album_id>/check', methods=['GET'])
def api_biblioteca_album_check(album_id):
    """Comprueba si un álbum está guardado en la biblioteca del usuario."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify({'saved': False})
    guardado = AlbumGuardado.query.filter_by(usuario_id=usuario_id, album_id=album_id).first()
    return jsonify({'saved': bool(guardado)})


# ==============================================================================
# SECCIÓN 10: REGISTRO DE AUDICIONES Y ACTIVIDAD (PLAY LOGGER)
# ==============================================================================

@api_bp.route('/api/play/<int:cancion_id>', methods=['POST'])
def api_register_play(cancion_id):
    """
    Registra una canción en el historial de audición y actualiza los contadores
    rápidos desnormalizados (play_count, play_duration, last_played).
    Respeta la privacidad del usuario en 'HistorialEscucha'.
    """
    data = request.get_json(silent=True) or {}
    is_skip = data.get('skip', False)

    cancion = db.session.get(Cancion, cancion_id)
    if cancion and not is_skip:
        cancion.play_count = (cancion.play_count or 0) + 1
        dur = data.get('duration') or cancion.duracion or 0
        try:
            cancion.play_duration = (cancion.play_duration or 0) + int(dur)
        except (ValueError, TypeError):
            pass
        cancion.last_played = datetime.utcnow()
        if cancion.album_obj:
            cancion.album_obj.play_count = (cancion.album_obj.play_count or 0) + 1

    if 'user_id' in session:
        usuario = db.session.get(Usuario, session['user_id'])
        if not usuario or usuario.activity_tracking:
            entry = HistorialEscucha(
                usuario_id=session['user_id'],
                cancion_id=cancion_id,
                skip=is_skip
            )
            db.session.add(entry)

    db.session.commit()
    if cancion and not is_skip:
        try:
            event_bus.dispatch('track_played', {
                'cancion_id': cancion.id,
                'titulo': cancion.titulo,
                'artista': cancion.artista_obj.nombre if cancion.artista_obj else None,
                'play_count': cancion.play_count,
                'album_id': cancion.album_id
            })
        except Exception:
            pass
    return jsonify({'ok': True})




# ==============================================================================
# SECCIÓN 10: MONITOREO DE TAREAS EN SEGUNDO PLANO (BARRA DE CARGA)
# ==============================================================================

@api_bp.route('/api/lyrics-progress', methods=['GET'])
def api_lyrics_progress():
    """Retorna el porcentaje de avance de la indexación masiva de letras LRC."""
    try:
        p = progress_get('lyrics') or {}
        resp = jsonify({
            'active': p.get('active', False),
            'finished': p.get('finished', True),
            'total': p.get('total', 0),
            'completed': p.get('completed', 0),
            'downloaded': p.get('downloaded', 0),
            'errors': p.get('errors', 0),
            'current_song': p.get('current_song', ''),
            'percent': int((p.get('completed', 0) / max(p.get('total', 1), 1)) * 100) if p.get('total', 0) > 0 else 0
        })
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 200
    except Exception as e:
        resp = jsonify({'error': str(e), 'active': False, 'finished': True})
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 500


@api_bp.route('/api/mb-progress', methods=['GET'])
def api_mb_progress():
    """Retorna el progreso actual de la sincronización de artistas de MusicBrainz."""
    try:
        p = get_mb_progress()
        resp = jsonify({
            'active': p['active'],
            'finished': p['finished'],
            'total': p['total'],
            'completed': p['completed'],
            'found': p['found'],
            'current_artist': p['current_artist'],
            'message': p['message'],
        })
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 200
    except Exception as e:
        resp = jsonify({'error': str(e), 'active': False, 'finished': True})
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 500


# ==============================================================================
# SECCIÓN 11: CONFIGURACIÓN DE PERFIL Y PREFERENCIAS
# ==============================================================================

@api_bp.route('/api/profile/update', methods=['POST'])
def api_profile_update():
    """Actualiza dinámicamente preferencias y datos del perfil (nombre, crossfade, password)."""
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
        
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'No user'}), 404

    data = request.get_json(silent=True) or {}
    if 'nombre_publico' in data:
        usuario.nombre_publico = data['nombre_publico'].strip() or None
    if 'crossfade_enabled' in data:
        usuario.crossfade_enabled = bool(data['crossfade_enabled'])
    if 'activity_tracking' in data:
        usuario.activity_tracking = bool(data['activity_tracking'])
    if 'idioma_preferido' in data:
        usuario.idioma_preferido = data['idioma_preferido'].strip()[:5] or 'es'
    if 'audio_quality' in data:
        audio_quality = data['audio_quality'].strip().lower()
        if audio_quality in ['lossless', 'high', 'standard', 'saver']:
            usuario.audio_quality = audio_quality
    if 'password' in data and data['password'].strip():
        usuario.set_password(data['password'].strip())
        session.pop('_fresh', None)

    db.session.commit()
    return jsonify({
        'ok': True,
        'crossfade_enabled': usuario.crossfade_enabled,
        'activity_tracking': usuario.activity_tracking,
        'idioma_preferido': usuario.idioma_preferido,
        'audio_quality': usuario.audio_quality
    })


@api_bp.route('/api/profile', methods=['GET'])
def api_profile():
    """Retorna la configuración y preferencias del usuario logueado actualmente."""
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'No user'}), 404
        
    return jsonify({
        'id': usuario.id,
        'nombre_usuario': usuario.nombre_usuario,
        'nombre_publico': usuario.nombre_publico,
        'role': usuario.role,
        'crossfade_enabled': usuario.crossfade_enabled,
        'activity_tracking': usuario.activity_tracking,
        'idioma_preferido': usuario.idioma_preferido,
        'audio_quality': usuario.audio_quality,
        'display_name': usuario.display_name()
    })


# ==============================================================================
# SECCIÓN 12.5: GESTIÓN DE SESIONES Y DISPOSITIVOS ACTIVOS
# ==============================================================================

@api_bp.route('/api/sessions', methods=['GET'])
def api_sessions_list():
    """
    Retorna la lista de sesiones activas del usuario actual.
    Incluye información del dispositivo, navegador, IP parcial y marca temporal.
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    
    current_token = session.get('session_token')
    sesiones = SesionActiva.query.filter_by(usuario_id=session['user_id'])\
        .order_by(SesionActiva.ultima_actividad.desc()).all()
    
    result = []
    for s in sesiones:
        # Ocultar parcialmente la IP por privacidad
        ip_parcial = None
        if s.ip_address:
            partes = s.ip_address.split('.')
            if len(partes) == 4:
                ip_parcial = f"{partes[0]}.{partes[1]}.*.*"
            else:
                ip_parcial = s.ip_address[:12] + '...'
        
        result.append({
            'id': s.id,
            'navegador': s.navegador or 'Desconocido',
            'sistema': s.sistema or 'Desconocido',
            'dispositivo': s.dispositivo or 'Desconocido',
            'ip': ip_parcial,
            'fecha_creacion': s.fecha_creacion.isoformat() + 'Z' if s.fecha_creacion else None,
            'ultima_actividad': s.ultima_actividad.isoformat() + 'Z' if s.ultima_actividad else None,
            'es_actual': (s.session_token == current_token)
        })
    
    return jsonify(result)


@api_bp.route('/api/sessions/<int:session_id>/revoke', methods=['POST'])
def api_session_revoke(session_id):
    """
    Revoca (cierra) una sesión activa del usuario tras verificar su contraseña.
    No permite revocar la sesión actual (para eso debe usar /logout).
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    data = request.get_json(silent=True) or {}
    password = data.get('password', '').strip()
    
    if not password:
        return jsonify({'error': 'La contraseña es requerida'}), 400
    
    if not usuario.check_password(password):
        return jsonify({'error': 'Contraseña incorrecta'}), 403
    
    sesion_target = SesionActiva.query.filter_by(
        id=session_id, usuario_id=session['user_id']
    ).first()
    
    if not sesion_target:
        return jsonify({'error': 'Sesión no encontrada'}), 404
    
    # No permitir cerrar la sesión actual
    current_token = session.get('session_token')
    if sesion_target.session_token == current_token:
        return jsonify({'error': 'No puedes cerrar tu sesión actual desde aquí. Usa el botón Salir.'}), 400
    
    db.session.delete(sesion_target)
    db.session.commit()
    
    return jsonify({'ok': True, 'message': 'Sesión cerrada exitosamente'})


# ==============================================================================
# SECCIÓN 12: TRADUCTOR DE LETRAS HÍBRIDO (LIBRE/GOOGLE)
# ==============================================================================

@api_bp.route('/api/translate', methods=['POST'])
def api_translate():
    """
    Traduce letras LRC sincronizadas al idioma objetivo.
    1. Intenta LibreTranslate.
    2. Si LibreTranslate da error o timeout, realiza fallback a Google Translate (móvil scrape).
    """
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    target = data.get('target', 'es').strip()
    if not text:
        return jsonify({'error': 'No text'}), 400

    cache_key = f"ducksound:translate:{hash(text)}:{target}"

    try:
        r = get_redis_connection()
        cached = r.get(cache_key)
        if cached:
            return jsonify({'translated': cached, 'source': 'cache'})
    except Exception:
        pass

    try:
        # LibreTranslate
        resp = requests.post('https://libretranslate.com/translate', json={
            'q': text,
            'source': 'auto',
            'target': target,
            'format': 'text'
        }, timeout=15)

        if resp.status_code == 200:
            result = resp.json()
            translated = result.get('translatedText', '')
            if translated:
                try:
                    r = get_redis_connection()
                    r.setex(cache_key, 86400, translated)
                except Exception:
                    pass
                return jsonify({'translated': translated, 'source': 'libre'})

        # Fallback Google Translate
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={quote(text[:5000])}'
        resp2 = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DuckSound/1.0)'
        })
        if resp2.status_code == 200:
            parts = resp2.json()
            translated = ''.join(p[0] for p in parts[0] if p[0])
            if translated:
                try:
                    r = get_redis_connection()
                    r.setex(cache_key, 86400, translated)
                except Exception:
                    pass
                return jsonify({'translated': translated, 'source': 'google'})

        return jsonify({'error': 'Translation failed'}), 502
    except Exception as e:
        current_app.logger.error(f"Error al traducir: {e}")
        return jsonify({'error': str(e)}), 502




# ==============================================================================
# SECCIÓN 14: DETECCIÓN DE SILENCIOS Y AUDIO GAPLESS
# ==============================================================================

@api_bp.route('/api/song/<int:cancion_id>/silence', methods=['GET'])
def api_song_silence(cancion_id):
    """
    Retorna el análisis de corte de silencio inicial y final de una pista
    para permitir transiciones continuas sin espacios muertos (True Gapless).
    """
    cancion = Cancion.query.get_or_404(cancion_id)
    silence_info = detect_silence_padding(cancion.ruta_archivo_audio)
    return jsonify({
        'cancion_id': cancion.id,
        'titulo': cancion.titulo,
        **silence_info
    })


@api_bp.route('/api/gapless/pair/<int:song1_id>/<int:song2_id>', methods=['GET'])
def api_gapless_pair(song1_id, song2_id):
    """
    Calcula los puntos de corte encadenados entre dos pistas consecutivas.
    """
    s1 = Cancion.query.get_or_404(song1_id)
    s2 = Cancion.query.get_or_404(song2_id)
    p1 = detect_silence_padding(s1.ruta_archivo_audio)
    p2 = detect_silence_padding(s2.ruta_archivo_audio)
    return jsonify({
        'song1': {
            'id': s1.id,
            'trim_end': p1['trim_end'],
            'trailing_silence': p1['trailing_silence'],
            'duration': p1['duration']
        },
        'song2': {
            'id': s2.id,
            'trim_start': p2['trim_start'],
            'leading_silence': p2['leading_silence'],
            'duration': p2['duration']
        }
    })


# ==============================================================================
# SECCIÓN 15: CANAL DE EVENTOS EN TIEMPO REAL (SERVER-SENT EVENTS - SSE)
# ==============================================================================

@api_bp.route('/api/events/stream', methods=['GET'])
def api_events_stream():
    """
    Stream Server-Sent Events (SSE) para actualizaciones en vivo de biblioteca,
    progreso de indexación, sincronización de letras y reproducción.
    """
    def event_generator():
        # Enviar evento inicial de conexión inmediatamente para confirmar el canal HTTP
        yield f"id: 0\nevent: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': time.time()})}\n\n"
        for event_id, payload in event_bus.listen(timeout=15.0):
            yield f"id: {event_id}\nevent: {payload['event']}\ndata: {json.dumps(payload)}\n\n"

    response = Response(
        event_generator(),
        mimetype="text/event-stream"
    )
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


@api_bp.route('/api/events/status', methods=['GET'])
def api_events_status():
    """Retorna estadísticas del bus de eventos SSE."""
    return jsonify({
        'active_listeners': event_bus.listener_count()
    })


# ==============================================================================
# SECCIÓN 16: EDITOR DE ETIQUETAS Y METADATOS (IN-APP TAGGER)
# ==============================================================================

@api_bp.route('/api/track/<int:cancion_id>/tags', methods=['GET', 'POST'])
def api_track_tags(cancion_id):
    """
    Lectura y edición de metadatos de audio en el archivo físico y en la base de datos.
    GET: Retorna las etiquetas físicas y del sistema.
    POST: (Solo admin) Escribe las etiquetas en el archivo físico y actualiza la BD.
    """
    cancion = Cancion.query.get_or_404(cancion_id)

    if request.method == 'GET':
        raw_tags = read_audio_tags(cancion.ruta_archivo_audio)
        return jsonify({
            'cancion_id': cancion.id,
            'titulo': cancion.titulo,
            'artista': cancion.artista_obj.nombre if cancion.artista_obj else '',
            'album': cancion.album_obj.titulo if cancion.album_obj else '',
            'numero_pista': cancion.numero_pista,
            'genero': cancion.genero or '',
            'anio': cancion.album_obj.anio if cancion.album_obj else None,
            'raw_file_tags': raw_tags,
            'filepath': cancion.ruta_archivo_audio
        })

    # POST: Requiere rol admin
    if 'user_id' not in session:
        return jsonify({'error': 'Acceso no autenticado'}), 401
    user = db.session.get(Usuario, session['user_id'])
    if not user or not user.is_admin():
        return jsonify({'error': 'Permiso denegado: solo administradores pueden editar etiquetas físicas'}), 403

    data = request.get_json(silent=True) or {}
    nuevo_titulo = data.get('titulo', '').strip()
    nuevo_artista = data.get('artista', '').strip()
    nuevo_album = data.get('album', '').strip()
    nuevo_genero = data.get('genero', '').strip()
    nuevo_num_pista = data.get('numero_pista')
    nuevo_anio = data.get('anio')

    if not nuevo_titulo:
        return jsonify({'error': 'El título de la canción no puede estar vacío'}), 400

    # 1. Escribir metadatos en el archivo físico con mutagen
    ok, err = write_audio_tags(cancion.ruta_archivo_audio, {
        'titulo': nuevo_titulo,
        'artista': nuevo_artista,
        'album': nuevo_album,
        'genero': nuevo_genero,
        'numero_pista': nuevo_num_pista,
        'anio': nuevo_anio
    })

    if not ok:
        current_app.logger.warning(f"[Tagger] Falló escritura física en {cancion.ruta_archivo_audio}: {err}")

    # 2. Actualizar entidad Artista si cambió
    if nuevo_artista:
        artista_obj = Artista.query.filter(Artista.nombre.ilike(nuevo_artista)).first()
        if not artista_obj:
            artista_obj = Artista(nombre=nuevo_artista)
            db.session.add(artista_obj)
            db.session.flush()
        cancion.artista_id = artista_obj.id

    # 3. Actualizar entidad Album si cambió
    if nuevo_album:
        album_obj = Album.query.filter(
            Album.titulo.ilike(nuevo_album),
            Album.artista_id == cancion.artista_id
        ).first()
        if not album_obj:
            album_obj = Album(
                titulo=nuevo_album,
                artista_id=cancion.artista_id,
                anio=int(nuevo_anio) if nuevo_anio and str(nuevo_anio).isdigit() else None
            )
            db.session.add(album_obj)
            db.session.flush()
        else:
            if nuevo_anio and str(nuevo_anio).isdigit():
                album_obj.anio = int(nuevo_anio)
        cancion.album_id = album_obj.id

    # 4. Actualizar campos de la canción
    cancion.titulo = nuevo_titulo
    if nuevo_genero:
        cancion.genero = nuevo_genero
    if nuevo_num_pista is not None and str(nuevo_num_pista).isdigit():
        cancion.numero_pista = int(nuevo_num_pista)

    db.session.commit()

    # 5. Notificar por SSE a todos los clientes que la biblioteca se actualizó
    try:
        event_bus.dispatch('track_updated', {
            'cancion_id': cancion.id,
            'titulo': cancion.titulo,
            'artista': cancion.artista_obj.nombre if cancion.artista_obj else None,
            'album': cancion.album_obj.titulo if cancion.album_obj else None
        })
    except Exception:
        pass

    return jsonify({
        'ok': True,
        'message': 'Metadatos actualizados exitosamente en disco y base de datos',
        'cancion': cancion.to_dict()
    })

