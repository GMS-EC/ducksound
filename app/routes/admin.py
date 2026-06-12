# -*- coding: utf-8 -*-
"""
Controlador de Rutas de Administración - DuckSound
===================================================
Este módulo encapsula todas las funciones y endpoints relacionados con el Panel de Control
del Administrador, incluyendo:
1. Indexación y escaneo de canciones (síncrono, asíncrono y rápido) mediante Redis/RQ y subprocesos.
2. Limpieza y normalización de la base de datos (eliminación de huérfanos, fusión de duplicados).
3. Visualización y sincronización de identidades de artistas con la base de datos de MusicBrainz.
4. Visualización del Changelog interactivo desde GitHub (rama main) y comprobación de actualizaciones.
5. Estadísticas avanzadas y agregadas de la plataforma a nivel global.
6. Operaciones CRUD y de gestión de cuentas de usuario.
"""

import os
import threading
import uuid
import re as _re
import time as _time
import requests as _requests
from datetime import datetime

from flask import Blueprint, request, session, jsonify, current_app, url_for
from config import Config
from app.models import db, Usuario, Artista, Album, Cancion, Coleccion, Favorito

# Servicios y utilidades externas desacopladas en la capa de servicios
from app.services.scanner import escanear_carpeta_audio, escaneo_rapido
from app.services.queue import (
    scan_task_set, scan_task_get, scan_set_active, scan_get_active, enqueue
)
from app.services.metadata import (
    normalizar_artista, normalizar_album,
    get_artista_name, buscar_artista, preview_artist_metadata,
    get_artista_by_deezer_id, enrich_artist, enrich_all_artists
)

# Declaración del Blueprint para la sección administrativa
admin_bp = Blueprint('admin', __name__)

# Caché en memoria para el changelog remoto de GitHub
_changelog_cache = {
    'content': None,
    'expires': 0
}


def _is_admin_session():
    """
    Comprueba si existe un usuario logueado en la sesión actual y si este posee
    el rol de administrador ('admin').
    
    Returns:
        bool: True si el usuario actual es administrador autenticado, False en caso contrario.
    """
    if 'user_id' not in session:
        return False

    usuario = db.session.get(Usuario, session['user_id'])
    return bool(usuario and usuario.is_admin())


def _is_admin_request():
    """
    Validador de peticiones administrativas.
    Al ser el repositorio público, se ha eliminado la validación por token de entorno estático
    para evitar vulnerabilidades de seguridad, confiando puramente en la autenticación por sesión segura.
    
    Returns:
        bool: True si la sesión actual pertenece a un administrador.
    """
    return _is_admin_session()


# ==============================================================================
# SECCIÓN 1: PROCESOS DE INDEXACIÓN Y ESCANEO DE MÚSICA (SÍNCRONOS/ASÍNCRONOS)
# ==============================================================================

