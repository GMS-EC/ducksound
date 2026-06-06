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

from flask import Blueprint, request, redirect, url_for, session, abort, current_app
from config import Config
from app.models import db, Usuario, Artista, Album, Cancion, Favorito, Coleccion, DailyMix, HistorialEscucha

# Importación de servicios de recomendación desacoplados
from app.services.recommender import generate_daily_mixes_for_user

# Definición del Blueprint Principal
main_bp = Blueprint('main', __name__)


# ==============================================================================
# SECCIÓN 1: VISTA DE INICIO Y REDIRECCIONES DE ACCESO
# ==============================================================================

@main_bp.route('/')
def index():
    """Redirige al dashboard si el usuario está autenticado, o al login en caso contrario."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
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
        'albumes_recientes': [a.to_dict() for a in albumes_recientes],
        'artistas_recientes': [art.to_dict() for art in artistas_recientes],
        'dashboard_stats': dashboard_stats,
        'top_canciones': [c[0].to_dict() for c in top_canciones],
        'canciones_recientes': [c.to_dict() for c in canciones_recientes]
    }


@main_bp.route('/favoritos')
def favoritos():
    """Lista las canciones que el usuario ha marcado con 'Me gusta'."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    favoritos_rel = Favorito.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Favorito.fecha_agregado.desc()).all()
        
    canciones = []
    for fav in favoritos_rel:
        c = db.session.get(Cancion, fav.cancion_id)
        if c:
            canciones.append(c)
            
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
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False

    audio_dir = Config.AUDIO_FOLDER
    tree = {}

    def build_tree(dirpath, prefix=''):
        """Función recursiva para escanear y compilar carpetas físicas de audio."""
        items = []
        try:
            # Ordenar primero carpetas, luego archivos
            for entry in sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.is_dir():
                    children = build_tree(entry.path, prefix + entry.name + '/')
                    # Contar en base de datos cuántas canciones registradas tienen esta subruta
                    songs = Cancion.query.filter(Cancion.ruta_archivo_audio.like(entry.path.replace('\\', '/') + '%')).count()
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'folder',
                        'children': children,
                        'song_count': songs
                    })
                elif entry.name.lower().endswith(tuple(('.mp3', '.flac', '.wav', '.m4a', '.ogg'))):
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'file'
                    })
        except PermissionError:
            pass  # Ignorar subcarpetas protegidas sin lanzar error 500
        return items

    tree = build_tree(audio_dir)
    return {'is_admin': is_admin, 'tree': tree}


# ==============================================================================
# SECCIÓN 4: GESTIÓN DE PLAYLISTS DE USUARIO (COLECCIONES)
# ==============================================================================

@main_bp.route('/colecciones')
def colecciones_list():
    """Muestra todas las listas de reproducción creadas por el usuario autenticado."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    colecciones = Coleccion.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Coleccion.fecha_creacion.desc()).all()
    return {'is_admin': is_admin, 'colecciones': [c.to_dict() for c in colecciones]}


@main_bp.route('/coleccion/<int:coleccion_id>')
def coleccion_detail(coleccion_id):
    """Muestra el catálogo y la cola de canciones de una playlist/colección."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('main.dashboard'))


