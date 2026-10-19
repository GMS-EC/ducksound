import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Configuración base de la aplicación DuckSound
class Config:
    APP_VERSION = '2.0.0'
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

    # Secret key para sesiones y CSRF
    SECRET_KEY = os.environ.get('SECRET_KEY')
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'ducksound')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ducksound')
    if not SECRET_KEY:
        _secret_file = BASE_DIR / '.secret_key'
        try:
            SECRET_KEY = _secret_file.read_text().strip()
        except FileNotFoundError:
            import secrets
            SECRET_KEY = secrets.token_hex(32)
            try:
                _secret_file.write_text(SECRET_KEY)
            except Exception:
                pass

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── RUTAS Y ALMACENAMIENTO PERSISTENTE ───────────────────────
    if Path('/data').exists() or Path('/music').exists():
        DATA_DIR = Path('/data')
    else:
        DATA_DIR = BASE_DIR / 'data'
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Detección inteligente de carpeta de música
    _music_env = os.environ.get('MUSIC_PATH')
    if Path('/music').exists():
        AUDIO_FOLDER = Path('/music')
    elif _music_env and Path(_music_env).exists():
        AUDIO_FOLDER = Path(_music_env)
    else:
        MEDIA_FOLDER = Path(r'C:\Users\marcu\Downloads\Musica')
        AUDIO_FOLDER = MEDIA_FOLDER / 'music' if (MEDIA_FOLDER / 'music').exists() else MEDIA_FOLDER

    LYRICS_FOLDER = DATA_DIR / 'lyrics'
    LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)
    ALBUM_ART_FOLDER = DATA_DIR / 'album_art'
    ALBUM_ART_FOLDER.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_FOLDER = DATA_DIR / 'thumbnails'
    THUMBNAILS_FOLDER.mkdir(parents=True, exist_ok=True)
    TRANSCODE_CACHE_FOLDER = DATA_DIR / 'transcode_cache'
    TRANSCODE_CACHE_FOLDER.mkdir(parents=True, exist_ok=True)
    ORIGINAL_CACHE_FOLDER = DATA_DIR / 'original_cache'
    ORIGINAL_CACHE_FOLDER.mkdir(parents=True, exist_ok=True)

    # ─── BASE DE DATOS (Por defecto SQLite Ultra-Ligero) ─────────
    _db_url = os.environ.get('DATABASE_URL')
    if not _db_url:
        _host = os.environ.get('DB_HOST')
        if _host and _host.lower() not in ('none', 'localhost', 'sqlite', ''):
            _port = os.environ.get('DB_PORT', '5432')
            _name = os.environ.get('DB_NAME', 'ducksound')
            _user = os.environ.get('DB_USER', 'ducksound')
            _pass = os.environ.get('DB_PASSWORD', 'ducksound')
            _db_url = f'postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}'
        else:
            db_file = DATA_DIR / 'ducksound.db'
            _db_url = f'sqlite:///{db_file.as_posix()}'

    SQLALCHEMY_DATABASE_URI = _db_url
    if _db_url.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'check_same_thread': False},
            'pool_pre_ping': True,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
            'pool_pre_ping': True,
        }

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'flac', 'wav', 'm4a', 'ogg'}
    ALLOWED_LYRICS_EXTENSIONS = {'lrc'}

    # ─── CORS ───────────────────────────────────────────────────────
    CORS_ORIGINS = os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173'
    ).split(',')