@admin_bp.route('/admin/escanear', methods=['GET'])
def escanear_canciones():
    """
    Despierta síncronamente el escaneo de la biblioteca en disco de música.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        resumen = escanear_carpeta_audio()
        return jsonify({'success': True, 'resumen': resumen})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/clean_metadata', methods=['POST'])
def admin_clean_metadata():
    """
    Inicia un hilo en segundo plano para limpiar y consolidar la base de datos de metadatos.
    Limpia canciones huérfanas físicas, unifica artistas tipográficamente duplicados
    y fusiona álbumes de forma segura.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    # Bloquear si ya hay una tarea de escaneo o limpieza activa en segundo plano
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
        """Rutina asíncrona de limpieza y unificación de la biblioteca de DuckSound."""
        # Se necesita un contexto de aplicación de Flask para consultas de SQLAlchemy dentro de hilos
        from app import create_app
        app = create_app()
        
        with app.app_context():
            def emit(data):
                t = scan_task_get(task_id)
                if t:
                    t.update(data)
                    scan_task_set(task_id, t)
            
            try:
                emit({'message': 'Eliminando canciones huérfanas...', 'percent': 5})
                
                # 1. Eliminar canciones cuyo archivo físico ya no exista
                canciones = Cancion.query.all()
                eliminadas = 0
                for c in canciones:
                    if not os.path.exists(c.ruta_archivo_audio):
                        db.session.delete(c)
                        eliminadas += 1
                if eliminadas > 0:
                    db.session.commit()
                    
                    # Eliminar álbumes que se hayan quedado vacíos
                    albumes_all = Album.query.all()
                    for a in albumes_all:
                        if not a.canciones:
                            db.session.delete(a)
                            
                    # Eliminar artistas que no tengan obras ni álbumes
                    artistas_all = Artista.query.all()
                    for a in artistas_all:
                        if not a.canciones and not a.albums:
                            db.session.delete(a)
                    db.session.commit()

                # 2. Agrupación por coincidencia fonética o tipográfica de Artistas
                emit({'message': 'Buscando artistas para agrupar...', 'percent': 10})
                artistas = Artista.query.all()
                total = len(artistas)
                
                mergeados = 0
                renombrados = 0
                
                for idx, artista in enumerate(artistas):
                    emit({
                        'percent': 10 + int((idx/total)*40),
                        'message': f'Artistas: {artista.nombre}',
                        'processed': idx,
                        'total': total
                    })
                    nombre_norm = normalizar_artista(artista.nombre)
                    
                    # Comprobar si existe otro artista con el mismo nombre normalizado pero id inferior
                    artista_existente = Artista.query.filter(Artista.nombre == nombre_norm, Artista.id < artista.id).first()
                    if artista_existente:
                        # Reasignar obras y colecciones al artista canonical principal
                        from app.services.metadata import actualizar_tags_disco
                        for cancion in list(artista.canciones):
                            cancion.artista_obj = artista_existente
                            if cancion.ruta_archivo_audio:
                                try:
                                    actualizar_tags_disco(cancion.ruta_archivo_audio, artista=artista_existente.nombre)
                                except Exception:
                                    pass
                        for album in list(artista.albums):
                            album.artista = artista_existente
                        db.session.delete(artista)
                        mergeados += 1
                    elif nombre_norm != artista.nombre:
                        from app.services.metadata import actualizar_tags_disco
                        for cancion in artista.canciones:
                            if cancion.ruta_archivo_audio:
                                try:
                                    actualizar_tags_disco(cancion.ruta_archivo_audio, artista=nombre_norm)
                                except Exception:
                                    pass
                        artista.nombre = nombre_norm
                        renombrados += 1
                db.session.commit()
                
                # 3. Unificación de Álbumes duplicados del mismo artista
                emit({'message': 'Buscando álbumes para unificar...', 'percent': 50})
                albumes = Album.query.all()
                total_al = len(albumes)
                for idx, album in enumerate(albumes):
                    emit({
                        'percent': 50 + int((idx/total_al)*40),
                        'message': f'Álbumes: {album.titulo}',
                        'processed': idx,
                        'total': total_al
                    })
                    titulo_norm = normalizar_album(album.titulo)
                    
                    album_existente = Album.query.filter(
                        Album.titulo == titulo_norm,
                        Album.artista_id == album.artista_id,
                        Album.id < album.id
                    ).first()
                    if album_existente:
                        from app.services.metadata import actualizar_tags_disco
                        for cancion in list(album.canciones):
                            cancion.album_obj = album_existente
                            if cancion.ruta_archivo_audio:
                                try:
                                    actualizar_tags_disco(cancion.ruta_archivo_audio, album=album_existente.titulo)
                                except Exception:
                                    pass
                        db.session.delete(album)
                    elif titulo_norm != album.titulo:
                        from app.services.metadata import actualizar_tags_disco
                        for cancion in album.canciones:
                            if cancion.ruta_archivo_audio:
                                try:
                                    actualizar_tags_disco(cancion.ruta_archivo_audio, album=titulo_norm)
                                except Exception:
                                    pass
                        album.titulo = titulo_norm
                db.session.commit()
                
                # Notificar finalización de la tarea en Redis
                emit({
                    'status': 'done',
                    'percent': 100,
                    'message': 'Limpieza terminada con éxito.',
                    'summary': {
                        'agregadas': 0,
                        'actualizadas': renombrados,
                        'omitidas': mergeados,
                        'procesadas': total + total_al
                    }
                })
            except Exception as e:
                emit({'status': 'error', 'message': str(e), 'percent': 100})

    t = threading.Thread(target=_run_clean)
    t.start()
    return jsonify({'message': 'started', 'task_id': task_id})


@admin_bp.route('/admin/escanear/start', methods=['POST'])
def admin_scan_start():
    """
    Encola un escaneo completo de música de forma asíncrona mediante Redis Queue (RQ).
    Devuelve un task_id para que el cliente realice polling de progreso.
    """
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

    # Delegar la tarea al worker de Redis mediante la función desacoplada
    from app.services.queue import run_full_scan
    enqueue(run_full_scan, task_id)
    return jsonify({'task_id': task_id})


@admin_bp.route('/admin/escanear/quick', methods=['POST'])
def admin_scan_quick():
    """
    Encola un escaneo rápido de música de forma asíncrona mediante Redis Queue (RQ).
    Compara marcas de tiempo de modificación (mtime) para procesar únicamente archivos nuevos o alterados.
    """
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

    from app.services.queue import run_quick_scan
    enqueue(run_quick_scan, task_id)
    return jsonify({'task_id': task_id})


