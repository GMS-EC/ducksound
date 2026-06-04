# -*- coding: utf-8 -*-
"""
Servicios de Metadatos y Normalización - DuckSound
Maneja las integraciones con APIs externas (MusicBrainz, Deezer) para enriquecer
los metadatos de artistas y álbumes, así como algoritmos de normalización de cadenas.
"""
import re
import os
import time
import logging
import requests
from rapidfuzz import fuzz
from unidecode import unidecode
from app.models import db, Artista, Album, Cancion
from app.services.queue import progress_update, progress_get

# Configuración básica de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Constantes para la API de Deezer
DEEZER_SEARCH_URL = 'https://api.deezer.com/search/artist'
DEEZER_ARTIST_URL = 'https://api.deezer.com/artist/{}'
DEEZER_SEARCH_ALBUM_URL = 'https://api.deezer.com/search/album'
DEEZER_ALBUM_URL = 'https://api.deezer.com/album/{}'

# Constantes para la API de MusicBrainz
_USER_AGENT = 'DuckSound/1.0 (https://github.com/GamersEC/ducksound; contacto@ducksound.local)'
_MB_BASE = 'https://musicbrainz.org/ws/2'
_SEARCH_URL = f'{_MB_BASE}/artist/'
_RELEASE_URL = f'{_MB_BASE}/release/'

REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 1.0  # Retraso para evitar bloqueos por exceder límite de tasa (Rate Limit)
_last_call = 0.0

# Patrones para detectar versiones específicas de álbumes
VERSION_PATTERNS = [
    (r'(?i)\b(deluxe|deluxe edition)\b', 'Deluxe Edition'),
    (r'(?i)\b(remaster(ed)?)\b', 'Remastered'),
    (r'(?i)\b(anniversary|anniversary edition)\b', 'Anniversary Edition'),
    (r'(?i)\b(expanded|expanded edition)\b', 'Expanded Edition'),
    (r'(?i)\b(reissue)\b', 'Reissue'),
    (r'(?i)\b(live)\b', 'Live'),
    (r'(?i)\b(remix|remixed)\b', 'Remix'),
    (r'(?i)\b(demo|demos)\b', 'Demo'),
    (r'(?i)\b(acoustic)\b', 'Acoustic'),
    (r'(?i)\b(instrumental)\b', 'Instrumental'),
    (r'(?i)\b(bonus track(s)?)\b', 'Bonus Track'),
    (r'(?i)\b(limited edition)\b', 'Limited Edition'),
    (r'(?i)\b(special edition)\b', 'Special Edition'),
    (r'(?i)\b(collector.edition)\b', "Collector's Edition"),
    (r'(?i)\b(fan edition)\b', 'Fan Edition'),
]

# Palabras de limpieza al final de nombres de artistas/álbumes
CLEANUP_WORDS = [
    r'(?i)\s*[-–—]+\s*(the original|original motion picture soundtrack|ost|soundtrack)\s*$',
    r'(?i)\s*[-–—]+\s*(feat\.|ft\.|featuring)\s*.*$',
    r'(?i)\s*[\(\[]\s*(feat\.|ft\.|featuring).*?[\)\]]',
    r'(?i)\s*(feat\.|ft\.|featuring)\s+.*$',
    r'(?i)\s*[\[\(].*?remaster(ed)?.*?[\]\)]\s*$',
    r'(?i)\s*[\[\(].*?deluxe.*?[\]\)]\s*$',
    r'^\s+|\s+$',
]


# ==========================================================
# 📊 MÉTODOS DE NORMALIZACIÓN DE METADATOS (metadata_normalizer)
# ==========================================================

def detectar_version(titulo):
    """
    Detecta si el título de un álbum denota una edición especial (Deluxe, Remaster, etc.).
    Retorna (nombre_base, version_detectada) o (titulo_original, None).
    """
    if not titulo:
        return titulo, None

    titulo_limpio = titulo.strip()
    for pattern, label in VERSION_PATTERNS:
        m = re.search(pattern, titulo)
        if m:
            base = re.sub(pattern, '', titulo).strip()
            base = re.sub(r'[\(\[]\s*[\)\]]', '', base).strip()
            base = re.sub(r'\s{2,}', ' ', base).strip().rstrip('-–— ')
            return base, label
    return titulo_limpio, None


