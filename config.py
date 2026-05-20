import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Configuración base de la aplicación
class Config:
    APP_VERSION = '1.0.0'
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

    # Secret key para sesiones y CSRF

    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        _secret_file = Path(__file__).resolve().parent / '.secret_key'
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

    # ─── BASE DE DATOS (PostgreSQL únicamente) ────────────────────
    _db_url = os.environ.get('DATABASE_URL')
    if not _db_url:
        _host = os.environ.get('DB_HOST', 'postgres')
        _port = os.environ.get('DB_PORT', '5432')
        _name = os.environ.get('DB_NAME', 'ducksound')
        _user = os.environ.get('DB_USER', 'ducksound')
        _pass = os.environ.get('DB_PASSWORD', 'ducksound')
        _db_url = f'postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}'

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
        'pool_pre_ping': True,
    }

    # ─── RUTAS ────────────────────────────────────────────────────
    if Path('/music').exists():
        AUDIO_FOLDER = Path('/music')
        DATA_DIR = Path('/data')
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LYRICS_FOLDER = DATA_DIR / 'lyrics'
        LYRICS_FOLDER.mkdir(parents=True, exist_ok=True)
        ALBUM_ART_FOLDER = DATA_DIR / 'album_art'
        ALBUM_ART_FOLDER.mkdir(exist_ok=True)
        TRANSCODE_CACHE_FOLDER = DATA_DIR / 'transcode_cache'
        TRANSCODE_CACHE_FOLDER.mkdir(parents=True, exist_ok=True)
    else:
        MEDIA_FOLDER = Path(r'C:\Users\marcu\Downloads\Musica')
        AUDIO_FOLDER = MEDIA_FOLDER / 'music'
        LYRICS_FOLDER = MEDIA_FOLDER / 'lyrics'
        ALBUM_ART_FOLDER = Path(__file__).resolve().parent / 'album_art'
        ALBUM_ART_FOLDER.mkdir(exist_ok=True)
        TRANSCODE_CACHE_FOLDER = Path(__file__).resolve().parent / 'transcode_cache'
        TRANSCODE_CACHE_FOLDER.mkdir(parents=True, exist_ok=True)
    
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'flac', 'wav', 'm4a'}
    ALLOWED_LYRICS_EXTENSIONS = {'lrc'}