@admin_bp.route('/admin/escanear/active', methods=['GET'])
def admin_scan_active():
    """
    API de monitoreo simple para averiguar si existe un escaneo actualmente activo en el sistema.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    tid, task = scan_get_active()
    if tid and task and task.get('status') in ('running', 'enriching'):
        resp = jsonify({'task_id': tid, 'status': task.get('status', 'unknown')})
    else:
        resp = jsonify({})
        
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp, 200


@admin_bp.route('/admin/escanear/status/<task_id>', methods=['GET'])
def admin_scan_status(task_id):
    """
    API detallada de progreso que devuelve el diccionario de avance de un escaneo en base a su ID.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    task = scan_task_get(task_id)
    if not task:
        resp = jsonify({'error': 'task_not_found'})
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp, 404

    resp = jsonify(task)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ==============================================================================
# SECCIÓN 2: CONTROLADOR DEL PANEL DE CONTROL Y CHANGELOG INTERACTIVO
# ==============================================================================

@admin_bp.route('/admin')
def admin_panel():
    """
    Carga el Panel de Control del Administrador.
    Extrae el historial de cambios (CHANGELOG.md) desde la rama `main` en GitHub
    para reflejar las actualizaciones estables, con fallback al archivo local en disco.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
    
    versions = []
    cl_content = ""
    
    # Intentar traer el changelog desde GitHub con caché de 1 hora para latencia baja
    global _changelog_cache
    now = _time.time()
    if _changelog_cache['content'] and now < _changelog_cache['expires']:
        cl_content = _changelog_cache['content']
    else:
        try:
            # Traer explícitamente de la rama main para versiones estables
            github_url = 'https://raw.githubusercontent.com/GamersEC/ducksound/main/CHANGELOG.md'
            resp = _requests.get(github_url, timeout=2)
            if resp.status_code == 200:
                cl_content = resp.text
                _changelog_cache['content'] = cl_content
                _changelog_cache['expires'] = now + 3600
        except Exception as e:
            current_app.logger.warning(f"No se pudo consultar el CHANGELOG remoto desde GitHub: {e}")

    # Fallback local al archivo de la instalación del servidor
    if not cl_content:
        from config import BASE_DIR
        changelog_path = os.path.join(BASE_DIR, 'CHANGELOG.md')
        try:
            if os.path.exists(changelog_path):
                with open(changelog_path, 'r', encoding='utf-8') as f:
                    cl_content = f.read()
        except Exception as e:
            current_app.logger.error(f"Fallo al abrir CHANGELOG.md localmente: {e}")

    # Parsear y estructurar el Markdown de forma interactiva para Jinja2
    if cl_content:
        lines = cl_content.splitlines()
        current_version = None
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            
            # Encabezado principal de versión (e.g. ## [1.3.0] - 2026-05-18)
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
            
            # Secciones (e.g. ### Agregado o ### Corregido)
            if stripped.startswith('### '):
                title_text = stripped[4:].strip()
                if not current_version['title']:
                    current_version['title'] = title_text
                else:
                    if current_section:
                        current_version['sections'].append(current_section)
                    current_section = {'title': title_text, 'entries': []}
                continue
                
            if stripped.startswith('#### '):
                if current_section:
                    current_version['sections'].append(current_section)
                current_section = {'title': stripped[5:].strip(), 'entries': []}
                continue
                
            # Viñetas de cambios
            if stripped.startswith('- '):
                entry = stripped[2:].strip()
                if not current_section:
                    current_section = {'title': 'Cambios', 'entries': []}
                current_section['entries'].append(entry)
        
        if current_version and current_section:
            current_version['sections'].append(current_section)
            
        # Clasificar versiones en base a la instalada en Config para mostrarlas en la UI
        def parse_version(v_str):
            try:
                digits = _re.findall(r'\d+', v_str)
                return tuple(int(x) for x in digits)
            except Exception:
                return (0, 0, 0)
                
        current_version_tuple = parse_version(Config.APP_VERSION)
        for v in versions:
            v_tuple = parse_version(v['number'])
            if v_tuple > current_version_tuple:
                v['status'] = 'newer'
            elif v_tuple == current_version_tuple:
                v['status'] = 'current'
            else:
                v['status'] = 'older'
    
    return jsonify({'changelog_versions': versions})


@admin_bp.route('/admin/check-update', methods=['GET'])
def admin_check_update():
    """
    Compara la versión local instalada con el tag publicado en el release más reciente de GitHub.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    current_version = Config.APP_VERSION
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'DuckSound-UpdateChecker'
    }
        
    try:
        resp = _requests.get(
            'https://api.github.com/repos/GamersEC/ducksound/releases/latest',
            headers=headers,
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


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE IDENTIDADES Y METADATOS DE ARTISTAS (MUSICBRAINZ / DEEZER)
# ==============================================================================

@admin_bp.route('/admin/enrich-artists', methods=['POST'])
def admin_enrich_artists():
    """
    Llama asíncronamente al enriquecedor de metadatos de artistas.
    Trae biografías y fotos de perfil que falten en la base de datos DuckSound.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

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
    """
    API para la gestión de artistas.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
        
    query = request.args.get('q', '').strip()
    if query:
        artistas = Artista.query.filter(Artista.nombre.ilike(f'%{query}%')).order_by(Artista.nombre).all()
    else:
        artistas = Artista.query.order_by(Artista.nombre).all()
        
    total = Artista.query.count()
    con_mbid = Artista.query.filter(Artista.musicbrainz_id.isnot(None)).count()
    return jsonify({
        'artistas': [a.to_dict() for a in artistas],
        'total': total,
        'con_mbid': con_mbid,
        'query': query
    })


@admin_bp.route('/admin/artistas/preview-metadata', methods=['POST'])
def admin_preview_artist_metadata():
    """
    API instantánea de previsualización que consulta al scraper Deezer/MusicBrainz
    los detalles del artista que se obtendrían de los IDs proporcionados en el body.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    mbid = (data.get('mbid') or '').strip()
    deezer_id = (data.get('deezer_id') or '').strip()
    
    if not mbid and not deezer_id:
        return jsonify({'error': 'Se requiere al menos un MBID o Deezer ID'}), 400
    
    preview = preview_artist_metadata(mbid=mbid if mbid else None, deezer_id=deezer_id if deezer_id else None)
    
    if not preview:
        return jsonify({'success': False, 'message': 'No se encontró ningún artista con esos IDs'}), 404
    
    return jsonify({'success': True, 'metadata': preview})


@admin_bp.route('/admin/artistas/<int:artist_id>/update-mbid', methods=['POST'])
def admin_update_artist_mbid(artist_id):
    """
    Actualiza la identidad e IDs de referencia de un artista en la base de datos.
    Reinicia y gatilla el scraper para descargar las fotos oficiales y la biografía correspondiente.
    """
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
        
        final_mbid = mbid
        foto_desde_deezer = None
        nombre_desde_deezer = None
        if deezer_id:
            d_data = get_artista_by_deezer_id(deezer_id)
            if d_data:
                foto_desde_deezer = d_data.get('picture_xl') or d_data.get('picture_big') or d_data.get('picture_medium')
                nombre_desde_deezer = d_data.get('name')
        
        if final_mbid:
            final_mbid = final_mbid.lower()
            if len(final_mbid) != 36:
                return jsonify({'error': 'MBID debe tener 36 caracteres (UUID)'}), 400
            existing = Artista.query.filter(Artista.musicbrainz_id == final_mbid, Artista.id != artist_id).first()
            if existing:
                return jsonify({'error': f'El MBID ya pertenece a {existing.nombre}'}), 400
        
        old_mbid = artista.musicbrainz_id
        old_nombre = artista.nombre
        artista.musicbrainz_id = final_mbid or None
        if nombre:
            artista.nombre = nombre
            artista.nombre_normalizado = normalizar_artista(nombre)
        db.session.commit()

        updated_metadata = {}
        mbid_changed = (final_mbid or None) != old_mbid
        nombre_changed = nombre and (nombre != old_nombre)
        deezer_provided = bool(deezer_id)
        deezer_only = deezer_provided and not final_mbid
        
        if mbid_changed or nombre_changed or deezer_provided:
            old_foto_url = artista.foto_url
            old_biografia = artista.biografia
            
            if mbid_changed or nombre_changed:
                # Resetear metadatos anteriores si la identidad (MBID o nombre) cambió
                artista.foto_url = None
                artista.biografia = None
                db.session.commit()
            
            if final_mbid:
                mb_name = get_artista_name(final_mbid)
                if mb_name:
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
                
                enrich_artist(artista, commit=True)
            
            # Aplicar foto de Deezer (tiene prioridad sobre lo que enrich_artist haya encontrado)
            if foto_desde_deezer:
                artista.foto_url = foto_desde_deezer
            
            # Si es solo Deezer y se obtuvo un nombre, actualizar si el usuario no lo cambió manualmente
            if deezer_only and nombre_desde_deezer and not nombre:
                artista.nombre = nombre_desde_deezer
                artista.nombre_normalizado = normalizar_artista(nombre_desde_deezer)
                updated_metadata['nombre'] = nombre_desde_deezer
            
            updated_metadata['foto_url'] = artista.foto_url or old_foto_url
            updated_metadata['biografia'] = artista.biografia or old_biografia
            
            # Preservar datos anteriores como fallback si no se encontraron nuevos y no hubo cambio de identidad
            if not mbid_changed and not nombre_changed:
                if not artista.foto_url and old_foto_url:
                    artista.foto_url = old_foto_url
                if not artista.biografia and old_biografia:
                    artista.biografia = old_biografia
            db.session.commit()
        else:
            updated_metadata['foto_url'] = artista.foto_url
            updated_metadata['biografia'] = artista.biografia
        
        # Incluir siempre el MBID final y nombre en la respuesta para que el frontend se actualice
        updated_metadata['mbid'] = artista.musicbrainz_id or ''
        if 'nombre' not in updated_metadata:
            updated_metadata['nombre'] = artista.nombre

        # Sincronizar nombre en los tags físicos en disco si cambió
        if artista.nombre != old_nombre:
            from app.services.metadata import actualizar_tags_disco
            for cancion in artista.canciones:
                if cancion.ruta_archivo_audio:
                    try:
                        actualizar_tags_disco(cancion.ruta_archivo_audio, artista=artista.nombre)
                    except Exception as tag_err:
                        current_app.logger.warning(
                            f"[Admin Artist Update] Error escribiendo tag al disco para {cancion.ruta_archivo_audio}: {tag_err}"
                        )
 
        return jsonify({
            'success': True,
            'message': f'Artista "{artista.nombre}" actualizado',
            'metadata': updated_metadata
        })
    except Exception as e:
        current_app.logger.exception('Error en admin_update_artist_mbid')
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/artistas/<int:artist_id>/lookup-mbid', methods=['POST'])
def admin_lookup_artist_mbid(artist_id):
    """
    Busca de manera interactiva y automática en los servidores de MusicBrainz
    proponiendo un MBID para el artista basado en su nombre DuckSound.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
        
    artista = db.session.get(Artista, artist_id)
    if not artista:
        return jsonify({'error': 'Artista no encontrado'}), 404
        
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


# ==============================================================================
# SECCIÓN 4: ESTADÍSTICAS GLOBALES DEL SISTEMA Y METRICAS
# ==============================================================================

@admin_bp.route('/admin/estadisticas')
def admin_estadisticas():
    """
    Carga el Panel de Estadísticas Administrativas.
    Genera métricas de uso agregando el historial global de reproducciones y bibliotecas.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    from app.models import HistorialEscucha
    import shutil
    
    resumen = {
        'usuarios': Usuario.query.count(),
        'artistas': Artista.query.count(),
        'albums': Album.query.count(),
        'canciones': Cancion.query.count(),
        'total_plays': HistorialEscucha.query.count(),
        'colecciones': Coleccion.query.count(),
        'favoritos': Favorito.query.count()
    }

    # Obtener el Top 5 de canciones más reproducidas a nivel global
    top_songs = db.session.query(Cancion, db.func.count(HistorialEscucha.id).label('plays'))\
        .join(HistorialEscucha)\
        .group_by(Cancion.id)\
        .order_by(db.desc('plays')).limit(5).all()

    # Obtener el Artista más escuchado a nivel global
    top_artist = db.session.query(Artista, db.func.count(HistorialEscucha.id).label('plays'))\
        .select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .group_by(Artista.id)\
        .order_by(db.desc('plays')).first()

    # Obtener el Género más escuchado a nivel global
    top_genre = db.session.query(Cancion.genero, db.func.count(HistorialEscucha.id).label('plays'))\
        .join(HistorialEscucha)\
        .filter(Cancion.genero.isnot(None), Cancion.genero != '')\
        .group_by(Cancion.genero)\
        .order_by(db.desc('plays')).first()

    # Canciones agregadas recientemente
    canciones_recientes = Cancion.query.order_by(Cancion.fecha_agregada.desc()).limit(8).all()

    # Actividad de escucha reciente (últimas 15 reproducciones)
    recientes = HistorialEscucha.query.order_by(HistorialEscucha.reproducido_en.desc()).limit(15).all()
    actividad_reciente = []
    for r in recientes:
        actividad_reciente.append({
            'id': r.id,
            'nombre_usuario': r.usuario.nombre_usuario if r.usuario else 'Desconocido',
            'cancion_titulo': r.cancion.titulo if r.cancion else 'Desconocido',
            'artista_nombre': r.cancion.artista_obj.nombre if r.cancion and r.cancion.artista_obj else 'Desconocido',
            'reproducido_en': r.reproducido_en.isoformat() if r.reproducido_en else None,
            'skip': r.skip
        })

    # Información de disco del volumen de datos
    data_dir = '/data' if os.path.exists('/data') else '.'
    disk_total, disk_used, disk_free = shutil.disk_usage(data_dir)
    disk_usage = {
        'total': disk_total,
        'used': disk_used,
        'free': disk_free,
        'percent': round((disk_used / disk_total) * 100, 1) if disk_total > 0 else 0
    }

    # Información de tamaños de caché
    transcode_size = 0
    original_size = 0
    try:
        if Config.TRANSCODE_CACHE_FOLDER.exists():
            transcode_size = sum(f.stat().st_size for f in Config.TRANSCODE_CACHE_FOLDER.glob('**/*') if f.is_file())
        if Config.ORIGINAL_CACHE_FOLDER.exists():
            original_size = sum(f.stat().st_size for f in Config.ORIGINAL_CACHE_FOLDER.glob('**/*') if f.is_file())
    except Exception as e:
        current_app.logger.warning(f"Error al calcular tamaños de caché: {e}")

    return jsonify({
        'resumen': resumen, 
        'canciones_recientes': [c.to_dict() for c in canciones_recientes],
        'top_songs': [{'cancion': c.to_dict(), 'plays': p} for c, p in top_songs],
        'top_artist': {'artista': top_artist[0].to_dict(), 'plays': top_artist[1]} if top_artist else None,
        'top_genre': {'genero': top_genre[0], 'plays': top_genre[1]} if top_genre else None,
        'actividad_reciente': actividad_reciente,
        'disk_usage': disk_usage,
        'cache': {
            'transcode_size': transcode_size,
            'original_size': original_size,
            'total_size': transcode_size + original_size
        }
    })


@admin_bp.route('/admin/cache/clear', methods=['POST'])
def admin_clear_cache():
    """
    Vacía las carpetas de caché local de audio transcodificado y original.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        transcode_folder = Config.TRANSCODE_CACHE_FOLDER
        original_folder = Config.ORIGINAL_CACHE_FOLDER
        
        transcode_count = 0
        if transcode_folder.exists():
            for f in transcode_folder.iterdir():
                if f.is_file():
                    f.unlink()
                    transcode_count += 1
                    
        original_count = 0
        if original_folder.exists():
            for f in original_folder.iterdir():
                if f.is_file():
                    f.unlink()
                    original_count += 1
                    
        return jsonify({
            'success': True,
            'message': f'Caché vaciado. Se eliminaron {transcode_count} archivos de transcodificación y {original_count} archivos originales.'
        })
    except Exception as e:
        return jsonify({'error': f'Error al vaciar caché: {str(e)}'}), 500


# ==============================================================================
# SECCIÓN 5: GESTIÓN Y PANEL CRUD DE USUARIOS
# ==============================================================================

@admin_bp.route('/admin/usuarios', methods=['GET'])
def admin_usuarios_list():
    """
    Renderiza el Panel de Gestión de Usuarios y lista todas las cuentas registradas con metadatos enriquecidos.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    usuarios = Usuario.query.all()
    res = []
    for u in usuarios:
        d = u.to_dict()
        d['fecha_creacion'] = u.fecha_creacion.isoformat() if u.fecha_creacion else None
        d['sesiones_activas'] = u.sesiones.count()
        
        # Buscar última actividad
        last_active = None
        for s in u.sesiones:
            if not last_active or (s.ultima_actividad and s.ultima_actividad > last_active):
                last_active = s.ultima_actividad
        d['ultima_actividad'] = last_active.isoformat() if last_active else None
        res.append(d)

    return jsonify({'usuarios': res})


@admin_bp.route('/admin/usuarios/crear', methods=['POST'])
def admin_crear_usuario():
    """
    Crea manualmente una nueva cuenta de usuario en la plataforma.
    Valida contraseñas y unicidad de nombre de usuario de forma segura.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    nombre_usuario = data.get('nombre_usuario', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user')

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
    return jsonify({'success': True, 'message': 'Usuario creado correctamente'})


@admin_bp.route('/admin/usuarios/<int:user_id>/editar', methods=['POST'])
def admin_editar_usuario(user_id):
    """
    Edita la información de un usuario (nombre, contraseña o rol).
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    usuario = db.session.get(Usuario, user_id)
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    data = request.get_json() or {}
    nombre_usuario = data.get('nombre_usuario', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user')

    if nombre_usuario:
        existente = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
        if existente and existente.id != user_id:
            return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
        usuario.nombre_usuario = nombre_usuario

    if password:
        if len(password) < 6:
            return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        usuario.set_password(password)

    # Prevenir que un admin se quite privilegios a sí mismo
    from flask import session
    current_user_id = session.get('user_id')
    if usuario.id == current_user_id and role != 'admin':
        return jsonify({'error': 'No puedes quitarte el rol de administrador a ti mismo'}), 400

    usuario.role = role

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Usuario actualizado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar usuario: {str(e)}'}), 500


@admin_bp.route('/admin/usuarios/<int:user_id>/eliminar', methods=['POST'])
def admin_eliminar_usuario(user_id):
    """
    Elimina a un usuario y realiza una limpieza en cascada.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    usuario = db.session.get(Usuario, user_id)
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    from flask import session
    current_user_id = session.get('user_id')
    if usuario.id == current_user_id:
        return jsonify({'error': 'No puedes eliminar tu propia cuenta de administrador'}), 400

    try:
        from app.models import SesionActiva, Favorito, Coleccion, HistorialEscucha, DailyMix, daily_mix_canciones
        
        # Eliminar relaciones
        SesionActiva.query.filter_by(usuario_id=user_id).delete()
        Favorito.query.filter_by(usuario_id=user_id).delete()
        Coleccion.query.filter_by(usuario_id=user_id).delete()
        HistorialEscucha.query.filter_by(usuario_id=user_id).delete()
        
        # Eliminar Daily Mixes y sus asociaciones
        mixes = DailyMix.query.filter_by(usuario_id=user_id).all()
        for m in mixes:
            db.session.execute(
                daily_mix_canciones.delete().where(daily_mix_canciones.c.mix_id == m.id)
            )
            db.session.delete(m)

        db.session.delete(usuario)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Usuario eliminado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar usuario: {str(e)}'}), 500


# ==============================================================================
# SECCIÓN 6: GESTIÓN DE LETRAS (BUSCAR, OBTENER Y GUARDAR)
# ==============================================================================

@admin_bp.route('/admin/lyrics/search', methods=['GET'])
@admin_bp.route('/api/admin/lyrics/search', methods=['GET'])
def admin_lyrics_search():
    """
    Busca canciones por título o artista y retorna el estado de sus letras.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    query_str = request.args.get('q', '').strip()
    if not query_str:
        return jsonify([])

    from app.models import Artista
    canciones = Cancion.query.join(Artista, Cancion.artista_id == Artista.id, isouter=True)\
        .filter(
            db.or_(
                Cancion.titulo.ilike(f'%{query_str}%'),
                Artista.nombre.ilike(f'%{query_str}%')
            )
        ).order_by(Cancion.titulo).limit(50).all()

    resultados = []
    for c in canciones:
        tiene_letra = False
        sincronizada = 'Ninguno'
        
        if c.ruta_archivo_lrc and os.path.exists(c.ruta_archivo_lrc):
            tiene_letra = True
            from app.services.lyrics import _detectar_tipo_lyrics
            try:
                with open(c.ruta_archivo_lrc, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                tipo = _detectar_tipo_lyrics(contenido)
                sincronizada = 'LRC (Sincronizada)' if tipo == 'lrc' else 'TXT (Plana)'
            except Exception:
                sincronizada = 'TXT (Plana)'

        resultados.append({
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
            'tiene_letra': tiene_letra,
            'sincronizada': sincronizada
        })

    return jsonify(resultados)


@admin_bp.route('/admin/lyrics/<int:cancion_id>', methods=['GET'])
def admin_get_lyrics(cancion_id):
    """
    Retorna la letra cruda de una canción para editar.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return jsonify({'error': 'Song not found'}), 404

    letra = ""
    exists = False
    
    if cancion.ruta_archivo_lrc and os.path.exists(cancion.ruta_archivo_lrc):
        try:
            with open(cancion.ruta_archivo_lrc, 'r', encoding='utf-8') as f:
                letra = f.read()
            exists = True
        except Exception as e:
            current_app.logger.error(f"Error leyendo archivo de letras: {e}")
    else:
        from app.services.lyrics import obtener_o_descargar_letra
        res = obtener_o_descargar_letra(cancion_id)
        if res and res.get('letra'):
            letra = res['letra']
            exists = True

    return jsonify({
        'exists': exists,
        'letra': letra,
        'titulo': cancion.titulo,
        'artista': cancion.artista_obj.nombre if cancion.artista_obj else 'Desconocido',
        'audio': url_for('audio.servir_audio', cancion_id=cancion_id),
        'cover': url_for('audio.servir_album_art', cancion_id=cancion_id, size='small')
    })


@admin_bp.route('/admin/lyrics/<int:cancion_id>/save', methods=['POST'])
def admin_save_lyrics(cancion_id):
    """
    Guarda las letras editadas/sincronizadas de una canción.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401

    cancion = db.session.get(Cancion, cancion_id)
    if not cancion:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json() or {}
    letra_contenido = data.get('letra', '').strip()

    # Si se vacía, eliminar el archivo físico y quitar la referencia en DB
    if not letra_contenido:
        if cancion.ruta_archivo_lrc and os.path.exists(cancion.ruta_archivo_lrc):
            try:
                os.remove(cancion.ruta_archivo_lrc)
            except Exception:
                pass
        cancion.ruta_archivo_lrc = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'Failed to delete lyrics from database'}), 500
        from app.services.lyrics import _lyrics_cache
        _lyrics_cache.pop(cancion_id, None)
        return jsonify({'success': True, 'message': 'Letra eliminada'})

    from app.services.lyrics import _guardar_letra, _detectar_tipo_lyrics
    tipo = _detectar_tipo_lyrics(letra_contenido)
    res = _guardar_letra(cancion, letra_contenido, tipo, cancion_id)

    if res:
        return jsonify({'success': True, 'message': 'Letra guardada con éxito'})
        
    return jsonify({'error': 'Failed to save lyrics file'}), 500


@admin_bp.route('/admin/albumes')
def admin_albumes():
    """
    API para la gestión de álbumes.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
        
    query = request.args.get('q', '').strip()
    if query:
        albumes = Album.query.join(Artista).filter(
            (Album.titulo.ilike(f'%{query}%')) | (Artista.nombre.ilike(f'%{query}%'))
        ).order_by(Album.titulo).all()
    else:
        albumes = Album.query.order_by(Album.titulo).all()
        
    total = Album.query.count()
    con_mbid = Album.query.filter(Album.musicbrainz_id.isnot(None)).count()
    con_portada = Album.query.filter(Album.portada_url.isnot(None)).count()
    
    return jsonify({
        'albumes': [a.to_dict() for a in albumes],
        'total': total,
        'con_mbid': con_mbid,
        'con_portada': con_portada,
        'query': query
    })


@admin_bp.route('/admin/albumes/preview-metadata', methods=['POST'])
def admin_preview_album_metadata():
    """
    API instantánea de previsualización que consulta al scraper Deezer/MusicBrainz
    los detalles del álbum a partir de los IDs provistos.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
        
    mbid = (data.get('mbid') or '').strip()
    deezer_id = (data.get('deezer_id') or '').strip()
    
    if not mbid and not deezer_id:
        return jsonify({'error': 'Se requiere al menos un MBID o Deezer ID'}), 400
        
    from app.services.metadata import preview_album_metadata
    preview = preview_album_metadata(mbid=mbid if mbid else None, deezer_id=deezer_id if deezer_id else None)
    
    if not preview:
        return jsonify({'success': False, 'message': 'No se encontró ningún álbum con esos IDs'}), 404
        
    return jsonify({'success': True, 'metadata': preview})


@admin_bp.route('/admin/albumes/<int:album_id>/update-metadata', methods=['POST'])
def admin_update_album_metadata(album_id):
    """
    Actualiza el título, año, MBID y portada de un álbum.
    Limpia el caché de miniaturas para forzar la actualización de imágenes en toda la app.
    """
    if not _is_admin_request():
        return jsonify({'error': 'Unauthorized'}), 401
        
    album = db.session.get(Album, album_id)
    if not album:
        return jsonify({'error': 'Álbum no encontrado'}), 404
        
    old_titulo = album.titulo
    old_anio = album.anio
        
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
        
    titulo = (data.get('titulo') or '').strip()
    anio_str = (data.get('anio') or '').strip()
    mbid = (data.get('mbid') or '').strip()
    deezer_id = (data.get('deezer_id') or '').strip()
    
    final_mbid = mbid
    if final_mbid:
        final_mbid = final_mbid.lower()
        if len(final_mbid) != 36:
            return jsonify({'error': 'MBID debe tener 36 caracteres (UUID)'}), 400
        existing = Album.query.filter(Album.musicbrainz_id == final_mbid, Album.id != album_id).first()
        if existing:
            return jsonify({'error': f'El MBID ya pertenece a {existing.titulo}'}), 400
            
    # Intentar resolver Deezer para la portada
    foto_desde_deezer = None
    if deezer_id:
        from app.services.metadata import get_album_by_deezer_id
        d_data = get_album_by_deezer_id(deezer_id)
        if d_data:
            foto_desde_deezer = d_data.get('cover')
            if d_data.get('release_date') and not anio_str:
                try:
                    anio_str = d_data['release_date'][:4]
                except:
                    pass
                    
    # Cambios básicos
    if titulo:
        album.titulo = titulo
        
    if anio_str:
        try:
            album.anio = int(anio_str)
        except ValueError:
            pass
            
    album.musicbrainz_id = final_mbid or None
    
    old_portada = album.portada_url
    if foto_desde_deezer:
        album.portada_url = foto_desde_deezer
        
    db.session.commit()
    
    # Sincronizar título y año en los tags físicos en disco si cambiaron
    if album.titulo != old_titulo or album.anio != old_anio:
        from app.services.metadata import actualizar_tags_disco
        for cancion in album.canciones:
            if cancion.ruta_archivo_audio:
                try:
                    actualizar_tags_disco(cancion.ruta_archivo_audio, album=album.titulo, anio=album.anio)
                except Exception as tag_err:
                    current_app.logger.warning(
                        f"[Admin Album Update] Error escribiendo tag al disco para {cancion.ruta_archivo_audio}: {tag_err}"
                    )
    
    # Si la portada del álbum cambió o se actualizó, limpiamos el caché de miniaturas WebP de sus canciones asociadas
    if foto_desde_deezer and foto_desde_deezer != old_portada:
        from pathlib import Path
        for cancion in album.canciones:
            for size in ['small', 'medium', 'large']:
                thumb_file = Config.THUMBNAILS_FOLDER / f"thumb_{size}_{cancion.id}.webp"
                if thumb_file.exists():
                    try:
                        thumb_file.unlink()
                    except Exception:
                        pass
                        
    return jsonify({
        'success': True,
        'message': f'Álbum "{album.titulo}" actualizado',
        'metadata': {
            'titulo': album.titulo,
            'anio': album.anio,
            'mbid': album.musicbrainz_id or '',
            'portada_url': album.portada_url or ''
        }
    })