def limpiar_nombre(nombre):
    """Limpia cadenas de texto quitando espacios duplicados y colaboradores secundarios."""
    if not nombre:
        return nombre
    n = nombre.strip()
    for pattern in CLEANUP_WORDS:
        n = re.sub(pattern, '', n)
    n = re.sub(r'\s{2,}', ' ', n)
    n = n.replace('...', '…').replace("''", '"').replace('``', '"')
    return n.strip()


def normalizar_artista(nombre):
    """
    Normaliza el nombre de un artista extrayendo solo la firma principal.
    Elimina featurings, colaboraciones secundarias y limpia el prefijo 'The'.
    """
    if not nombre:
        return nombre
    n = limpiar_nombre(nombre)
    if not n:
        return n
    
    n = re.sub(r'(?i)\s*[-–—]+\s*(feat\.|ft\.|featuring)\s+.*$', '', n)
    n = re.sub(r'(?i)\s*[\(\[]\s*(feat\.|ft\.|featuring).*?[\)\]]', '', n)
    n = re.sub(r'(?i)\s+(feat\.|ft\.|featuring)\s+.*$', '', n)
    
    original_n = n
    n = re.sub(r',\s*The$', '', n).strip()
    if n != original_n:
        n = 'The ' + n
    
    separadores = [
        r'\s+feat\.?\s+', r'\s+ft\.?\s+', r'\s+featuring\s+',
        r'\s+&\s+', r'\s+vs\.?\s+', r'\s+x\s+', r'\s+\+\s+',
        r',\s+', r'\s*/\s*',
    ]
    for pat in separadores:
        partes = re.split(pat, n, maxsplit=1)
        if len(partes) > 1 and partes[0].strip():
            if '/' in pat and len(partes[0].strip()) <= 2:
                continue
            n = partes[0].strip()
            break
    
    m = re.search(r'\b[a-z]+ and [a-z]', n)
    if m:
        n = n.split(' and ')[0].strip()
    
    n = re.sub(r',\s*The$', '', n).strip()
    n = re.sub(r'(?i)\s+B\.C\.$', '', n)
    return n.strip()


def normalizar_album(titulo):
    """Limpia y normaliza el título de un álbum agrupando variantes ortográficas equivalentes."""
    if not titulo:
        return titulo

    n = limpiar_nombre(titulo)
    base, _ = detectar_version(n)
    n = limpiar_nombre(base)

    n = re.sub(
        r'(?i)\s*[-–—:]\s*(original motion picture soundtrack|ost|soundtrack)\s*$',
        '',
        n,
    )
    n = re.sub(
        r'(?i)\s*[\(\[]\s*(original motion picture soundtrack|ost|soundtrack|deluxe(ed\.)?|remaster(ed)?|anniversary( edition)?|expanded( edition)?|reissue|live|remix|demo|acoustic|instrumental|bonus track(s)?|limited edition|special edition|collector.?edition|fan edition).*?[\)\]]\s*$',
        '',
        n,
    )
    n = re.sub(r'\s{2,}', ' ', n)
    return n.strip()


def agrupar_albumes_por_base(albumes):
    """Agrupa álbumes por su nombre base normalizado (omitiendo variantes 'Deluxe', 'Remastered')."""
    grupos = {}
    for album in albumes:
        base = normalizar_album(album.titulo)
        version = detectar_version(album.titulo)[1]
        if base not in grupos:
            grupos[base] = []
        grupos[base].append((album, version))
    return grupos


def _texto_fuzzy_album(titulo):
    """Limpia caracteres especiales y acentos para comparación difusa (Fuzzy)."""
    if not titulo:
        return ''
    n = normalizar_album(titulo)
    n = unidecode(n).lower()
    n = re.sub(r'[^a-z0-9]+', ' ', n)
    return re.sub(r'\s{2,}', ' ', n).strip()


