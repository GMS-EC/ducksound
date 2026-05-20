from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_compress import Compress
from config import Config
from models import db, Usuario, Artista, Cancion, Favorito, HistorialEscucha, DailyMix, Coleccion, Album
from datetime import datetime, date, timedelta
import os
import sys
import requests
from pathlib import Path

# Configurar UTF-8 para la salida en Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config.from_object(Config)

compress = Compress()
compress.init_app(app)

# Inicializar la base de datos
db.init_app(app)

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Crear las tablas si no existen
with app.app_context():
    db.create_all()
    
    # Crear usuario administrador si no existe ninguno
    if Usuario.query.count() == 0:

        admin_user = Usuario(
            nombre_usuario='ducksound',
            role='admin'
        )
        admin_user.set_password('ducksound')  # Contraseña por defecto
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario administrador creado: ducksound / admin123")

# ============================================
# SEGURIDAD GLOBAL (ESCUDO)
# ============================================

@app.before_request
def require_login():
    """
    Escudo global: intercepta TODAS las peticiones.
    Si el usuario no está logueado y la ruta no es pública, bloquea el acceso.
    Esto protege los archivos multimedia y APIs contra accesos directos por URL.
    """
    # Rutas que no requieren sesión
    allowed_endpoints = ['login', 'static', 'index']
    
    # Ignorar las peticiones CORS preflight
    if request.method == 'OPTIONS':
        return
        
    # Si la ruta existe pero el usuario no tiene sesión
    if request.endpoint not in allowed_endpoints and 'user_id' not in session:
        # Respuestas JSON para APIs
        if request.path.startswith('/api/') or request.path.startswith('/admin/'):
            return jsonify({'error': 'Acceso denegado: Inicia sesión primero'}), 401
            
        # Respuestas planas para multimedia (evita enviar el HTML del login a un reproductor)
        if request.path.startswith('/audio/') or request.path.startswith('/album-art/') or request.path.startswith('/lyrics/'):
            return "Acceso denegado", 401
            
        # Redirigir al login para cualquier otra página
        return redirect(url_for('login'))

import secrets

@app.before_request
def csrf_protect():
    """
    Protección CSRF solo para rutas regulares (form-based).
    Las rutas /api/* y /admin/* ya están protegidas por sesión o token Bearer.
    """
    if request.method not in ["GET", "HEAD", "OPTIONS", "TRACE"]:
        # Exentar API y admin (autenticación por sesión o token)
        if request.path.startswith('/api/') or request.path.startswith('/admin/'):
            return
        
        token = session.get('_csrf_token')
        if not token:
            return jsonify({'error': 'Falta el token CSRF en la sesión'}), 403
            
        req_token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        # Para peticiones fetch/JSON que envíen el token en el body:
        if not req_token and request.is_json:
            req_token = request.json.get('csrf_token')
            
        if not req_token or req_token != token:
            return jsonify({'error': 'Token CSRF inválido o faltante'}), 403

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# ============================================
# RUTAS DE AUTENTICACIÓN
# ============================================

@app.route('/')
def index():
    """Página de inicio - redirige a login o dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login de usuarios"""
    if request.method == 'POST':
        nombre_usuario = request.form.get('nombre_usuario')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
        
        if usuario and usuario.check_password(password):
            session['user_id'] = usuario.id
            session['nombre_usuario'] = usuario.nombre_usuario
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Credenciales inválidas')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cerrar sesión del usuario"""
    session.clear()
    return redirect(url_for('login'))


# ============================================
# RUTAS DEL DASHBOARD / BIBLIOTECA
# ============================================

@app.route('/dashboard')
def dashboard():
    """Dashboard principal con la biblioteca de canciones"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Ordenamos por título (artista queda disponible vía relación artista_obj)
    from sqlalchemy.orm import joinedload
    canciones = Cancion.query.options(
        joinedload(Cancion.artista_obj),
        joinedload(Cancion.album_obj)
    ).order_by(Cancion.titulo).all()
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    # Nuevas variables para la vista tipo Spotify
    daily_mixes = DailyMix.query.filter_by(usuario_id=session['user_id']).order_by(DailyMix.fecha.desc()).limit(6).all()
    if not daily_mixes:
        today = datetime.utcnow().date()
        mixes_hoy = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).first()
        if not mixes_hoy:
            _generate_daily_mixes(session['user_id'])
            daily_mixes = DailyMix.query.filter_by(usuario_id=session['user_id']).order_by(DailyMix.fecha.desc()).limit(6).all()
    albumes_recientes = Album.query.order_by(Album.id.desc()).limit(12).all()
    artistas_recientes = Artista.query.order_by(Artista.id.desc()).limit(12).all()
    canciones_recientes = Cancion.query.order_by(Cancion.fecha_agregada.desc()).limit(10).all()

    return render_template('dashboard.html', 
                           canciones=canciones, 
                           usuario=session.get('nombre_usuario'), 
                           is_admin=is_admin, 
                           es_favoritos=False,
                           daily_mixes=daily_mixes,
                           albumes_recientes=albumes_recientes,
                           artistas_recientes=artistas_recientes,
                           canciones_recientes=canciones_recientes)


# Ruta de favoritos (Me gusta)
@app.route('/favoritos')
def favoritos():
    """Página con canciones favoritas del usuario"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    favoritos = Favorito.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Favorito.fecha_agregado.desc()).all()
    canciones = []
    for fav in favoritos:
        c = Cancion.query.get(fav.cancion_id)
        if c:
            canciones.append(c)
    return render_template('dashboard.html', canciones=canciones,
                           usuario=session.get('nombre_usuario'),
                           is_admin=is_admin, es_favoritos=True)


