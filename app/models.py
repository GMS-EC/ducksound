# -*- coding: utf-8 -*-
"""
Modelos de Datos - DuckSound
Define la estructura de base de datos usando SQLAlchemy.
Todos los modelos son compatibles con SQLite (desarrollo local) y PostgreSQL (producción).
"""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Instancia central de SQLAlchemy. Se vinculará a la aplicación Flask en la fábrica (create_app).
db = SQLAlchemy()


class Usuario(db.Model):
    """
    Modelo de Usuario para autenticación y control de accesos en DuckSound.
    Guarda las credenciales hasheadas y las preferencias del usuario (crossfade, tracking, idioma).
    """
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(80), unique=True, nullable=False, index=True)
    nombre_publico = db.Column(db.String(80), nullable=True) # Apodo visible en el reproductor
    password_hash = db.Column(db.String(255), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' o 'user'
    crossfade_enabled = db.Column(db.Boolean, default=True) # Habilita la transición suave entre pistas
    activity_tracking = db.Column(db.Boolean, default=True) # Habilita el registro de historial de escucha
    idioma_preferido = db.Column(db.String(10), nullable=False, default='es')
    audio_quality = db.Column(db.String(20), nullable=False, default='lossless') # Preferencia de calidad: 'lossless' (original), 'high' (320k), 'standard' (192k), 'saver' (96k)

    def set_password(self, password):
        """Genera y guarda un hash seguro de la contraseña usando PBKDF2/SHA256."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Compara la contraseña en texto plano contra el hash almacenado."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Indica si el usuario tiene privilegios de administrador."""
        return self.role == 'admin'

    def display_name(self):
        """Retorna el apodo público si existe; de lo contrario, el nombre de usuario base."""
        return self.nombre_publico or self.nombre_usuario

    def __repr__(self):
        return f'<Usuario {self.nombre_usuario}>'


# Tabla de asociación (muchos a muchos) entre Playlists y Canciones.
# Permite guardar la lista de reproducción y su orden personalizado de tracks.
playlist_canciones = db.Table(
    'playlist_canciones',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('cancion_id', db.Integer, db.ForeignKey('canciones.id'), primary_key=True),
    db.Column('orden', db.Integer, nullable=True)
)


class Artista(db.Model):
    """
    Modelo de Artista.
    Representa a los cantantes o bandas de la biblioteca musical.
    """
    __tablename__ = 'artistas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    nombre_normalizado = db.Column(db.String(200), nullable=True, index=True) # Nombre limpio sin caracteres especiales para búsquedas
    musicbrainz_id = db.Column(db.String(36), nullable=True, unique=True) # ID externo para metadatos
    foto_url = db.Column(db.String(500), nullable=True) # URL o ruta local a la foto del artista
    biografia = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones directas: cascada de borrado elimina álbumes y canciones asociadas si el artista se elimina
    albums = db.relationship('Album', back_populates='artista', cascade='all, delete-orphan')
    canciones = db.relationship('Cancion', back_populates='artista_obj', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Artista {self.nombre}>'


class Album(db.Model):
    """
    Modelo de Álbum.
    Colección de canciones del mismo artista.
    """
    __tablename__ = 'albums'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(250), nullable=False, index=True)
    anio = db.Column(db.Integer, nullable=True)
    portada_url = db.Column(db.String(500), nullable=True) # Ruta de la portada descargada localmente
    artista_id = db.Column(db.Integer, db.ForeignKey('artistas.id'), nullable=False)
    musicbrainz_id = db.Column(db.String(36), nullable=True, unique=True)

    # Relaciones
    artista = db.relationship('Artista', back_populates='albums')
    canciones = db.relationship('Cancion', back_populates='album_obj', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Album {self.titulo} ({self.anio})>'


class Playlist(db.Model):
    """
    Modelo de Playlist tradicional.
    Listas de canciones personalizadas creadas por el usuario administrador u otros fines.
    """
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    portada_url = db.Column(db.String(500), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación muchos a muchos usando la tabla intermedia playlist_canciones
    canciones = db.relationship('Cancion', secondary=playlist_canciones, back_populates='playlists')

    def __repr__(self):
        return f'<Playlist {self.nombre}>'


class Favorito(db.Model):
    """
    Modelo de Canciones Favoritas (Me Gusta).
    Vincula a un usuario con sus canciones preferidas.
    """
    __tablename__ = 'favoritos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    cancion_id = db.Column(db.Integer, db.ForeignKey('canciones.id'), nullable=False)
    fecha_agregado = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones y búsquedas diferidas (lazy='dynamic') para rendimiento
    usuario = db.relationship('Usuario', backref=db.backref('favoritos', lazy='dynamic'))
    cancion = db.relationship('Cancion', backref=db.backref('favoritos', lazy='dynamic'))

    # Restricción de unicidad: Un usuario no puede agregar dos veces la misma canción a favoritos
    __table_args__ = (db.UniqueConstraint('usuario_id', 'cancion_id', name='uq_usuario_cancion'),)

    def __repr__(self):
        return f'<Favorito usuario={self.usuario_id} cancion={self.cancion_id}>'


# Tabla auxiliar de asociación muchos a muchos entre Colecciones y Canciones
coleccion_canciones = db.Table(
    'coleccion_canciones',
    db.Column('coleccion_id', db.Integer, db.ForeignKey('colecciones.id'), primary_key=True),
    db.Column('cancion_id', db.Integer, db.ForeignKey('canciones.id'), primary_key=True)
)


class Coleccion(db.Model):
    """
    Modelo de Colección de canciones.
    Permite agrupar pistas de forma modular por usuarios.
    """
    __tablename__ = 'colecciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    portada_url = db.Column(db.String(500), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('colecciones', lazy='dynamic'))
    canciones = db.relationship('Cancion', secondary=coleccion_canciones, backref='colecciones')

    def __repr__(self):
        return f'<Coleccion {self.nombre}>'


class HistorialEscucha(db.Model):
    """
    Historial de reproducción detallado.
    Sirve como fuente primaria para alimentar el motor de recomendación de mixes diarios.
    """
    __tablename__ = 'historial_escucha'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    cancion_id = db.Column(db.Integer, db.ForeignKey('canciones.id'), nullable=False, index=True)
    reproducido_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    skip = db.Column(db.Boolean, default=False)  # True si el usuario saltó la canción antes de los 30s

    usuario = db.relationship('Usuario', backref=db.backref('historial', lazy='dynamic'))
    cancion = db.relationship('Cancion', backref=db.backref('historial', lazy='dynamic'))

    def __repr__(self):
        return f'<Historial u={self.usuario_id} c={self.cancion_id} t={self.reproducido_en}>'


class DailyMix(db.Model):
    """
    Mezcla diaria de música recomendada por DuckSound.
    Contiene un pool curado de 20 canciones mezcladas de forma proporcional y adaptada al momento.
    """
    __tablename__ = 'daily_mixes'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    nombre = db.Column(db.String(100), nullable=False) # Ej: Morning Vibes, Afternoon Chill, Night Beats
    fecha = db.Column(db.Date, default=datetime.utcnow().date, index=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('daily_mixes', lazy='dynamic'))
    canciones = db.relationship('Cancion', secondary=db.Table(
        'daily_mix_canciones',
        db.Column('mix_id', db.Integer, db.ForeignKey('daily_mixes.id'), primary_key=True),
        db.Column('cancion_id', db.Integer, db.ForeignKey('canciones.id'), primary_key=True),
        db.Column('orden', db.Integer, nullable=True)
    ), lazy='dynamic')

    def __repr__(self):
        return f'<DailyMix {self.nombre} {self.fecha}>'


class Cancion(db.Model):
    """
    Modelo de Canción.
    Es el núcleo de DuckSound. Almacena metadatos y especificaciones de calidad de audio
    de cada archivo local indexado en la carpeta de música.
    """
    __tablename__ = 'canciones'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False, index=True)
    artista_id = db.Column(db.Integer, db.ForeignKey('artistas.id'), nullable=True, index=True)
    album_id = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=True, index=True)
    duracion = db.Column(db.Integer, nullable=True)  # Duración del audio en segundos
    ruta_archivo_audio = db.Column(db.String(500), nullable=False) # Ruta física absoluta
    ruta_archivo_lrc = db.Column(db.String(500), nullable=True)   # Ruta física absoluta al archivo de letras sincronizadas
    ruta_imagen_album = db.Column(db.String(500), nullable=True)  # Ruta a la carátula o artwork
    numero_pista = db.Column(db.Integer, nullable=True)  # Posición del track en el álbum (TRCK tag)
    fecha_agregada = db.Column(db.DateTime, default=datetime.utcnow)

    # Métricas y Análisis de Calidad del Audio (extraído por audio_analyzer.py durante el escaneo)
    sample_rate = db.Column(db.Integer, nullable=True)
    bit_depth = db.Column(db.Integer, nullable=True)
    channels = db.Column(db.Integer, nullable=True)
    nyquist_freq = db.Column(db.Float, nullable=True)
    dynamic_range = db.Column(db.Float, nullable=True) # Rango dinámico promedio (en decibelios)
    peak_level = db.Column(db.Float, nullable=True)    # Nivel pico de amplitud
    rms_level = db.Column(db.Float, nullable=True)     # Sonoridad/Volumen promedio RMS
    bpm = db.Column(db.Float, nullable=True)           # Beats por minuto (tempo)
    total_samples = db.Column(db.BigInteger, nullable=True)
    bit_rate = db.Column(db.Integer, nullable=True)

    # Género musical extraído de etiquetas ID3/Vorbis
    genero = db.Column(db.String(100), nullable=True)
    
    # Número de disco en álbumes dobles o boxsets
    numero_disco = db.Column(db.Integer, nullable=True)

    # Relaciones directas con Artista y Álbum
    artista_obj = db.relationship('Artista', back_populates='canciones')
    album_obj = db.relationship('Album', back_populates='canciones')
    playlists = db.relationship('Playlist', secondary=playlist_canciones, back_populates='canciones')

    def __repr__(self):
        return '<Cancion {} - {}>'.format(self.titulo, self.artista_obj.nombre if self.artista_obj else '?')

    def to_dict(self, include_vector=False):
        """Convierte el modelo de canción a un diccionario nativo de Python para serialización JSON."""
        artista = self.artista_obj.nombre if self.artista_obj else None
        album = self.album_obj.titulo if self.album_obj else None
        data = {
            'id': self.id,
            'titulo': self.titulo,
            'artista': artista,
            'album': album,
            'duracion': self.duracion,
            'ruta_audio': self.ruta_archivo_audio,
            'ruta_lrc': self.ruta_archivo_lrc,
            'ruta_imagen': self.ruta_imagen_album,
            'genero': self.genero,
            'sample_rate': self.sample_rate,
            'bit_depth': self.bit_depth,
            'channels': self.channels,
            'nyquist_freq': self.nyquist_freq,
            'dynamic_range': self.dynamic_range,
            'peak_level': self.peak_level,
            'rms_level': self.rms_level,
            'total_samples': self.total_samples,
            'bit_rate': self.bit_rate
        }
        return data
