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

import re
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, jsonify, request, session, url_for, current_app, Response
from app.models import db, Usuario, Artista, Album, Playlist, Cancion, Favorito, Coleccion, DailyMix, HistorialEscucha, SesionActiva
from app.services.queue import get_connection as get_redis_connection
import json

# Importaciones de servicios desacoplados
from app.services.lyrics import obtener_o_descargar_letra
from app.services.recommender import get_similar_songs
from app.services.queue import progress_get
from app.services.metadata import get_mb_progress

# Definición del Blueprint de API
api_bp = Blueprint('api', __name__)


# ==============================================================================
# SECCIÓN 1: MOTOR DE BÚSQUEDA NORMALIZADA E INSTANTÁNEA
# ==============================================================================

@api_bp.route('/api/search', methods=['GET'])
def api_search():
    """
    Endpoint principal del motor de búsqueda global con caché de Redis.
    Aplica coincidencia flexible insensible a acentos e insensible a mayúsculas/minúsculas
    en canciones, artistas y álbumes. Retorna arrays JSON limitados para alto rendimiento.
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'songs': [], 'artists': [], 'albums': []})

    # Intentar obtener la respuesta desde la caché de Redis
    cache_key = f"ducksound:cache:search:{q.lower()}"
    try:
        r = get_redis_connection()
        cached_data = r.get(cache_key)
        if cached_data:
            return Response(cached_data, mimetype='application/json')
    except Exception as e:
        current_app.logger.warning(f"[Cache Search] Error leyendo de Redis: {e}")

    term = f'%{q}%'
    try:
        from unidecode import unidecode
        q_norm = unidecode(q)
    except Exception:
        q_norm = q
    term_norm = f'%{q_norm}%'

    # Consultas optimizadas con límite para mantener el retardo de red bajo
    songs = Cancion.query.filter(
        Cancion.titulo.ilike(term) | Cancion.titulo.ilike(term_norm)
    ).limit(8).all()
    
    artists = Artista.query.filter(
        (Artista.nombre.ilike(term)) | (Artista.nombre_normalizado.ilike(term_norm))
    ).limit(5).all()
    
    albums = Album.query.filter(
        Album.titulo.ilike(term) | Album.titulo.ilike(term_norm)
    ).limit(5).all()

    response_data = {
        'songs': [{
            'id': s.id,
            'titulo': s.titulo,
            'artista': s.artista_obj.nombre if s.artista_obj else None,
            'audio': url_for('audio.servir_audio', cancion_id=s.id),
            'cover': url_for('audio.servir_album_art', cancion_id=s.id),
            'lyrics': url_for('audio.servir_lyrics', cancion_id=s.id),
        } for s in songs],
        'artists': [{
            'id': a.id,
            'nombre': a.nombre,
            'foto': a.foto_url or '',
        } for a in artists],
        'albums': [{
            'id': al.id,
            'titulo': al.titulo,
            'artista': al.artista.nombre if al.artista else None,
        } for al in albums],
    }

    # Escribir en caché con TTL de 5 minutos (300 segundos)
    try:
        r = get_redis_connection()
        r.setex(cache_key, 300, json.dumps(response_data))
    except Exception as e:
        current_app.logger.warning(f"[Cache Search] Error escribiendo en Redis: {e}")

    return jsonify(response_data)


# ==============================================================================
# SECCIÓN 2: APIS DEL CATÁLOGO DE CANCIONES Y ÁLBUMES
# ==============================================================================

@api_bp.route('/api/canciones')
def api_canciones():
    """
    Retorna la lista de canciones indexadas en formato JSON.
    Soporta parámetros de consulta opcionales 'limit' y 'offset' para paginación.
    """
    try:
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        
        query = Cancion.query.order_by(Cancion.titulo)
        
        if limit is not None:
            if offset is not None:
                query = query.offset(offset)
            query = query.limit(limit)
            
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

    favoritos = Favorito.query.filter_by(usuario_id=usuario_id)\
        .order_by(Favorito.fecha_agregado.desc()).all()

    canciones = []
    for fav in favoritos:
        c = db.session.get(Cancion, fav.cancion_id)
        if c:
            canciones.append({
                'id': c.id,
                'titulo': c.titulo,
                'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
                'album': c.album_obj.titulo if c.album_obj else None,
                'duracion': c.duracion,
                'cover': url_for('audio.servir_album_art', cancion_id=c.id),
                'lyrics': url_for('audio.servir_lyrics', cancion_id=c.id)
            })
    return jsonify(canciones)


# ==============================================================================
# SECCIÓN 9: REGISTRO DE AUDICIONES Y ACTIVIDAD (PLAY LOGGER)
# ==============================================================================

@api_bp.route('/api/play/<int:cancion_id>', methods=['POST'])
def api_register_play(cancion_id):
    """
    Registra una canción en el historial de audición.
    Respeta la privacidad: si el usuario tiene desactivado 'activity_tracking', no persiste nada.
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
        
    usuario = db.session.get(Usuario, session['user_id'])
    if usuario and not usuario.activity_tracking:
        return jsonify({'ok': True, 'tracking': False})
        
    data = request.get_json(silent=True) or {}
    entry = HistorialEscucha(
        usuario_id=session['user_id'],
        cancion_id=cancion_id,
        skip=data.get('skip', False)
    )
    db.session.add(entry)
    db.session.commit()
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
                return jsonify({'translated': translated, 'source': 'google'})

        return jsonify({'error': 'Translation failed'}), 502
    except Exception as e:
        current_app.logger.error(f"Error al traducir: {e}")
        return jsonify({'error': str(e)}), 502