# ============================================
# VISTA DE CARPETAS (EXPLORADOR DE ARCHIVOS)
# ============================================
@app.route('/folders')
def folders():
    """
    Genera una vista en árbol del sistema de archivos de música en el servidor.
    
    Permite navegar recursivamente por la carpeta configurada de audio, listando directorios
    y archivos con extensiones compatibles. Adicionalmente, cuenta en tiempo real cuántas
    canciones de cada directorio están actualmente indexadas en la base de datos mediante
    búsquedas de coincidencia de prefijos de ruta.
    
    Returns:
        Render de la plantilla 'folders.html' con la estructura del árbol de directorios.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False

    import os
    from pathlib import Path
    from config import Config

    audio_dir = Config.AUDIO_FOLDER
    tree = {}

    def build_tree(dirpath, prefix=''):
        """
        Función recursiva interna para escanear y estructurar directorios de audio.
        
        Args:
            dirpath (str): Ruta absoluta del directorio actual en el disco.
            prefix (str): Prefijo de ruta acumulado para visualización o indexación.
            
        Returns:
            list: Lista de diccionarios que representan carpetas y archivos en la ruta.
        """
        items = []
        try:
            # Iterar sobre las entradas del directorio ordenando primero carpetas y luego archivos (sin distinguir mayúsculas/minúsculas)
            for entry in sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.is_dir():
                    # Llamada recursiva para subcarpetas
                    children = build_tree(entry.path, prefix + entry.name + '/')
                    # Contar canciones en la base de datos cuya ruta de archivo comience con la ruta de este directorio
                    songs = Cancion.query.filter(Cancion.ruta_archivo_audio.like(entry.path.replace('\\', '/') + '%')).count()
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'folder',
                        'children': children,
                        'song_count': songs
                    })
                elif entry.name.lower().endswith(tuple(('.mp3','.flac','.wav','.m4a','.ogg'))):
                    # Archivo de audio válido encontrado
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'file'
                    })
        except PermissionError:
            # Ignorar de forma segura si no se tienen permisos de lectura en algún subdirectorio
            pass
        return items

    tree = build_tree(audio_dir)
    return render_template('folders.html', tree=tree, is_admin=is_admin)


# ============================================
# COLECCIONES (PLAYLISTS PERSONALIZADAS)
# ============================================
@app.route('/colecciones')
def colecciones_list():
    """
    Muestra el listado de colecciones (playlists) creadas por el usuario autenticado.
    
    Returns:
        Render de la plantilla 'colecciones.html' con la lista de colecciones del usuario.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    # Obtener todas las colecciones del usuario ordenadas de las más recientes a las más antiguas
    colecciones = Coleccion.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Coleccion.fecha_creacion.desc()).all()
    return render_template('colecciones.html', colecciones=colecciones, is_admin=is_admin)


@app.route('/coleccion/<int:coleccion_id>')
def coleccion_detail(coleccion_id):
    """
    Muestra los detalles y la lista de canciones contenidas en una colección específica.
    
    Args:
        coleccion_id (int): Identificador único de la colección.
        
    Returns:
        Render de la plantilla 'coleccion_detail.html' con los datos y canciones de la playlist.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    coleccion = Coleccion.query.get_or_404(coleccion_id)
    
    # Validar que la colección pertenezca al usuario que realiza la petición
    if coleccion.usuario_id != session['user_id']:
        abort(403)
        
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return render_template('coleccion_detail.html', coleccion=coleccion, is_admin=is_admin)


# ============================================
# DAILY MIXES (RECOMENDACIONES DIARIAS)
# ============================================
@app.route('/daily-mixes')
def daily_mixes():
    """
    Muestra las mezclas recomendadas automáticas para el día de hoy.
    Si no se han generado para el día actual, las crea al instante antes de renderizar la vista.
    
    Returns:
        Render de la plantilla 'daily_mixes.html' con los 3 mixes personalizados del día.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    today = datetime.utcnow().date()
    
    # Buscar si ya existen mixes generados hoy para este usuario
    mixes = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).all()
    if not mixes:
        # Generar dinámicamente los mixes del día mediante el motor de recomendación
        _generate_daily_mixes(session['user_id'])
        mixes = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).all()
    return render_template('daily_mixes.html', mixes=mixes, is_admin=is_admin)


