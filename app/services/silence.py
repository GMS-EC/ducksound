# -*- coding: utf-8 -*-
"""
Servicio de Detección de Silencios y Reproducción Gapless - DuckSound
=====================================================================
Analiza la forma de onda de los archivos de audio para detectar:
1. Silencio inicial (leading silence): milisegundos mudos al inicio por padding de compresión.
2. Silencio final (trailing silence): milisegundos mudos al final antes del corte de pista.
Permite transiciones continuas sin pausas molestas (True Gapless Playback).
"""

import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Caché en memoria para evitar re-analizar archivos idénticos: clave (path, mtime) -> dict
_silence_cache: dict[str, dict] = {}


def detect_silence_padding(filepath: str, noise_threshold_db: float = -40.0) -> dict:
    """
    Analiza un archivo de audio mediante el filtro silencedetect de FFmpeg
    para determinar los puntos óptimos de recorte de silencio inicial y final.

    Args:
        filepath: Ruta física al archivo de audio.
        noise_threshold_db: Umbral en decibelios para considerar silencio (por defecto -40 dB).

    Returns:
        dict con leading_silence, trailing_silence, trim_start, trim_end y duration.
    """
    if not filepath or not os.path.exists(filepath):
        return _fallback_silence()

    p = Path(filepath)
    try:
        stat_key = f"{p.as_posix()}_{p.stat().st_mtime}"
        if stat_key in _silence_cache:
            return _silence_cache[stat_key]
    except OSError:
        stat_key = None

    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-nostats',
        '-i', filepath,
        '-af', f'silencedetect=noise={noise_threshold_db}dB:d=0.1',
        '-f', 'null',
        '-'
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=12
        )
        output = proc.stderr or ""
    except Exception as e:
        logger.warning(f"[Gapless] Error al ejecutar ffmpeg silencedetect en {filepath}: {e}")
        return _fallback_silence()

    # Parsear duración total del audio
    duration = 0.0
    dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', output)
    if dur_match:
        h, m, s = dur_match.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)

    leading_silence = 0.0
    trailing_silence = 0.0
    trim_start = 0.0
    trim_end = duration

    silence_segments = []
    # Líneas típicas:
    # [silencedetect @ 0x...] silence_start: 0
    # [silencedetect @ 0x...] silence_end: 0.207812 | silence_duration: 0.207812
    # [silencedetect @ 0x...] silence_start: 176.322042
    # [silencedetect @ 0x...] silence_end: 179.012167 | silence_duration: 2.690125

    current_start = None
    for line in output.splitlines():
        if 'silence_start:' in line:
            m = re.search(r'silence_start:\s*([0-9.]+)', line)
            if m:
                current_start = float(m.group(1))
        elif 'silence_end:' in line:
            m_end = re.search(r'silence_end:\s*([0-9.]+)', line)
            m_dur = re.search(r'silence_duration:\s*([0-9.]+)', line)
            if m_end:
                end_val = float(m_end.group(1))
                dur_val = float(m_dur.group(1)) if m_dur else (end_val - (current_start or 0.0))
                silence_segments.append((current_start if current_start is not None else 0.0, end_val, dur_val))
                current_start = None

    if silence_segments:
        # Silencio inicial: si el primer segmento comienza en 0 o muy cerca de 0 (< 0.15s)
        first_start, first_end, first_dur = silence_segments[0]
        if first_start <= 0.15:
            leading_silence = first_end
            trim_start = first_end

        # Silencio final: el último segmento si termina cerca del final de la pista
        last_start, last_end, last_dur = silence_segments[-1]
        if duration > 0 and (last_end >= (duration - 0.5) or last_start >= (duration - 10.0)):
            trailing_silence = duration - last_start
            trim_end = last_start

    result = {
        'leading_silence': round(leading_silence, 3),
        'trailing_silence': round(max(0.0, trailing_silence), 3),
        'trim_start': round(trim_start, 3),
        'trim_end': round(trim_end if trim_end > trim_start else duration, 3),
        'duration': round(duration, 3)
    }

    if stat_key:
        _silence_cache[stat_key] = result

    return result


def _fallback_silence() -> dict:
    return {
        'leading_silence': 0.0,
        'trailing_silence': 0.0,
        'trim_start': 0.0,
        'trim_end': 0.0,
        'duration': 0.0
    }