@main_bp.route('/daily-mix/<int:mix_id>')
def daily_mix_detail(mix_id):
    """Muestra el tracklist y la interfaz de reproducción de una mezcla diaria."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    mix = DailyMix.query.get_or_404(mix_id)
    if mix.usuario_id != session['user_id']:
        abort(403)
    
    print(f"DEBUG: Mix {mix_id} songs count: {len(mix.canciones)}")
    
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    artists = Artista.query.order_by(Artista.nombre).all()
    
    # Conteo agrupado y eficiente en una sola transacción SQL para evitar N+1
    album_stats = db.session.query(
        Album, sqlfunc.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).group_by(Album.id).order_by(Album.titulo).limit(20).all()
    
    albums_data = []
    for al, track_count in album_stats:
        albums_data.append({
            'album': al.to_dict(),
            'cover_url': _album_cover_url(al),
            'track_count': track_count
        })
    return {'artists': [a.to_dict() for a in artists], 'albums_data': albums_data}


@main_bp.route('/artists')
def artists_list():
    """Lista completa de artistas de la plataforma con agregaciones cargadas previamente."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Agrupaciones masivas en base de datos para latencia ultra-baja
    album_counts = db.session.query(Album.artista_id, sqlfunc.count(Album.id)).group_by(Album.artista_id).all()
    album_dict = {a_id: count for a_id, count in album_counts}
    
    song_counts = db.session.query(Cancion.artista_id, sqlfunc.count(Cancion.id)).group_by(Cancion.artista_id).all()
    song_dict = {a_id: count for a_id, count in song_counts}

    artists = Artista.query.order_by(Artista.nombre).all()
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
    """Muestra el catálogo detallado de un artista (biografía, álbumes e index de canciones)."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    artist = Artista.query.get_or_404(artist_id)
    songs = Cancion.query.filter_by(artista_id=artist.id).order_by(
        Cancion.album_id,
        Cancion.numero_disco.asc(),
        Cancion.numero_pista.asc(),
        Cancion.titulo.asc()
    ).all()
    
    album_stats = db.session.query(
        Album, sqlfunc.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).filter(Album.artista_id == artist.id).group_by(Album.id).order_by(Album.anio.desc()).all()
    
    albums_data = []
    for al, track_count in album_stats:
        albums_data.append({
            'album': al.to_dict(),
            'cover_url': _album_cover_url(al),
            'track_count': track_count
        })
    album_count = len(albums_data)
    song_count = len(songs)
    return {
        'artist': artist.to_dict(),
        'albums_data': albums_data,
        'songs': [s.to_dict() for s in songs],
        'album_count': album_count,
        'song_count': song_count
    }


@main_bp.route('/albums')
def albums_list():
    """Listado general de Álbumes en DuckSound con sus respectivas agregaciones de tiempo y conteo."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    album_stats = db.session.query(
        Album,
        sqlfunc.count(Cancion.id).label('track_count'),
        sqlfunc.coalesce(sqlfunc.sum(Cancion.duracion), 0).label('total_dur')
    ).outerjoin(Cancion).group_by(Album.id).order_by(Album.titulo).all()
    
    albums_data = []
    for al, track_count, total_dur in album_stats:
        albums_data.append({
            'album': al.to_dict(),
            'cover_url': _album_cover_url(al),
            'track_count': track_count,
            'total_duration': total_dur
        })
    return {'albums_data': albums_data}


@main_bp.route('/album/<int:album_id>')
def album_detail(album_id):
    """Muestra la lista de reproducción estructurada de un álbum, ordenando canciones por disco y pista."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
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
    
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
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
    - Las 10 canciones más escuchadas (excluyendo skips rápidos).
    - Los 8 artistas más reproducidos.
    - Volumen de audición global.
    - Horas acumuladas totales escuchando canciones.
    - Conteo de canciones reproducidas en las últimas 24 horas.
    """
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return redirect(url_for('auth.login'))
        
    is_admin = usuario.is_admin()
    user_id = session['user_id']
    from app.models import HistorialEscucha

    # 1. Top 10 canciones más escuchadas del usuario
    top_songs = db.session.query(
        Cancion, sqlfunc.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion).order_by(db.desc('plays')).limit(10).all()

    # 2. Top 8 artistas más reproducidos
    top_artists = db.session.query(
        Artista.nombre, Artista.id, sqlfunc.count(HistorialEscucha.id).label('plays')
    ).select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False)\
        .group_by(Artista.id)\
        .order_by(db.desc('plays')).limit(8).all()

    # 3. Suma total de audiciones completas
    total_plays = HistorialEscucha.query.filter_by(usuario_id=user_id, skip=False).count()

    # 4. Horas dedicadas en total
    total_hours = db.session.query(sqlfunc.sum(Cancion.duracion))\
        .join(HistorialEscucha)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False,
                Cancion.duracion.isnot(None)).scalar() or 0
    total_hours = total_hours // 3600  # Reducir segundos agregados a horas enteras

    # 5. Escuchas en las últimas 24 horas
    last_24h = HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.reproducido_en >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    return {
        'usuario': usuario.to_dict(),
        'is_admin': is_admin,
        'top_songs': [{'cancion': c[0].to_dict(), 'plays': c[1]} for c in top_songs],
        'top_artists': [{'nombre': a[0], 'id': a[1], 'plays': a[2]} for a in top_artists],
        'total_plays': total_plays,
        'total_hours': total_hours,
        'last_24h': last_24h
    }
