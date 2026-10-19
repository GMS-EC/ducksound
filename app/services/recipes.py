# -*- coding: utf-8 -*-
"""
Motor de Recetas y Mezclas Inteligentes (Smart Mixes & Recipes) - DuckSound
==========================================================================

Proporciona generación de mezclas dinámicas y listas inteligentes:
1. Top Mix ("Tus Más Escuchadas" / "Top Streamed"): Basado en historial de reproducciones del usuario o biblioteca.
2. Recent Mix ("Recién Añadidas" / "Descubrimientos Recientes"): Canciones añadidas recientemente o historial fresco.
3. Track Radio ("Radio de la Canción"): Estación inteligente basada en una semilla, combinando similitud acústica
   (BPM, rango dinámico, RMS), coincidencias de género difuso y artistas relacionados.
4. Artist Radio ("Radio de Artista"): Mezcla centrada en un artista y sus artistas afines.
5. Overview de Mezclas: Resumen de mezclas disponibles para la pantalla principal o sección de mezclas.
"""

from datetime import datetime, timedelta
import random
from sqlalchemy import func, desc
from app.models import db, Cancion, Artista, Album, HistorialEscucha, DailyMix


def violates_gap_rule(balanced_mix: dict[int, dict], position: int, track: dict, gap: int = 2) -> bool:
    """
    Verifica si colocar 'track' en 'position' viola la regla de distanciamiento (Gap Rule).
    Se viola si alguna de las 'gap' pistas anteriores pertenece al mismo artista.
    """
    track_artist = track.get('artista') or (track.get('artista_obj') or {}).get('nombre') or ''
    if not track_artist:
        return False
    track_artist_lower = str(track_artist).lower().strip()

    for i in range(max(0, position - gap), position):
        if i in balanced_mix:
            other = balanced_mix[i]
            other_artist = other.get('artista') or (other.get('artista_obj') or {}).get('nombre') or ''
            if other_artist and str(other_artist).lower().strip() == track_artist_lower:
                return True
    return False


def find_next_position(balanced_mix: dict[int, dict], start: int, track: dict, total_tracks: int, gap: int = 2) -> int:
    """
    Encuentra la siguiente posición disponible para una pista que no viole la regla de gap,
    avanzando desde 'start' y haciendo wrap-around si es necesario.
    """
    for i in range(start, total_tracks):
        if i not in balanced_mix and not violates_gap_rule(balanced_mix, i, track, gap=gap):
            return i
    for i in range(start):
        if i not in balanced_mix and not violates_gap_rule(balanced_mix, i, track, gap=gap):
            return i
    for i in range(total_tracks):
        if i not in balanced_mix:
            return i
    return start


def balance_mix(tracks: list[dict], gap: int = 2) -> list[dict]:
    """
    Equilibra una lista de canciones aplicando la regla de distanciamiento (Gap Rule):
    evita que canciones del mismo artista suenen consecutivamente.
    Preserva el orden original tanto como sea posible.
    """
    if len(tracks) <= gap + 1:
        return tracks

    balanced_mix: dict[int, dict] = {}
    total_tracks = len(tracks)

    for i, track in enumerate(tracks):
        if i not in balanced_mix and not violates_gap_rule(balanced_mix, i, track, gap=gap):
            balanced_mix[i] = track
        else:
            new_pos = find_next_position(balanced_mix, i, track, total_tracks, gap=gap)
            balanced_mix[new_pos] = track

    return [balanced_mix[i] for i in sorted(balanced_mix.keys())]


def get_top_mix(user_id=None, limit=30):
    """
    Retorna la mezcla de canciones más escuchadas (Top Streamed).
    Si se especifica user_id, prioriza el historial del usuario; de lo contrario, usa el contador global.
    """
    canciones_ids = []
    seen = set()

    if user_id:
        try:
            # Consultar historial del usuario excluyendo skips rápidos
            user_history = db.session.query(
                HistorialEscucha.cancion_id,
                func.count(HistorialEscucha.id).label('play_cnt')
            ).filter(
                HistorialEscucha.usuario_id == user_id,
                HistorialEscucha.skip == False
            ).group_by(
                HistorialEscucha.cancion_id
            ).order_by(
                desc('play_cnt')
            ).limit(limit).all()

            for cid, _ in user_history:
                canciones_ids.append(cid)
                seen.add(cid)
        except Exception as e:
            print(f"[DuckSound Recipes] Error consultando historial usuario en get_top_mix: {e}")

    # Si faltan canciones para alcanzar el límite, complementar con el ranking global
    if len(canciones_ids) < limit:
        needed = limit - len(canciones_ids)
        query = Cancion.query
        if seen:
            query = query.filter(~Cancion.id.in_(seen))
        global_top = query.order_by(
            Cancion.play_count.desc(),
            Cancion.id.desc()
        ).limit(needed).all()

        for c in global_top:
            canciones_ids.append(c.id)
            seen.add(c.id)

    # Recuperar objetos y mantener el orden estricto de puntuación
    canciones_dict_map = {c.id: c.to_dict() for c in Cancion.query.filter(Cancion.id.in_(canciones_ids)).all()}
    resultado = [canciones_dict_map[cid] for cid in canciones_ids if cid in canciones_dict_map]
    return balance_mix(resultado, gap=2)[:limit]



