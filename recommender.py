import math


# ============================================
# Caché simple en memoria con TTL
# ============================================
import time

_similar_cache = {}
_CACHE_TTL = 600  # 10 minutos


def _cache_get(key):
    """Obtiene un valor del caché si no ha expirado."""
    if key in _similar_cache:
        value, expires = _similar_cache[key]
        if time.time() < expires:
            return value
        del _similar_cache[key]
    return None


def _cache_set(key, value):
    """Guarda un valor en el caché con TTL."""
    # Limpiar entradas expiradas si el caché crece demasiado
    if len(_similar_cache) > 500:
        now = time.time()
        expired = [k for k, (_, exp) in _similar_cache.items() if now >= exp]
        for k in expired:
            del _similar_cache[k]
    _similar_cache[key] = (value, time.time() + _CACHE_TTL)


def get_similar_songs(cancion_id, top_k=5):
    """
    Calcula la similitud de canciones con la canción objetivo
    utilizando un modelo híbrido de scoring.

    Optimizado: pre-filtra candidatos en SQL en vez de cargar toda la DB.
    Incluye caché en memoria con TTL de 10 minutos.
    """
    # Verificar caché
    cache_key = f'{cancion_id}:{top_k}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from app import app
    from models import Cancion, db

    with app.app_context():
        target = Cancion.query.get(cancion_id)
        if not target:
            return []

        # ============================================
        # FASE 1: Pre-filtrar candidatos en SQL
        # En vez de cargar TODA la biblioteca (O(n)),
        # filtramos por género y/o artista (máximo ~200 candidatos)
        # ============================================
        base_query = Cancion.query.filter(Cancion.id != cancion_id)

        filters = []
        if target.genero:
            filters.append(Cancion.genero == target.genero)
        if target.artista_id:
            filters.append(Cancion.artista_id == target.artista_id)

        if filters:
            from sqlalchemy import or_
            candidates = base_query.filter(or_(*filters)).limit(200).all()
            # Si encontramos pocos, complementar con aleatorios
            if len(candidates) < top_k * 4:
                existing_ids = {c.id for c in candidates}
                extras = base_query.filter(
                    ~Cancion.id.in_(existing_ids) if existing_ids else db.true()
                ).order_by(db.func.random()).limit(50).all()
                candidates.extend(extras)
        else:
            # Sin metadatos de género/artista: usar aleatorios
            candidates = base_query.order_by(db.func.random()).limit(100).all()

        if not candidates:
            return []

        # ============================================
        # FASE 2: Scoring sobre candidatos pre-filtrados
        # ============================================
        resultados = []

        # Pesos del modelo híbrido
        WEIGHT_GENRE = 35.0
        WEIGHT_ARTIST = 25.0
        WEIGHT_ALBUM = 10.0
        WEIGHT_ACOUSTIC = 20.0
        WEIGHT_DURATION = 10.0

        # Calcular puntuación máxima posible según los datos que SÍ tiene la canción actual
        max_score = 0.0
        if target.genero: max_score += WEIGHT_GENRE
        if target.artista_id: max_score += WEIGHT_ARTIST
        if target.album_id: max_score += WEIGHT_ALBUM
        if target.duracion: max_score += WEIGHT_DURATION
        if target.dynamic_range is not None or target.rms_level is not None or target.bit_rate is not None:
            max_score += WEIGHT_ACOUSTIC

        if max_score == 0:
            max_score = 100.0  # Por seguridad

        for c in candidates:
            score = 0.0

            # 1. Similitud de Metadatos
            # Género
            if target.genero and c.genero and target.genero.lower().strip() == c.genero.lower().strip():
                score += WEIGHT_GENRE

            # Artista
            if target.artista_id and c.artista_id and target.artista_id == c.artista_id:
                score += WEIGHT_ARTIST

            # Álbum (suelen ser del mismo estilo si están en el mismo disco)
            if target.album_id and c.album_id and target.album_id == c.album_id:
                score += WEIGHT_ALBUM

            # 2. Similitud de Duración (Campana de Gauss simple)
            # Canciones de duraciones similares suelen tener estructuras similares (ej. pop de 3 mins vs épica de 10 mins)
            if target.duracion and c.duracion:
                diff_sec = abs(target.duracion - c.duracion)
                # Si la diferencia es 0, gana WEIGHT_DURATION. Si es 60 segs, cae drásticamente.
                dur_score = WEIGHT_DURATION * math.exp(-(diff_sec**2) / (2 * 30**2))
                score += dur_score

            # 3. Similitud Acústica (Energía y masterización)
            acoustic_score = 0
            valid_metrics = 0

            # Dynamic Range (Rango Dinámico)
            if target.dynamic_range is not None and c.dynamic_range is not None:
                diff_dr = abs(target.dynamic_range - c.dynamic_range)
                acoustic_score += max(0, 1.0 - (diff_dr / 10.0))  # Cae a 0 si difieren por 10dB
                valid_metrics += 1

            # RMS Level (Volumen percibido medio)
            if target.rms_level is not None and c.rms_level is not None:
                diff_rms = abs(target.rms_level - c.rms_level)
                acoustic_score += max(0, 1.0 - (diff_rms / 6.0))   # Cae a 0 si difieren por 6dB
                valid_metrics += 1

            # Bit Rate (Calidad general de compresión/estilo)
            if target.bit_rate is not None and c.bit_rate is not None:
                diff_br = abs(target.bit_rate - c.bit_rate)
                acoustic_score += max(0, 1.0 - (diff_br / 128000.0))
                valid_metrics += 1

            if valid_metrics > 0:
                # Normalizar el score acústico al peso máximo
                score += (acoustic_score / valid_metrics) * WEIGHT_ACOUSTIC

            # Penalizaciones eliminadas: la variedad se maneja en el filtrado final

            sim_percent = score / max_score
            sim_percent = min(1.0, sim_percent)  # Tope al 100%

            resultados.append({
                'id': c.id,
                'titulo': c.titulo,
                'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
                'album': c.album_obj.titulo if c.album_obj else 'Desconocido',
                'cover': f"/album-art/{c.id}" if getattr(c, 'ruta_imagen_album', None) else None,
                'similarity': round(sim_percent, 4)
            })

        # Ordenar por score descendente
        resultados.sort(key=lambda x: x['similarity'], reverse=True)

        # Filtrar para forzar la variedad musical sin estropear los porcentajes
        final_resultados = []
        album_counts = {}
        artist_counts = {}

        target_album = target.album_obj.titulo if target.album_obj else None
        target_artist = target.artista_obj.nombre if target.artista_obj else None

        for r in resultados:
            art = r['artista']
            alb = r['album']

            # Si estamos reproduciendo X álbum, permitir máximo 2 canciones del mismo álbum
            if target_album and alb == target_album:
                if album_counts.get(alb, 0) >= 2:
                    continue

            # Permitir máximo 3 canciones del mismo artista (para dar lugar a otras bandas similares)
            if target_artist and art == target_artist:
                if artist_counts.get(art, 0) >= 3:
                    continue

            final_resultados.append(r)
            album_counts[alb] = album_counts.get(alb, 0) + 1
            artist_counts[art] = artist_counts.get(art, 0) + 1

            if len(final_resultados) >= top_k:
                break

        # Guardar en caché
        _cache_set(cache_key, final_resultados)

        return final_resultados
