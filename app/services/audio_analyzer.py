# -*- coding: utf-8 -*-
"""
Servicio de Análisis Técnico y Acústico de Audio - DuckSound
============================================================
Este servicio se encarga de analizar los archivos físicos de audio en disco para
extraer parámetros técnicos avanzados como:
- sample_rate (tasa de muestreo en Hz)
- bit_depth (profundidad de bits, ej. 16, 24 bits)
- channels (canales, estéreo/mono)
- duration (duración en segundos)
- nyquist_freq (frecuencia de Nyquist)
- dynamic_range (rango dinámico en dB)
- peak_level (nivel de pico máximo en dB)
- rms_level (volumen RMS promedio en dB)
- bpm (tempo estimado por detección de beats)

Usa de forma híbrida Mutagen (para cabeceras rápidas) y Librosa (para procesar señales de audio).
"""

import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Variable global para controlar la emisión del aviso de librosa en consola
_librosa_warning_shown = False

# Intentar importar la librería librosa (opcional, requerida para análisis de espectro y beats)
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    if not _librosa_warning_shown:
        logger.warning("[AudioAnalyzer] librosa no disponible, usando análisis básico con mutagen")
        _librosa_warning_shown = True


def analyze_audio(filepath):
    """
    Analiza un archivo físico de música y calcula todas las características acústicas.

    Args:
        filepath (str o Path): Ruta física al archivo de música (.mp3, .flac, .wav, etc.).

    Returns:
        dict: Diccionario con los valores extraídos. Las métricas principales incluyen:
            - nyquist_freq: Frecuencia de Nyquist en kHz (sample_rate / 2000). Representa la 
              frecuencia más alta que puede ser representada digitalmente sin aliasing.
            - dynamic_range: Diferencia entre el pico máximo y el nivel RMS. Indica cuán 
              comprimida está la grabación.
            - rms_level: Nivel de sonoridad promedio (Root Mean Square) en dBFS.
            - peak_level: Nivel de pico máximo absoluto en dBFS.
            - bpm: Tempo estimado en pulsos por minuto mediante detección de beats con librosa.
    """
    fp = Path(filepath)
    if not fp.exists():
        logger.error(f"Archivo de audio no encontrado para análisis: {filepath}")
        return {}

    result = {
        'sample_rate': None,
        'bit_depth': None,
        'channels': None,
        'duration': None,
        'nyquist_freq': None,
        'dynamic_range': None,
        'peak_level': None,
        'rms_level': None,
        'total_samples': None,
        'bit_rate': None,
        'genero': None
    }

    # --- FASE 1: Extracción rápida de metadatos de cabecera con mutagen ---
    try:
        from mutagen import File as MFile
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.wave import WAVE
        from mutagen.oggvorbis import OggVorbis

        af = MFile(filepath)
        if af is None:
            logger.warning(f"Mutagen no pudo interpretar las cabeceras del archivo: {filepath}")
        else:
            # Obtener datos de stream si existen
            if hasattr(af, 'info'):
                info = af.info
                if hasattr(info, 'sample_rate'):
                    result['sample_rate'] = info.sample_rate
                if hasattr(info, 'channels'):
                    result['channels'] = info.channels
                if hasattr(info, 'length'):
                    result['duration'] = info.length
                if hasattr(info, 'bitrate'):
                    result['bit_rate'] = info.bitrate

            # Lógica específica por contenedor
            if isinstance(af, MP3):
                result['bit_depth'] = 16  # Estimación estándar para MP3
                genre_tag = af.get('TCON', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

            elif isinstance(af, FLAC):
                if hasattr(info, 'bits_per_sample'):
                    result['bit_depth'] = info.bits_per_sample
                genre_tag = af.get('GENRE', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

            elif isinstance(af, WAVE):
                if hasattr(info, 'bit_width'):
                    result['bit_depth'] = info.bit_width
                if af.tags:
                    genre_tag = af.tags.get('GENRE', [None])[0] if hasattr(af.tags, 'get') else None
                    if genre_tag:
                        result['genero'] = str(genre_tag)

            elif isinstance(af, OggVorbis):
                genre_tag = af.get('GENRE', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

    except Exception as e:
        logger.warning(f"Error extrayendo cabeceras con mutagen para {filepath}: {e}")

    # Calcular la frecuencia de Nyquist (Tasa de muestreo / 2). 
    # Es la frecuencia máxima que puede ser capturada fielmente sin producir aliasing.
    if result['sample_rate']:
        result['nyquist_freq'] = result['sample_rate'] / 2000  # Convertir a kHz

    # Estimación de muestras totales aproximadas
    if result['duration'] and result['sample_rate']:
        result['total_samples'] = int(result['duration'] * result['sample_rate'])

    # --- FASE 2: Análisis acústico y digital de señal con librosa ---
    # En esta etapa procesamos la señal de audio real (PCM) para obtener métricas de sonoridad y tempo.
    if HAS_LIBROSA and result['sample_rate']:
        try:
            # Optimizamos el escaneo cargando solo una ventana de 30 segundos.
            # Si la canción es larga, saltamos los primeros 30s para evitar intros silenciosas.
            duration = result.get('duration', 0)
            if duration >= 60:
                y, sr = librosa.load(filepath, sr=None, mono=True, offset=30.0, duration=30.0)
            else:
                y, sr = librosa.load(filepath, sr=None, mono=True)

            if len(y) > 0:
                # Nivel de pico máximo en dB (dBFS). Se calcula buscando el valor absoluto máximo.
                peak = np.max(np.abs(y))
                result['peak_level'] = float(20 * np.log10(max(peak, 1e-10)))

                # Nivel RMS (Root Mean Square). Representa la energía promedio de la señal.
                rms = np.sqrt(np.mean(y ** 2))
                result['rms_level'] = float(20 * np.log10(max(rms, 1e-10)))

                # Estimación del tempo (BPM) mediante análisis de la función de autocorrelación del onset.
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                result['bpm'] = float(tempo.item() if hasattr(tempo, 'item') else tempo)

                # El rango dinámico se define aquí como la diferencia entre el pico y la media (RMS).
                if result['peak_level'] is not None and result['rms_level'] is not None:
                    result['dynamic_range'] = float(result['peak_level'] - result['rms_level'])

                # Actualizar datos con los calculados de precisión por librosa
                result['sample_rate'] = int(sr)
                result['total_samples'] = len(y)
                result['duration'] = float(len(y) / sr)
                result['nyquist_freq'] = sr / 2000

        except Exception as e:
            logger.warning(f"Error en procesamiento digital de señal con librosa para {filepath}: {e}")

    # Redondear campos de volumen y dinámicas para almacenamiento limpio en base de datos
    for key in ['dynamic_range', 'peak_level', 'rms_level']:
        if result[key] is not None:
            result[key] = round(result[key], 1)

    return result
