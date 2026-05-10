import time
import logging
import requests
import threading

# ===== Progreso de enriquecimiento =====
_mb_progress = {
    'active': False,
    'total': 0,
    'completed': 0,
    'found': 0,
    'current_artist': '',
    'finished': False,
    'message': ''
}
_mb_lock = threading.Lock()

def _progress(**kw):
    with _mb_lock:
        _mb_progress.update(kw)

def get_mb_progress():
    with _mb_lock:
        return dict(_mb_progress)

_USER_AGENT = 'DuckSound/1.0 (https://github.com/anomalyco/ducksound; contacto@ducksound.local)'
_MB_BASE = 'https://musicbrainz.org/ws/2'
_SEARCH_URL = f'{_MB_BASE}/artist/'
_RELEASE_URL = f'{_MB_BASE}/release/'
_TIMEOUT = 15
_last_call = 0.0


def _rate_limit():
    """MusicBrainz requiere max 1 request/segundo."""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 1.2:
        time.sleep(1.2 - elapsed)
    _last_call = time.time()


def _get(url, params):
    _rate_limit()
    params['fmt'] = 'json'
    try:
        resp = requests.get(url, params=params, headers={'User-Agent': _USER_AGENT}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.warning(f"MusicBrainz error: {e}")
        return None


def buscar_artista(nombre):
    """Busca un artista en MusicBrainz. Retorna dict con mbid, nombre, sort_name o None."""
    if not nombre or not nombre.strip():
        return None
    data = _get(_SEARCH_URL, {'query': f'artist:{nombre.strip()}', 'limit': 5})
    if not data or 'artists' not in data:
        return None
    for artista in data['artists']:
        score = artista.get('score', 0)
        if score >= 90:
            # Obtener nombre principal y sort_name
            nombre_mb = artista.get('name', nombre)
            sort_name_mb = artista.get('sort-name', nombre_mb)
            
            # Buscar alias en latín si el nombre principal no es latino
            alias_latin = None
            if not _es_latino(nombre_mb):
                for alias in artista.get('aliases', []):
                    if alias.get('locale', '').startswith('en') or _es_latino(alias.get('name', '')):
                        alias_latin = alias['name']
                        break
            
            # sort_name suele ser la versión romanizada
            from metadata_normalizer import normalizar_artista
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
    """Verifica si un texto usa caracteres latinos (no CJK, cirílico, etc.)."""
    if not texto:
        return True
    for ch in texto:
        cp = ord(ch)
        # CJK (japonés, chino, coreano)
        if 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF:
            return False
        # Cirílico
        if 0x0400 <= cp <= 0x04FF:
            return False
        # Árabe
        if 0x0600 <= cp <= 0x06FF:
            return False
    return True


def buscar_album(titulo, artista_mbid):
    """Busca un álbum por título + artista. Retorna dict con mbid, titulo o None."""
    if not titulo or not artista_mbid:
        return None
    query = f'release:"{titulo.strip()}" AND arid:{artista_mbid}'
    data = _get(_RELEASE_URL, {'query': query, 'limit': 5})
    if not data or 'releases' not in data:
        return None
    for release in data['releases']:
        return {'mbid': release['id'], 'titulo': release.get('title', titulo)}
    return None


def enriquecer_artistas_sin_mbid(limite=100):
    """Busca MBID en MusicBrainz para artistas que no tienen uno.
    Ejecutar en segundo plano. Rate-limited a 1 req/s."""
    from models import db, Artista
    
    _progress(active=True, finished=False, message='Consultando artistas sin MBID...')
    
    artistas = Artista.query.filter(Artista.musicbrainz_id.is_(None)).limit(limite).all()
    if not artistas:
        print("Todos los artistas ya tienen MBID")
        _progress(active=False, finished=True, message='Todos los artistas ya tienen MBID', total=0, completed=0)
        return 0
    
    total = len(artistas)
    _progress(total=total, completed=0, found=0, message=f'Enriqueciendo {total} artistas...')
    print(f"Buscando MBID para {total} artistas...")
    
    actualizados = 0
    for idx, a in enumerate(artistas, start=1):
        _progress(completed=idx, current_artist=a.nombre, message=f'Buscando MBID para {a.nombre} ({idx}/{total})')
        
        resultado = buscar_artista(a.nombre)
        if resultado:
            a.musicbrainz_id = resultado['mbid']
            norm_name = resultado.get('nombre_norm')
            if norm_name and norm_name != a.nombre:
                a.nombre_normalizado = norm_name
            actualizados += 1
            _progress(found=actualizados)
        
        if actualizados % 20 == 0 or idx == total:
            db.session.commit()
    
    db.session.commit()
    _progress(active=False, finished=True, found=actualizados, message=f'MBID actualizados: {actualizados}/{total}')
    print(f"MBID actualizados: {actualizados}/{total}")
    return actualizados
