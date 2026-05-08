from app import app
from models import db, Artista, Album
from metadata_normalizer import normalizar_artista, normalizar_album, obtener_album_base_fuzz


with app.app_context():
    print("Unificando artistas...")
    artistas = Artista.query.order_by(Artista.id).all()
    for artista in artistas:
        nombre_norm = normalizar_artista(artista.nombre)
        artista_existente = Artista.query.filter(Artista.nombre == nombre_norm, Artista.id < artista.id).first()
        if artista_existente:
            print(f"Combinando '{artista.nombre}' con '{artista_existente.nombre}'...")
            for cancion in list(artista.canciones):
                cancion.artista_id = artista_existente.id
            for album in list(artista.albums):
                album.artista_id = artista_existente.id
            db.session.delete(artista)
        elif nombre_norm != artista.nombre:
            print(f"Renombrando '{artista.nombre}' a '{nombre_norm}'...")
            artista.nombre = nombre_norm

    db.session.commit()

    print("Unificando albumes...")
    artistas = Artista.query.order_by(Artista.id).all()
    for artista in artistas:
        albumes_artista = Album.query.filter_by(artista_id=artista.id).order_by(Album.id).all()
        albumes_base = []

        for album in albumes_artista:
            titulo_norm = normalizar_album(album.titulo)
            if titulo_norm and titulo_norm != album.titulo:
                print(f"Renombrando album '{album.titulo}' a '{titulo_norm}'...")
                album.titulo = titulo_norm

            album_existente = obtener_album_base_fuzz(titulo_norm or album.titulo, albumes_base)
            if album_existente and album_existente.id != album.id:
                print(f"Combinando album '{album.titulo}' con '{album_existente.titulo}'...")
                for cancion in list(album.canciones):
                    cancion.album_id = album_existente.id
                if not album_existente.portada_url and album.portada_url:
                    album_existente.portada_url = album.portada_url
                if not album_existente.anio and album.anio:
                    album_existente.anio = album.anio
                db.session.delete(album)
            else:
                albumes_base.append(album)

    db.session.commit()
    print("Listo!")
