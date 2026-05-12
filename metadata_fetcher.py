import logging
import re
import requests
import time
from rapidfuzz import fuzz
from models import db, Artista, Album

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

DEEZER_SEARCH_URL = 'https://api.deezer.com/search/artist'
DEEZER_ARTIST_URL = 'https://api.deezer.com/artist/{}'
DEEZER_SEARCH_ALBUM_URL = 'https://api.deezer.com/search/album'
DEEZER_ALBUM_URL = 'https://api.deezer.com/album/{}'
REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 1.0  # segundos entre requests para no saturar la API


def _normalizar_nombre(texto):
    """Normaliza nombre para comparación fuzzy eliminando caracteres especiales."""
    if not texto:
        return ''
    n = texto.lower().strip()
    n = re.sub(r'[^\w\s]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def buscar_artista_deezer(nombre_artista, mbid=None):
    """
    Busca un artista en Deezer y devuelve sus datos (picture, bio, etc.)
    Si se proporciona un MBID de MusicBrainz, intenta la búsqueda precisa primero.
    Retorna un dict con 'name', 'picture', 'picture_small', 'nb_album', 'nb_fan' o None.
    """
    # 1. Búsqueda precisa por MBID de MusicBrainz (evita confusiones con homónimos)
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
                    logging.info(f"Encontrado en Deezer (vía MBID): {result['name']}")
                    return result
        except Exception as e:
            logging.warning(f"Error al buscar por MBID {mbid} en Deezer: {e}")

    # 2. Fallback: búsqueda por nombre con coincidencia fuzzy
    try:
        params = {'q': nombre_artista, 'limit': 5}
        resp = requests.get(DEEZER_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('data'):
            logging.warning(f"No se encontró artista en Deezer: {nombre_artista}")
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
            logging.warning(
                f"No se encontró coincidencia segura en Deezer para '{nombre_artista}' "
                f"(mejor puntaje: {mejor_puntaje}, umbral: {UMBRAL_CONFIANZA})"
            )
            return None

        # Obtener detalles completos del artista
        artist_id = mejor_resultado['id']
        detail_resp = requests.get(
            DEEZER_ARTIST_URL.format(artist_id),
            timeout=REQUEST_TIMEOUT
        )
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

        logging.info(f"Encontrado en Deezer: {result['name']} (confianza: {mejor_puntaje}%)")
        return result

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al consultar Deezer para '{nombre_artista}': {e}")
        return None
    except Exception as e:
        logging.error(f"Error inesperado para '{nombre_artista}': {e}")
        return None


from musicbrainz_client import get_artista_bio


def buscar_biografia(nombre_artista, mbid=None):
    """
    Obtiene la biografía de un artista. 
    Intenta primero MusicBrainz (alta calidad) y luego Deezer como fallback.
    """
    # 1. Intentar MusicBrainz primero si tenemos MBID
    if mbid:
        try:
            bio_mb = get_artista_bio(mbid)
            if bio_mb:
                logging.info(f"✅ Biografía obtenida de MusicBrainz para {nombre_artista}")
                return bio_mb
        except Exception as e:
            logging.warning(f"Error consultando MusicBrainz bio para {nombre_artista}: {e}")

    # 2. Fallback a Deezer
    try:
        bio_deezer = buscar_biografia_deezer(nombre_artista, mbid=mbid)
        if bio_deezer:
            logging.info(f"✅ Biografía obtenida de Deezer para {nombre_artista}")
            return bio_deezer
    except Exception as e:
        logging.error(f"Error al obtener biografía de Deezer para '{nombre_artista}': {e}")
        
    return None


def buscar_biografia_deezer(nombre_artista, mbid=None):
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
            if fans >= 1000000:
                fans_str = f"{fans/1000000:.1f}M"
            elif fans >= 1000:
                fans_str = f"{fans/1000:.1f}K"
            else:
                fans_str = str(fans)
            partes.append(f"{fans_str} oyentes mensuales en Deezer")

        if len(partes) > 1:
            bio = '. '.join(partes) + '.'
            return bio[:400]

        return None

    except Exception as e:
        logging.error(f"Error al obtener biografía de Deezer para '{nombre_artista}': {e}")
    return None


def enrich_artist(artista_obj, commit=True):
    """
    Enriquece un objeto Artista con foto y biografía desde MusicBrainz.
    - artista_obj: instancia de Artista (debe tener .nombre)
    - commit: si True, hace db.session.commit() al final
    Retorna True si se actualizó algo, False si no.
    """
    if not artista_obj or not artista_obj.nombre:
        return False

    actualizado = False

    # Foto: solo desde Deezer usando MBID (búsqueda precisa), sin fallback por nombre
    if not artista_obj.foto_url and artista_obj.musicbrainz_id:
        deezer_data = buscar_artista_deezer(artista_obj.nombre, mbid=artista_obj.musicbrainz_id)
        if deezer_data and deezer_data.get('picture'):
            artista_obj.foto_url = deezer_data['picture']
            logging.info(f"✅ Foto obtenida para {artista_obj.nombre}")
            actualizado = True
        time.sleep(RATE_LIMIT_DELAY)

    # Biografía: solo desde MusicBrainz (no Deezer fallback)
    if artista_obj.musicbrainz_id and not artista_obj.biografia:
        bio = get_artista_bio(artista_obj.musicbrainz_id)
        if bio:
            artista_obj.biografia = bio
            logging.info(f"✅ Biografía obtenida de MusicBrainz para {artista_obj.nombre}")
            actualizado = True

    if actualizado:
        db.session.add(artista_obj)
        if commit:
            db.session.commit()
            logging.info(f"💾 Guardados metadatos para: {artista_obj.nombre}")

    return actualizado


def enrich_all_artists(commit=True):
    """
    Enriquece todos los artistas que no tengan foto o biografía (o tengan una bio básica de Deezer).
    Retorna (actualizados, total).
    """
    artistas = Artista.query.filter(
        (Artista.foto_url.is_(None)) | 
        (Artista.biografia.is_(None)) | 
        (Artista.biografia.ilike('%en Deezer%'))
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