def obtener_album_base_fuzz(titulo_escaneado, albumes_existentes, umbral=85):
    """Compara y busca el álbum más coincidente en la biblioteca usando RapidFuzz."""
    titulo_limpio = _texto_fuzzy_album(titulo_escaneado)
    if not titulo_limpio:
        return None

    mejor_album = None
    mejor_puntaje = 0
    for album in albumes_existentes or []:
        titulo_album = _texto_fuzzy_album(getattr(album, 'titulo', None))
        if not titulo_album:
            continue
        puntaje = fuzz.token_set_ratio(titulo_limpio, titulo_album)
        if puntaje > mejor_puntaje:
            mejor_album = album
            mejor_puntaje = puntaje

    return mejor_album if mejor_puntaje >= umbral else None


# ==========================================================
# 🌐 INTEGRACIÓN CON MUSICBRAINZ (musicbrainz_client)
# ==========================================================

def _progress_mb(**kw):
    """Actualiza en Redis el progreso del enriquecedor de MusicBrainz."""
    progress_update('mb', **kw)


def get_mb_progress():
    """Retorna el progreso activo del enriquecimiento de MusicBrainz."""
    p = progress_get('mb') or {}
    return p


def _rate_limit_mb():
    """Garantiza la regla estricta de MusicBrainz de un máximo de 1 petición por segundo."""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 1.2:
        time.sleep(1.2 - elapsed)
    _last_call = time.time()


