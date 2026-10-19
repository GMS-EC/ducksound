# -*- coding: utf-8 -*-
"""
Motor de Búsqueda y Puntuación Semántica de Carátulas - DuckSound
==================================================================

Evalúa y clasifica imágenes en las carpetas de música para seleccionar
la portada frontal auténtica en lugar de scans traseros, folletos o imágenes de CD:
1. Puntuación léxica de tokens (ej. 'front: 8', 'cover: 7' vs 'back: -6', 'cd: -3', 'booklet: -8').
2. Puntuación geométrica por aspect ratio (bonifica formato cuadrado 1:1, penaliza rectangulares).
3. Puntuación por resolución y ubicación de carpeta.
"""

import os
import re
from pathlib import Path
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Puntuación por tokens léxicos en el nombre del archivo
TOKEN_SCORES = {
    "front": 8,
    "cover": 7,
    "folder": 6,
    "album": 5,
    "artwork": 4,
    "box": 2,
    "art": 2,
    "cd": -3,
    "small": -4,
    "thumb": -4,
    "back": -6,
    "spine": -6,
    "inlay": -6,
    "inside": -6,
    "disc": -8,
    "disk": -8,
    "tray": -8,
    "booklet": -8,
    "matrix": -8,
}


def list_candidate_images(folder: Path) -> list[Path]:
    """
    Retorna los archivos de imagen en la carpeta y sus subcarpetas inmediatas,
    omitiendo archivos y carpetas ocultas.
    """
    images: list[Path] = []
    if not folder.exists() or not folder.is_dir():
        return images

    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return images

    subfolders: list[Path] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            subfolders.append(entry)
        elif entry.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(entry)

    for subfolder in subfolders:
        try:
            children = sorted(subfolder.iterdir())
        except OSError:
            continue

        for child in children:
            if child.name.startswith("."):
                continue
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(child)

    return images


def get_name_score(filename: str) -> int:
    """
    Puntúa el nombre de un archivo sumando los pesos de sus tokens léxicos.
    Remueve números finales de cada token (ej. 'cd1' -> 'cd').
    """
    tokens = re.split(r"[^a-z0-9]+", filename.lower())
    score = 0
    for token in tokens:
        token = token.rstrip("0123456789")
        score += TOKEN_SCORES.get(token, 0)
    return score


def get_dimension_score(filepath: Path) -> int:
    """
    Puntúa una imagen según su relación de aspecto y resolución mínima.
    Imágenes casi cuadradas (1:1) y de alta resolución reciben la mayor puntuación.
    """
    try:
        with Image.open(filepath) as img:
            width, height = img.size
    except Exception:
        return -4

    if width == 0 or height == 0:
        return -4

    ratio = max(width, height) / min(width, height)

    if ratio <= 1.1:
        score = 5
    elif ratio <= 1.4:
        score = 2
    elif ratio <= 1.8:
        score = -2
    else:
        score = -8

    short_edge = min(width, height)
    if short_edge >= 500:
        score += 4
    elif short_edge >= 256:
        score += 2
    else:
        score -= 4

    return score


def score_cover_image(filepath: Path, folder: Path) -> int:
    """
    Calcula el puntaje global de una imagen como candidata a carátula de álbum.
    Las imágenes ubicadas en la raíz de la carpeta del álbum reciben un bono de +2.
    """
    score = get_name_score(filepath.stem)
    score += get_dimension_score(filepath)
    if filepath.parent.resolve() == folder.resolve():
        score += 2
    return score


def rank_cover_images(folder: Path | str) -> list[Path]:
    """
    Retorna la lista ordenada de imágenes candidatas en la carpeta,
    con la mejor opción al inicio.
    """
    f = Path(folder)
    images = list_candidate_images(f)
    return sorted(images, key=lambda img: score_cover_image(img, f), reverse=True)


def find_best_cover(folder: Path | str) -> Path | None:
    """
    Encuentra y retorna la ruta a la mejor carátula en la carpeta, o None si no hay imágenes.
    """
    ranked = rank_cover_images(folder)
    return ranked[0] if ranked else None


def find_cover_in_audio_dir(audio_filepath: str | Path) -> str | None:
    """
    Helper para obtener la ruta física de la mejor carátula dada la ruta de un archivo de audio.
    """
    try:
        p = Path(audio_filepath)
        folder = p.parent if p.is_file() else p
        best = find_best_cover(folder)
        return str(best.resolve()) if best else None
    except Exception:
        return None
