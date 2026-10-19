# -*- coding: utf-8 -*-
"""
Controlador de Rutas Principales y Exploración - DuckSound
=========================================================
Este módulo encapsula todas las funciones y endpoints relacionados con la interfaz
de usuario principal y el catálogo de música:
1. Dashboard principal (vista tipo Spotify) con mixes diarios, álbumes y artistas recientes.
2. Explorador de carpetas físico en árbol con mapeo en tiempo real de tracks indexados.
3. Lista de reproducción de canciones favoritas ("Me gusta").
4. Listas de reproducción y colecciones personalizadas creadas por los usuarios.
5. Catálogo general de artistas, álbumes y sus respectivos detalles, optimizados
   con consultas SQLAlchemy cargadas de forma masiva (para evitar cuellos de botella N+1).
6. Generación e integración de "Mezclas Diarias" (Daily Mixes) personalizadas.
7. Estadísticas personales de escucha y configuración de perfil.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import joinedload

from flask import Blueprint, request, redirect, url_for, session, abort, current_app, jsonify
from config import Config
from app.models import db, Usuario, Artista, Album, Cancion, Favorito, Coleccion, DailyMix, HistorialEscucha

# Importación de servicios de recomendación desacoplados
from app.services.recommender import generate_daily_mixes_for_user

# Definición del Blueprint Principal
main_bp = Blueprint('main', __name__)


def _album_card_payload(album, track_count=0, total_duration=None, cover_url=None):
    """Datos que consume React para tarjetas de album."""
    payload = {
        'album': album.to_dict(),
        'album_id': album.id,
        'id': album.id,
        'titulo': album.titulo,
        'anio': album.anio,
        'artista_id': album.artista_id,
        'cover_url': cover_url if cover_url is not None else _album_cover_url(album),
        'track_count': int(track_count or 0),
    }
    if total_duration is not None:
        payload['total_duration'] = int(total_duration or 0)
    return payload


# ==============================================================================
# SECCIÓN 1: VISTA DE INICIO Y REDIRECCIONES DE ACCESO
# ==============================================================================


# ==============================================================================
# SECCIÓN 2: BIBLIOTECA GENERAL Y VISTA SPOTIFY (DASHBOARD)
# ==============================================================================

@main_bp.route('/dashboard')
def dashboard():
    """
    Dashboard Principal de DuckSound.
    Renderiza la biblioteca completa ordenada por título junto a los mixes del día,
    álbumes nuevos, artistas agregados y un listado de descubrimientos recientes.
    """
    # Evitamos cargar la biblioteca completa (Cancion.query.all()) en el dashboard
    # ya que no se renderiza en la vista principal y degrada masivamente el rendimiento.
    canciones = []
    
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    # 1. Obtener los Mixes Diarios del usuario para el día actual
    today = datetime.utcnow().date()
    daily_mixes = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).all()
    if not daily_mixes:
        # Encolar la generación asíncrona en Redis RQ para no bloquear la carga HTTP
        from app.services.queue import enqueue, run_generate_daily_mixes
        try:
            enqueue(run_generate_daily_mixes, session['user_id'])
        except Exception as e:
            current_app.logger.error(f"Error encolando generación de mixes diarios: {e}")

    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        target_mix_name = 'Morning Vibes'
    elif 12 <= current_hour < 19:
        target_mix_name = 'Afternoon Chill'
    else:
        target_mix_name = 'Night Beats'
    spotlight_mix = next((mix for mix in daily_mixes if mix.nombre == target_mix_name), None)
    if spotlight_mix is None and daily_mixes:
        spotlight_mix = daily_mixes[0]

    # 2. Obtener feeds de descubrimiento para la interfaz fluida
    albumes_recientes = Album.query.order_by(Album.id.desc()).limit(12).all()
    artistas_recientes = Artista.query.order_by(Artista.id.desc()).limit(12).all()
    
    # Canciones más reproducidas: consulta directa rápida por play_count indexado
    top_canciones_list = Cancion.query.filter(Cancion.play_count > 0).order_by(Cancion.play_count.desc()).limit(5).all()
    if top_canciones_list:
        top_canciones_data = [{'cancion': c.to_dict(), 'plays': int(c.play_count)} for c in top_canciones_list]
    else:
        top_canciones = db.session.query(
            Cancion,
            sqlfunc.count(HistorialEscucha.id).label('plays')
        ).join(
            HistorialEscucha,
            HistorialEscucha.cancion_id == Cancion.id
        ).filter(
            HistorialEscucha.skip == False
        ).group_by(
            Cancion
        ).order_by(
            db.desc('plays')
        ).limit(5).all()
        top_canciones_data = [{'cancion': c.to_dict(), 'plays': int(plays)} for c, plays in top_canciones]

    canciones_recientes = Cancion.query.order_by(Cancion.fecha_agregada.desc()).limit(5).all()
    dashboard_stats = {
        'canciones': Cancion.query.count(),
        'albumes': Album.query.count(),
        'artistas': Artista.query.count(),
        'mixes': len(daily_mixes)
    }

    return {
        'usuario': session.get('nombre_usuario'),
        'is_admin': is_admin,
        'daily_mixes': [m.to_dict() for m in daily_mixes],
        'spotlight_mix': spotlight_mix.to_dict() if spotlight_mix else None,
        'albumes_recientes': [_album_card_payload(a, track_count=len(a.canciones)) for a in albumes_recientes],
        'artistas_recientes': [art.to_dict() for art in artistas_recientes],
        'dashboard_stats': dashboard_stats,
        'top_canciones': top_canciones_data,
        'canciones_recientes': [c.to_dict() for c in canciones_recientes]
    }


@main_bp.route('/favoritos')
def favoritos():
    """Lista las canciones que el usuario ha marcado con 'Me gusta'."""
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    canciones = Cancion.query.join(
        Favorito, Favorito.cancion_id == Cancion.id
    ).filter(
        Favorito.usuario_id == session['user_id']
    ).order_by(Favorito.fecha_agregado.desc()).all()
            
    return {
        'usuario': session.get('nombre_usuario'),
        'is_admin': is_admin,
        'favoritos': [c.to_dict() for c in canciones]
    }


# ==============================================================================
# SECCIÓN 3: NAVEGACIÓN FÍSICA Y ARBOL DE CARPETAS (FILE SYSTEM DISK)
# ==============================================================================

@main_bp.route('/folders')
def folders():
    """
    Escanea la carpeta de música física montada en el servidor y genera una vista
    en árbol para permitir explorar las canciones por directorios. Muestra en tiempo real
    cuántas pistas de cada subcarpeta ya han sido indexadas en DuckSound.
    Optimizado para evitar consultas N+1 en bases de datos grandes.
    """
    usuario_obj = db.session.get(Usuario, session.get('user_id'))
    is_admin = usuario_obj.is_admin() if usuario_obj else False

    audio_dir = str(Config.AUDIO_FOLDER)
    if not os.path.exists(audio_dir):
        return {'is_admin': is_admin, 'tree': []}

    # Cargar rutas de canciones en memoria en una sola consulta para conteo instantáneo
    try:
        rutas_db = [r[0].replace('\\', '/') for r in db.session.query(Cancion.ruta_archivo_audio).all() if r[0]]
    except Exception:
        rutas_db = []

    def build_tree(dirpath, depth=0):
        if depth > 3:  # Limitar profundidad para prevenir sobrecargas
            return []
        items = []
        try:
            for entry in sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower())):
                entry_norm = entry.path.replace('\\', '/')
                if entry.is_dir():
                    if entry.name.startswith(('.', '$')):
                        continue
                    children = build_tree(entry.path, depth + 1)
                    # Conteo rápido en memoria
                    songs_count = sum(1 for r in rutas_db if r.startswith(entry_norm + '/'))
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'folder',
                        'children': children,
                        'song_count': songs_count
                    })
                elif entry.name.lower().endswith(tuple(('.mp3', '.flac', '.wav', '.m4a', '.ogg'))):
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'file'
                    })
        except (PermissionError, OSError):
            pass
        return items

    tree = build_tree(audio_dir)
    return {'is_admin': is_admin, 'tree': tree}



# ==============================================================================
# SECCIÓN 4: GESTIÓN DE PLAYLISTS DE USUARIO (COLECCIONES)
# ==============================================================================

@main_bp.route('/colecciones')
def colecciones_list():
    """Muestra todas las listas de reproducción creadas por el usuario autenticado."""
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    colecciones = Coleccion.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Coleccion.fecha_creacion.desc()).all()
    return {'is_admin': is_admin, 'colecciones': [c.to_dict() for c in colecciones]}


@main_bp.route('/coleccion/<int:coleccion_id>')
def coleccion_detail(coleccion_id):
    """Muestra el catálogo y la cola de canciones de una playlist/colección."""
    coleccion = Coleccion.query.get_or_404(coleccion_id)
    
    # Restricción de propiedad: no permitir a usuarios ver playlists ajenas
    if coleccion.usuario_id != session['user_id']:
        abort(403)
        
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return {
        'is_admin': is_admin,
        'coleccion': coleccion.to_dict(),
        'songs': [c.to_dict() for c in coleccion.canciones]
    }


# ==============================================================================
# SECCIÓN 5: RECOMENDACIONES DIARIAS (DAILY MIXES)
# ==============================================================================


@main_bp.route('/daily-mixes')
def daily_mixes_redirect():
    """Compatibilidad: la lista de mixes vive en el dashboard principal."""
    return redirect(url_for('main.dashboard'))


@main_bp.route('/daily-mix/<int:mix_id>')
def daily_mix_detail(mix_id):
    """Muestra el tracklist y la interfaz de reproducción de una mezcla diaria."""
    mix = DailyMix.query.get_or_404(mix_id)
    if mix.usuario_id != session['user_id']:
        abort(403)
    
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return {'is_admin': is_admin, 'mix': mix.to_dict()}


# ==============================================================================
# SECCIÓN 6: NAVEGACIÓN Y CATÁLOGO DE ARTISTAS Y ÁLBUMES (EXPLORE MODULE)
# ==============================================================================

def _album_cover_url(album):
    """Determina dinámicamente el enlace de portada de un álbum (carátula remota o fallback local)."""
    if not album:
        return None
    if album.portada_url:
        return album.portada_url
    primer_cancion = Cancion.query.filter_by(album_id=album.id).first()
    if primer_cancion:
        # Apunta a la ruta modular de audio
        return url_for('audio.servir_album_art', cancion_id=primer_cancion.id)
    return None


def _album_total_duration(album):
    """Suma y retorna en segundos la duración de todas las pistas que integran un álbum."""
    result = db.session.query(sqlfunc.sum(Cancion.duracion)).filter(Cancion.album_id == album.id).scalar()
    return result or 0


@main_bp.route('/explore')
def explore():
    """Ruta del Dashboard de Exploración. Muestra el mosaico de artistas y álbumes."""
    artists = Artista.query.order_by(Artista.nombre).all()
    
    # Conteo agrupado y eficiente en una sola transacción SQL para evitar N+1
    album_stats = db.session.query(
        Album, sqlfunc.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).group_by(Album.id).order_by(Album.titulo).limit(20).all()
    
    albums_data = []
    for al, track_count in album_stats:
        albums_data.append(_album_card_payload(al, track_count=track_count))

    return {'artists': [a.to_dict() for a in artists], 'albums_data': albums_data}


@main_bp.route('/artists')
def artists_list():
    """Lista completa de artistas de la plataforma con agregaciones cargadas previamente."""
    # Agrupaciones masivas en base de datos para latencia ultra-baja
    album_counts = db.session.query(Album.artista_id, sqlfunc.count(Album.id)).group_by(Album.artista_id).all()
    album_dict = {a_id: count for a_id, count in album_counts}
    
    song_counts = db.session.query(Cancion.artista_id, sqlfunc.count(Cancion.id)).group_by(Cancion.artista_id).all()
    song_dict = {a_id: count for a_id, count in song_counts}

    from app.services.parsers import get_sort_name, natural_sort_key
    artists = Artista.query.all()
    artists.sort(key=lambda a: natural_sort_key(get_sort_name(a.nombre)))
    artists_data = []
    
    # Obtener el primer álbum de cada artista de manera masiva para usar su portada en el mosaico
    first_albums = Album.query.order_by(Album.artista_id, Album.id).all()
    first_album_dict = {}
    seen_artists = set()
    for al in first_albums:
        if al.artista_id not in seen_artists:
            seen_artists.add(al.artista_id)
            first_album_dict[al.artista_id] = al

    for a in artists:
        ac = album_dict.get(a.id, 0)
        sc = song_dict.get(a.id, 0)
        fa = first_album_dict.get(a.id)
        cover_url = _album_cover_url(fa) if fa else None
        
        artists_data.append({
            'artist': a.to_dict(),
            'album_count': ac,
            'song_count': sc,
            'cover_url': cover_url
        })
    return {'artists_data': artists_data}


@main_bp.route('/artist/<int:artist_id>')
def artist_detail(artist_id):
    """Muestra el catálogo detallado de un artista (biografía, álbumes oficiales, apariciones y canciones)."""
    artist = Artista.query.get_or_404(artist_id)
    songs = Cancion.query.filter_by(artista_id=artist.id).order_by(
        Cancion.album_id,
        Cancion.numero_disco.asc(),
        Cancion.numero_pista.asc(),
        Cancion.titulo.asc()
    ).all()
    
    # Álbumes oficiales del artista
    album_stats = db.session.query(
        Album, sqlfunc.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).filter(Album.artista_id == artist.id).group_by(Album.id).order_by(Album.anio.desc()).all()
    
    albums_data = []
    albums_only = []
    singles_eps = []
    own_album_ids = set()
    for al, track_count in album_stats:
        own_album_ids.add(al.id)
        card = _album_card_payload(al, track_count=track_count)
        albums_data.append(card)
        if track_count <= 3:
            singles_eps.append(card)
        else:
            albums_only.append(card)

    # Buscar "Aparece en" (Appears On):
    # Álbumes de otros artistas donde participa este artista (pistas del artista o feat en el título)
    collab_album_ids = set()
    # 1. Canciones donde artista_id coincide pero el album no es suyo
    collab_songs_q = db.session.query(Cancion.album_id).filter(
        Cancion.artista_id == artist.id,
        Cancion.album_id.isnot(None)
    )
    if own_album_ids:
        collab_songs_q = collab_songs_q.filter(~Cancion.album_id.in_(own_album_ids))
    for r in collab_songs_q.distinct().all():
        if r[0]:
            collab_album_ids.add(r[0])

    # 2. Canciones de otros artistas donde el título incluye feat/ft con el nombre de este artista
    feat_filter = (
        Cancion.titulo.ilike(f'%feat% {artist.nombre}%') |
        Cancion.titulo.ilike(f'%ft% {artist.nombre}%') |
        Cancion.titulo.ilike(f'%(feat% {artist.nombre}%)') |
        Cancion.titulo.ilike(f'%(ft% {artist.nombre}%)')
    )
    feat_q = db.session.query(Cancion.album_id).filter(
        feat_filter,
        Cancion.album_id.isnot(None)
    )
    if own_album_ids:
        feat_q = feat_q.filter(~Cancion.album_id.in_(own_album_ids))
    for r in feat_q.distinct().all():
        if r[0]:
            collab_album_ids.add(r[0])

    appears_on = []
    if collab_album_ids:
        collab_albums = db.session.query(
            Album, sqlfunc.count(Cancion.id).label('track_count')
        ).outerjoin(Cancion).filter(Album.id.in_(collab_album_ids)).group_by(Album.id).order_by(Album.anio.desc()).all()
        for al, track_count in collab_albums:
            appears_on.append(_album_card_payload(al, track_count=track_count))

    album_count = len(albums_data)
    song_count = len(songs)
    return {
        'artist': artist.to_dict(),
        'albums_data': albums_data,
        'albums_only': albums_only,
        'singles_eps': singles_eps,
        'appears_on': appears_on,
        'songs': [s.to_dict() for s in songs],
        'album_count': album_count,
        'song_count': song_count
    }


@main_bp.route('/albums')
def albums_list():
    """Listado general de Álbumes en DuckSound con sus respectivas agregaciones de tiempo y conteo."""
    from app.services.parsers import get_sort_name, natural_sort_key
    album_stats = db.session.query(
        Album,
        sqlfunc.count(Cancion.id).label('track_count'),
        sqlfunc.coalesce(sqlfunc.sum(Cancion.duracion), 0).label('total_dur')
    ).outerjoin(Cancion).group_by(Album.id).all()
    
    albums_data = []
    for al, track_count, total_dur in album_stats:
        albums_data.append(_album_card_payload(al, track_count=track_count, total_duration=total_dur))

    albums_data.sort(key=lambda card: natural_sort_key(get_sort_name(card['album']['titulo'])))
    return {'albums_data': albums_data}


@main_bp.route('/album/<int:album_id>')
def album_detail(album_id):
    """Muestra la lista de reproducción estructurada de un álbum, ordenando canciones por disco y pista."""
    album = Album.query.get_or_404(album_id)
    songs = Cancion.query.filter_by(album_id=album.id).order_by(
        Cancion.numero_disco.asc(),
        Cancion.numero_pista.asc(),
        Cancion.titulo.asc()
    ).all()
    
    # Separar canciones por volumen / disco físico
    discos_dict = {}
    for s in songs:
        disc_num = s.numero_disco if s.numero_disco is not None else 1
        if disc_num not in discos_dict:
            discos_dict[disc_num] = []
        discos_dict[disc_num].append(s)
    
    discos_ordenados = sorted(discos_dict.items())
    
    from app.services.parsers import get_track_sort_pos
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            t = c.numero_pista
        else:
            filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
            m = re.match(r'^\s*(\d+)', filename)
            t = int(m.group(1)) if m else 999
        return get_track_sort_pos(c.numero_disco, t)
    
    discos = []
    for disc_num, canciones_disco in discos_ordenados:
        canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
        discos.append({
            'disc_num': disc_num,
            'songs': [c.to_dict() for c in canciones_ordenadas]
        })
    
    cover_url = _album_cover_url(album)
    total_dur = _album_total_duration(album)
    track_count = len(songs)
    return {'album': album.to_dict(), 'discos': discos, 'cover_url': cover_url, 'total_duration': total_dur, 'track_count': track_count}


# ==============================================================================
# SECCIÓN 7: PERFIL DE USUARIO Y ANÁLISIS DE TIEMPO DE ESCUCHA (ESTADÍSTICAS RICAS)
# ==============================================================================

@main_bp.route('/stats')
def user_stats():
    """Redirige al perfil principal donde se encuentran renderizadas las estadísticas."""
    return redirect(url_for('main.profile'))


@main_bp.route('/profile')
def profile():
    """
    Renderiza la ficha de Perfil de Usuario con estadísticas enriquecidas:
    Soporta filtro dinámico por ventana de tiempo con query param: period=week|month|all.
    """
    from flask import request
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        session.clear()
        return jsonify({'error': 'Usuario no encontrado'}), 401
        
    is_admin = usuario.is_admin()
    user_id = session['user_id']
    from app.models import HistorialEscucha

    period = request.args.get('period', 'all').lower()
    now = datetime.utcnow()
    start_date = None
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'day':
        start_date = now - timedelta(days=1)

    # 1. Top 10 canciones más escuchadas del usuario
    top_songs_q = db.session.query(
        Cancion, sqlfunc.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.skip == False
    )
    if start_date:
        top_songs_q = top_songs_q.filter(HistorialEscucha.reproducido_en >= start_date)
    top_songs = top_songs_q.group_by(Cancion).order_by(db.desc('plays')).limit(10).all()

    # 2. Top 8 artistas más reproducidos
    top_artists_q = db.session.query(
        Artista.nombre, Artista.id, sqlfunc.count(HistorialEscucha.id).label('plays')
    ).select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False)
    if start_date:
        top_artists_q = top_artists_q.filter(HistorialEscucha.reproducido_en >= start_date)
    top_artists = top_artists_q.group_by(Artista.id, Artista.nombre).order_by(db.desc('plays')).limit(8).all()

    # 3. Suma total de audiciones completas
    plays_q = HistorialEscucha.query.filter_by(usuario_id=user_id, skip=False)
    if start_date:
        plays_q = plays_q.filter(HistorialEscucha.reproducido_en >= start_date)
    total_plays = plays_q.count()

    # 4. Horas dedicadas en total
    dur_q = db.session.query(sqlfunc.sum(Cancion.duracion))\
        .join(HistorialEscucha)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False,
                Cancion.duracion.isnot(None))
    if start_date:
        dur_q = dur_q.filter(HistorialEscucha.reproducido_en >= start_date)
    total_seconds = int(dur_q.scalar() or 0)
    total_hours = round(total_seconds / 3600.0, 1)

    # 5. Escuchas en las últimas 24 horas
    last_24h = HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.reproducido_en >= now - timedelta(hours=24)
    ).count()

    return {
        'usuario': usuario.to_dict(),
        'is_admin': is_admin,
        'period': period,
        'top_songs': [{'cancion': c[0].to_dict(), 'plays': c[1]} for c in top_songs],
        'top_artists': [{'nombre': a[0], 'id': a[1], 'plays': a[2]} for a in top_artists],
        'total_plays': total_plays,
        'total_hours': total_hours,
        'total_seconds': total_seconds,
        'last_24h': last_24h
    }