@app.route('/daily-mix/<int:mix_id>')
def daily_mix_detail(mix_id):
    """
    Detalle de un Mix Diario específico y su cola ordenada de reproducción.
    
    Args:
        mix_id (int): ID de la mezcla diaria.
        
    Returns:
        Render de la plantilla 'daily_mix_detail.html' con el título del mix y sus pistas.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mix = DailyMix.query.get_or_404(mix_id)
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return render_template('daily_mix_detail.html', mix=mix, is_admin=is_admin)


def _generate_daily_mixes(usuario_id):
    """
    Motor de Recomendación de Mixes Diarios Personalizados.
    
    Genera 3 mezclas temáticas distintas basadas en los hábitos de escucha del usuario:
    1. 'Morning Vibes': Mezcla energética basada en popularidad general, géneros favoritos y temas acústicamente similares.
    2. 'Afternoon Chill': Orientado a favoritos directos del usuario combinados con descubrimiento de canciones similares y exploración.
    3. 'Night Beats': Enfocado en el historial de reproducción histórica del usuario, adición de temas nuevos y sugerencias de similitud.
    
    La mezcla utiliza un algoritmo proporcional de selección de pools (fuentes de datos) y excluye las canciones
    escuchadas en la última semana para mantener las listas frescas y dinámicas.
    
    Args:
        usuario_id (int): Identificador del usuario al cual generarle los mixes.
    """
    import random
    from models import Favorito, HistorialEscucha
    from datetime import date, timedelta
    from recommender import get_similar_songs

    today = datetime.utcnow().date()
    last_week = datetime.utcnow() - timedelta(days=7)

    # === 1. OBTENER FUENTES DE DATOS DE HÁBITOS DE ESCUCHA ===

    # Obtener el Top 50 de canciones más escuchadas del usuario (excluyendo canciones saltadas/skips)
    mas_escuchadas = db.session.query(
        Cancion.id, db.func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion.id).order_by(db.desc('plays')).limit(50).all()
    mas_escuchadas_ids = [c.id for c in mas_escuchadas]
    mas_escuchadas_plays = {c.id: c.plays for c in mas_escuchadas}

    # Obtener IDs de las canciones marcadas como "Me gusta" (Favoritos)
    fav_ids = [f.cancion_id for f in Favorito.query.filter_by(usuario_id=usuario_id).all()]

    # Canciones reproducidas en la última semana (usadas para exclusión temporal para evitar fatiga auditiva)
    recientes_ids = [h.cancion_id for h in HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.reproducido_en >= last_week
    ).distinct(HistorialEscucha.cancion_id).all()]

    # Determinar los 3 géneros más escuchados por el usuario
    top_generos = db.session.query(
        Cancion.genero, db.func.count(Cancion.id).label('cnt')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        Cancion.genero.isnot(None),
        Cancion.genero != ''
    ).group_by(Cancion.genero).order_by(db.desc('cnt')).limit(3).all()
    top_generos_list = [g[0] for g in top_generos if g[0]]

    # === 2. FUNCIONES AUXILIARES PARA CÁLCULO DE POOLS ===
    
    def _random_ids(limit, extra_filters=None):
        """
        Obtiene de manera óptima un muestreo aleatorio de IDs de canciones que cumplen ciertos criterios.
        """
        base = Cancion.query.with_entities(Cancion.id)
        if extra_filters:
            for f in extra_filters:
                base = base.filter(f)
        ids = [r[0] for r in base.all()]
        if not ids:
            return []
        return random.sample(ids, min(limit, len(ids)))

    def canciones_por_vibe(max_bpm=None, min_bpm=None, excluir_ids=None, limit=25):
        """
        Filtra y extrae canciones aleatorias que encajan en un perfil de tempo (BPM).
        """
        excluir = set(excluir_ids or [])
        filters = []
        if min_bpm is not None:
            filters.append(Cancion.bpm >= min_bpm)
        if max_bpm is not None:
            filters.append(Cancion.bpm <= max_bpm)
        candidatos_ids = _random_ids(limit * 3, filters)
        return [c for c in candidatos_ids if c not in excluir][:limit]

    def obtener_similares_a(song_ids, top_k=8):
        """
        Consulta canciones similares acústicamente en base al subconjunto de entrada (usando embeddings/perfil acústico).
        """
        similares_ids = set()
        for sid in song_ids[:5]:  # Usar un máximo de 5 canciones semilla para evitar lentitud
            try:
                similares = get_similar_songs(sid, top_k=top_k)
                for s in similares:
                    if s['id'] not in similares_ids:
                        similares_ids.add(s['id'])
            except Exception:
                continue
        return list(similares_ids)

    def mezclar_pool(pools, target=20):
        """
        Algoritmo de mezcla round-robin proporcional.
        Toma elementos de múltiples fuentes (pools) de forma rotatoria hasta llenar el target.
        Evita duplicados dentro de la mezcla final.
        """
        result = []
        seen = set()
        idx = [0] * len(pools)
        rounds = 0
        while len(result) < target and rounds < target * 2:
            for i, pool in enumerate(pools):
                if len(result) >= target:
                    break
                if idx[i] < len(pool):
                    cid = pool[idx[i]]
                    idx[i] += 1
                    if cid not in seen:
                        seen.add(cid)
                        result.append(cid)
            rounds += 1
        return result[:target]

    # === 3. ESQUEMAS DE CONFIGURACIÓN DE LOS 3 MIXES ===

    # Pool inicial: Combinación sin duplicados de las más reproducidas e identificadas como favoritas
    pool_populares = list(dict.fromkeys(mas_escuchadas_ids + fav_ids))

    mixes_data = [
        {
            'name': 'Morning Vibes',
            'desc': 'Energía para empezar el día',
            'bpm_range': (None, None),
            'pools': ['populares', 'similares', 'genero'],
        },
        {
            'name': 'Afternoon Chill',
            'desc': 'Relax para la tarde',
            'bpm_range': (None, None),
            'pools': ['favoritos', 'similares', 'explorar'],
        },
        {
            'name': 'Night Beats',
            'desc': 'Ritmo para la noche',
            'bpm_range': (None, None),
            'pools': ['historial', 'similares', 'nuevos'],
        },
    ]

    for mix_info in mixes_data:
        name = mix_info['name']
        pools = []
        pool_similares_ids = []
        excluir_ids_set = set(recientes_ids)

        # Pool 1: Canciones conocidas / familiares al usuario (excluyendo lo escuchado recientemente)
        populares_pool = pool_populares.copy()
        random.shuffle(populares_pool)
        pool_populares_filtrado = [c for c in populares_pool if c not in excluir_ids_set]
        if pool_populares_filtrado:
            pools.append(pool_populares_filtrado)
            excluir_ids_set.update(pool_populares_filtrado)

        # Pool 2: Canciones recomendadas similares acústicamente a sus favoritas
        if fav_ids:
            raw_similares = obtener_similares_a(fav_ids, top_k=6)
            pool_similares_ids = [s for s in raw_similares if s not in excluir_ids_set]
            if pool_similares_ids:
                pools.append(pool_similares_ids)
                excluir_ids_set.update(pool_similares_ids)

        # Pool 3: Descubrimiento de nuevos temas dentro de sus géneros de música favoritos
        if top_generos_list:
            genre = top_generos_list[(hash(name) % len(top_generos_list))]
            explorar_ids = _random_ids(30, [
                Cancion.genero.ilike(f'%{genre}%'),
                ~Cancion.id.in_(excluir_ids_set) if excluir_ids_set else db.true()
            ])
            if explorar_ids:
                pools.append(explorar_ids)
                excluir_ids_set.update(explorar_ids)

        # Fallback de seguridad en caso de que los pools estén vacíos (usuario muy nuevo)
        if not pools or sum(len(p) for p in pools) < 5:
            fallback_ids = _random_ids(30)
            fallback_ids = [c for c in fallback_ids if c not in excluir_ids_set]
            pools = [fallback_ids]

        # Mezclar las fuentes de recomendación usando el algoritmo round-robin
        mix_canciones_ids = mezclar_pool(pools, target=20)

        # Si se queda vacío a pesar de todo, rellenar de la biblioteca global de forma aleatoria
        if not mix_canciones_ids:
            mix_canciones_ids = _random_ids(20)

        # === 4. GUARDAR E INSERTAR MIX DIARIO ===
        # Limpiar registros obsoletos del mismo mix diario del usuario para el día actual
        DailyMix.query.filter_by(usuario_id=usuario_id, nombre=name, fecha=today).delete()

        mix = DailyMix(usuario_id=usuario_id, nombre=name, fecha=today)
        db.session.add(mix)
        db.session.flush() # flush para obtener el ID asignado por base de datos

        # Registrar la relación de canciones con orden de prioridad explícito
        for idx, cid in enumerate(mix_canciones_ids[:20]):
            db.session.execute(
                db.text("INSERT INTO daily_mix_canciones (mix_id, cancion_id, orden) VALUES (:m, :c, :o) ON CONFLICT (mix_id, cancion_id) DO NOTHING"),
                {'m': mix.id, 'c': cid, 'o': idx}
            )

    db.session.commit()
    print(f"✅ Daily mixes generados para usuario {usuario_id}: Morning Vibes, Afternoon Chill, Night Beats")


# ============================================
# REDIRECCIÓN DE ESTADÍSTICAS
# ============================================
@app.route('/stats')
def user_stats():
    """Redirige al perfil principal donde se encuentran renderizadas las estadísticas."""
    return redirect(url_for('profile'))


# ============================================
# API DE ARTISTAS RELACIONADOS (RECOMENDACIÓN)
# ============================================
@app.route('/api/related/artists/<int:artist_id>')
def related_artists(artist_id):
    """
    Endpoint JSON para obtener artistas similares/relacionados a un artista dado.
    
    Implementa 4 niveles de cascada (estrategias de búsqueda):
    1. Género Compartido: Artistas que tienen canciones con el mismo género del artista actual.
    2. Colaboraciones o Álbumes Cruzados: Artistas que comparten pistas en álbumes de compilación.
    3. Perfil Acústico Similar: Compara promedios de BPM, rango dinámico (Dynamic Range)
       y sonoridad RMS de todas las canciones del artista buscando perfiles con baja varianza.
    4. Fallback de Popularidad: Sugiere artistas con mayor volumen de canciones en la base de datos.
    
    Args:
        artist_id (int): Identificador del artista de referencia.
        
    Returns:
        JSON: Lista de diccionarios de artistas similares con detalles básicos.
    """
    artist = Artista.query.get_or_404(artist_id)
    related_ids = set()
    related = []
    limit = 4

    # ---- ESTRATEGIA 1: Coincidencia por género musical idéntico ----
    genres = db.session.query(Cancion.genero).filter(
        Cancion.artista_id == artist_id, Cancion.genero.isnot(None)
    ).distinct().all()
    genre_list = [g[0] for g in genres if g[0]]

    if genre_list:
        genre_matches = db.session.query(Artista).join(Cancion).filter(
            Cancion.genero.in_(genre_list),
            Artista.id != artist_id
        ).distinct().all()
        for a in genre_matches:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)

    # ---- ESTRATEGIA 2: Álbumes en común o compilaciones cruzadas ----
    if len(related) < limit:
        album_ids = db.session.query(Album.id).filter(Album.artista_id == artist_id).subquery()
        same_album_artists = db.session.query(Artista).join(Album).join(Cancion).filter(
            Album.id.in_(db.session.query(Cancion.album_id).filter(
                Cancion.album_id.in_(album_ids),
                Cancion.artista_id != artist_id
            )),
            Artista.id != artist_id
        ).distinct().all()
        for a in same_album_artists:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)
                if len(related) >= limit:
                    break

    # ---- ESTRATEGIA 3: Perfil acústico similar (tempo BPM, rango dinámico, volumen promedio) ----
    if len(related) < limit:
        # Extraer el promedio de BPM, rango dinámico y sonoridad del artista de referencia
        avg_profile = db.session.query(
            db.func.avg(Cancion.bpm),
            db.func.avg(Cancion.dynamic_range),
            db.func.avg(Cancion.rms_level)
        ).filter(Cancion.artista_id == artist_id).first()

        if avg_profile and avg_profile[0] is not None:
            bpm, dyn, rms = avg_profile
            tolerance_bpm = 20  # +/- 20 beats por minuto
            tolerance_dyn = 5   # +/- 5 dB de rango dinámico
            
            # Buscar artistas cuyas canciones tengan valores promedio dentro del rango de tolerancia
            acoustic_matches = db.session.query(
                Artista,
                db.func.count(Cancion.id).label('song_count')
            ).join(Cancion).filter(
                Cancion.bpm.between(bpm - tolerance_bpm, bpm + tolerance_bpm),
                Cancion.dynamic_range.between(dyn - tolerance_dyn, dyn + tolerance_dyn),
                Artista.id != artist_id
            ).group_by(Artista.id).order_by(db.func.count(Cancion.id).desc()).limit(limit).all()

            for a, _ in acoustic_matches:
                if a.id not in related_ids:
                    related_ids.add(a.id)
                    related.append(a)
                    if len(related) >= limit:
                        break

    # ---- ESTRATEGIA 4: Fallback de seguridad - artistas más populares / biblioteca activa ----
    if len(related) < 4:
        popular = db.session.query(Artista).join(Cancion).filter(
            Artista.id != artist_id
        ).group_by(Artista.id).order_by(
            db.func.count(Cancion.id).desc()
        ).limit(limit - len(related)).all()
        for a in popular:
            if a.id not in related_ids:
                related_ids.add(a.id)
                related.append(a)
                if len(related) >= limit:
                    break

    return jsonify([{
        'id': a.id,
        'nombre': a.nombre,
        'nombre_normalizado': a.nombre_normalizado,
        'foto': a.foto_url or '',
        'album_count': len(a.albums)
    } for a in related[:limit]])


# ============================================
# PERFIL DE USUARIO Y ESTADÍSTICAS RICAS
# ============================================
@app.route('/profile')
def profile():
    """
    Ruta del Perfil de Usuario.
    
    Calcula y reúne estadísticas avanzadas y paneles de escucha del usuario:
    - Las 10 canciones más escuchadas del usuario.
    - Los 8 artistas más reproducidos.
    - Total acumulado de canciones completas reproducidas.
    - Horas de escucha totales calculadas sumando los segundos de duración de las canciones escuchadas.
    - Conteo de canciones reproducidas en las últimas 24 horas.
    
    Returns:
        Render de la plantilla 'profile.html' con las estadísticas del perfil.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return redirect(url_for('login'))
    is_admin = usuario.is_admin()
    user_id = session['user_id']

    # Consultar las 10 canciones más escuchadas (excluyendo saltos rápidos)
    top_songs = db.session.query(
        Cancion, db.func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion).order_by(db.desc('plays')).limit(10).all()

    # Consultar los 8 artistas más escuchados por agregación de reproducciones
    top_artists = db.session.query(
        Artista.nombre, Artista.id, db.func.count(HistorialEscucha.id).label('plays')
    ).select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False)\
        .group_by(Artista.id)\
        .order_by(db.desc('plays')).limit(8).all()

    # Suma total de pistas reproducidas completas
    total_plays = HistorialEscucha.query.filter_by(usuario_id=user_id, skip=False).count()

    # Calcular las horas totales dedicadas a escuchar música en la plataforma
    total_hours = db.session.query(db.func.sum(Cancion.duracion))\
        .join(HistorialEscucha)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False,
                Cancion.duracion.isnot(None)).scalar() or 0
    total_hours = total_hours // 3600  # Convertir segundos acumulados a horas enteras

    # Estadísticas rápidas de las últimas 24 horas
    last_24h = HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.reproducido_en >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    return render_template('profile.html', usuario=usuario, is_admin=is_admin,
                           top_songs=top_songs, top_artists=top_artists,
                           total_plays=total_plays, total_hours=total_hours,
                           last_24h=last_24h)


