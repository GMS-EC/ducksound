# -*- coding: utf-8 -*-
"""
Utilidades de Normalización y Limpieza Inteligente de Títulos - DuckSound
========================================================================

Permite limpiar metadatos de pistas para mejorar drásticamente:
1. La búsqueda en catálogos y concordancia con RapidFuzz.
2. El raspado y descarga de letras sincronizadas (LRC) en Musixmatch y LRCLIB.
3. La búsqueda de carátulas en servicios externos (Deezer, MusicBrainz).
"""

import re
from unidecode import unidecode


def remove_prod(title: str) -> str:
    """
    Elimina menciones a productores en el título de la canción.
    Ej: "Song Title (prod. Metro Boomin)" -> "Song Title"
        "Song Title [Prod. by Pharrell]" -> "Song Title"
    """
    if not title or "prod" not in title.lower():
        return title or ""

    # Con paréntesis o corchetes
    title_clean = re.sub(r"\s*[\(\[]prod(?:\.|uced)?(?:\s+by)?\s*.*?[\)\]]", "", title, flags=re.IGNORECASE)
    # Sin paréntesis (al final o como token suelto)
    title_clean = re.sub(r"\s+prod\.(?:\s+by)?\s*\S+.*$", "", title_clean, flags=re.IGNORECASE)
    return title_clean.strip()


def remove_bracketed_remaster(text: str) -> str:
    """Elimina etiquetas de remasterización entre paréntesis o corchetes."""
    return re.sub(
        r"\s*[\(\[][^\)\]]*(?:remaster|remastered|deluxe|edition|anniversary|version)[^\)\]]*[\)\]]",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()


def remove_hyphen_remasters(text: str) -> str:
    """Elimina etiquetas de remasterización tras guión (- 2011 Remaster)."""
    return re.sub(
        r"\s+[-–—]\s+[^-–—]*(?:remaster|remastered|deluxe|anniversary|reissue).*$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()


def clean_title(title: str) -> str:
    """
    Limpia etiquetas de remaster, deluxe, aniversario y productores de un título.
    Retorna el título puro ideal para emparejar con bases de datos de letras y carátulas.
    """
    if not title:
        return ""

    t = remove_prod(title)
    lower = t.lower()
    
    if any(k in lower for k in ["remaster", "deluxe", "anniversary", "edition", "reissue", "version"]):
        rem_1 = remove_bracketed_remaster(t)
        rem_2 = remove_hyphen_remasters(rem_1)
        t = rem_2

    # Limpiar espacios duplicados o caracteres colgantes
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"[\(\[]\s*[\)\]]", "", t)
    return t.strip(" -–—_")


def parse_feat_from_title(title: str) -> tuple[list[str], str]:
    """
    Extrae artistas colaboradores mencionados en el título y retorna (artistas_feat, titulo_limpio).
    Ej: "Under Pressure (feat. David Bowie)" -> (["David Bowie"], "Under Pressure")
    """
    if not title:
        return [], ""

    regex = r"[\(\[](?:feat|ft|featuring|with)\.?\s+(.+?)[\)\]]"
    match = re.search(regex, title, re.IGNORECASE)

    if not match:
        return [], title.strip()

    feat_raw = match.group(1)
    # Separar por comas, &, 'and', 'y'
    parts = re.split(r",|\s+(?:&|and|y)\s+", feat_raw, flags=re.IGNORECASE)
    artists = [p.strip() for p in parts if p.strip()]

    clean = re.sub(regex, "", title, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s{2,}", " ", clean).strip(" -–—_")
    return artists, clean


def normalize_search_text(text: str) -> str:
    """
    Normaliza texto para comparación difusa: minúsculas, sin acentos y sin puntuación excesiva.
    """
    if not text:
        return ""
    try:
        decoded = unidecode(text).lower()
    except Exception:
        decoded = text.lower()
    # Reemplazar signos por espacios y colapsar
    cleaned = re.sub(r"[^\w\s]", " ", decoded)
    return " ".join(cleaned.split())


SORT_ARTICLES = {
    "the", "a", "an", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "le", "les", "der", "die", "das", "il", "lo", "gli", "i"
}


def get_sort_name(name: str, articles: set[str] | None = None) -> str:
    """
    Retorna el nombre sin artículos iniciales (ej. "The Beatles" -> "Beatles")
    para garantizar que la biblioteca no concentre el 40% de los artistas bajo la T o la L.
    """
    if not name or " " not in name:
        return name or ""
    
    arts = articles if articles is not None else SORT_ARTICLES
    parts = name.strip().split(maxsplit=1)
    if parts[0].casefold() in arts and len(parts) > 1:
        return parts[1]
    return name.strip()


def natural_sort_key(s: str) -> list:
    """
    Clave para ordenamiento natural (humano), permitiendo que 'Pista 2' se ordene
    antes de 'Pista 10' en vez de orden alfabético estricto.
    """
    if not s:
        return []
    return [int(text) if text.isdigit() else text.casefold() for text in re.split(r'(\d+)', str(s))]


def get_track_sort_pos(disc: int | None, track: int | None) -> int:
    """
    Calcula una posición numérica unificada para ordenar pistas en álbumes multi-disco.
    Fórmula: (disc or 1) * 1000 + (track or 1).
    Ej: CD 1 Pista 1 -> 1001, CD 2 Pista 1 -> 2001.
    """
    try:
        d = max(int(disc or 1), 1)
    except (ValueError, TypeError):
        d = 1
    try:
        t = min(max(int(track or 1), 0), 999)
    except (ValueError, TypeError):
        t = 1
    return d * 1000 + t

