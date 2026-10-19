# -*- coding: utf-8 -*-
"""
Servicio de Extracción de Paleta de Colores Dinámica - DuckSound
Extrae colores dominantes y vibrantes de las portadas de álbumes
para generar gradientes ambientales y temas adaptativos.
"""

import os
from pathlib import Path
from PIL import Image

_color_cache = {}

def _calcular_puntuacion_vibrante(r, g, b):
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    if max_c == 0:
        return 0.0
    sat = (max_c - min_c) / max_c
    bright = max_c / 255.0
    # Premiar saturación moderada a alta y brillo entre 20% y 80%
    if 0.20 <= bright <= 0.85:
        score = sat * (1.2 - abs(bright - 0.5))
    else:
        score = sat * 0.3
    return score

def extraer_colores_imagen(image_path):
    """
    Extrae color primario vibrante y secundario de una imagen.
    Retorna un diccionario con primary, accent y css_gradient.
    """
    if not image_path:
        return _color_por_defecto()

    p = Path(image_path)
    if not p.exists():
        return _color_por_defecto()

    stat_key = f"{p.as_posix()}_{p.stat().st_mtime}"
    if stat_key in _color_cache:
        return _color_cache[stat_key]

    try:
        with Image.open(p) as img:
            img = img.convert('RGB')
            # Reducir imagen para velocidad instantánea (< 2ms)
            img = img.resize((50, 50), Image.Resampling.BOX)
            q = img.quantize(colors=8, method=Image.Quantize.FASTOCTREE)
            palette = q.getpalette()
            colors_count = sorted(q.getcolors(), reverse=True)

            parsed = []
            for count, idx in colors_count:
                r = palette[idx * 3]
                g = palette[idx * 3 + 1]
                b = palette[idx * 3 + 2]
                score = _calcular_puntuacion_vibrante(r, g, b)
                parsed.append(((r, g, b), count, score))

            # Ordenar por vibrancia
            parsed_sorted = sorted(parsed, key=lambda x: (x[2], x[1]), reverse=True)

            if parsed_sorted:
                pr, pg, pb = parsed_sorted[0][0]
                # Buscar un secundario diferente si existe
                accent = (217, 88, 64)
                for item in parsed_sorted[1:]:
                    ar, ag, ab = item[0]
                    # Distancia euclídea de color
                    dist = ((pr - ar) ** 2 + (pg - ag) ** 2 + (pb - ab) ** 2) ** 0.5
                    if dist > 40:
                        accent = (ar, ag, ab)
                        break
            else:
                pr, pg, pb = (217, 88, 64)
                accent = (240, 106, 80)

            primary_rgb = f"rgb({pr}, {pg}, {pb})"
            accent_rgb = f"rgb({accent[0]}, {accent[1]}, {accent[2]})"
            gradient = f"linear-gradient(180deg, rgba({pr}, {pg}, {pb}, 0.45) 0%, rgba(26, 26, 31, 0.95) 75%, #1a1a1f 100%)"
            ambient_glow = f"0 20px 60px rgba({pr}, {pg}, {pb}, 0.35)"

            res = {
                "primary": primary_rgb,
                "accent": accent_rgb,
                "gradient": gradient,
                "glow": ambient_glow,
                "rgb": [pr, pg, pb]
            }

            _color_cache[stat_key] = res
            return res
    except Exception as e:
        return _color_por_defecto()

def _color_por_defecto():
    return {
        "primary": "rgb(217, 88, 64)",
        "accent": "rgb(240, 106, 80)",
        "gradient": "linear-gradient(180deg, rgba(217, 88, 64, 0.35) 0%, rgba(26, 26, 31, 0.95) 75%, #1a1a1f 100%)",
        "glow": "0 20px 60px rgba(217, 88, 64, 0.35)",
        "rgb": [217, 88, 64]
    }
