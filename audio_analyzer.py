import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Variable global para controlar el aviso de librosa
_librosa_warning_shown = False

# Intentar importar librosa (opcional, para análisis más precisos)
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    if not _librosa_warning_shown:
        logger.warning("librosa no disponible, usando análisis básico con mutagen")
        _librosa_warning_shown = True


def analyze_audio(filepath):
    """
    Analiza un archivo de audio y devuelve un dict con todos los parámetros.
    Siempre retorna los campos que pueda extraer, incluso si algunos son None.
    """
    fp = Path(filepath)
    if not fp.exists():
        logger.error(f"Archivo no encontrado: {filepath}")
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

    # --- FASE 1: Metadatos con mutagen ---
    try:
        from mutagen import File as MFile
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.wave import WAVE
        from mutagen.oggvorbis import OggVorbis

        af = MFile(filepath)
        if af is None:
            logger.warning(f"mutagen no pudo leer: {filepath}")
        else:
            # Info general del stream
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

            # MP3 específico
            if isinstance(af, MP3):
                # Bit depth no es nativo de MP3, estimamos 16 bits
                result['bit_depth'] = 16
                # Extraer género
                genre_tag = af.get('TCON', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

            # FLAC específico
            elif isinstance(af, FLAC):
                if hasattr(info, 'bits_per_sample'):
                    result['bit_depth'] = info.bits_per_sample
                genre_tag = af.get('GENRE', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

            # WAVE específico
            elif isinstance(af, WAVE):
                if hasattr(info, 'bit_width'):
                    result['bit_depth'] = info.bit_width
                if af.tags:
                    genre_tag = af.tags.get('GENRE', [None])[0] if hasattr(af.tags, 'get') else None
                    if genre_tag:
                        result['genero'] = str(genre_tag)

            # OGG Vorbis
            elif isinstance(af, OggVorbis):
                genre_tag = af.get('GENRE', [None])[0]
                if genre_tag:
                    result['genero'] = str(genre_tag)

    except Exception as e:
        logger.warning(f"Error en mutagen para {filepath}: {e}")

    # Nyquist frequency = sample_rate / 2
    if result['sample_rate']:
        result['nyquist_freq'] = result['sample_rate'] / 2000  # en kHz

    # Total samples aproximado
    if result['duration'] and result['sample_rate']:
        result['total_samples'] = int(result['duration'] * result['sample_rate'])

    # --- FASE 2: Análisis de señal con librosa (más preciso) ---
    if HAS_LIBROSA and result['sample_rate']:
        try:
            # Cargar solo 30 segundos desde el segundo 30 para análisis rápido
            # Si la canción dura menos de 60 segundos, cargar sin offset
            duration = result.get('duration', 0)
            if duration >= 60:
                # Cargar 30 segundos comenzando desde el segundo 30
                y, sr = librosa.load(filepath, sr=None, mono=True, offset=30.0, duration=30.0)
            else:
                # Canción corta: cargar sin offset
                y, sr = librosa.load(filepath, sr=None, mono=True)

            if len(y) > 0:
                # Peak level (dB)
                peak = np.max(np.abs(y))
                result['peak_level'] = float(20 * np.log10(max(peak, 1e-10)))

                # RMS level (dB)
                rms = np.sqrt(np.mean(y ** 2))
                result['rms_level'] = float(20 * np.log10(max(rms, 1e-10)))

                # Detectar el tempo (BPM)
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                result['bpm'] = float(tempo.item() if hasattr(tempo, 'item') else tempo)

                # Dynamic Range (dB) - diferencia entre pico y RMS
                if result['peak_level'] is not None and result['rms_level'] is not None:
                    result['dynamic_range'] = float(result['peak_level'] - result['rms_level'])

                # Actualizar sample_rate desde librosa (más fiable)
                result['sample_rate'] = int(sr)
                result['total_samples'] = len(y)
                result['duration'] = float(len(y) / sr)
                result['nyquist_freq'] = sr / 2000

        except Exception as e:
            logger.warning(f"Error en librosa para {filepath}: {e}")

    # Redondear valores para legibilidad
    for key in ['dynamic_range', 'peak_level', 'rms_level']:
        if result[key] is not None:
            result[key] = round(result[key], 1)

    return result
