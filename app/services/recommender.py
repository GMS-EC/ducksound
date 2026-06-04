# -*- coding: utf-8 -*-
"""
Servicio de Recomendaciones y Mezclas Diarias (Daily Mixes) - DuckSound
========================================================================
Este servicio encapsula el motor de recomendación híbrido de DuckSound y la lógica
para generar las mezclas diarias personalizadas (Daily Mixes) para los usuarios.

Calcula la similitud entre canciones mediante un scoring híbrido:
1. Similitud de género (Fuzzy matching con RapidFuzz).
2. Similitud acústica (tempo/BPM, volumen RMS, rango dinámico).
3. Bonificación por artista en común.

Genera 3 mezclas temáticas distintas basadas en los hábitos de escucha del usuario:
- 'Morning Vibes': Energía, BPMs altos, favoritos mezclados con novedades.
- 'Afternoon Chill': Descubrimiento relajado, BPM moderado.
- 'Night Beats': Ritmo nocturno, basado en historial histórico y canciones nuevas.
"""

import time
import random
from datetime import datetime, date, timedelta
from rapidfuzz import fuzz
from app.models import db, Cancion, Favorito, HistorialEscucha, DailyMix, Usuario

# ============================================
# 💾 CACHÉ SIMPLE EN MEMORIA CON TTL PARA RECOMENDACIONES
# ============================================
_similar_cache = {}
_CACHE_TTL = 600  # 10 minutos de tiempo de vida (TTL)


def _cache_get(key):
    """Obtiene un valor del caché si no ha expirado aún."""
    if key in _similar_cache:
        value, expires = _similar_cache[key]
        if time.time() < expires:
            return value
        del _similar_cache[key]
    return None


def _cache_set(key, value):
    """Guarda un valor en el caché con un tiempo de expiración y limpia el caché si crece demasiado."""
    if len(_similar_cache) > 500:
        now = time.time()
        expired = [k for k, (_, exp) in _similar_cache.items() if now >= exp]
        for k in expired:
            del _similar_cache[k]
    _similar_cache[key] = (value, time.time() + _CACHE_TTL)


# ============================================
# 🎛️ MOTOR DE RECOMENDACIÓN DE CANCIONES SIMILARES
# ============================================

def get_similar_songs(cancion_id, top_k=5):
    """
    Calcula la similitud de canciones con la canción objetivo utilizando un modelo híbrido.
    
    Args:
        cancion_id (int): Identificador de la canción semilla.
        top_k (int): Número de canciones similares a retornar.
        
    Returns:
        list: Lista de diccionarios que representan las canciones similares y su porcentaje.
    """
    # 1. Verificar el caché local para evitar consultas SQL pesadas
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
    # Filtrar candidatos básicos en base de datos para no cargar toda la biblioteca en RAM
    query = Cancion.query.filter(Cancion.id != target.id)

    if target.genero:
        # Extraer el género principal (ej. "Rock/Pop" -> "Rock")
        genero_limpio = target.genero.split('/')[0].split(',')[0].strip()
        query = query.filter(Cancion.genero.ilike(f"%{genero_limpio}%"))

    # Limitamos a 200 candidatos máximos para balancear rendimiento y calidad
    candidatos = query.limit(200).all()

    # Si hay pocos candidatos del mismo género, rellenamos con otras canciones generales
    if len(candidatos) < top_k * 3:
        faltantes = 200 - len(candidatos)
        candidatos_extra = Cancion.query.filter(Cancion.id != target.id).limit(faltantes).all()
        for c in candidatos_extra:
            if c not in candidatos:
                candidatos.append(c)

    # ==========================================
    # FASE 2: Puntuación de Similitud (Scoring)
    # ==========================================
    resultados = []
    
    for c in candidatos:
        score = 0.0
        
        # --- 1. Similitud de Género (Fuzzy Matching) ---
        if target.genero and c.genero:
            sim_genero = fuzz.partial_ratio(target.genero.lower(), c.genero.lower()) / 100.0
            if sim_genero >= 0.9:
                score += 0.35  # Peso del género
            elif sim_genero >= 0.6:
                score += 0.35 * (sim_genero - 0.6) / 0.3
        
        # --- 2. Similitud Acústica ---
        acoustic_score = 0.0
        acoustic_factors = 0
        
        # Rango Dinámico (Dynamic Range)
        if target.dynamic_range is not None and c.dynamic_range is not None:
            diff_dr = abs(target.dynamic_range - c.dynamic_range)
            acoustic_score += max(0, 1.0 - (diff_dr / 10.0))
            acoustic_factors += 1
        
        # RMS Level (Volumen promedio de la señal)
        if target.rms_level is not None and c.rms_level is not None:
            diff_rms = abs(target.rms_level - c.rms_level)
            acoustic_score += max(0, 1.0 - (diff_rms / 10.0))
            acoustic_factors += 1
        
        # Tempo (BPM)
        target_bpm = getattr(target, 'bpm', None)
        c_bpm = getattr(c, 'bpm', None)
        if target_bpm is not None and c_bpm is not None:
            diff_bpm = abs(target_bpm - c_bpm)
            acoustic_score += max(0, 1.0 - (diff_bpm / 20.0))
            acoustic_factors += 1
        
        if acoustic_factors > 0:
            score += (acoustic_score / acoustic_factors) * 0.35  # Peso acústico
        
        # --- 3. Bonificación por coincidencia de Artista ---
        if target.artista_id and c.artista_id and target.artista_id == c.artista_id:
            score += 0.10  # Peso del artista
        
        # Acotar score a un límite de 1.0
        score = min(1.0, score)
        
        resultados.append({
            'id': c.id,
            'titulo': c.titulo,
            'artista': c.artista_obj.nombre if c.artista_obj else 'Desconocido',
            'album': c.album_obj.titulo if c.album_obj else 'Desconocido',
            'cover': f"/album-art/{c.id}" if getattr(c, 'ruta_imagen_album', None) else None,
            'similarity': round(score, 4)
        })

    # ==========================================
    # FASE 3: Filtro de Variedad y Ordenamiento
    # ==========================================
    resultados.sort(key=lambda x: x['similarity'], reverse=True)

    final_resultados = []
    album_counts = {}
    artist_counts = {}

    target_album = target.album_obj.titulo if target.album_obj else None
    target_artist = target.artista_obj.nombre if target.artista_obj else None

    for r in resultados:
        art = r['artista']
        alb = r['album']

        # Evitar fatiga permitiendo máximo 2 canciones del mismo álbum
        if target_album and alb == target_album:
            if album_counts.get(alb, 0) >= 2:
                continue

        # Evitar fatiga permitiendo máximo 3 canciones del mismo artista
        if target_artist and art == target_artist:
            if artist_counts.get(art, 0) >= 3:
                continue

        final_resultados.append(r)
        album_counts[alb] = album_counts.get(alb, 0) + 1
        artist_counts[art] = artist_counts.get(art, 0) + 1

        if len(final_resultados) >= top_k:
            break

    # Guardar en caché antes de devolver el resultado
    _cache_set(cache_key, final_resultados)
    return final_resultados