@app.route('/api/profile/update', methods=['POST'])
def api_profile_update():
    """
    Endpoint JSON para actualizar dinámicamente preferencias y datos del perfil de usuario.
    
    Parámetros recibidos en el JSON del body:
        nombre_publico (str): Apodo público visible en lugar de su login.
        crossfade_enabled (bool): Activar/desactivar transición suave de crossfade.
        activity_tracking (bool): Guardar o no el historial de audición.
        idioma_preferido (str): Código ISO del idioma (e.g. 'es', 'en').
        password (str): Nueva contraseña de acceso.
        
    Returns:
        JSON: Estado 'ok' y preferencias actuales tras la persistencia en base de datos.
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'No user'}), 404

    data = request.get_json(silent=True) or {}
    if 'nombre_publico' in data:
        usuario.nombre_publico = data['nombre_publico'].strip() or None
    if 'crossfade_enabled' in data:
        usuario.crossfade_enabled = bool(data['crossfade_enabled'])
    if 'activity_tracking' in data:
        usuario.activity_tracking = bool(data['activity_tracking'])
    if 'idioma_preferido' in data:
        usuario.idioma_preferido = data['idioma_preferido'].strip()[:5] or 'es'
    if 'password' in data and data['password'].strip():
        usuario.set_password(data['password'].strip())
        session.pop('_fresh', None) # Invalidar marca de credencial fresca en sesión si existiera

    db.session.commit()
    return jsonify({
        'ok': True,
        'crossfade_enabled': usuario.crossfade_enabled,
        'activity_tracking': usuario.activity_tracking,
        'idioma_preferido': usuario.idioma_preferido
    })


@app.route('/api/profile', methods=['GET'])
def api_profile():
    """
    API JSON que retorna la configuración y metadatos del usuario logueado en la sesión actual.
    
    Returns:
        JSON: Diccionario con preferencias y propiedades básicas de cuenta.
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'No user'}), 404
    return jsonify({
        'id': usuario.id,
        'nombre_usuario': usuario.nombre_usuario,
        'nombre_publico': usuario.nombre_publico,
        'role': usuario.role,
        'crossfade_enabled': usuario.crossfade_enabled,
        'activity_tracking': usuario.activity_tracking,
        'idioma_preferido': usuario.idioma_preferido,
        'display_name': usuario.display_name()
    })


