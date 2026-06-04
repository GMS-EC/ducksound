from app import app, db
from models import Artista, Cancion
from metadata_normalizer import normalizar_artista
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('db_cleaner')

def clean_brackets():
    """Limpia nombres de artistas que quedaron guardados como ['Artista']."""
    logger.info("Limpiando corchetes en nombres de artistas...")
    count = 0
    artistas = Artista.query.filter(
        (Artista.nombre.like('[\'%') & Artista.nombre.like('%\']')) |
        (Artista.nombre_normalizado.like('[\'%') & Artista.nombre_normalizado.like('%\']'))
    ).all()
    
    for a in artistas:
        old_name = a.nombre
        old_norm = a.nombre_normalizado
        
        def fix(text):
            if text and text.startswith('[') and text.endswith(']'):
                # Quitar [ ] y ' ' o " "
                cleaned = text[1:-1].strip()
                if (cleaned.startswith("'") and cleaned.endswith("'")) or (cleaned.startswith('"') and cleaned.endswith('"')):
                    cleaned = cleaned[1:-1]
                return cleaned
            return text
        
        a.nombre = fix(a.nombre)
        a.nombre_normalizado = fix(a.nombre_normalizado)
        count += 1
    
    db.session.commit()
    logger.info(f"Se limpiaron {count} artistas con corchetes.")
    return count

def unify_ghost():
    """Unifica variaciones de Ghost (ej: Ghost B.C. -> Ghost)."""
    logger.info("Unificando variantes de Ghost...")
    # 1. Encontrar el artista principal "Ghost"
    principal = Artista.query.filter(
        Artista.nombre_normalizado == 'Ghost'
    ).first()
    
    if not principal:
        # Si no existe exactamente "Ghost", buscar el primero que normalice a "Ghost"
        all_ghosts = Artista.query.all()
        for a in all_ghosts:
            if normalizar_artista(a.nombre) == 'Ghost':
                principal = a
                break
    
    if not principal:
        logger.info("No se encontró un artista principal para Ghost.")
        return 0
    
    principal_id = principal.id
    logger.info(f"Artista principal Ghost: {principal.nombre} (ID: {principal_id})")
    
    # 2. Buscar otros que normalicen a Ghost
    duplicados = []
    for a in Artista.query.filter(Artista.id != principal_id).all():
        if normalizar_artista(a.nombre) == 'Ghost':
            duplicados.append(a)
    
    if not duplicados:
        logger.info("No se encontraron duplicados de Ghost.")
        return 0
    
    count = 0
    for dup in duplicados:
        logger.info(f"Unificando {dup.nombre} (ID: {dup.id}) -> Ghost (ID: {principal_id})")
        # Mover canciones
        Cancion.query.filter_by(artista_id=dup.id).update({'artista_id': principal_id})
        # Eliminar artista duplicado
        db.session.delete(dup)
        count += 1
    
    db.session.commit()
    logger.info(f"Se unificaron {count} variantes de Ghost.")
    return count

if __name__ == '__main__':
    with app.app_context():
        try:
            c1 = clean_brackets()
            c2 = unify_ghost()
            print(f"Limpieza completada. Corchetes: {c1}, Ghost: {c2}")
        except Exception as e:
            db.session.rollback()
            print(f"Error durante la limpieza: {e}")
