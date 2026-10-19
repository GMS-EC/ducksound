# -*- coding: utf-8 -*-
"""
Servicio de Edición de Etiquetas y Metadatos de Audio (In-App Tagger) - DuckSound
================================================================================
Permite leer y escribir etiquetas estándar (ID3v2, Vorbis Comments, MP4 Atoms)
directamente en los archivos físicos de audio en el almacenamiento.
"""

import logging
import os
from pathlib import Path
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)


def read_audio_tags(filepath: str) -> dict:
    """
    Lee las etiquetas actuales de un archivo de audio físico.
    """
    if not filepath or not os.path.exists(filepath):
        return {}

    try:
        import mutagen
        f = mutagen.File(filepath, easy=True)
        if f is None:
            # Fallback a mutagen genérico
            f = mutagen.File(filepath)
            if f is None:
                return {}

        tags = {}
        for key in ['title', 'artist', 'album', 'tracknumber', 'genre', 'date']:
            val = f.get(key)
            if val:
                tags[key] = val[0] if isinstance(val, (list, tuple)) else str(val)

        return tags
    except Exception as e:
        logger.warning(f"[Tagger] Error leyendo etiquetas de {filepath}: {e}")
        return {}


def write_audio_tags(filepath: str, metadata: dict) -> Tuple[bool, Optional[str]]:
    """
    Escribe metadatos en un archivo de audio físico soportando MP3, FLAC, M4A, OGG y OPUS.

    Args:
        filepath: Ruta absoluta al archivo de música.
        metadata: Diccionario con campos a actualizar:
            - titulo (str)
            - artista (str)
            - album (str)
            - numero_pista (int o str)
            - genero (str)
            - anio (int o str)

    Returns:
        (éxito: bool, error: Optional[str])
    """
    if not filepath or not os.path.exists(filepath):
        return False, "El archivo de audio no existe en el disco."

    ext = Path(filepath).suffix.lower()

    try:
        titulo = metadata.get('titulo') or metadata.get('title')
        artista = metadata.get('artista') or metadata.get('artist')
        album = metadata.get('album')
        numero_pista = metadata.get('numero_pista') or metadata.get('tracknumber')
        genero = metadata.get('genero') or metadata.get('genre')
        anio = metadata.get('anio') or metadata.get('year') or metadata.get('date')

        if ext == '.mp3':
            from mutagen.easyid3 import EasyID3
            from mutagen.id3 import ID3NoHeaderError

            try:
                audio = EasyID3(filepath)
            except ID3NoHeaderError:
                audio = EasyID3()

            if titulo is not None:
                audio['title'] = str(titulo)
            if artista is not None:
                audio['artist'] = str(artista)
            if album is not None:
                audio['album'] = str(album)
            if numero_pista is not None and str(numero_pista).strip():
                audio['tracknumber'] = str(numero_pista)
            if genero is not None and str(genero).strip():
                audio['genre'] = str(genero)
            if anio is not None and str(anio).strip():
                audio['date'] = str(anio)

            audio.save(filepath)
            return True, None

        elif ext == '.flac':
            from mutagen.flac import FLAC

            audio = FLAC(filepath)
            if titulo is not None:
                audio['TITLE'] = [str(titulo)]
            if artista is not None:
                audio['ARTIST'] = [str(artista)]
            if album is not None:
                audio['ALBUM'] = [str(album)]
            if numero_pista is not None and str(numero_pista).strip():
                audio['TRACKNUMBER'] = [str(numero_pista)]
            if genero is not None and str(genero).strip():
                audio['GENRE'] = [str(genero)]
            if anio is not None and str(anio).strip():
                audio['DATE'] = [str(anio)]

            audio.save()
            return True, None

        elif ext in ['.m4a', '.mp4', '.aac']:
            from mutagen.mp4 import MP4

            audio = MP4(filepath)
            if titulo is not None:
                audio['\xa9nam'] = [str(titulo)]
            if artista is not None:
                audio['\xa9ART'] = [str(artista)]
            if album is not None:
                audio['\xa9alb'] = [str(album)]
            if genero is not None and str(genero).strip():
                audio['\xa9gen'] = [str(genero)]
            if anio is not None and str(anio).strip():
                audio['\xa9day'] = [str(anio)]
            if numero_pista is not None:
                try:
                    num = int(numero_pista)
                    audio['trkn'] = [(num, 0)]
                except ValueError:
                    pass

            audio.save()
            return True, None

        elif ext in ['.ogg', '.opus']:
            import mutagen

            audio = mutagen.File(filepath)
            if audio is not None and hasattr(audio, 'tags') and audio.tags is not None:
                if titulo is not None:
                    audio.tags['TITLE'] = [str(titulo)]
                if artista is not None:
                    audio.tags['ARTIST'] = [str(artista)]
                if album is not None:
                    audio.tags['ALBUM'] = [str(album)]
                if numero_pista is not None and str(numero_pista).strip():
                    audio.tags['TRACKNUMBER'] = [str(numero_pista)]
                if genero is not None and str(genero).strip():
                    audio.tags['GENRE'] = [str(genero)]
                if anio is not None and str(anio).strip():
                    audio.tags['DATE'] = [str(anio)]
                audio.save()
                return True, None

        # Para otros formatos, intentar mutagen.File genérico con EasyID3 o tags
        import mutagen
        audio = mutagen.File(filepath, easy=True)
        if audio is not None:
            if titulo is not None:
                audio['title'] = str(titulo)
            if artista is not None:
                audio['artist'] = str(artista)
            if album is not None:
                audio['album'] = str(album)
            audio.save()
            return True, None

        return False, f"Formato de archivo '{ext}' no soportado para escritura directa."

    except Exception as e:
        logger.error(f"[Tagger] Error escribiendo metadatos en {filepath}: {e}")
        return False, str(e)