# ============================================
# API: REGISTRAR HISTORIAL DE REPRODUCCIÓN
# ============================================
@app.route('/api/play/<int:cancion_id>', methods=['POST'])
def api_register_play(cancion_id):
    """
    Registra una canción en el historial de audición del usuario.
    
    Respeta la privacidad del usuario; si 'activity_tracking' está desactivado en su perfil,
    no se guardará ningún registro de historial y el endpoint retornará exitosamente de inmediato.
    
    Args:
        cancion_id (int): ID de la canción reproducida.
        
    Returns:
        JSON: Estado del guardado ('ok': True).
    """
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    
    # Solo registrar si el usuario tiene el seguimiento de actividad habilitado
    if usuario and not usuario.activity_tracking:
        return jsonify({'ok': True, 'tracking': False})
        
    data = request.get_json(silent=True) or {}
    entry = HistorialEscucha(
        usuario_id=session['user_id'],
        cancion_id=cancion_id,
        skip=data.get('skip', False) # Marca si la canción se saltó antes del 30% de reproducción
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'ok': True})


# ============================================
# API: TRADUCTOR DE LETRAS HÍBRIDO (LIBRE/GOOGLE)
# ============================================
@app.route('/api/translate', methods=['POST'])
def api_translate():
    """
    Traduce texto o letras (como archivos LRC) en tiempo real al idioma objetivo.
    
    Utiliza una estrategia de traducción híbrida:
    1. Primero intenta de forma directa con LibreTranslate (servicio descentralizado y gratuito).
    2. Si LibreTranslate da error, responde con timeout o no está disponible, realiza un fallback
       automático hacia una llamada por scraping no autenticada de la API móvil de Google Translate.
       
    Returns:
        JSON: Texto traducido y el motor que sirvió la traducción ('libre' o 'google').
    """
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    target = data.get('target', 'es').strip()
    if not text:
        return jsonify({'error': 'No text'}), 400

    try:
        # Estrategia 1: Intentar con LibreTranslate
        resp = requests.post('https://libretranslate.com/translate', json={
            'q': text,
            'source': 'auto',
            'target': target,
            'format': 'text'
        }, timeout=15)

        if resp.status_code == 200:
            result = resp.json()
            translated = result.get('translatedText', '')
            if translated:
                return jsonify({'translated': translated, 'source': 'libre'})

        # Estrategia 2 (Fallback): Google Translate via web scraping móvil (sin requerir API Keys)
        from urllib.parse import quote
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={quote(text[:5000])}'
        resp2 = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DuckSound/1.0)'
        })
        if resp2.status_code == 200:
            parts = resp2.json()
            translated = ''.join(p[0] for p in parts[0] if p[0])
            if translated:
                return jsonify({'translated': translated, 'source': 'google'})

        return jsonify({'error': 'Translation failed'}), 502
    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({'error': str(e)}), 502


