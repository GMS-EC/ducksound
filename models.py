from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


class Usuario(db.Model):
    """Modelo de Usuario para autenticación"""
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(80), unique=True, nullable=False, index=True)
    nombre_publico = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' or 'user'
    crossfade_enabled = db.Column(db.Boolean, default=True)
    activity_tracking = db.Column(db.Boolean, default=True)
    idioma_preferido = db.Column(db.String(10), nullable=False, default='es')

    def set_password(self, password):
        """Hashea la contraseña antes de guardarla"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica si la contraseña coincide con el hash almacenado"""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def display_name(self):
        return self.nombre_publico or self.nombre_usuario

    def __repr__(self):
        return f'<Usuario {self.nombre_usuario}>'


# Asociación many-to-many entre playlists y canciones
playlist_canciones = db.Table(
    'playlist_canciones',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('cancion_id', db.Integer, db.ForeignKey('canciones.id'), primary_key=True),
    db.Column('orden', db.Integer, nullable=True)
)


class Artista(db.Model):
    __tablename__ = 'artistas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True, index=True)
    foto_url = db.Column(db.String(500), nullable=True)
    biografia = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    albums = db.relationship('Album', back_populates='artista', cascade='all, delete-orphan')
    canciones = db.relationship('Cancion', back_populates='artista_obj', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Artista {self.nombre}>'


class Album(db.Model):
    __tablename__ = 'albums'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(250), nullable=False, index=True)
    anio = db.Column(db.Integer, nullable=True)
    portada_url = db.Column(db.String(500), nullable=True)
    artista_id = db.Column(db.Integer, db.ForeignKey('artistas.id'), nullable=False)

    artista = db.relationship('Artista', back_populates='albums')
    canciones = db.relationship('Cancion', back_populates='album_obj', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Album {self.titulo} ({self.anio})>'


class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    portada_url = db.Column(db.String(500), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    canciones = db.relationship('Cancion', secondary=playlist_canciones, back_populates='playlists')

    def __repr__(self):
        return f'<Playlist {self.nombre}>'


class Favorito(db.Model):
    """Canciones favoritas por usuario"""
    __tablename__ = 'favoritos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    cancion_id = db.Column(db.Integer, db.ForeignKey('canciones.id'), nullable=False)
    fecha_agregado = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', backref=db.backref('favoritos', lazy='dynamic'))
    cancion = db.relationship('Cancion', backref=db.backref('favoritos', lazy='dynamic'))

    __table_args__ = (db.UniqueConstraint('usuario_id', 'cancion_id', name='uq_usuario_cancion'),)

    def __repr__(self):
        return f'<Favorito usuario={self.usuario_id} cancion={self.cancion_id}>'




# Tabla auxiliar para colecciones (many-to-many canciones)
coleccion_canciones = db.Table(
    'coleccion_canciones',
    db.Column('coleccion_id', db.Integer, db.ForeignKey('colecciones.id'), primary_key=True),
    db.Column('cancion_id', db.Integer, db.ForeignKey('canciones.id'), primary_key=True)
)


class Coleccion(db.Model):
    """Colecciones de álbumes/artistas creadas por usuarios"""
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
    """Registro de reproducciones de canciones por usuario"""
    __tablename__ = 'historial_escucha'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    cancion_id = db.Column(db.Integer, db.ForeignKey('canciones.id'), nullable=False, index=True)
    reproducido_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    skip = db.Column(db.Boolean, default=False)  # True si saltó antes de 30s

    usuario = db.relationship('Usuario', backref=db.backref('historial', lazy='dynamic'))
    cancion = db.relationship('Cancion', backref=db.backref('historial', lazy='dynamic'))

    def __repr__(self):
        return f'<Historial u={self.usuario_id} c={self.cancion_id} t={self.reproducido_en}>'


class DailyMix(db.Model):
    """Mix diario generado para un usuario"""
    __tablename__ = 'daily_mixes'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    nombre = db.Column(db.String(100), nullable=False)
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
    """Modelo de Canción para la biblioteca de música"""
    __tablename__ = 'canciones'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False, index=True)
    artista_id = db.Column(db.Integer, db.ForeignKey('artistas.id'), nullable=True, index=True)
    album_id = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=True, index=True)
    duracion = db.Column(db.Integer, nullable=True)  # en segundos
    ruta_archivo_audio = db.Column(db.String(500), nullable=False)
    ruta_archivo_lrc = db.Column(db.String(500), nullable=True)
    ruta_imagen_album = db.Column(db.String(500), nullable=True)  # Ruta a la imagen del álbum
    numero_pista = db.Column(db.Integer, nullable=True)  # Nuevo campo: TRCK
    fecha_agregada = db.Column(db.DateTime, default=datetime.utcnow)

    # Audio quality analysis
    sample_rate = db.Column(db.Integer, nullable=True)
    bit_depth = db.Column(db.Integer, nullable=True)
    channels = db.Column(db.Integer, nullable=True)
    nyquist_freq = db.Column(db.Float, nullable=True)
    dynamic_range = db.Column(db.Float, nullable=True)
    peak_level = db.Column(db.Float, nullable=True)
    rms_level = db.Column(db.Float, nullable=True)
    total_samples = db.Column(db.BigInteger, nullable=True)
    bit_rate = db.Column(db.Integer, nullable=True)

    # Género musical
    genero = db.Column(db.String(100), nullable=True)

    # Relaciones
    artista_obj = db.relationship('Artista', back_populates='canciones')
    album_obj = db.relationship('Album', back_populates='canciones')
    playlists = db.relationship('Playlist', secondary=playlist_canciones, back_populates='canciones')

    def __repr__(self):
        # Usar format para evitar problemas con f-strings y nesting de comillas
        return '<Cancion {} - {}>'.format(self.titulo, self.artista_obj.nombre if self.artista_obj else '?')

    def to_dict(self, include_vector=False):
        """Convierte el modelo a diccionario para JSON. Por defecto no incluye vector_acustico."""
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
