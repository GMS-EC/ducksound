import logging
import requests
import time
from models import db, Artista, Album

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

DEEZER_SEARCH_URL = 'https://api.deezer.com/search/artist'
DEEZER_ARTIST_URL = 'https://api.deezer.com/artist/{}'
DEEZER_SEARCH_ALBUM_URL = 'https://api.deezer.com/search/album'
DEEZER_ALBUM_URL = 'https://api.deezer.com/album/{}'
REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 1.0  # segundos entre requests para no saturar la API


def buscar_artista_deezer(nombre_artista):
    """
    Busca un artista en Deezer y devuelve sus datos (picture, bio, etc.)
    Retorna un dict con 'name', 'picture', 'picture_small', 'nb_album', 'nb_fan' o None.
    """
    try:
        params = {'q': nombre_artista, 'limit': 3}
        resp = requests.get(DEEZER_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('data'):
            logging.warning(f"No se encontró artista en Deezer: {nombre_artista}")
            return None

        # Buscar el que mejor coincida (exacto o primero)
        mejor = None
        nombre_lower = nombre_artista.lower()
        for artista in data['data']:
            if artista.get('name', '').lower() == nombre_lower:
                mejor = artista
                break
        if not mejor:
            mejor = data['data'][0]

        # Obtener detalles completos del artista
        artist_id = mejor['id']
        detail_resp = requests.get(DEEZER_ARTIST_URL.format(artist_id), timeout=REQUEST_TIMEOUT)
        detail_resp.raise_for_status()
        detalles = detail_resp.json()

        # Intentar obtener biografía desde Deezer (radio/channel)
        bio = None
        try:
            radio_url = f'https://api.deezer.com/artist/{artist_id}/radio'
            radio_resp = requests.get(radio_url, timeout=REQUEST_TIMEOUT)
            if radio_resp.ok:
                radio_data = radio_resp.json()
                if radio_data.get('data'):
                    # La bio no viene en Deezer directamente, usamos la descripción del artista
                    pass
        except Exception:
            pass

        result = {
            'name': detalles.get('name', nombre_artista),
            'picture': detalles.get('picture_xl') or detalles.get('picture_big') or detalles.get('picture_medium'),
            'picture_medium': detalles.get('picture_medium'),
            'picture_small': detalles.get('picture_small'),
            'nb_album': detalles.get('nb_album', 0),
            'nb_fan': detalles.get('nb_fan', 0),
            'deezer_url': detalles.get('link', ''),
        }

        logging.info(f"Encontrado en Deezer: {result['name']}")
        return result

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al consultar Deezer para '{nombre_artista}': {e}")
        return None
    except Exception as e:
        logging.error(f"Error inesperado para '{nombre_artista}': {e}")
        return None


def buscar_biografia_wikipedia(nombre_artista):
    """
    Obtiene un resumen biográfico de Wikipedia para un artista.
    """
    try:
        params = {
            'action': 'query',
            'format': 'json',
            'titles': nombre_artista,
            'prop': 'extracts',
            'exintro': True,
            'explaintext': True,
            'redirects': 1,
            'exchars': 500,
        }
        headers = {'User-Agent': 'DuckSound/1.0 (contacto@ejemplo.com)'}
        
        # Intentar en español primero
        resp = requests.get(
            'https://es.wikipedia.org/w/api.php',
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        pages = data.get('query', {}).get('pages', {})
        for page_id, page in pages.items():
            if page_id != '-1' and page.get('extract'):
                extract = page['extract'].strip()
                # Limitar a ~400 caracteres
                if len(extract) > 400:
                    extract = extract[:397] + '...'
                return extract

        # Si no encontró en español, intentar en inglés
        params['titles'] = nombre_artista + ' (musician)'
        resp2 = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        if resp2.ok:
            data2 = resp2.json()
            pages2 = data2.get('query', {}).get('pages', {})
            for page_id, page in pages2.items():
                if page_id != '-1' and page.get('extract'):
                    extract = page['extract'].strip()
                    if len(extract) > 400:
                        extract = extract[:397] + '...'
                    return extract

    except Exception as e:
        logging.error(f"Error al obtener biografía de Wikipedia para '{nombre_artista}': {e}")

    return None


def enrich_artist(artista_obj, commit=True):
    """
    Enriquece un objeto Artista con foto y biografía desde APIs públicas.
    - artista_obj: instancia de Artista (debe tener .nombre)
    - commit: si True, hace db.session.commit() al final
    Retorna True si se actualizó algo, False si no.
    """
    if not artista_obj or not artista_obj.nombre:
        return False

    actualizado = False

    # 1. Foto desde Deezer
    if not artista_obj.foto_url:
        deezer_data = buscar_artista_deezer(artista_obj.nombre)
        if deezer_data and deezer_data.get('picture'):
            artista_obj.foto_url = deezer_data['picture']
            logging.info(f"✅ Foto obtenida para {artista_obj.nombre}")
            actualizado = True
        time.sleep(RATE_LIMIT_DELAY)

    # 2. Biografía desde Wikipedia
    if not artista_obj.biografia:
        bio = buscar_biografia_wikipedia(artista_obj.nombre)
        if bio:
            artista_obj.biografia = bio
            logging.info(f"✅ Biografía obtenida para {artista_obj.nombre}")
            actualizado = True

    if actualizado:
        db.session.add(artista_obj)
        if commit:
            db.session.commit()
            logging.info(f"💾 Guardados metadatos para: {artista_obj.nombre}")

    return actualizado


def enrich_all_artists(commit=True):
    """
    Enriquece todos los artistas que no tengan foto o biografía.
    Retorna (actualizados, total).
    """
    artistas = Artista.query.filter(
        (Artista.foto_url.is_(None)) | (Artista.biografia.is_(None))
    ).all()
    total = len(artistas)
    actualizados = 0

    if total == 0:
        logging.info("Todos los artistas ya tienen metadatos completos.")
        return 0, 0

    logging.info(f"Enriqueciendo {total} artistas...")
    for artista in artistas:
        try:
            if enrich_artist(artista, commit=False):
                actualizados += 1
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            logging.error(f"Error al enriquecer {artista.nombre}: {e}")

    if commit and actualizados > 0:
        db.session.commit()
        logging.info(f"💾 Guardados metadatos para {actualizados} artistas")

    return actualizados, total


# ============================================
# ÁLBUMES
# ============================================

def buscar_album_deezer(titulo_album, artista_nombre=None):
    """
    Busca un álbum en Deezer por título y opcionalmente artista.
    Retorna dict con 'title', 'cover', 'cover_medium', 'release_date',
    'nb_tracks', 'tracklist' o None.
    """
    try:
        query = titulo_album
        if artista_nombre:
            query = f'{artista_nombre} {titulo_album}'
        params = {'q': query, 'limit': 5}
        resp = requests.get(DEEZER_SEARCH_ALBUM_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('data'):
            logging.warning(f"No se encontró álbum en Deezer: {titulo_album}")
            return None

        # Buscar el que mejor coincida
        mejor = None
        query_lower = titulo_album.lower()
        for album in data['data']:
            if album.get('title', '').lower() == query_lower:
                mejor = album
                break
        if not mejor:
            mejor = data['data'][0]

        # Obtener detalles completos
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

        logging.info(f"Álbum encontrado en Deezer: {result['title']}")
        return result

    except Exception as e:
        logging.error(f"Error al buscar álbum '{titulo_album}': {e}")
        return None


def enrich_album(album_obj, commit=True):
    """
    Enriquece un objeto Album con portada y año desde Deezer.
    - album_obj: instancia de Album (debe tener .titulo y .artista)
    - commit: si True, hace db.session.commit() al final
    Retorna True si se actualizó algo.
    """
    if not album_obj or not album_obj.titulo:
        return False

    actualizado = False

    # 1. Portada desde Deezer
    if not album_obj.portada_url:
        artista_nombre = album_obj.artista.nombre if album_obj.artista else None
        deezer_data = buscar_album_deezer(album_obj.titulo, artista_nombre)
        if deezer_data and deezer_data.get('cover'):
            album_obj.portada_url = deezer_data['cover']
            logging.info(f"✅ Portada obtenida para álbum {album_obj.titulo}")
            actualizado = True
        time.sleep(RATE_LIMIT_DELAY)

    # 2. Año desde release_date si no tiene
    if not album_obj.anio:
        if not deezer_data:
            artista_nombre = album_obj.artista.nombre if album_obj.artista else None
            deezer_data = buscar_album_deezer(album_obj.titulo, artista_nombre)
        if deezer_data and deezer_data.get('release_date'):
            try:
                album_obj.anio = int(deezer_data['release_date'][:4])
                logging.info(f"✅ Año obtenido para álbum {album_obj.titulo}: {album_obj.anio}")
                actualizado = True
            except (ValueError, TypeError):
                pass

    if actualizado:
        db.session.add(album_obj)
        if commit:
            db.session.commit()
            logging.info(f"💾 Guardados metadatos para álbum: {album_obj.titulo}")

    return actualizado


def enrich_all_albums(commit=True):
    """
    Enriquece todos los álbumes sin portada ni año.
    Retorna (actualizados, total).
    """
    albums = Album.query.filter(
        (Album.portada_url.is_(None)) | (Album.anio.is_(None))
    ).all()
    total = len(albums)
    actualizados = 0

    if total == 0:
        logging.info("Todos los álbumes ya tienen metadatos completos.")
        return 0, 0

    logging.info(f"Enriqueciendo {total} álbumes...")
    for album in albums:
        try:
            if enrich_album(album, commit=False):
                actualizados += 1
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            logging.error(f"Error al enriquecer álbum {album.titulo}: {e}")

    if commit and actualizados > 0:
        db.session.commit()
        logging.info(f"💾 Guardados metadatos para {actualizados} álbumes")

    return actualizados, total


# ============================================
# TODO EN UNO
# ============================================

def enrich_all(commit=True):
    """
    Enriquece TODOS los metadatos: artistas + álbumes.
    Retorna dict con resultados.
    """
    result = {'artistas': (0, 0), 'albumes': (0, 0)}
    result['artistas'] = enrich_all_artists(commit=False)
    result['albumes'] = enrich_all_albums(commit=False)
    total = result['artistas'][0] + result['albumes'][0]
    if commit and total > 0:
        db.session.commit()
        logging.info(f"💾 Guardados metadatos para {total} elementos")
    return result


if __name__ == '__main__':
    from app import app
    with app.app_context():
        res = enrich_all()
        print(f"Artistas actualizados: {res['artistas'][0]}/{res['artistas'][1]}")
        print(f"Álbumes actualizados: {res['albumes'][0]}/{res['albumes'][1]}")