# Registrar rutas adicionales e integraciones (blueprints de Flask)
from routes import admin_bp, api_bp, browse_bp
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)
app.register_blueprint(browse_bp)


# Vista del contenedor principal de reproducción (Iframe de persistencia de audio)
@app.route('/player_frame')
def player_frame():
    """Sirve el marco iframe dedicado del reproductor para aislar y blindar el AudioContext."""
    return render_template('player_frame.html')


# ============================================
# CONTEXT PROCESSOR (INYECCIÓN DE JINJA)
# ============================================
@app.context_processor
def inject_user_info():
    """
    Inyecta información y permisos del usuario automáticamente en todas las plantillas HTML (templates).
    
    Evita la necesidad de pasar redundante y manualmente variables comunes como 'is_admin'
    o la instancia del usuario a cada función render_template en la aplicación.
    
    Returns:
        dict: Variables agregadas al contexto global del motor de plantillas Jinja2.
    """
    from flask import g
    is_admin = False
    usuario_obj = None
    if 'user_id' in session:
        if 'user_info' not in g:
            usuario_obj = db.session.get(Usuario, session['user_id'])
            g.user_info = usuario_obj
            g.user_is_admin = usuario_obj.is_admin() if usuario_obj else False
        else:
            usuario_obj = g.user_info
        is_admin = g.user_is_admin
    return dict(
        is_admin=is_admin,
        es_favoritos=False,
        current_user=usuario_obj,
        app_version=Config.APP_VERSION
    )


# ============================================
# SERVIDORES DE AUDIO, LETRAS Y MULTIMEDIA
# ============================================

@app.route('/audio/<int:cancion_id>')
def servir_audio(cancion_id):
    """
    Sirve el flujo del archivo binario de audio de una canción.
    
    > [!IMPORTANT]
    > **Streaming Eficiente y Navegación Seekable:**
    > Este endpoint hace uso del parámetro `conditional=True` en `send_file`. Esto le indica
    > a Flask que procese y responda de manera nativa a cabeceras de rango HTTP 206 ('Range').
    > Esto es crucial para los reproductores multimedia HTML5, ya que les permite realizar
    > peticiones por rangos de bytes para rebobinar, saltar adelante en la pista de forma instantánea
    > y amortiguar el búfer de reproducción sin descargar el archivo de audio completo de golpe.
    
    Aplica heurísticas adaptativas de búsqueda de rutas:
    1. Ruta absoluta de archivo original tal como se indexó.
    2. Conversión inteligente de rutas absolutas de Windows (ej. 'G:\\Musica\\...') a sistemas de
       montaje compartidos en Docker/Linux (ej. '/music/Musica/...').
    3. Resolución y validación en rutas relativas al directorio de ejecución local de DuckSound.
    
    Args:
        cancion_id (int): Identificador de la canción a transmitir.
        
    Returns:
        Response: Stream binario de audio con soporte de solicitudes por rangos parciales.
    """
    cancion = Cancion.query.get_or_404(cancion_id)
    original_path = cancion.ruta_archivo_audio
    tried_paths = [original_path]

    def _mime_for(p):
        """Asigna el MIME Type correcto de transmisión según la extensión del archivo."""
        ext = Path(p).suffix.lower()
        return {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg'
        }.get(ext, 'audio/mpeg')

    # 1. Intentar servir por la ruta exacta mapeada directamente en disco
    if os.path.exists(original_path):
        print(f"Serving audio (original): {original_path}")
        return send_file(original_path, mimetype=_mime_for(original_path), conditional=True, max_age=86400)

    # 2. Conversión Heurística de rutas Windows montadas en Docker/Linux
    try:
        p = original_path.replace('\\\\', '/').replace(':/', ':/')
        import re
        # Detecta letras de unidades Windows típicas como 'G:/MiMusica/cancion.mp3'
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            rest = m.group(2)
            alt = '/music/' + rest
            tried_paths.append(alt)
            if os.path.exists(alt):
                print(f"Serving audio (mapped from {original_path} -> {alt})")
                return send_file(alt, mimetype=_mime_for(alt), conditional=True, max_age=86400)
    except Exception as e:
        print('Error mapping audio path:', e)

    # 3. Intentar como ruta relativa en el directorio de trabajo actual
    rel = os.path.join(os.getcwd(), original_path)
    tried_paths.append(rel)
    if os.path.exists(rel):
        print(f"Serving audio (relative): {rel}")
        return send_file(rel, mimetype=_mime_for(rel), conditional=True, max_age=86400)

    print(f"Audio not found for id={cancion_id}. Tried: {tried_paths}")
    return "Archivo de audio no encontrado", 404


