import time
from rapidfuzz import fuzz
from models import db, Cancion

# ============================================
# Caché simple en memoria con TTL
# ============================================
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
    # Limpiar entradas expiradas si el caché crece demasiado para liberar memoria
    if len(_similar_cache) > 500:
        now = time.time()
        expired = [k for k, (_, exp) in _similar_cache.items() if now >= exp]
        for k in expired:
            del _similar_cache[k]
    _similar_cache[key] = (value, time.time() + _CACHE_TTL)

# ============================================
# Motor de Recomendación Principal
# ============================================
def get_similar_songs(cancion_id, top_k=5):
    """
    Calcula la similitud de canciones con la canción objetivo
    utilizando un modelo híbrido de scoring.

    Optimizado: pre-filtra candidatos en SQL en vez de cargar toda la DB.
    Incluye caché en memoria con TTL de 10 minutos.
    """
    # 1. Verificar caché para evitar carga innecesaria a la BD
    cache_key = f'{cancion_id}:{top_k}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    target = Cancion.query.get(cancion_id)
    if not target:
        return []

    # ==========================================
    # FASE 1: Pre-filtrado (SQL Candidates)
    # ==========================================
    # Traemos un pool más grande (ej. 200) usando SQL puro para luego puntuar en Python
    query = Cancion.query.filter(Cancion.id != target.id)

    if target.genero:
        # Extraer la palabra principal del género (ej. "Rock/Pop" -> "Rock")
        genero_limpio = target.genero.split('/')[0].split(',')[0].strip()
        # Buscar cualquier canción que contenga esa palabra clave (ilike ignora mayúsculas)
        query = query.filter(Cancion.genero.ilike(f"%{genero_limpio}%"))

    # Limitamos a 200 candidatos para no colapsar la RAM
    candidatos = query.limit(200).all()

    # Si no hay suficientes candidatos por género (ej. es un género muy raro), rellenamos con otras canciones
    if len(candidatos) < top_k * 3:
        faltantes = 200 - len(candidatos)
        candidatos_extra = Cancion.query.filter(Cancion.id != target.id).limit(faltantes).all()
        # Evitar duplicados
        candidatos.extend([c for c in candidatos_extra if c not in candidatos])

    # ==========================================
    # FASE 2: Scoring de Similitud
    # ==========================================
    resultados = []
    
    for c in candidatos:
        score = 0.0
        
        # --- 1. Similitud de Género (Fuzzy Matching) ---
        if target.genero and c.genero:
            # fuzz.partial_ratio devuelve 0-100, normalizar a 0-1
            sim_genero = fuzz.partial_ratio(target.genero.lower(), c.genero.lower()) / 100.0
            if sim_genero >= 0.9:
                score += 0.35  # WEIGHT_GENRE (reducido de 0.45)
            elif sim_genero >= 0.6:
                # Proporcional entre 0.6 y 0.9
                score += 0.35 * (sim_genero - 0.6) / 0.3
        
        # --- 2. Similitud Acústica ---
        acoustic_score = 0.0
        acoustic_factors = 0
        
        # Dynamic Range
        if target.dynamic_range is not None and c.dynamic_range is not None:
            diff_dr = abs(target.dynamic_range - c.dynamic_range)
            # Diferencias mayores a 10dB son mundos distintos
            acoustic_score += max(0, 1.0 - (diff_dr / 10.0))
            acoustic_factors += 1
        
        # RMS (Volumen promedio)
        if target.rms_level is not None and c.rms_level is not None:
            diff_rms = abs(target.rms_level - c.rms_level)
            acoustic_score += max(0, 1.0 - (diff_rms / 10.0))
            acoustic_factors += 1
        
        # BPM (Tempo)
        target_bpm = getattr(target, 'bpm', None)
        c_bpm = getattr(c, 'bpm', None)
        if target_bpm is not None and c_bpm is not None:
            diff_bpm = abs(target_bpm - c_bpm)
            acoustic_score += max(0, 1.0 - (diff_bpm / 20.0))
            acoustic_factors += 1
        
        if acoustic_factors > 0:
            # Promedio de factores acústicos (0-1), luego multiplicar por peso
            score += (acoustic_score / acoustic_factors) * 0.35  # WEIGHT_ACOUSTIC (reducido de 0.40)
        
        # --- 3. Bono por Artista ---
        if target.artista_id and c.artista_id and target.artista_id == c.artista_id:
            score += 0.10  # WEIGHT_ARTIST (reducido de 0.15)
        
        # Asegurar que el score no pase de 1.0
        score = min(1.0, score)
        
        # Devolver en rango 0-1 (ej: 0.6 para 60%)
        resultados.append({
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
            'album': c.album_obj.titulo if c.album_obj else 'Desconocido',
            'cover': f"/album-art/{c.id}" if getattr(c, 'ruta_imagen_album', None) else None,
            'similarity': round(score, 4)  # 0-1 range (ej: 0.6 para 60%)
        })

    # ==========================================
    # FASE 3: Filtro de Variedad y Ordenamiento
    # ==========================================
    # Ordenar por score descendente
    resultados.sort(key=lambda x: x['similarity'], reverse=True)

    final_resultados = []
    album_counts = {}
    artist_counts = {}

    target_album = target.album_obj.titulo if target.album_obj else None
    target_artist = target.artista_obj.nombre if target.artista_obj else None

    for r in resultados:
        art = r['artista']
        alb = r['album']

        # Permitir máximo 2 canciones del mismo álbum
        if target_album and alb == target_album:
            if album_counts.get(alb, 0) >= 2:
                continue

        # Permitir máximo 3 canciones del mismo artista (para descubrir más bandas)
        if target_artist and art == target_artist:
            if artist_counts.get(art, 0) >= 3:
                continue

        final_resultados.append(r)
        album_counts[alb] = album_counts.get(alb, 0) + 1
        artist_counts[art] = artist_counts.get(art, 0) + 1

        if len(final_resultados) >= top_k:
            break

    # Guardar en caché antes de devolver
    _cache_set(cache_key, final_resultados)
    return final_resultados