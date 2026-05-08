import re

from rapidfuzz import fuzz
from unidecode import unidecode

# Patrones para detectar versiones de álbumes
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

# Palabras a limpiar al final de nombres de artistas/álbumes
CLEANUP_WORDS = [
    r'(?i)\s*[-–—]+\s*(the original|original motion picture soundtrack|ost|soundtrack)\s*$',
    r'(?i)\s*[-–—]+\s*(feat\.|ft\.|featuring)\s*.*$',
    r'(?i)\s*[\(\[]\s*(feat\.|ft\.|featuring).*?[\)\]]',  # Remove (feat. Person) completely anywhere
    r'(?i)\s*(feat\.|ft\.|featuring)\s+.*$',              # Remove feat. Person at the end
    r'(?i)\s*[\[\(].*?remaster(ed)?.*?[\]\)]\s*$',
    r'(?i)\s*[\[\(].*?deluxe.*?[\]\)]\s*$',
    r'^\s+|\s+$',
]


def detectar_version(titulo):
    """
    Detecta si un título de álbum contiene una versión (Deluxe, Remaster, etc.)
    Retorna (nombre_base, version) o (titulo_original, None)
    """
    if not titulo:
        return titulo, None

    titulo_limpio = titulo.strip()
    for pattern, label in VERSION_PATTERNS:
        m = re.search(pattern, titulo)
        if m:
            # Quitar la versión del título para obtener el nombre base
            base = re.sub(pattern, '', titulo).strip()
            base = re.sub(r'[\(\[]\s*[\)\]]', '', base).strip()  # paréntesis vacíos
            base = re.sub(r'\s{2,}', ' ', base).strip().rstrip('-–— ')
            return base, label
    return titulo_limpio, None


def limpiar_nombre(nombre):
    """Limpia un nombre (artista/álbum): quita espacios extra, normaliza"""
    if not nombre:
        return nombre
    n = nombre.strip()
    
    # Limpiar palabras extra comunes al final del nombre
    for pattern in CLEANUP_WORDS:
        n = re.sub(pattern, '', n)

    n = re.sub(r'\s{2,}', ' ', n)
    # Quitar puntos suspensivos y normalizar comillas
    n = n.replace('...', '…').replace("''", '"').replace('``', '"')
    return n.strip()


def normalizar_artista(nombre):
    """Normaliza nombre de artista separando feats y colaboraciones"""
    if not nombre:
        return nombre
    n = limpiar_nombre(nombre)
    
    # Detectar si es una colaboración con "and" vs un nombre legítimo con "and"
    # Regla: Si hay más de 3 palabras y "and" está en medio, probablemente es colaboración
    palabras = n.split()
    if len(palabras) > 3 and 'and' in palabras:
        # Probablemente es una colaboración: "Artist A and Artist B"
        and_index = palabras.index('and')
        # Solo separar si hay palabras antes y después de "and"
        if 0 < and_index < len(palabras) - 1:
            # Separar en el primer "and" que cumpla las condiciones
            primera_parte = ' '.join(palabras[:and_index])
            n = primera_parte.strip()
    else:
        # Para nombres cortos con "and" (ej: "Blade and Bath"), mantener completo
        pass
    
    # Expresiones regulares para separar por colaboraciones o feat (excluyendo "and")
    separadores = (
        r'(?i:\s+feat\.?\s+)'
        r'|(?i:\s+ft\.?\s+)'
        r'|(?i:\s+featuring\s+)'
        r'|\s*/\s*'
        r'|\s*,\s+'
        r'|\s*&\s*'
        r'|\s+y\s+(?=[A-ZÁÉÍÓÚÑ])'
        r'|\s+x\s+(?=[A-ZÁÉÍÓÚÑ])'
    )
    partes = re.split(separadores, n, maxsplit=1)
    if len(partes) > 1:
        n = partes[0].strip()
            
    # Casos ultra-específicos que suelen repetirse:
    n = re.sub(r'(?i)\s+B\.C\.$', '', n)  # Ghost B.C. -> Ghost
            
    return n


def normalizar_titulo(titulo):
    """Normaliza título de canción"""
    if not titulo:
        return titulo
    return limpiar_nombre(titulo)


def normalizar_album(titulo):
    """Normaliza títulos de álbum para agrupar versiones y variantes equivalentes."""
    if not titulo:
        return titulo

    n = limpiar_nombre(titulo)
    base, _ = detectar_version(n)
    n = limpiar_nombre(base)

    # Elimina descriptores editoriales o de banda sonora que suelen quedar al final.
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
    """
    Agrupa álbumes por su nombre base (ignorando versiones).
    Retorna dict: {nombre_base: [(album, version), ...]}
    """
    grupos = {}
    for album in albumes:
        base = normalizar_album(album.titulo)
        version = detectar_version(album.titulo)[1]
        if base not in grupos:
            grupos[base] = []
        grupos[base].append((album, version))
    return grupos


def _texto_fuzzy_album(titulo):
    """Normaliza texto de album para comparaciones fuzzy."""
    if not titulo:
        return ''
    n = normalizar_album(titulo)
    n = unidecode(n).lower()
    n = re.sub(r'[^a-z0-9]+', ' ', n)
    return re.sub(r'\s{2,}', ' ', n).strip()


def obtener_album_base_fuzz(titulo_escaneado, albumes_existentes, umbral=85):
    """
    Busca el album existente mas parecido al titulo escaneado.
    Retorna el objeto Album con mayor puntaje si supera el umbral, o None.
    """
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