def get_recent_mix(user_id=None, limit=30):
    """
    Retorna la mezcla de adiciones recientes o canciones escuchadas recientemente.
    """
    canciones_ids = []
    seen = set()

    if user_id:
        try:
            # Canciones reproducidas recientemente por el usuario
            recent_plays = db.session.query(
                HistorialEscucha.cancion_id,
                func.max(HistorialEscucha.reproducido_en).label('last_time')
            ).filter(
                HistorialEscucha.usuario_id == user_id
            ).group_by(
                HistorialEscucha.cancion_id
            ).order_by(
                desc('last_time')
            ).limit(limit).all()

            for cid, _ in recent_plays:
                canciones_ids.append(cid)
                seen.add(cid)
        except Exception as e:
            print(f"[DuckSound Recipes] Error consultando historial reciente: {e}")

    # Complementar con canciones recientemente agregadas a la biblioteca
    if len(canciones_ids) < limit:
        needed = limit - len(canciones_ids)
        query = Cancion.query
        if seen:
            query = query.filter(~Cancion.id.in_(seen))
        newest = query.order_by(
            Cancion.fecha_agregada.desc(),
            Cancion.id.desc()
        ).limit(needed).all()

        for c in newest:
            canciones_ids.append(c.id)
            seen.add(c.id)

    canciones_dict_map = {c.id: c.to_dict() for c in Cancion.query.filter(Cancion.id.in_(canciones_ids)).all()}
    resultado = [canciones_dict_map[cid] for cid in canciones_ids if cid in canciones_dict_map]
    return balance_mix(resultado, gap=2)[:limit]


def get_radio_mix(cancion_id, limit=30):
    """
    Genera una lista de reproducción inteligente estilo 'Radio de la canción'.
    Combina la canción semilla con canciones acústicamente similares y temas afines del catálogo.
    """
    from app.services.recommender import get_similar_songs

    seed = db.session.get(Cancion, cancion_id)
    if not seed:
        return []

    resultado = [seed.to_dict()]
    seen_ids = {seed.id}
    artist_counts = {seed.artista_id: 1} if seed.artista_id else {}

    # 1. Obtener canciones similares usando el motor híbrido (acústico + BPM + fuzzy género)
    try:
        similares = get_similar_songs(cancion_id, top_k=limit)
        for s in similares:
            sid = s.get('id')
            if sid and sid not in seen_ids:
                c = db.session.get(Cancion, sid)
                if c:
                    d = c.to_dict()
                    d['similarity'] = s.get('similarity')
                    resultado.append(d)
                    seen_ids.add(sid)
                    if c.artista_id:
                        artist_counts[c.artista_id] = artist_counts.get(c.artista_id, 0) + 1
    except Exception as e:
        print(f"[DuckSound Recipes] Error obteniendo similares en radio: {e}")

    # 2. Si se requieren más canciones, rellenar con temas del mismo artista (hasta un límite para evitar fatiga)
    if len(resultado) < limit and seed.artista_id:
        same_artist = Cancion.query.filter(
            Cancion.artista_id == seed.artista_id,
            ~Cancion.id.in_(seen_ids)
        ).order_by(Cancion.play_count.desc()).limit(5).all()

        for c in same_artist:
            if len(resultado) >= limit:
                break
            if artist_counts.get(c.artista_id, 0) < 4:
                resultado.append(c.to_dict())
                seen_ids.add(c.id)
                artist_counts[c.artista_id] = artist_counts.get(c.artista_id, 0) + 1

    # 3. Si aún faltan, complementar con canciones del mismo género
    if len(resultado) < limit and seed.genero:
        genero_base = seed.genero.split('/')[0].split(',')[0].strip()
        same_genre = Cancion.query.filter(
            Cancion.genero.ilike(f"%{genero_base}%"),
            ~Cancion.id.in_(seen_ids)
        ).order_by(Cancion.play_count.desc()).limit(limit - len(resultado)).all()

        for c in same_genre:
            if len(resultado) >= limit:
                break
            resultado.append(c.to_dict())
            seen_ids.add(c.id)

    # 4. Fallback final: canciones aleatorias populares
    if len(resultado) < limit:
        extras = Cancion.query.filter(
            ~Cancion.id.in_(seen_ids)
        ).order_by(Cancion.play_count.desc()).limit(limit - len(resultado)).all()
        for c in extras:
            resultado.append(c.to_dict())

    # Bloquear la semilla en la posición 0 y balancear el resto para evitar repeticiones consecutivas
    if len(resultado) > 1:
        return ([resultado[0]] + balance_mix(resultado[1:], gap=2))[:limit]
    return resultado[:limit]


