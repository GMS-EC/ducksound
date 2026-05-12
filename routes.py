from flask import Blueprint, session, redirect, url_for, render_template, jsonify, abort, request, current_app
from models import db, Usuario, Artista, Album, Playlist, Cancion, Favorito, Coleccion
from scan_songs import escanear_carpeta_audio, escaneo_rapido
import os
import threading
import uuid
from datetime import datetime
from flask import current_app

admin_bp = Blueprint('admin', __name__)
api_bp = Blueprint('api', __name__)
browse_bp = Blueprint('browse', __name__)

# Scan task tracking via Redis (persistente entre procesos)
from task_queue import scan_task_set, scan_task_get, scan_set_active, scan_get_active

# Caché en memoria simple para endpoints (evita saturar APIs externas)
import time
from functools import wraps


def _cleanup_old_tasks():
    """Limpieza manejada por Redis TTL."""
    pass





# Caché en memoria simple para endpoints (evita saturar APIs externas)
_route_cache = {}

def route_cache(ttl_seconds=3600):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{f.__name__}:{args}:{kwargs}"
            now = time.time()
            if key in _route_cache:
                value, expires = _route_cache[key]
                if now < expires:
                    return value
            result = f(*args, **kwargs)
            _route_cache[key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return decorator


def _is_admin_session():
    if 'user_id' not in session:
        return False

    usuario = Usuario.query.get(session['user_id'])
    return bool(usuario and usuario.is_admin())


def _is_admin_request():
    if _is_admin_session():
        return True

    admin_token = os.getenv('ADMIN_SECRET_TOKEN')
    if not admin_token:
        return False

    auth = request.headers.get('Authorization', '')
    token = None
    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
    else:
        token = request.headers.get('X-Admin-Token')

    return token == admin_token


@admin_bp.route('/admin/escanear', methods=['GET'])
def escanear_canciones():
    """Endpoint para que el administrador dispare el escaneo de la carpeta de audio.
    Ejecuta la función `escanear_carpeta_audio` del módulo `scan_songs`.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    # Llamar a la función de escaneo (estamos dentro del contexto de app)
    try:
        resumen = escanear_carpeta_audio()
    except Exception as e:
        return render_template('scan_result.html', error=str(e), resumen=None)

    return render_template('scan_result.html', error=None, resumen=resumen)


@admin_bp.route('/admin/clean_metadata', methods=['POST'])
def admin_clean_metadata():
    """Agrupa artistas y álbumes duplicados sin requerir un escaneo del disco."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    existing_tid, existing_task = scan_get_active()
    if existing_tid and existing_task and existing_task.get('status') in ('running', 'enriching'):
        return jsonify({'error': 'scan_in_progress', 'task_id': existing_tid}), 409

    task_id = str(uuid.uuid4())
    scan_set_active(task_id)
    scan_task_set(task_id, {
        'status': 'running',
        'message': 'Iniciando limpieza...',
        'percent': 0,
        'processed': 0,
        'total': 0,
        'summary': None
    })

    def _run_clean():
        from models import Artista, Album, db
        from metadata_normalizer import normalizar_artista, normalizar_album
        from app import app
        
        with app.app_context():
            def emit(data):
                t = scan_task_get(task_id)
                if t:
                    t.update(data)
                    scan_task_set(task_id, t)
            
            try:
                import os
                from models import Cancion
                emit({'message': 'Eliminando canciones huérfanas...', 'percent': 5})
                canciones = Cancion.query.all()
                eliminadas = 0
                for c in canciones:
                    if not os.path.exists(c.ruta_archivo_audio):
                        db.session.delete(c)
                        eliminadas += 1
                if eliminadas > 0:
                    db.session.commit()
                    # Limpiar álbumes vacíos
                    albumes_all = Album.query.all()
                    for a in albumes_all:
                        if not a.canciones:
                            db.session.delete(a)
                    # Limpiar artistas vacíos
                    artistas_all = Artista.query.all()
                    for a in artistas_all:
                        if not a.canciones and not a.albums:
                            db.session.delete(a)
                    db.session.commit()

                emit({'message': 'Buscando artistas para agrupar...', 'percent': 10})
                artistas = Artista.query.all()
                total = len(artistas)
                
                mergeados = 0
                renombrados = 0
                
                for idx, artista in enumerate(artistas):
                    emit({'percent': 10 + int((idx/total)*40), 'message': f'Artistas: {artista.nombre}', 'processed': idx, 'total': total})
                    nombre_norm = normalizar_artista(artista.nombre)
                    
                    artista_existente = Artista.query.filter(Artista.nombre == nombre_norm, Artista.id < artista.id).first()
                    if artista_existente:
                        for cancion in artista.canciones:
                            cancion.artista_id = artista_existente.id
                        for album in artista.albums:
                            album.artista_id = artista_existente.id
                        db.session.delete(artista)
                        mergeados += 1
                    elif nombre_norm != artista.nombre:
                        artista.nombre = nombre_norm
                        renombrados += 1
                db.session.commit()
                
                emit({'message': 'Buscando álbumes para unificar...', 'percent': 50})
                albumes = Album.query.all()
                total_al = len(albumes)
                for idx, album in enumerate(albumes):
                    emit({'percent': 50 + int((idx/total_al)*40), 'message': f'Álbumes: {album.titulo}', 'processed': idx, 'total': total_al})
                    titulo_norm = normalizar_album(album.titulo)
                    
                    album_existente = Album.query.filter(Album.titulo == titulo_norm, Album.artista_id == album.artista_id, Album.id < album.id).first()
                    if album_existente:
                        for cancion in album.canciones:
                            cancion.album_id = album_existente.id
                        db.session.delete(album)
                    elif titulo_norm != album.titulo:
                        album.titulo = titulo_norm
                db.session.commit()
                
                emit({
                    'status': 'done',
                    'percent': 100,
                    'message': 'Limpieza terminada con éxito.',
                    'summary': {'agregadas': 0, 'actualizadas': renombrados, 'omitidas': mergeados, 'procesadas': total + total_al}
                })
            except Exception as e:
                emit({'status': 'error', 'message': str(e), 'percent': 100})

    import threading
    t = threading.Thread(target=_run_clean)
    t.start()
    return jsonify({'message': 'started', 'task_id': task_id})


@admin_bp.route('/admin/escanear/start', methods=['POST'])
def admin_scan_start():
    """Inicia un escaneo completo vía RQ worker."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    existing_tid, existing_task = scan_get_active()
    if existing_tid and existing_task and existing_task.get('status') in ('running', 'enriching'):
        return jsonify({'error': 'scan_in_progress', 'task_id': existing_tid}), 409

    task_id = str(uuid.uuid4())

    scan_set_active(task_id)
    scan_task_set(task_id, {
        'task_id': task_id, 'status': 'running', 'percent': 0,
        'message': 'Preparando escaneo...', 'processed': 0, 'total': 0,
        'current_file': None, 'summary': None, 'error': None,
        'started_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    })

    from task_queue import enqueue
    from tasks import run_full_scan
    enqueue(run_full_scan, task_id)
    return jsonify({'task_id': task_id})


@admin_bp.route('/admin/escanear/quick', methods=['POST'])
def admin_scan_quick():
    """Inicia un escaneo rápido vía RQ worker."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    existing_tid, existing_task = scan_get_active()
    if existing_tid and existing_task and existing_task.get('status') in ('running', 'enriching'):
        return jsonify({'error': 'scan_in_progress', 'task_id': existing_tid}), 409

    task_id = str(uuid.uuid4())

    scan_set_active(task_id)
    scan_task_set(task_id, {
        'task_id': task_id, 'status': 'running', 'percent': 0,
        'message': 'Iniciando escaneo rápido...', 'processed': 0, 'total': 0,
        'current_file': None, 'summary': None, 'error': None,
        'started_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    })

    from task_queue import enqueue
    from tasks import run_quick_scan
    enqueue(run_quick_scan, task_id)
    return jsonify({'task_id': task_id})


@admin_bp.route('/admin/escanear/active', methods=['GET'])
def admin_scan_active():
    """Devuelve el escaneo activo actual si hay uno en curso."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    tid, task = scan_get_active()
    if tid and task and task.get('status') in ('running', 'enriching'):
        return jsonify({'task_id': tid, 'status': task.get('status', 'unknown')})
    return jsonify({}), 200

    return jsonify({'active': False}), 200



@admin_bp.route('/admin/escanear/status/<task_id>', methods=['GET'])
def admin_scan_status(task_id):
    """Devuelve el estado de un escaneo iniciado con /admin/escanear/start."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    task = scan_task_get(task_id)
    if not task:
        return jsonify({'error': 'task_not_found'}), 404
    return jsonify(task)


@admin_bp.route('/admin')
def admin_panel():
    """Panel de administración con acciones disponibles."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Parsear CHANGELOG para mostrarlo en el admin
    import re as _re
    import requests as _requests
    from config import Config, BASE_DIR
    
    versions = []
    cl_content = ""
    
    # 1. Intentar obtener el changelog desde GitHub
    try:
        github_url = 'https://raw.githubusercontent.com/GamersEC/ducksound/main/CHANGELOG.md'
        resp = _requests.get(github_url, timeout=5)
        if resp.status_code == 200:
            cl_content = resp.text
    except Exception as e:
        print(f"Remote changelog fetch failed: {e}")

    # 2. Fallback al archivo local
    if not cl_content:
        changelog_path = os.path.join(BASE_DIR, 'CHANGELOG.md')
        try:
            if os.path.exists(changelog_path):
                with open(changelog_path, 'r', encoding='utf-8') as f:
                    cl_content = f.read()
        except Exception as e:
            print(f"Local changelog read failed: {e}")

    # 3. Parseo robusto línea por línea
    if cl_content:
        lines = cl_content.splitlines()
        current_version = None
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            
            # Detectar inicio de versión: ## [1.2.0] ...
            if stripped.startswith('## '):
                header = stripped[3:].strip()
                m = _re.match(r'\[?([\d\.]+)\]?(\s*-\s*(.+))?', header)
                if m:
                    number = m.group(1)
                    date = m.group(3).strip() if m.group(3) else ''
                    
                    current_version = {
                        'number': number,
                        'date': date,
                        'title': '',
                        'sections': []
                    }
                    versions.append(current_version)
                    current_section = None
                continue
            
            if not current_version: continue
            
            # Detectar sección: ### Título
            if stripped.startswith('### '):
                title_text = stripped[4:].strip()
                # Si es el primer ###, es el título de la versión
                if not current_version['title']:
                    current_version['title'] = title_text
                else:
                    # Si ya hay título, es una sección de cambios
                    if current_section:
                        current_version['sections'].append(current_section)
                    current_section = {'title': title_text, 'entries': []}
                continue
                
            # Detectar subsección: #### Subtítulo
            if stripped.startswith('#### '):
                if current_section:
                    current_version['sections'].append(current_section)
                current_section = {'title': stripped[5:].strip(), 'entries': []}
                continue
                
            # Detectar entrada: - Cambio
            if stripped.startswith('- '):
                entry = stripped[2:].strip()
                if not current_section:
                    # Crear sección por defecto si no hay una
                    current_section = {'title': 'Cambios', 'entries': []}
                current_section['entries'].append(entry)
        
        # Añadir última sección si existe
        if current_version and current_section:
            current_version['sections'].append(current_section)
    
    return render_template('admin.html', changelog_versions=versions)


@admin_bp.route('/admin/check-update', methods=['GET'])
@route_cache(ttl_seconds=3600)  # Caché de 1 hora
def admin_check_update():
    """Consulta GitHub Releases para verificar si hay una versión más nueva."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    import requests as _requests
    from flask import current_app
    current_version = current_app.config.get('APP_VERSION', '1.0.0')
    try:
        resp = _requests.get(
            'https://api.github.com/repos/GamersEC/ducksound/releases/latest',
            headers={'Accept': 'application/vnd.github.v3+json',
                     'User-Agent': 'DuckSound-UpdateChecker'},
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            latest_tag = data.get('tag_name', '').lstrip('vV')
            return jsonify({
                'current': current_version,
                'latest': latest_tag,
                'name': data.get('name', ''),
                'url': data.get('html_url', ''),
                'body': data.get('body', ''),
                'published_at': data.get('published_at', ''),
                'update_available': latest_tag != current_version and latest_tag > current_version
            })
        elif resp.status_code == 404:
            return jsonify({
                'current': current_version,
                'latest': current_version,
                'update_available': False,
                'message': 'No hay releases publicados aún'
            })
        else:
            return jsonify({'error': f'GitHub API respondió {resp.status_code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e), 'current': current_version}), 502



@admin_bp.route('/admin/enrich-artists', methods=['POST'])
def admin_enrich_artists():
    """Enriquece todos los artistas sin foto/biografía desde APIs públicas."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    from metadata_fetcher import enrich_all_artists
    try:
        actualizados, total = enrich_all_artists()
        return jsonify({
            'success': True,
            'actualizados': actualizados,
            'total': total,
            'message': f'Metadatos actualizados para {actualizados} de {total} artistas'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/artistas')
def admin_artistas():
    """Panel para gestionar artistas (MBID, nombres, etc.)."""
    if not _is_admin_request():
        return redirect(url_for('login'))
    query = request.args.get('q', '').strip()
    if query:
        artistas = Artista.query.filter(Artista.nombre.ilike(f'%{query}%')).order_by(Artista.nombre).all()
    else:
        artistas = Artista.query.order_by(Artista.nombre).all()
    total = Artista.query.count()
    con_mbid = Artista.query.filter(Artista.musicbrainz_id.isnot(None)).count()
    return render_template('admin_artistas.html', artistas=artistas, total=total, con_mbid=con_mbid, query=query)


@admin_bp.route('/admin/artistas/preview-metadata', methods=['POST'])
def admin_preview_artist_metadata():
    """Proporciona una previsualización de metadatos basada en MBID o Deezer ID."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    mbid = (data.get('mbid') or '').strip()
    deezer_id = (data.get('deezer_id') or '').strip()
    
    if not mbid and not deezer_id:
        return jsonify({'error': 'Se requiere al menos un MBID o Deezer ID'}), 400
    
    from metadata_fetcher import preview_artist_metadata
    preview = preview_artist_metadata(mbid=mbid if mbid else None, deezer_id=deezer_id if deezer_id else None)
    
    if not preview:
        return jsonify({'success': False, 'message': 'No se encontró ningún artista con esos IDs'}), 404
    
    return jsonify({'success': True, 'metadata': preview})


@admin_bp.route('/admin/artistas/<int:artist_id>/update-mbid', methods=['POST'])
def admin_update_artist_mbid(artist_id):
    try:
        if not _is_admin_request():
            return jsonify({'error': 'Unauthorized'}), 401
        artista = db.session.get(Artista, artist_id)
        if not artista:
            return jsonify({'error': 'Artista no encontrado'}), 404
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
        
        mbid = (data.get('mbid') or '').strip()
        deezer_id = (data.get('deezer_id') or '').strip()
        nombre = (data.get('nombre') or '').strip()
        
        # Resolver el MBID final si se proporcionó Deezer ID
        final_mbid = mbid
        if deezer_id:
            from metadata_fetcher import get_artista_by_deezer_id
            d_data = get_artista_by_deezer_id(deezer_id)
            if d_data:
                resolved = d_data.get('musicbrainz_id')
                if resolved:
                    final_mbid = resolved
        
        if final_mbid:
            final_mbid = final_mbid.lower()
            if len(final_mbid) != 36:
                return jsonify({'error': 'MBID debe tener 36 caracteres (UUID)'}), 400
            existing = Artista.query.filter(Artista.musicbrainz_id == final_mbid, Artista.id != artist_id).first()
            if existing:
                return jsonify({'error': f'El MBID ya pertenece a {existing.nombre}'}), 400
        
        old_mbid = artista.musicbrainz_id
        artista.musicbrainz_id = final_mbid or None
        if nombre:
            from metadata_normalizer import normalizar_artista
            artista.nombre = nombre
            artista.nombre_normalizado = normalizar_artista(nombre)
        db.session.commit()

        updated_metadata = {}
        # Reset and Enrich if the identity has changed (including removing the ID)
        if final_mbid != old_mbid:
            artista.foto_url = None
            artista.biografia = None
            db.session.commit()
            
            if final_mbid:
                from musicbrainz_client import get_artista_name
                mb_name = get_artista_name(final_mbid)
                if mb_name:
                    from metadata_normalizer import normalizar_artista
                    mb_norm = normalizar_artista(mb_name)
                    conflict = Artista.query.filter(
                        Artista.id != artist_id,
                        (Artista.nombre == mb_name) | (Artista.nombre_normalizado == mb_norm)
                    ).first()
                    if conflict:
                        updated_metadata['nombre_conflicto'] = conflict.nombre
                    else:
                        artista.nombre = mb_name
                        artista.nombre_normalizado = mb_norm
                        updated_metadata['nombre'] = mb_name
                
                from metadata_fetcher import enrich_artist
                enrich_artist(artista, commit=True)
                updated_metadata['foto_url'] = artista.foto_url
                updated_metadata['biografia'] = artista.biografia
                db.session.commit()
            else:
                # If ID was removed, we just leave metadata as None
                updated_metadata['foto_url'] = None
                updated_metadata['biografia'] = None
                db.session.commit()
        else:
            # If ID is the same, just return current state
            updated_metadata['foto_url'] = artista.foto_url
            updated_metadata['biografia'] = artista.biografia

        return jsonify({
            'success': True,
            'message': f'Artista "{artista.nombre}" actualizado',
            'metadata': updated_metadata
        })
    except Exception as e:
        current_app.logger.exception('Error in admin_update_artist_mbid')
        return jsonify({'error': str(e)}), 500



@admin_bp.route('/admin/artistas/<int:artist_id>/lookup-mbid', methods=['POST'])
def admin_lookup_artist_mbid(artist_id):
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
    artista = db.session.get(Artista, artist_id)
    if not artista:
        return jsonify({'error': 'Artista no encontrado'}), 404
    from musicbrainz_client import buscar_artista
    try:
        resultado = buscar_artista(artista.nombre)
        if resultado:
            return jsonify({
                'success': True,
                'mbid': resultado['mbid'],
                'nombre': resultado['nombre'],
                'disambiguation': resultado.get('disambiguation', '')
            })
        return jsonify({'success': False, 'message': 'No se encontró en MusicBrainz'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/estadisticas')
def admin_estadisticas():
    """Panel de estadísticas básicas de la plataforma."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    from models import HistorialEscucha
    
    resumen = {
        'usuarios': Usuario.query.count(),
        'artistas': Artista.query.count(),
        'albums': Album.query.count(),
        'canciones': Cancion.query.count(),
        'total_plays': HistorialEscucha.query.count(),
        'colecciones': Coleccion.query.count(),
        'favoritos': Favorito.query.count()
    }

    # Top Canciones globales (top 5)
    top_songs = db.session.query(Cancion, db.func.count(HistorialEscucha.id).label('plays'))\
        .join(HistorialEscucha)\
        .group_by(Cancion.id)\
        .order_by(db.desc('plays')).limit(5).all()

    # Top Artista global
    top_artist = db.session.query(Artista, db.func.count(HistorialEscucha.id).label('plays'))\
        .select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .group_by(Artista.id)\
        .order_by(db.desc('plays')).first()

    # Género más escuchado global
    top_genre = db.session.query(Cancion.genero, db.func.count(HistorialEscucha.id).label('plays'))\
        .join(HistorialEscucha)\
        .filter(Cancion.genero.isnot(None), Cancion.genero != '')\
        .group_by(Cancion.genero)\
        .order_by(db.desc('plays')).first()

    canciones_recientes = Cancion.query.order_by(Cancion.fecha_agregada.desc()).limit(8).all()
    
    return render_template('admin_stats.html', 
                           resumen=resumen, 
                           canciones_recientes=canciones_recientes,
                           top_songs=top_songs,
                           top_artist=top_artist,
                           top_genre=top_genre)




# --------------------------------------------
# Endpoints API JSON
# --------------------------------------------


@api_bp.route('/api/artist/<int:artist_id>/albums', methods=['GET'])
def api_albums_by_artist(artist_id):
    """Devuelve los álbumes de un artista (por id) en JSON"""
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
    """Devuelve todas las canciones de un artista en JSON ordenadas por álbum, disco y pista"""
    artista = Artista.query.get_or_404(artist_id)
    songs = Cancion.query.filter_by(artista_id=artista.id).all()
    
    # Primero agrupar por álbum
    albums_dict = {}
    for s in songs:
        album_id = s.album_id if s.album_id is not None else 0
        if album_id not in albums_dict:
            albums_dict[album_id] = {
                'album': s.album_obj,
                'songs': []
            }
        albums_dict[album_id]['songs'].append(s)
    
    # Ordenar álbumes por año (o por ID si no hay año)
    def sort_album_key(item):
        album = item[1]['album']
        if album and hasattr(album, 'anio') and album.anio:
            return (album.anio, album.id or 0)
        return (9999, item[0])
    
    albums_ordenados = sorted(albums_dict.items(), key=sort_album_key)
    
    # Para cada álbum, ordenar por disco y pista
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        import re
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
    result = []
    for album_id, album_data in albums_ordenados:
        album = album_data['album']
        album_songs = album_data['songs']
        
        # Agrupar por número de disco dentro del álbum
        discos_dict = {}
        for s in album_songs:
            disc_num = s.numero_disco if s.numero_disco is not None else 1
            if disc_num not in discos_dict:
                discos_dict[disc_num] = []
            discos_dict[disc_num].append(s)
        
        # Ordenar discos y luego canciones por pista
        discos_ordenados = sorted(discos_dict.items())
        for disc_num, canciones_disco in discos_ordenados:
            canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
            for c in canciones_ordenadas:
                result.append({
                    'id': c.id,
                    'titulo': c.titulo,
                    'artista': artista.nombre,
                    'album': album.titulo if album else 'Desconocido',
                    'audio': f'/audio/{c.id}',
                    'cover': f'/album-art/{c.id}',
                    'lyrics': f'/lyrics/{c.id}',
                    'numero_pista': c.numero_pista,
                    'numero_disco': c.numero_disco
                })
    
    return jsonify(result)


@api_bp.route('/api/album/<int:album_id>/canciones', methods=['GET'])
def api_songs_by_album(album_id):
    """Devuelve todas las canciones de un álbum en JSON ordenadas por disco y pista"""
    album = Album.query.get_or_404(album_id)
    songs = Cancion.query.filter_by(album_id=album.id).all()
    
    # Agrupar por número de disco
    discos_dict = {}
    for s in songs:
        disc_num = s.numero_disco if s.numero_disco is not None else 1
        if disc_num not in discos_dict:
            discos_dict[disc_num] = []
        discos_dict[disc_num].append(s)
    
    # Ordenar discos numéricamente
    discos_ordenados = sorted(discos_dict.items())
    
    # Dentro de cada disco, ordenar por número de pista
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        import re
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
    # Construir resultado final ordenado
    result = []
    for disc_num, canciones_disco in discos_ordenados:
        canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
        for c in canciones_ordenadas:
            result.append({
                'id': c.id,
                'titulo': c.titulo,
                'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
                'audio': f'/audio/{c.id}',
                'cover': f'/album-art/{c.id}',
                'lyrics': f'/lyrics/{c.id}',
                'numero_pista': c.numero_pista,
                'numero_disco': c.numero_disco
            })
    
    return jsonify(result)


# --------------------------------------------
# Helpers
# --------------------------------------------
from sqlalchemy import func as sqlfunc


def _album_cover_url(album):
    """Devuelve la URL para mostrar la portada de un álbum.
    Si el álbum tiene portada_url (de Deezer), la usa directamente.
    Si no, busca la primera canción con imagen local y genera URL local.
    Retorna string URL o None.
    """
    if album.portada_url:
        return album.portada_url  # URL directa de Deezer
    primer_cancion = Cancion.query.filter_by(album_id=album.id).first()
    if primer_cancion:
        return url_for('servir_album_art', cancion_id=primer_cancion.id)
    return None


def _album_total_duration(album):
    """Devuelve la duración total de un álbum en segundos."""
    result = db.session.query(sqlfunc.sum(Cancion.duracion)).filter(Cancion.album_id == album.id).scalar()
    return result or 0


# --------------------------------------------
# Rutas de exploración / navegación
# --------------------------------------------


@browse_bp.route('/explore')
def explore():
    from sqlalchemy import func
    artists = Artista.query.order_by(Artista.nombre).all()
    # Query optimizada: álbumes + conteo de canciones en una sola query
    album_stats = db.session.query(
        Album, func.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).group_by(Album.id).order_by(Album.titulo).limit(20).all()
    albums_data = []
    for al, track_count in album_stats:
        albums_data.append({
            'album': al,
            'cover_url': _album_cover_url(al),
            'track_count': track_count
        })
    return render_template('explore.html', artists=artists, albums_data=albums_data)


@browse_bp.route('/artists')
def artists_list():
    from sqlalchemy import func
    
    # 1. Obtener conteos de álbumes por artista en una sola query
    album_counts = db.session.query(Album.artista_id, func.count(Album.id)).group_by(Album.artista_id).all()
    album_dict = {a_id: count for a_id, count in album_counts}
    
    # 2. Obtener conteos de canciones por artista en una sola query
    song_counts = db.session.query(Cancion.artista_id, func.count(Cancion.id)).group_by(Cancion.artista_id).all()
    song_dict = {a_id: count for a_id, count in song_counts}

    artists = Artista.query.order_by(Artista.nombre).all()
    artists_data = []
    
    # Pre-cargamos portadas de todos los álbumes para evitar query N+1 en las portadas
    # Solo tomamos un álbum por artista (el primero por orden de ID)
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
            'artist': a,
            'album_count': ac,
            'song_count': sc,
            'cover_url': cover_url
        })
    return render_template('artists.html', artists_data=artists_data)


@browse_bp.route('/artist/<int:artist_id>')
def artist_detail(artist_id):
    from sqlalchemy import func
    artist = Artista.query.get_or_404(artist_id)
    songs = Cancion.query.filter_by(artista_id=artist.id).order_by(Cancion.album_id, Cancion.ruta_archivo_audio).all()
    # Query optimizada: álbumes + conteo de canciones en una sola query
    album_stats = db.session.query(
        Album, func.count(Cancion.id).label('track_count')
    ).outerjoin(Cancion).filter(Album.artista_id == artist.id).group_by(Album.id).order_by(Album.anio.desc()).all()
    albums_data = []
    for al, track_count in album_stats:
        albums_data.append({
            'album': al,
            'cover_url': _album_cover_url(al),
            'track_count': track_count
        })
    album_count = len(albums_data)
    song_count = len(songs)
    return render_template('artist.html', artist=artist, albums_data=albums_data, songs=songs, album_count=album_count, song_count=song_count)


@browse_bp.route('/albums')
def albums_list():
    from sqlalchemy import func
    # Query optimizada: álbum + conteo + duración total en una sola query (elimina N+1)
    album_stats = db.session.query(
        Album,
        func.count(Cancion.id).label('track_count'),
        func.coalesce(func.sum(Cancion.duracion), 0).label('total_dur')
    ).outerjoin(Cancion).group_by(Album.id).order_by(Album.titulo).all()
    albums_data = []
    for al, track_count, total_dur in album_stats:
        albums_data.append({
            'album': al,
            'cover_url': _album_cover_url(al),
            'track_count': track_count,
            'total_duration': total_dur
        })
    return render_template('albums.html', albums_data=albums_data)


@browse_bp.route('/album/<int:album_id>')
def album_detail(album_id):
    import re
    album = Album.query.get_or_404(album_id)
    songs = Cancion.query.filter_by(album_id=album.id).all()
    
    # Agrupar por número de disco
    discos_dict = {}
    for s in songs:
        disc_num = s.numero_disco if s.numero_disco is not None else 1
        if disc_num not in discos_dict:
            discos_dict[disc_num] = []
        discos_dict[disc_num].append(s)
    
    # Ordenar discos numéricamente
    discos_ordenados = sorted(discos_dict.items())
    
    # Dentro de cada disco, ordenar por número de pista
    def get_track_num(c):
        if hasattr(c, 'numero_pista') and c.numero_pista is not None:
            return c.numero_pista
        filename = c.ruta_archivo_audio.replace('\\', '/').split('/')[-1]
        m = re.match(r'^\s*(\d+)', filename)
        return int(m.group(1)) if m else 9999
    
    discos = []
    for disc_num, canciones_disco in discos_ordenados:
        canciones_ordenadas = sorted(canciones_disco, key=get_track_num)
        discos.append((disc_num, canciones_ordenadas))
    
    cover_url = _album_cover_url(album)
    total_dur = _album_total_duration(album)
    track_count = len(songs)
    return render_template('album.html', album=album, discos=discos, cover_url=cover_url, total_duration=total_dur, track_count=track_count)


@api_bp.route('/api/daily-mix/<int:mix_id>/songs', methods=['GET'])
def api_daily_mix_songs(mix_id):
    """Devuelve las canciones de un daily mix en JSON."""
    mix = DailyMix.query.get_or_404(mix_id)
    canciones = [
        {
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
            'audio': f'/audio/{c.id}',
            'cover': f'/album-art/{c.id}',
            'lyrics': f'/lyrics/{c.id}'
        }
        for c in mix.canciones
    ]
    return jsonify(canciones)


@api_bp.route('/api/playlist/<int:playlist_id>/songs', methods=['GET'])
def api_songs_by_playlist(playlist_id):
    """Devuelve las canciones asociadas a una playlist en JSON"""
    playlist = Playlist.query.get_or_404(playlist_id)
    canciones = [c.to_dict() for c in playlist.canciones]
    return jsonify(canciones)


@api_bp.route('/api/audio-info/<int:cancion_id>', methods=['GET'])
def api_audio_info(cancion_id):
    """Devuelve la información de calidad de audio de una canción."""
    from models import Cancion as CancionModel
    c = CancionModel.query.get(cancion_id)
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
        'genero': c.genero
    })


@api_bp.route('/api/similares/<int:cancion_id>', methods=['GET'])
def api_similares(cancion_id):
    """Devuelve las canciones similares a la dada (por contenido acústico)."""
    try:
        # Importar aquí para evitar overhead al importar el blueprint desde app
        from importlib import import_module
        recommender = import_module('recommender')
        get_similar_songs = getattr(recommender, 'get_similar_songs')
        similares = get_similar_songs(cancion_id, top_k=10)
        return jsonify(similares)
    except Exception as e:
        # Registrar y devolver lista vacía para que el frontend no reciba 500
        try:
            current_app.logger.exception('Error al calcular similares')
        except Exception:
            pass
        return jsonify([]), 200


@api_bp.route('/api/cancion/<int:cancion_id>/lyrics', methods=['GET'])
def api_cancion_lyrics(cancion_id):
    """Devuelve la letra de una canción (sincronizada o plano) desde caché o API LRCLIB."""
    try:
        from lyrics_fetcher import obtener_o_descargar_letra
        from models import Cancion
        
        # Debug logging: mostrar información de la canción
        cancion = Cancion.query.get(cancion_id)
        if cancion:
            current_app.logger.info(f"Solicitando letra para canción ID {cancion_id}: '{cancion.titulo}' - '{cancion.artista_obj.nombre if cancion.artista_obj else 'Desconocido'}'")
            current_app.logger.info(f"Ruta LRC en BD: {cancion.ruta_archivo_lrc}")
            if cancion.ruta_archivo_lrc:
                exists = Path(cancion.ruta_archivo_lrc).exists()
                current_app.logger.info(f"Archivo LRC existe: {exists}")
        else:
            current_app.logger.info(f"Canción ID {cancion_id} no encontrada en BD")
        
        resultado = obtener_o_descargar_letra(cancion_id)
        
        if resultado:
            current_app.logger.info(f"Letra encontrada para canción ID {cancion_id}, tipo: {resultado.get('tipo')}")
            return jsonify(resultado), 200
        else:
            current_app.logger.info(f"Letra no encontrada para canción ID {cancion_id}")
            return jsonify({'error': 'Letra no encontrada'}), 404
            
    except Exception as e:
        # Registrar error pero no exponer detalles al cliente
        try:
            current_app.logger.exception('Error obteniendo letra')
        except Exception:
            pass
        return jsonify({'error': 'Error interno del servidor'}), 500


# ============================================
# API - Colecciones
# ============================================

@api_bp.route('/api/colecciones/crear', methods=['POST'])
def api_colecciones_crear():
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify({'error': 'No auth'}), 401
    
    # Soporta tanto JSON como form data
    if request.is_json:
        data = request.get_json()
        nombre = data.get('nombre', '').strip()
        descripcion = data.get('descripcion', '').strip()
    else:
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        
    if not nombre:
        if request.is_json:
            return jsonify({'error': 'Nombre requerido'}), 400
        else:
            return "Nombre requerido", 400
            
    c = Coleccion(nombre=nombre, descripcion=descripcion or None, usuario_id=usuario_id)
    db.session.add(c)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'ok': True, 'id': c.id, 'nombre': c.nombre})
    return redirect(url_for('coleccion_detail', coleccion_id=c.id))


@api_bp.route('/api/coleccion-lista', methods=['GET'])
def api_coleccion_lista():
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([])
    cols = Coleccion.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([{'id': c.id, 'nombre': c.nombre} for c in cols])


@api_bp.route('/api/colecciones/<int:coleccion_id>/add-album/<int:album_id>', methods=['POST'])
def api_coleccion_add_album(coleccion_id, album_id):
    usuario_id = session.get('user_id')
    c = Coleccion.query.get_or_404(coleccion_id)
    if c.usuario_id != usuario_id:
        return jsonify({'error': 'Forbidden'}), 403
    a = Album.query.get_or_404(album_id)
    if a not in c.albumes:
        c.albumes.append(a)
        db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/api/colecciones/<int:coleccion_id>/add-artist/<int:artist_id>', methods=['POST'])
def api_coleccion_add_artist(coleccion_id, artist_id):
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
    usuario_id = session.get('user_id')
    c = Coleccion.query.get_or_404(coleccion_id)
    if c.usuario_id != usuario_id:
        return jsonify({'error': 'Forbidden'}), 403
    song = Cancion.query.get_or_404(cancion_id)
    if song not in c.canciones:
        c.canciones.append(song)
        db.session.commit()
    return jsonify({'ok': True})


# ============================================
# API - Favoritos (Me gusta)
# ============================================

@api_bp.route('/api/favoritos', methods=['GET'])
def api_favoritos_list():
    """Devuelve los IDs de canciones favoritas del usuario actual."""
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([]), 200
    favoritos = Favorito.query.filter_by(usuario_id=usuario_id).all()
    return jsonify([f.cancion_id for f in favoritos])


@api_bp.route('/api/favoritos/toggle/<int:cancion_id>', methods=['POST'])
def api_favoritos_toggle(cancion_id):
    """Alterna el estado de favorito de una canción para el usuario actual."""
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
    """Devuelve la lista completa de canciones favoritas del usuario."""
    from models import Cancion
    usuario_id = session.get('user_id')
    if not usuario_id:
        return jsonify([]), 200

    favoritos = Favorito.query.filter_by(usuario_id=usuario_id)\
        .order_by(Favorito.fecha_agregado.desc()).all()

    canciones = []
    for fav in favoritos:
        c = Cancion.query.get(fav.cancion_id)
        if c:
            canciones.append({
                'id': c.id,
                'titulo': c.titulo,
                'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
                'album': c.album_obj.titulo if c.album_obj else None,
                'duracion': c.duracion,
                'cover': c.ruta_imagen_album,
                'lyrics': f'/lyrics/{c.id}'
            })
    return jsonify(canciones)


# ============================================
# ADMIN - Gestión de Usuarios
# ============================================

@admin_bp.route('/admin/usuarios', methods=['GET'])
def admin_usuarios_list():
    """Panel de administración de usuarios."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    usuarios = Usuario.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios)


@admin_bp.route('/admin/usuarios/crear', methods=['POST'])
def admin_crear_usuario():
    """Endpoint para que el admin cree nuevos usuarios."""
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    nombre_usuario = data.get('nombre_usuario', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user')  # 'user' o 'admin'

    if not nombre_usuario or not password:
        return jsonify({'error': 'nombre_usuario y password son requeridos'}), 400

    if len(password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400

    if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
        return jsonify({'error': 'El usuario ya existe'}), 400

    nuevo_usuario = Usuario(nombre_usuario=nombre_usuario, role=role)
    nuevo_usuario.set_password(password)
    db.session.add(nuevo_usuario)
    db.session.commit()

    return jsonify({
        'id': nuevo_usuario.id,
        'nombre_usuario': nuevo_usuario.nombre_usuario,
        'role': nuevo_usuario.role,
        'message': 'Usuario creado exitosamente'
    }), 201


# ========== API PARA PROGRESO DE LETRAS ==========

@api_bp.route('/api/lyrics-progress', methods=['GET'])
def api_lyrics_progress():
    """Devuelve el progreso actual de la descarga de letras en segundo plano."""
    try:
        from task_queue import progress_get
        p = progress_get('lyrics') or {}
        return jsonify({
            'active': p.get('active', False),
            'finished': p.get('finished', True),
            'total': p.get('total', 0),
            'completed': p.get('completed', 0),
            'downloaded': p.get('downloaded', 0),
            'errors': p.get('errors', 0),
            'current_song': p.get('current_song', ''),
            'percent': int((p.get('completed', 0) / max(p.get('total', 1), 1)) * 100) if p.get('total', 0) > 0 else 0
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'active': False, 'finished': True}), 500


# ========== API PARA PROGRESO DE MUSICBRAINZ ==========

@api_bp.route('/api/mb-progress', methods=['GET'])
def api_mb_progress():
    """Devuelve el progreso actual del enriquecimiento MusicBrainz."""
    try:
        from musicbrainz_client import get_mb_progress
        p = get_mb_progress()
        return jsonify({
            'active': p['active'],
            'finished': p['finished'],
            'total': p['total'],
            'completed': p['completed'],
            'found': p['found'],
            'current_artist': p['current_artist'],
            'message': p['message'],
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'active': False, 'finished': True}), 500


@api_bp.route('/api/search', methods=['GET'])
def api_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'songs': [], 'artists': [], 'albums': []})

    term = f'%{q}%'
    try:
        from unidecode import unidecode
        q_norm = unidecode(q)
    except Exception:
        q_norm = q
    term_norm = f'%{q_norm}%'

    songs = Cancion.query.filter(
        Cancion.titulo.ilike(term) | Cancion.titulo.ilike(term_norm)
    ).limit(8).all()
    artists = Artista.query.filter(
        (Artista.nombre.ilike(term)) | (Artista.nombre_normalizado.ilike(term_norm))
    ).limit(5).all()
    albums = Album.query.filter(
        Album.titulo.ilike(term) | Album.titulo.ilike(term_norm)
    ).limit(5).all()

    return jsonify({
        'songs': [{
            'id': s.id,
            'titulo': s.titulo,
            'artista': s.artista_obj.nombre if s.artista_obj else None,
            'audio': url_for('servir_audio', cancion_id=s.id),
            'cover': url_for('servir_album_art', cancion_id=s.id),
            'lyrics': url_for('servir_lyrics', cancion_id=s.id),
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
    })


