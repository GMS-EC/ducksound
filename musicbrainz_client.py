import time
import logging
import requests

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
            return {
                'mbid': artista['id'],
                'nombre': artista.get('name', nombre),
                'sort_name': artista.get('sort-name', artista.get('name', nombre)),
                'disambiguation': artista.get('disambiguation', ''),
            }
    return None


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
    
    artistas = Artista.query.filter(Artista.musicbrainz_id.is_(None)).limit(limite).all()
    if not artistas:
        print("Todos los artistas ya tienen MBID")
        return 0
    
    print(f"Buscando MBID para {len(artistas)} artistas...")
    actualizados = 0
    for a in artistas:
        resultado = buscar_artista(a.nombre)
        if resultado:
            a.musicbrainz_id = resultado['mbid']
            if not a.nombre_normalizado or a.nombre_normalizado == a.nombre:
                from metadata_normalizer import normalizar_artista
                a.nombre_normalizado = normalizar_artista(resultado['nombre'])
            actualizados += 1
        if actualizados % 20 == 0:
            db.session.commit()
    
    db.session.commit()
    print(f"MBID actualizados: {actualizados}/{len(artistas)}")
    return actualizados
