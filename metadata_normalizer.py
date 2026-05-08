import re

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
    r'(?i)\s*[-–—]+\s*(feat\.|ft\.)\s*.*$',
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
    
    # Expresiones regulares para separar por colaboraciones o feat
    separators = [
        r'(?i)\s+feat\.?\s+', 
        r'(?i)\s+ft\.?\s+', 
        r'(?i)\s+featuring\s+', 
        r'\s*/\s*',
        r'\s*,\s*(?=(?:feat|ft)\.?\s)',
    ]
    for sep in separators:
        partes = re.split(sep, n)
        if len(partes) > 1:
            n = partes[0].strip()
            
    return n


def normalizar_titulo(titulo):
    """Normaliza título de canción"""
    if not titulo:
        return titulo
    return limpiar_nombre(titulo)


def agrupar_albumes_por_base(albumes):
    """
    Agrupa álbumes por su nombre base (ignorando versiones).
    Retorna dict: {nombre_base: [(album, version), ...]}
    """
    grupos = {}
    for album in albumes:
        base, version = detectar_version(album.titulo)
        if base not in grupos:
            grupos[base] = []
        grupos[base].append((album, version))
    return grupos
