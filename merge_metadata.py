from app import app
from models import db, Artista, Album, Cancion
from metadata_normalizer import normalizar_artista, limpiar_nombre

with app.app_context():
    print("Unificando artistas...")
    artistas = Artista.query.all()
    for artista in artistas:
        nombre_norm = normalizar_artista(artista.nombre)
        if nombre_norm != artista.nombre:
            # Buscar si ya existe el artista normalizado
            artista_existente = Artista.query.filter_by(nombre=nombre_norm).first()
            if artista_existente and artista_existente.id != artista.id:
                print(f"Combinando '{artista.nombre}' con '{artista_existente.nombre}'...")
                # Mover canciones
                for cancion in artista.canciones:
                    cancion.artista_id = artista_existente.id
                # Mover álbumes
                for album in artista.albums:
                    album.artista_id = artista_existente.id
                db.session.delete(artista)
            else:
                print(f"Renombrando '{artista.nombre}' a '{nombre_norm}'...")
                artista.nombre = nombre_norm
    
    db.session.commit()

    print("Unificando álbumes...")
    albumes = Album.query.all()
    for album in albumes:
        titulo_norm = limpiar_nombre(album.titulo)
        if titulo_norm != album.titulo:
            album_existente = Album.query.filter_by(titulo=titulo_norm, artista_id=album.artista_id).first()
            if album_existente and album_existente.id != album.id:
                print(f"Combinando álbum '{album.titulo}' con '{album_existente.titulo}'...")
                for cancion in album.canciones:
                    cancion.album_id = album_existente.id
                db.session.delete(album)
            else:
                print(f"Renombrando álbum '{album.titulo}' a '{titulo_norm}'...")
                album.titulo = titulo_norm

    db.session.commit()
    print("¡Listo!")