def _get_mb(url, params):
    """Petición GET robusta y controlada para MusicBrainz API."""
    _rate_limit_mb()
    params['fmt'] = 'json'
    try:
        resp = requests.get(url, params=params, headers={'User-Agent': _USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.warning(f"[MusicBrainz] Error: {e}")
        return None


def get_artista_bio(mbid):
    """Obtiene la biografía en texto de un artista en MusicBrainz usando su MBID."""
    if not mbid:
        return None
    mbid = mbid.lower()
    url = f'{_MB_BASE}/artist/{mbid}'
    data = _get_mb(url, {'inc': 'bio'})
    if not data:
        return None
    
    bio_data = data.get('bio', {})
    text = bio_data.get('text') if isinstance(bio_data, dict) else bio_data
    if not text:
        return None
        
    text = re.sub(r'<[^>]*>', '', text)
    return text.strip()


def get_artista_name(mbid):
    """Obtiene el nombre canónico de un artista usando su MBID."""
    if not mbid:
        return None
    mbid = mbid.lower()
    url = f'{_MB_BASE}/artist/{mbid}'
    data = _get_mb(url, {'inc': 'aliases'})
    if not data:
        return None
    name = data.get('name')
    if name:
        return name.strip()
    return None


def buscar_artista(nombre):
    """Busca coincidencias de artistas en la API de MusicBrainz."""
    if not nombre or not nombre.strip():
        return None
    data = _get_mb(_SEARCH_URL, {'query': f'artist:{nombre.strip()}', 'limit': 5})
    if not data or 'artists' not in data:
        return None
    for artista in data['artists']:
        score = artista.get('score', 0)
        if score >= 90:
            nombre_mb = artista.get('name', nombre)
            sort_name_mb = artista.get('sort-name', nombre_mb)
            
            alias_latin = None
            if not _es_latino(nombre_mb):
                for alias in artista.get('aliases', []):
                    if alias.get('locale', '').startswith('en') or _es_latino(alias.get('name', '')):
                        alias_latin = alias['name']
                        break
            
            nombre_norm = alias_latin or (sort_name_mb if _es_latino(sort_name_mb) else nombre_mb)
            
            return {
                'mbid': artista['id'],
                'nombre': nombre_mb,
                'sort_name': sort_name_mb,
                'alias_latin': alias_latin,
                'nombre_norm': normalizar_artista(nombre_norm),
                'disambiguation': artista.get('disambiguation', ''),
            }
    return None


def _es_latino(texto):
    """Identifica si el nombre del artista tiene alfabetos latinos legibles."""
    if not texto:
        return True
    for ch in texto:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF:
            return False
        if 0x0400 <= cp <= 0x04FF:
            return False
        if 0x0600 <= cp <= 0x06FF:
            return False
    return True


def buscar_album(titulo, artista_mbid):
    """Busca el MBID de un álbum mediante consulta exacta por título de álbum y ID del artista."""
    if not titulo or not artista_mbid:
        return None
    query = f'release:"{titulo.strip()}" AND arid:{artista_mbid}'
    data = _get_mb(_RELEASE_URL, {'query': query, 'limit': 5})
    if not data or 'releases' not in data:
        return None
    for release in data['releases']:
        return {'mbid': release['id'], 'titulo': release.get('title', titulo)}
    return None


def enriquecer_artistas_sin_mbid(limite=100):
    """Busca asíncronamente MBID y normaliza nombres para artistas locales sin indexar."""
    from app import create_app
    app = create_app()
    with app.app_context():
        return _enriquecer_artistas_sin_mbid_impl(limite)


def _enriquecer_artistas_sin_mbid_impl(limite):
    """Implementación interna que requiere contexto de aplicación Flask."""
    _progress_mb(active=True, finished=False, message='Consultando artistas sin MBID...')
    
    artistas = Artista.query.filter(Artista.musicbrainz_id.is_(None)).limit(limite).all()
    if not artistas:
        artistas = Artista.query.filter(
            Artista.nombre_normalizado.is_(None),
            ~Artista.musicbrainz_id.is_(None)
        ).limit(limite).all()
        if not artistas:
            _progress_mb(active=False, finished=True, message='Todos los artistas ya tienen MBID y nombre_normalizado', total=0, completed=0)
            return 0
    
    total = len(artistas)
    _progress_mb(total=total, completed=0, found=0, message=f'Enriqueciendo {total} artistas...')
    
    actualizados = 0
    for idx, a in enumerate(artistas, start=1):
        _progress_mb(completed=idx, current_artist=a.nombre, message=f'Procesando {a.nombre} ({idx}/{total})')
        
        actualizado = False
        if not a.musicbrainz_id:
            resultado = buscar_artista(a.nombre)
            if resultado:
                a.musicbrainz_id = resultado['mbid']
                norm_name = resultado.get('nombre_norm')
                if norm_name and norm_name != a.nombre:
                    a.nombre_normalizado = norm_name
                    actualizado = True
                actualizados += 1
                _progress_mb(found=actualizados)
        
        if not a.nombre_normalizado and not _es_latino(a.nombre):
            romanizado = normalizar_artista(unidecode(a.nombre))
            if romanizado and romanizado != a.nombre:
                a.nombre_normalizado = romanizado
                actualizado = True
        
        if actualizado and idx % 20 == 0:
            db.session.commit()
    
    db.session.commit()
    _progress_mb(active=False, finished=True, found=actualizados, message=f'Actualizados: {actualizados}/{total}')
    return actualizados


# ==========================================================
# 🎵 INTEGRACIÓN CON DEEZER Y ENRIQUECEDOR (metadata_fetcher)
# ==========================================================

def _normalizar_nombre(texto):
    """Normaliza texto auxiliar para Deezer API."""
    if not texto:
        return ''
    n = texto.lower().strip()
    n = re.sub(r'[^\w\s]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def buscar_artista_deezer(nombre_artista, mbid=None):
    """Busca la foto oficial y la información del artista en la API de Deezer."""
    if mbid:
        try:
            mbid_url = f'https://api.deezer.com/artist/mbid/{mbid}'
            mbid_resp = requests.get(mbid_url, timeout=REQUEST_TIMEOUT)
            if mbid_resp.ok:
                detalle = mbid_resp.json()
                if detalle and 'id' in detalle and 'error' not in detalle:
                    result = {
                        'name': detalle.get('name', nombre_artista),
                        'picture': (
                            detalle.get('picture_xl')
                            or detalle.get('picture_big')
                            or detalle.get('picture_medium')
                        ),
                        'picture_medium': detalle.get('picture_medium'),
                        'picture_small': detalle.get('picture_small'),
                        'nb_album': detalle.get('nb_album', 0),
                        'nb_fan': detalle.get('nb_fan', 0),
                        'deezer_url': detalle.get('link', ''),
                    }
                    logging.info(f"[Deezer] Artista resuelto por MBID: {result['name']}")
                    return result
        except Exception as e:
            logging.warning(f"[Deezer] Error resolviendo MBID {mbid}: {e}")

    try:
        params = {'q': nombre_artista, 'limit': 5}
        resp = requests.get(DEEZER_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('data'):
            return None

        nombre_normalizado = _normalizar_nombre(nombre_artista)
        mejor_resultado = None
        mejor_puntaje = 0

        for artista in data['data']:
            nombre_resultado = artista.get('name', '')
            if not nombre_resultado:
                continue
            nombre_resultado_norm = _normalizar_nombre(nombre_resultado)
            puntaje = fuzz.token_set_ratio(nombre_normalizado, nombre_resultado_norm)
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_resultado = artista

        UMBRAL_CONFIANZA = 85
        if not mejor_resultado or mejor_puntaje < UMBRAL_CONFIANZA:
            return None

        artist_id = mejor_resultado['id']
        detail_resp = requests.get(DEEZER_ARTIST_URL.format(artist_id), timeout=REQUEST_TIMEOUT)
        detail_resp.raise_for_status()
        detalle = detail_resp.json()

        result = {
            'name': detalle.get('name', nombre_artista),
            'picture': (
                detalle.get('picture_xl')
                or detalle.get('picture_big')
                or detalle.get('picture_medium')
            ),
            'picture_medium': detalle.get('picture_medium'),
            'picture_small': detalle.get('picture_small'),
            'nb_album': detalle.get('nb_album', 0),
            'nb_fan': detalle.get('nb_fan', 0),
            'deezer_url': detalle.get('link', ''),
        }
        return result

    except Exception as e:
        logging.error(f"[Deezer] Error en búsqueda de {nombre_artista}: {e}")
        return None


def get_artista_by_deezer_id(deezer_id):
    """Busca directamente un artista mediante su Deezer ID."""
    try:
        url = DEEZER_ARTIST_URL.format(deezer_id)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            return None
        return data
    except Exception as e:
        logging.error(f"[Deezer] Error en lookup ID {deezer_id}: {e}")
        return None


def preview_artist_metadata(mbid=None, deezer_id=None):
    """Proporciona metadatos del artista de manera unificada para su validación manual."""
    resolved_mbid = None
    name = None
    photo = None
    bio = None

    if deezer_id:
        deezer_data = get_artista_by_deezer_id(deezer_id)
        if deezer_data:
            name = deezer_data.get('name')
            photo = (
                deezer_data.get('picture_xl')
                or deezer_data.get('picture_big')
                or deezer_data.get('picture_medium')
            )
            resolved_mbid = deezer_data.get('musicbrainz_id')
    
    target_mbid = mbid or resolved_mbid
    if target_mbid:
        target_mbid = target_mbid.lower()
        if not name:
            name = get_artista_name(target_mbid)
        
        resolved_mbid = target_mbid
        bio = get_artista_bio(target_mbid)
        
        if not photo:
            deezer_by_mbid = buscar_artista_deezer(name or 'Unknown', mbid=target_mbid)
            if deezer_by_mbid:
                photo = deezer_by_mbid.get('picture')

    if not bio and deezer_id:
        bio = buscar_biografia_deezer(name or 'Unknown', mbid=resolved_mbid)

    if not name and not photo and not resolved_mbid:
        return None

    return {
        'nombre': name,
        'foto_url': photo,
        'biografia': bio,
        'mbid': resolved_mbid
    }


def buscar_biografia(nombre_artista, mbid=None):
    """Intenta obtener la biografía de un artista de MusicBrainz, con fallback dinámico de Deezer."""
    if mbid:
        try:
            bio_mb = get_artista_bio(mbid)
            if bio_mb:
                return bio_mb
        except Exception:
            pass

    try:
        bio_deezer = buscar_biografia_deezer(nombre_artista, mbid=mbid)
        if bio_deezer:
            return bio_deezer
    except Exception:
        pass
    return None


def buscar_biografia_deezer(nombre_artista, mbid=None):
    """Construye una descripción textual rápida a partir del recuento de álbumes y fans de Deezer."""
    try:
        deezer_data = buscar_artista_deezer(nombre_artista, mbid=mbid)
        if not deezer_data:
            return None

        partes = []
        if deezer_data.get('name'):
            partes.append(deezer_data['name'])

        if deezer_data.get('nb_album', 0) > 0:
            discos = deezer_data['nb_album']
            partes.append(f"Cuenta con {discos} álbum{'es' if discos != 1 else ''}")

        if deezer_data.get('nb_fan', 0) > 0:
            fans = deezer_data['nb_fan']
            fans_str = f"{fans/1000000:.1f}M" if fans >= 1000000 else (f"{fans/1000:.1f}K" if fans >= 1000 else str(fans))
            partes.append(f"{fans_str} oyentes mensuales en Deezer")

        if len(partes) > 1:
            return '. '.join(partes) + '.'[:400]
        return None
    except Exception:
        return None


def enrich_artist(artista_obj, commit=True):
    """Enriquece un artista con foto (Deezer) y biografía (MusicBrainz)."""
    if not artista_obj or not artista_obj.nombre:
        return False

    actualizado = False
    if not artista_obj.foto_url and artista_obj.musicbrainz_id:
        deezer_data = buscar_artista_deezer(artista_obj.nombre, mbid=artista_obj.musicbrainz_id)
        if deezer_data and deezer_data.get('picture'):
            artista_obj.foto_url = deezer_data['picture']
            actualizado = True
        time.sleep(RATE_LIMIT_DELAY)

    if artista_obj.musicbrainz_id and not artista_obj.biografia:
        bio = get_artista_bio(artista_obj.musicbrainz_id)
        if bio:
            artista_obj.biografia = bio
            actualizado = True

    if actualizado:
        db.session.add(artista_obj)
        if commit:
            db.session.commit()
    return actualizado


def enrich_all_artists(commit=True):
    """Actualiza metadatos de todos los artistas con biografías básicas o vacías."""
    artistas = Artista.query.filter(
        (Artista.foto_url.is_(None)) | 
        (Artista.biografia.is_(None)) | 
        (Artista.biografia.ilike('%en Deezer%'))
    ).all()
    total = len(artistas)
    actualizados = 0

    if total == 0:
        return 0, 0

    for artista in artistas:
        try:
            if enrich_artist(artista, commit=False):
                actualizados += 1
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            logging.error(f"[Enricher] Error en {artista.nombre}: {e}")

    if commit and actualizados > 0:
        db.session.commit()
    return actualizados, total


def buscar_album_deezer(titulo_album, artista_nombre=None):
    """Busca y recupera metadatos del álbum desde Deezer."""
    try:
        query = titulo_album
        if artista_nombre:
            query = f'{artista_nombre} {titulo_album}'
        params = {'q': query, 'limit': 5}
        resp = requests.get(DEEZER_SEARCH_ALBUM_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('data'):
            return None

        mejor = None
        query_lower = titulo_album.lower()
        for album in data['data']:
            if album.get('title', '').lower() == query_lower:
                mejor = album
                break
        if not mejor:
            mejor = data['data'][0]

        album_id = mejor['id']
        detail_resp = requests.get(DEEZER_ALBUM_URL.format(album_id), timeout=REQUEST_TIMEOUT)
        detail_resp.raise_for_status()
        detalles = detail_resp.json()

        result = {
            'title': detalles.get('title', titulo_album),
            'cover': detalles.get('cover_xl') or detalles.get('cover_big') or detalles.get('cover_medium'),
            'cover_medium': detalles.get('cover_medium'),
            'release_date': detalles.get('release_date'),
            'nb_tracks': detalles.get('nb_tracks', 0),
            'artist_name': detalles.get('artist', {}).get('name', ''),
            'deezer_url': detalles.get('link', ''),
        }
        return result
    except Exception as e:
        logging.error(f"[Deezer] Error buscando álbum '{titulo_album}': {e}")
        return None


def enrich_album(album_obj, commit=True):
    """Asigna automáticamente portada y año de lanzamiento a un álbum desde la API de Deezer."""
    if not album_obj or not album_obj.titulo:
        return False

    actualizado = False
    deezer_data = None

    if not album_obj.portada_url:
        artista_nombre = album_obj.artista.nombre if album_obj.artista else None
        deezer_data = buscar_album_deezer(album_obj.titulo, artista_nombre)
        if deezer_data and deezer_data.get('cover'):
            album_obj.portada_url = deezer_data['cover']
            actualizado = True
        time.sleep(RATE_LIMIT_DELAY)

    if not album_obj.anio:
        if not deezer_data:
            artista_nombre = album_obj.artista.nombre if album_obj.artista else None
            deezer_data = buscar_album_deezer(album_obj.titulo, artista_nombre)
        if deezer_data and deezer_data.get('release_date'):
            try:
                album_obj.anio = int(deezer_data['release_date'][:4])
                actualizado = True
            except (ValueError, TypeError):
                pass

    if actualizado:
        db.session.add(album_obj)
        if commit:
            db.session.commit()
    return actualizado


def enrich_all_albums(commit=True):
    """Enriquece masivamente todos los álbumes que carecen de portada o año de publicación."""
    albums = Album.query.filter(
        (Album.portada_url.is_(None)) | (Album.anio.is_(None))
    ).all()
    total = len(albums)
    actualizados = 0

    if total == 0:
        return 0, 0

    for album in albums:
        try:
            if enrich_album(album, commit=False):
                actualizados += 1
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            logging.error(f"[Enricher] Error en álbum {album.titulo}: {e}")

    if commit and actualizados > 0:
        db.session.commit()
    return actualizados, total


def enrich_all(commit=True):
    """Inicia el proceso completo de enriquecimiento para todos los artistas y álbumes."""
    result = {'artistas': (0, 0), 'albumes': (0, 0)}
    result['artistas'] = enrich_all_artists(commit=False)
    result['albumes'] = enrich_all_albums(commit=False)
    total = result['artistas'][0] + result['albumes'][0]
    if commit and total > 0:
        db.session.commit()
    return result


def get_album_by_deezer_id(deezer_album_id):
    """Busca directamente un álbum mediante su Deezer Album ID."""
    try:
        url = DEEZER_ALBUM_URL.format(deezer_album_id)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        detalles = resp.json()
        if 'error' in detalles:
            return None
        return {
            'title': detalles.get('title'),
            'cover': detalles.get('cover_xl') or detalles.get('cover_big') or detalles.get('cover_medium'),
            'cover_medium': detalles.get('cover_medium'),
            'release_date': detalles.get('release_date'),
            'nb_tracks': detalles.get('nb_tracks', 0),
            'artist_name': detalles.get('artist', {}).get('name', ''),
            'deezer_url': detalles.get('link', ''),
        }
    except Exception as e:
        logging.error(f"[Deezer] Error en lookup ID de álbum {deezer_album_id}: {e}")
        return None


def preview_album_metadata(mbid=None, deezer_id=None):
    """Proporciona metadatos del álbum de manera unificada para su validación manual."""
    resolved_mbid = None
    title = None
    cover = None
    year = None
    artist_name = None

    if deezer_id:
        deezer_data = get_album_by_deezer_id(deezer_id)
        if deezer_data:
            title = deezer_data.get('title')
            cover = deezer_data.get('cover')
            artist_name = deezer_data.get('artist_name')
            if deezer_data.get('release_date'):
                try:
                    year = int(deezer_data['release_date'][:4])
                except:
                    pass

    # MusicBrainz lookup if MBID is provided
    # (En una versión básica, retornamos lo que obtuvimos de Deezer o buscamos en MusicBrainz si se requiere)
    if mbid and not title:
        # MusicBrainz release lookup can be added if needed, fallback to basic placeholders
        resolved_mbid = mbid.lower()

    if not title and not cover:
        return None

    return {
        'titulo': title,
        'portada_url': cover,
        'anio': year,
        'artista_nombre': artist_name,
        'mbid': mbid or resolved_mbid
    }