def get_artist_radio(artista_id, limit=30):
    """
    Genera una estación de radio inteligente centrada en un artista y artistas afines.
    """
    artista = db.session.get(Artista, artista_id)
    if not artista:
        return []

    canciones_artista = Cancion.query.filter_by(
        artista_id=artista_id
    ).order_by(Cancion.play_count.desc()).limit(10).all()

    resultado = [c.to_dict() for c in canciones_artista]
    seen_ids = {c.id for c in canciones_artista}

    # Buscar géneros del artista para emparejar artistas relacionados
    generos = set()
    for c in canciones_artista:
        if c.genero:
            for g in c.genero.replace('/', ',').split(','):
                g_strip = g.strip()
                if g_strip:
                    generos.add(g_strip)

    # Encontrar canciones de artistas que comparten género
    if generos and len(resultado) < limit:
        for g in list(generos)[:3]:
            if len(resultado) >= limit:
                break
            related_tracks = Cancion.query.filter(
                Cancion.artista_id != artista_id,
                Cancion.genero.ilike(f"%{g}%"),
                ~Cancion.id.in_(seen_ids)
            ).order_by(Cancion.play_count.desc()).limit(6).all()

            for c in related_tracks:
                if len(resultado) >= limit:
                    break
                resultado.append(c.to_dict())
                seen_ids.add(c.id)

    # Si faltan canciones, completar con pistas de mayor reproducción
    if len(resultado) < limit:
        extras = Cancion.query.filter(~Cancion.id.in_(seen_ids)).order_by(
            Cancion.play_count.desc()
        ).limit(limit - len(resultado)).all()
        for c in extras:
            resultado.append(c.to_dict())

    # Bloquear el primer tema del artista y balancear el resto con un gap moderado (gap=1)
    if len(resultado) > 1:
        return ([resultado[0]] + balance_mix(resultado[1:], gap=1))[:limit]
    return resultado[:limit]


def get_smart_mixes_overview(user_id=None):
    """
    Retorna un resumen de las recetas y mezclas automáticas disponibles en el sistema.
    Ideal para alimentar componentes del frontend y tarjetas de descubrimiento.
    """
    today = datetime.utcnow().date()
    mixes = []

    # 1. Top Streamed
    top_tracks = get_top_mix(user_id=user_id, limit=4)
    top_cover = top_tracks[0].get('ruta_imagen') if top_tracks else None
    mixes.append({
        'id': 'top-streamed',
        'title': 'Tus Más Escuchadas',
        'subtitle': 'Tus temas favoritos en rotación',
        'type': 'recipe',
        'endpoint': '/api/mixes/top',
        'cover': top_cover,
        'count': len(top_tracks)
    })

    # 2. Recently Added
    recent_tracks = get_recent_mix(user_id=user_id, limit=4)
    recent_cover = recent_tracks[0].get('ruta_imagen') if recent_tracks else None
    mixes.append({
        'id': 'recently-added',
        'title': 'Recién Añadidas',
        'subtitle': 'Últimas novedades en la colección',
        'type': 'recipe',
        'endpoint': '/api/mixes/recent',
        'cover': recent_cover,
        'count': len(recent_tracks)
    })

    # 3. Daily Mixes (si existen generados para el usuario)
    if user_id:
        daily_mixes = DailyMix.query.filter_by(usuario_id=user_id, fecha=today).all()
        for dm in daily_mixes:
            first_song = dm.canciones[0] if dm.canciones else None
            cover = getattr(first_song, 'ruta_imagen_album', None) if first_song else None
            mixes.append({
                'id': f'daily-mix-{dm.id}',
                'title': dm.nombre,
                'subtitle': f'Mix diario personalizado • {today.strftime("%d/%m")}',
                'type': 'daily_mix',
                'mix_id': dm.id,
                'cover': cover,
                'count': len(dm.canciones)
            })

    return mixes
