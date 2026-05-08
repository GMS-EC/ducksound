from app import app
from models import db, Artista, Album, Cancion
from metadata_normalizer import normalizar_artista, limpiar_nombre

with app.app_context():
    print("Unificando artistas...")
    artistas = Artista.query.all()
    for artista in artistas:
        nombre_norm = normalizar_artista(artista.nombre)
        artista_existente = Artista.query.filter(Artista.nombre == nombre_norm, Artista.id < artista.id).first()
        if artista_existente:
            print(f"Combinando '{artista.nombre}' con '{artista_existente.nombre}'...")
            for cancion in artista.canciones:
                cancion.artista_id = artista_existente.id
            for album in artista.albums:
                album.artista_id = artista_existente.id
            db.session.delete(artista)
        elif nombre_norm != artista.nombre:
            print(f"Renombrando '{artista.nombre}' a '{nombre_norm}'...")
            artista.nombre = nombre_norm
    
    db.session.commit()

    print("Unificando álbumes...")
    albumes = Album.query.all()
    for album in albumes:
        titulo_norm = limpiar_nombre(album.titulo)
        album_existente = Album.query.filter(Album.titulo == titulo_norm, Album.artista_id == album.artista_id, Album.id < album.id).first()
        if album_existente:
            print(f"Combinando álbum '{album.titulo}' con '{album_existente.titulo}'...")
            for cancion in album.canciones:
                cancion.album_id = album_existente.id
            db.session.delete(album)
        elif titulo_norm != album.titulo:
            print(f"Renombrando álbum '{album.titulo}' a '{titulo_norm}'...")
            album.titulo = titulo_norm

    db.session.commit()
    print("¡Listo!")