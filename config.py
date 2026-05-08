import os
from pathlib import Path

# Configuración base de la aplicación
class Config:
    # Versión de la aplicación
    APP_VERSION = '1.0.1'

    # Secret key para sesiones y CSRF
    _secret = os.environ.get('SECRET_KEY')
    if not _secret:
        _secret_file = Path(__file__).resolve().parent / '.secret_key'
        try:
            with open(_secret_file, 'r') as f:
                _secret = f.read().strip()
        except FileNotFoundError:
            import secrets
            _secret = secrets.token_hex(32)
            try:
                with open(_secret_file, 'w') as f:
                    f.write(_secret)
            except Exception:
                pass
    SECRET_KEY = _secret
    
    # Configuración de la base de datos SQLite
    BASE_DIR = Path(__file__).resolve().parent
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Opciones de motor para SQLite: timeout de espera + pool health check
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 30,              # Esperar hasta 30s si la DB está bloqueada
            'check_same_thread': False   # Requerido para servidores multi-thread (Gunicorn/Waitress)
        },
        'pool_pre_ping': True,          # Verificar que la conexión esté viva antes de usarla
    }
    
    # Rutas de medios - Detectar si estamos en Docker o localmente
    if Path('/music').exists():
        # En Docker: música montada como volumen del usuario (solo lectura)
        AUDIO_FOLDER = Path('/music')
        MEDIA_FOLDER = Path('/music')

        # Directorio /data es un volumen persistente gestionado por la app
        DATA_DIR = Path('/data')
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Base de datos
        DB_DIR = DATA_DIR / 'db'
        DB_DIR.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_DIR}/ducksound.db'

        # Lyrics (la app los descarga/gestiona)
        LYRICS_FOLDER = DATA_DIR / 'lyrics'
        LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)

        # Álbum art
        ALBUM_ART_FOLDER = DATA_DIR / 'album_art'
        ALBUM_ART_FOLDER.mkdir(exist_ok=True)
    else:
        # Localmente: usar carpetas en Downloads
        MEDIA_FOLDER = Path(r'C:\Users\marcu\Downloads\Musica')
        AUDIO_FOLDER = MEDIA_FOLDER / 'music'
        LYRICS_FOLDER = MEDIA_FOLDER / 'lyrics'
        # DB local junto a la app
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR}/ducksound.db'
        # Álbum art junto a la DB
        ALBUM_ART_FOLDER = BASE_DIR / 'album_art'
        ALBUM_ART_FOLDER.mkdir(exist_ok=True)
    
    # Configuración de subida de archivos
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB máximo
    ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'flac', 'wav', 'm4a'}
    ALLOWED_LYRICS_EXTENSIONS = {'lrc'}