@app.route('/lyrics/<int:cancion_id>')
def servir_lyrics(cancion_id):
    """
    Sirve archivos de letras LRC sincronizadas para el reproductor de karaoke.
    
    Aplica una estrategia de resolución dinámica:
    1. Consulta al módulo `lyrics_fetcher` para comprobar si existe la letra; si no existe,
       realiza una descarga asíncrona automática en tiempo real desde APIs libres en internet.
    2. En caso de fallback, busca el archivo de letras físico mapeado localmente en la base de datos,
       aplicando las mismas heurísticas de mapeo de directorios cruzados Windows/Docker.
       
    Args:
        cancion_id (int): ID de la canción asociada.
        
    Returns:
        Response: Archivo .lrc en texto plano con cabeceras de codificación UTF-8.
    """
    from lyrics_fetcher import obtener_o_descargar_letra
    
    cancion = Cancion.query.get_or_404(cancion_id)
    
    # Intentar obtener la letra descargada u obtenerla dinámicamente mediante el scraper
    resultado = obtener_o_descargar_letra(cancion_id)
    
    if resultado and resultado.get('letra'):
        # Retornar contenido de letras LRC directo como texto plano UTF-8 con caché
        from flask import Response, make_response
        response = make_response(Response(resultado['letra'], mimetype='text/plain; charset=utf-8'))
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    
    # Fallback físico directo si el servidor de scraping falló
    original_path = cancion.ruta_archivo_lrc
    tried_paths = [original_path]

    if original_path and os.path.exists(original_path):
        return send_file(original_path, mimetype='text/plain', max_age=3600)

    # Conversión de rutas Windows a volúmenes Docker
    try:
        if original_path:
            p = original_path.replace('\\\\', '/').replace(':/', ':/')
            import re
            m = re.match(r'^([A-Za-z]):/(.*)', p)
            if m:
                rest = m.group(2)
                alt = '/music/' + rest
                tried_paths.append(alt)
                if os.path.exists(alt):
                    return send_file(alt, mimetype='text/plain')
    except Exception as e:
        print('Error mapping lyrics path:', e)

    # Buscar bajo ruta relativa
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        return send_file(rel, mimetype='text/plain')

    print(f"Lyrics not found for id={cancion_id}. Tried: {tried_paths}")
    return "Archivo de letras no encontrado", 404


def _extract_cover_from_file(audio_path):
    """
    Extrae la portada incrustada directamente en los metadatos binarios del archivo de audio.
    
    Soporta:
    - Portadas tipo bloque de imagen en metadatos de archivos FLAC (Vorbis Comments - pictures).
    - Portadas incrustadas en frames APIC dentro de etiquetas ID3v2 para archivos MP3.
    
    Args:
        audio_path (str): Ruta al archivo físico de audio.
        
    Returns:
        bytes: Datos binarios de la imagen de portada extraída, o None si no se encuentra.
    """
    if not audio_path or not os.path.exists(audio_path):
        return None
    try:
        from mutagen import File as MFile
        from mutagen.id3 import ID3, APIC
        af = MFile(audio_path)
        if af is None:
            return None
        # FLAC y Ogg encapsulan portadas en el atributo .pictures
        if hasattr(af, 'pictures') and af.pictures:
            return af.pictures[0].data
        # MP3 almacena portadas en frames APIC dentro de las etiquetas ID3
        if hasattr(af, 'tags') and af.tags is not None:
            apic = af.tags.getall('APIC')
            if apic:
                return apic[0].data
    except Exception:
        pass
    return None