# ==========================================================
# ⚡ MOTOR DE RECOMENDACIÓN DE MIXES DIARIOS PERSONALIZADOS
# ==========================================================

def generate_daily_mixes_for_user(usuario_id):
    """
    Motor de Recomendación de Mixes Diarios Personalizados.
    
    Genera 3 mezclas temáticas distintas basadas en los hábitos de escucha de un usuario.
    Excluye canciones reproducidas en la última semana para mantener las listas frescas.
    
    Args:
        usuario_id (int): Identificador del usuario al cual generarle los mixes.
    """
    today = datetime.utcnow().date()
    last_week = datetime.utcnow() - timedelta(days=7)

    # === 1. OBTENER FUENTES DE DATOS DE HÁBITOS DE ESCUCHA ===

    # Obtener el Top 50 de canciones más escuchadas del usuario
    mas_escuchadas = db.session.query(
        Cancion.id, db.func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion.id).order_by(db.desc('plays')).limit(50).all()
    mas_escuchadas_ids = [c.id for c in mas_escuchadas]

    # Obtener IDs de las canciones marcadas como "Favoritos" ("Me gusta")
    fav_ids = [f.cancion_id for f in Favorito.query.filter_by(usuario_id=usuario_id).all()]

    # Canciones reproducidas recientemente (exclusión temporal)
    recientes_ids = [h.cancion_id for h in HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.reproducido_en >= last_week
    ).distinct(HistorialEscucha.cancion_id).all()]

    # Determinar los 3 géneros más escuchados por el usuario
    top_generos = db.session.query(
        Cancion.genero, db.func.count(Cancion.id).label('cnt')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        Cancion.genero.isnot(None),
        Cancion.genero != ''
    ).group_by(Cancion.genero).order_by(db.desc('cnt')).limit(3).all()
    top_generos_list = [g[0] for g in top_generos if g[0]]

    # === 2. FUNCIONES AUXILIARES INTERNAS ===
    
    def _random_ids(limit, extra_filters=None):
        """Muestreo aleatorio de canciones de la base de datos que cumplen ciertos criterios."""
        base = Cancion.query.with_entities(Cancion.id)
        if extra_filters:
            for f in extra_filters:
                base = base.filter(f)
        ids = [r[0] for r in base.all()]
        if not ids:
            return []
        return random.sample(ids, min(limit, len(ids)))

    def obtener_similares_a(song_ids, top_k=8):
        """Consulta canciones similares acústicamente basándose en una semilla de hasta 5 temas."""
        similares_ids = set()
        for sid in song_ids[:5]:
            try:
                similares = get_similar_songs(sid, top_k=top_k)
                for s in similares:
                    if s['id'] not in similares_ids:
                        similares_ids.add(s['id'])
            except Exception:
                continue
        return list(similares_ids)

    def mezclar_pool(pools, target=20):
        """Algoritmo de mezcla round-robin proporcional para evitar duplicados en la lista final."""
        result = []
        seen = set()
        idx = [0] * len(pools)
        rounds = 0
        while len(result) < target and rounds < target * 2:
            for i, pool in enumerate(pools):
                if len(result) >= target:
                    break
                if idx[i] < len(pool):
                    cid = pool[idx[i]]
                    idx[i] += 1
                    if cid not in seen:
                        seen.add(cid)
                        result.append(cid)
            rounds += 1
        return result[:target]

    # === 3. CONFIGURACIÓN Y CONSTRUCCIÓN DE LOS 3 MIXES ===
    
    pool_populares = list(dict.fromkeys(mas_escuchadas_ids + fav_ids))

    mixes_data = [
        {
            'name': 'Morning Vibes',
            'desc': 'Energía para empezar el día',
            'pools': ['populares', 'similares', 'genero'],
        },
        {
            'name': 'Afternoon Chill',
            'desc': 'Relax para la tarde',
            'pools': ['favoritos', 'similares', 'explorar'],
        },
        {
            'name': 'Night Beats',
            'desc': 'Ritmo para la noche',
            'pools': ['historial', 'similares', 'nuevos'],
        },
    ]

    for mix_info in mixes_data:
        name = mix_info['name']
        pools = []
        excluir_ids_set = set(recientes_ids)

        # Pool 1: Canciones familiares del usuario (excluyendo lo reciente)
        populares_pool = pool_populares.copy()
        random.shuffle(populares_pool)
        pool_populares_filtrado = [c for c in populares_pool if c not in excluir_ids_set]
        if pool_populares_filtrado:
            pools.append(pool_populares_filtrado)
            excluir_ids_set.update(pool_populares_filtrado)

        # Pool 2: Canciones recomendadas acústicamente similares a sus favoritas
        if fav_ids:
            raw_similares = obtener_similares_a(fav_ids, top_k=6)
            pool_similares_ids = [s for s in raw_similares if s not in excluir_ids_set]
            if pool_similares_ids:
                pools.append(pool_similares_ids)
                excluir_ids_set.update(pool_similares_ids)

        # Pool 3: Descubrimiento de nuevos temas dentro de sus géneros favoritos
        if top_generos_list:
            genre = top_generos_list[(hash(name) % len(top_generos_list))]
            explorar_ids = _random_ids(30, [
                Cancion.genero.ilike(f'%{genre}%'),
                ~Cancion.id.in_(excluir_ids_set) if excluir_ids_set else db.true()
            ])
            if explorar_ids:
                pools.append(explorar_ids)
                excluir_ids_set.update(explorar_ids)

        # Fallback de seguridad en caso de que el usuario sea nuevo y no tenga suficiente historial
        if not pools or sum(len(p) for p in pools) < 5:
            fallback_ids = _random_ids(30)
            fallback_ids = [c for c in fallback_ids if c not in excluir_ids_set]
            pools = [fallback_ids]

        # Combinar las listas rotativamente
        mix_canciones_ids = mezclar_pool(pools, target=20)

        # Si aún queda vacío, rellenar aleatoriamente
        if not mix_canciones_ids:
            mix_canciones_ids = _random_ids(20)

        # === 4. GUARDAR E INSERTAR MIX DIARIO ===
        # Eliminar mixes del mismo tipo generados hoy para evitar duplicados
        DailyMix.query.filter_by(usuario_id=usuario_id, nombre=name, fecha=today).delete()

        mix = DailyMix(usuario_id=usuario_id, nombre=name, fecha=today)
        db.session.add(mix)
        db.session.flush()  # Obtener el ID asignado por base de datos

        # Registrar las canciones del mix diario conservando el orden asignado
        for idx, cid in enumerate(mix_canciones_ids[:20]):
            cancion = Cancion.query.get(cid)
            if cancion:
                mix.canciones.append(cancion)

    db.session.commit()
    print(f"✅ Daily Mixes generados con éxito para el usuario {usuario_id}.")


def generate_daily_mixes_for_all_users():
    """Genera daily mixes de forma masiva para todos los usuarios registrados."""
    usuarios = Usuario.query.all()
    for usuario in usuarios:
        print(f"Procesando Daily Mixes para: {usuario.nombre_usuario} (ID: {usuario.id})")
        generate_daily_mixes_for_user(usuario.id)
