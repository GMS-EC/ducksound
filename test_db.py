from app import app
from models import Album, Cancion, Artista

with app.app_context():
    print(f"Total artists: {Artista.query.count()}")
    print(f"Total albums: {Album.query.count()}")
    print(f"Total songs: {Cancion.query.count()}")