@app.route('/album-art/<int:cancion_id>')
def servir_album_art(cancion_id):
    """
    Sirve la imagen de portada de álbum asociada a una canción.
    
    Posee una arquitectura de búsqueda por cascada ultra-robusta de 6 niveles:
    1. Ruta física original registrada en base de datos.
    2. Nueva ubicación centralizada y persistente de portadas ('ALBUM_ART_FOLDER').
    3. Ubicación clásica heredada ('media/album_art').
    4. Rutas compartidas absolutas heredadas bajo Docker ('/music/album_art').
    5. Conversión de mapeo de rutas híbridas Windows-Linux.
    6. Extracción directa "al vuelo" del artwork incrustado en el archivo de audio.
    
    Si todas las búsquedas fallan, devuelve de forma elegante un gráfico vectorial SVG
    dinámico con un icono de nota musical en lugar de un error 404, previniendo fallos en UI.
    
    Args:
        cancion_id (int): Identificador de la canción.
        
    Returns:
        Response: Imagen JPG/PNG/WebP encontrada o archivo SVG vectorial.
    """
    cancion = Cancion.query.get_or_404(cancion_id)
    original_path = cancion.ruta_imagen_album
    tried_paths = [original_path]

    def _image_mime_for(p):
        """Asigna cabeceras MIME de imagen idóneas."""
        ext = Path(p).suffix.lower()
        return {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }.get(ext, 'image/jpeg')

    # 1. Intentar ruta original exacta en disco
    if original_path and os.path.exists(original_path):
        mimetype = _image_mime_for(original_path)
        return send_file(original_path, mimetype=mimetype, max_age=86400)

    # 2. Carpeta centralizada ALBUM_ART_FOLDER (PWA caché persistente)
    if original_path:
        alt_name = Path(original_path).name
        alt_path = Config.ALBUM_ART_FOLDER / alt_name
        tried_paths.append(str(alt_path))
        if alt_path.exists():
            mimetype = _image_mime_for(str(alt_path))
            return send_file(str(alt_path), mimetype=mimetype)

    # 3. Carpeta clásica de archivos multimedia del proyecto
    if hasattr(Config, 'MEDIA_FOLDER') and original_path:
        old_path = Path(str(Config.MEDIA_FOLDER)) / 'album_art' / Path(original_path).name
        tried_paths.append(str(old_path))
        if old_path.exists():
            mimetype = _image_mime_for(str(old_path))
            return send_file(str(old_path), mimetype=mimetype)

    # 4. Volumen heredado /music/album_art/ en contenedores Docker
    if original_path:
        docker_legacy = Path('/music/album_art') / Path(original_path).name
        tried_paths.append(str(docker_legacy))
        if docker_legacy.exists():
            mimetype = _image_mime_for(str(docker_legacy))
            return send_file(str(docker_legacy), mimetype=mimetype)

    # 5. Mapeo de sistemas de archivos cruzados Windows/Docker
    try:
        if original_path:
            p = original_path.replace('\\\\', '/').replace(':/', ':/')
            import re
            m = re.match(r'^([A-Za-z]):/(.*)', p)
            if m:
                rest = m.group(2)
                alt = '/music/' + rest
                tried_paths.append(alt)
                if os.path.exists(alt):
                    mimetype = _image_mime_for(alt)
                    return send_file(alt, mimetype=mimetype)
    except Exception as e:
        print('Error mapping album art path:', e)

    # 6. Intentar ruta relativa
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        mimetype = _image_mime_for(rel)
        return send_file(rel, mimetype=mimetype)

    # 7. EXTRACCIÓN BINARIA: Extraer metadatos incrustados en la propia pista
    img_data = _extract_cover_from_file(cancion.ruta_archivo_audio)
    if img_data is None and cancion.ruta_archivo_audio:
        # Intentar extracción mapeando la ruta de audio en Docker si fuese necesario
        p = cancion.ruta_archivo_audio.replace('\\\\', '/').replace(':/', ':/')
        import re
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            alt = '/music/' + m.group(2)
            tried_paths.append(f"audio_fallback:{alt}")
            img_data = _extract_cover_from_file(alt)
            
    if img_data:
        import io
        return send_file(io.BytesIO(img_data), mimetype='image/jpeg')

    # Fallback total de visualización: Servir un marcador de posición SVG vectorial moderno
    print(f"Album art not found for id={cancion_id}. Tried: {tried_paths}")
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
        <rect width="300" height="300" fill="#2a2a33" rx="12"/>
        <circle cx="150" cy="150" r="70" fill="none" stroke="#9ca3af" stroke-width="2" opacity="0.3"/>
        <text x="150" y="172" font-size="90" text-anchor="middle" fill="#9ca3af" font-family="sans-serif" opacity="0.5">&#9835;</text>
    </svg>'''
    return placeholder_svg, 200, {'Content-Type': 'image/svg+xml'}


@app.route('/service-worker.js')
def service_worker():
    """
    Sirve el Service Worker de la PWA desde la raíz del dominio web.
    
    Es un requerimiento del estándar W3C servir el Service Worker en la raíz ('/') para que
    su ámbito de interceptación de red (scope) cubra la totalidad de la aplicación.
    Sobrescribe las cabeceras HTTP de caché para forzar al navegador a revalidar el script
    siempre, garantizando la carga inmediata de actualizaciones.
    
    Returns:
        Response: Archivo service-worker.js.
    """
    from flask import send_from_directory, make_response
    response = make_response(send_from_directory('static/js', 'service-worker.js', mimetype='application/javascript'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ============================================
# ENDPOINTS API AUXILIARES DE CANCIONES
# ============================================

@app.route('/api/canciones')
def api_canciones():
    """
    Retorna la lista de todas las canciones registradas en la biblioteca en formato JSON.
    
    Returns:
        JSON: Lista de diccionarios serializados de canciones.
    """
    canciones = Cancion.query.all()
    return jsonify([c.to_dict() for c in canciones])


@app.route('/api/cancion/<int:cancion_id>')
def api_cancion(cancion_id):
    """
    Retorna la información y metadatos detallados de una única canción específica.
    
    Args:
        cancion_id (int): Identificador de la canción.
        
    Returns:
        JSON: Canción serializada.
    """
    cancion = Cancion.query.get_or_404(cancion_id)
    return jsonify(cancion.to_dict())


# ============================================
# ARRANQUE DE LA APLICACIÓN
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("🎵 PLATAFORMA DE STREAMING DE MÚSICA CON KARAOKE 🎵")
    print("DuckSound - v" + Config.APP_VERSION)
    print("Servidor iniciado en: http://0.0.0.0:8604")
    
    # Intentar utilizar Waitress multi-hilo para alto rendimiento y soporte óptimo de concurrencia
    try:
        from waitress import serve
        print("Usando Waitress (8 threads)...")
        serve(app, host='0.0.0.0', port=8604, threads=8)
    except ImportError:
        # Servidor de desarrollo Flask por defecto si Waitress no está disponible en el entorno
        print("Waitress no encontrado, usando servidor de desarrollo Flask...")
        app.run(host='0.0.0.0', port=8604, debug=False)

