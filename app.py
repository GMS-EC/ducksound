from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
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

# Inicializar la base de datos
db.init_app(app)

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
    canciones = Cancion.query.order_by(Cancion.titulo).all()
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    
    # Nuevas variables para la vista tipo Spotify
    daily_mixes = DailyMix.query.filter_by(usuario_id=session['user_id']).order_by(DailyMix.fecha.desc()).limit(6).all()
    if not daily_mixes:
        from datetime import date
        today = date.today()
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
# VISTA DE CARPETAS
# ============================================
@app.route('/folders')
def folders():
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
        items = []
        try:
            for entry in sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.is_dir():
                    children = build_tree(entry.path, prefix + entry.name + '/')
                    # count songs in this folder
                    songs = Cancion.query.filter(Cancion.ruta_archivo_audio.like(entry.path.replace('\\', '/') + '%')).count()
                    items.append({'name': entry.name, 'path': entry.path, 'type': 'folder',
                                  'children': children, 'song_count': songs})
                elif entry.name.lower().endswith(tuple(('.mp3','.flac','.wav','.m4a','.ogg'))):
                    items.append({'name': entry.name, 'path': entry.path, 'type': 'file'})
        except PermissionError:
            pass
        return items

    tree = build_tree(audio_dir)
    return render_template('folders.html', tree=tree, is_admin=is_admin)


# ============================================
# COLECCIONES
# ============================================
@app.route('/colecciones')
def colecciones_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    colecciones = Coleccion.query.filter_by(usuario_id=session['user_id'])\
        .order_by(Coleccion.fecha_creacion.desc()).all()
    return render_template('colecciones.html', colecciones=colecciones, is_admin=is_admin)


@app.route('/coleccion/<int:coleccion_id>')
def coleccion_detail(coleccion_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    coleccion = Coleccion.query.get_or_404(coleccion_id)
    if coleccion.usuario_id != session['user_id']:
        abort(403)
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return render_template('coleccion_detail.html', coleccion=coleccion, is_admin=is_admin)


# ============================================
# DAILY MIXES
# ============================================
@app.route('/daily-mixes')
def daily_mixes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    today = date.today()
    mixes = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).all()
    if not mixes:
        # Generar mixes del día
        _generate_daily_mixes(session['user_id'])
        mixes = DailyMix.query.filter_by(usuario_id=session['user_id'], fecha=today).all()
    return render_template('daily_mixes.html', mixes=mixes, is_admin=is_admin)


@app.route('/daily-mix/<int:mix_id>')
def daily_mix_detail(mix_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mix = DailyMix.query.get_or_404(mix_id)
    usuario_obj = db.session.get(Usuario, session['user_id'])
    is_admin = usuario_obj.is_admin() if usuario_obj else False
    return render_template('daily_mix_detail.html', mix=mix, is_admin=is_admin)


def _generate_daily_mixes(usuario_id):
    """Genera 3 daily mixes personalizados basados en historial, favoritos y similitud acústica."""
    import random
    from models import Favorito, HistorialEscucha
    from datetime import date, timedelta
    from recommender import get_similar_songs

    today = date.today()
    last_week = datetime.utcnow() - timedelta(days=7)

    # === 1. OBTENER FUENTES DE DATOS ===

    # Canciones más reproducidas (top 50)
    mas_escuchadas = db.session.query(
        Cancion.id, db.func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion.id).order_by(db.desc('plays')).limit(50).all()
    mas_escuchadas_ids = [c.id for c in mas_escuchadas]
    mas_escuchadas_plays = {c.id: c.plays for c in mas_escuchadas}

    # Canciones favoritas
    fav_ids = [f.cancion_id for f in Favorito.query.filter_by(usuario_id=usuario_id).all()]

    # Canciones escuchadas en la última semana (para excluir)
    recientes_ids = [h.cancion_id for h in HistorialEscucha.query.filter(
        HistorialEscucha.usuario_id == usuario_id,
        HistorialEscucha.reproducido_en >= last_week
    ).distinct(HistorialEscucha.cancion_id).all()]

    # Top 3 géneros más escuchados
    top_generos = db.session.query(
        Cancion.genero, db.func.count(Cancion.id).label('cnt')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == usuario_id,
        Cancion.genero.isnot(None),
        Cancion.genero != ''
    ).group_by(Cancion.genero).order_by(db.desc('cnt')).limit(3).all()
    top_generos_list = [g[0] for g in top_generos if g[0]]

    # Canciones con análisis acústico (BPM, energía, etc.)
    todas_canciones = {c.id: c for c in Cancion.query.all()}

    # === 2. FUNCIÓN AUXILIAR: OBTENER CANCIONES POR VIBE ===
    def canciones_por_vibe(max_bpm=None, min_bpm=None, excluir_ids=None, limit=25):
        """Filtra canciones por rango de BPM."""
        excluir = set(excluir_ids or [])
        query = Cancion.query
        if min_bpm is not None:
            query = query.filter(Cancion.bpm >= min_bpm)
        if max_bpm is not None:
            query = query.filter(Cancion.bpm <= max_bpm)
        # Preferir canciones con BPM conocido
        query = query.order_by(Cancion.bpm.desc().nullslast(), db.func.random())
        candidatos = query.limit(limit * 3).all()
        return [c.id for c in candidatos if c.id not in excluir][:limit]

    def obtener_similares_a(song_ids, top_k=8):
        """Obtiene canciones similares a un conjunto de canciones."""
        similares_ids = set()
        for sid in song_ids[:5]:  # Top 5 para similitud
            try:
                similares = get_similar_songs(sid, top_k=top_k)
                for s in similares:
                    if s['id'] not in similares_ids:
                        similares_ids.add(s['id'])
            except Exception:
                continue
        return list(similares_ids)

    def mezclar_pool(pools, target=20):
        """Mezcla proporcionalmente de varios pools."""
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

    # === 3. GENERAR CADA MIX ===

    # Pool base compartido: canciones más escuchadas + favoritas
    pool_populares = list(dict.fromkeys(mas_escuchadas_ids + fav_ids))

    mixes_data = [
        {
            'name': 'Morning Vibes',
            'desc': 'Energía para empezar el día',
            'bpm_range': (None, None),  # Sin filtro de BPM
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
        pool_similares_ids = []  # IDs de canciones similares en esta iteración
        excluir_ids_set = set(recientes_ids)

        # Pool 1: Populares (más escuchadas + favoritas) excluyendo recientes
        populares_pool = pool_populares.copy()
        random.shuffle(populares_pool)
        pool_populares_filtrado = [c for c in populares_pool if c not in excluir_ids_set]
        if pool_populares_filtrado:
            pools.append(pool_populares_filtrado)
            excluir_ids_set.update(pool_populares_filtrado)

        # Pool 2: Similares a las favoritas
        if fav_ids:
            raw_similares = obtener_similares_a(fav_ids, top_k=6)
            pool_similares_ids = [s for s in raw_similares if s not in excluir_ids_set]
            if pool_similares_ids:
                pools.append(pool_similares_ids)
                excluir_ids_set.update(pool_similares_ids)

        # Pool 3: Exploración del género (canciones no escuchadas)
        if top_generos_list:
            genre = top_generos_list[(hash(name) % len(top_generos_list))]
            explorar_ids = [
                c.id for c in Cancion.query.filter(
                    Cancion.genero.ilike(f'%{genre}%'),
                    ~Cancion.id.in_(excluir_ids_set) if excluir_ids_set else db.true()
                ).order_by(db.func.random()).limit(30).all()
            ]
            if explorar_ids:
                pools.append(explorar_ids)
                excluir_ids_set.update(explorar_ids)

        # Fallback si no hay suficientes
        if not pools or sum(len(p) for p in pools) < 5:
            fallback_ids = [c.id for c in Cancion.query.order_by(db.func.random()).limit(30).all()]
            fallback_ids = [c for c in fallback_ids if c not in excluir_ids_set]
            pools = [fallback_ids]

        # Mezclar pools proporcionalmente
        mix_canciones_ids = mezclar_pool(pools, target=20)

        # Si aún así está vacío, fallback total
        if not mix_canciones_ids:
            mix_canciones_ids = [c.id for c in Cancion.query.order_by(db.func.random()).limit(20).all()]

        # === 4. GUARDAR MIX ===
        # Limpiar mixes viejos del mismo nombre para este usuario (opcional)
        DailyMix.query.filter_by(usuario_id=usuario_id, nombre=name, fecha=today).delete()

        mix = DailyMix(usuario_id=usuario_id, nombre=name, fecha=today)
        db.session.add(mix)
        db.session.flush()

        for idx, cid in enumerate(mix_canciones_ids[:20]):
            db.session.execute(
                db.text("INSERT OR IGNORE INTO daily_mix_canciones (mix_id, cancion_id, orden) VALUES (:m, :c, :o)"),
                {'m': mix.id, 'c': cid, 'o': idx}
            )

    db.session.commit()
    print(f"✅ Daily mixes generados para usuario {usuario_id}: Morning Vibes, Afternoon Chill, Night Beats")


# ============================================
# ESTADÍSTICAS DE USUARIO
# ============================================
@app.route('/stats')
def user_stats():
    return redirect(url_for('profile'))


# ============================================
# ARTISTAS RELACIONADOS
# ============================================
@app.route('/api/related/artists/<int:artist_id>')
def related_artists(artist_id):
    artist = Artista.query.get_or_404(artist_id)
    # Artistas del mismo género (comparten canciones del mismo género)
    genres = db.session.query(Cancion.genero).filter(
        Cancion.artista_id == artist_id, Cancion.genero.isnot(None)
    ).distinct().all()
    genre_list = [g[0] for g in genres if g[0]]

    related = []
    if genre_list:
        related = db.session.query(Artista).join(Cancion).filter(
            Cancion.genero.in_(genre_list),
            Artista.id != artist_id
        ).distinct().limit(6).all()

    return jsonify([{
        'id': a.id, 'nombre': a.nombre,
        'foto': a.foto_url or '',
        'album_count': len(a.albums)
    } for a in related])


# ============================================
# ============================================
# PERFIL DE USUARIO
# ============================================
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return redirect(url_for('login'))
    is_admin = usuario.is_admin()
    user_id = session['user_id']

    # Canciones más escuchadas
    top_songs = db.session.query(
        Cancion, db.func.count(HistorialEscucha.id).label('plays')
    ).join(HistorialEscucha).filter(
        HistorialEscucha.usuario_id == user_id,
        HistorialEscucha.skip == False
    ).group_by(Cancion).order_by(db.desc('plays')).limit(10).all()

    # Artistas más escuchados
    top_artists = db.session.query(
        Artista.nombre, Artista.id, db.func.count(HistorialEscucha.id).label('plays')
    ).select_from(HistorialEscucha)\
        .join(Cancion, HistorialEscucha.cancion_id == Cancion.id)\
        .join(Artista, Cancion.artista_id == Artista.id)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False)\
        .group_by(Artista.id)\
        .order_by(db.desc('plays')).limit(8).all()

    # Total de escuchas
    total_plays = HistorialEscucha.query.filter_by(usuario_id=user_id, skip=False).count()

    # Horas totales
    total_hours = db.session.query(db.func.sum(Cancion.duracion))\
        .join(HistorialEscucha)\
        .filter(HistorialEscucha.usuario_id == user_id, HistorialEscucha.skip == False,
                Cancion.duracion.isnot(None)).scalar() or 0
    total_hours = total_hours // 3600

    # Últimas 24h
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
        session.pop('_fresh', None)

    db.session.commit()
    return jsonify({'ok': True,
        'crossfade_enabled': usuario.crossfade_enabled,
        'activity_tracking': usuario.activity_tracking,
        'idioma_preferido': usuario.idioma_preferido})


@app.route('/api/profile', methods=['GET'])
def api_profile():
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
# API: REGISTRAR REPRODUCCIÓN
# ============================================
@app.route('/api/play/<int:cancion_id>', methods=['POST'])
def api_register_play(cancion_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No auth'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    # Solo registrar si activity_tracking está activo
    if usuario and not usuario.activity_tracking:
        return jsonify({'ok': True, 'tracking': False})
    data = request.get_json(silent=True) or {}
    entry = HistorialEscucha(
        usuario_id=session['user_id'],
        cancion_id=cancion_id,
        skip=data.get('skip', False)
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'ok': True})


# ============================================
# API: TRADUCIR LETRAS
# ============================================
@app.route('/api/translate', methods=['POST'])
def api_translate():
    """Traduce texto usando LibreTranslate pública o Google Translate."""
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    target = data.get('target', 'es').strip()
    if not text:
        return jsonify({'error': 'No text'}), 400

    try:
        # Intentar con LibreTranslate (público, gratuito, sin API key)
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

        # Fallback: Google Translate via web scraping (sin API key)
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


# Registrar rutas adicionales (blueprints)
from routes import admin_bp, api_bp, browse_bp
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)
app.register_blueprint(browse_bp)


# Player frame (persistent iframe)
@app.route('/player_frame')
def player_frame():
    return render_template('player_frame.html')


# ============================================
# CONTEXT PROCESSOR - Variables globales para templates
# ============================================

@app.context_processor
def inject_user_info():
    """Inyecta información del usuario en todos los templates"""
    is_admin = False
    usuario_obj = None
    if 'user_id' in session:
        usuario_obj = db.session.get(Usuario, session['user_id'])
        if usuario_obj:
            is_admin = usuario_obj.is_admin()
    return dict(is_admin=is_admin, es_favoritos=False, current_user=usuario_obj, app_version=Config.APP_VERSION)


# ============================================
# RUTAS DE AUDIO Y LETRAS
# ============================================


@app.route('/audio/<int:cancion_id>')
def servir_audio(cancion_id):
    """Sirve el archivo de audio de una canción"""
    cancion = Cancion.query.get_or_404(cancion_id)
    # Intenta servir el archivo; si no existe, intenta mapear rutas Windows montadas en Docker
    original_path = cancion.ruta_archivo_audio
    tried_paths = [original_path]

    def _mime_for(p):
        ext = Path(p).suffix.lower()
        return {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg'
        }.get(ext, 'audio/mpeg')

    if os.path.exists(original_path):
        print(f"Serving audio (original): {original_path}")
        return send_file(original_path, mimetype=_mime_for(original_path))

    # Si la ruta no existe, intentar convertir rutas Windows como 'G:\\...' a la ruta montada '/music/...'
    try:
        p = original_path.replace('\\\\', '/').replace(':/', ':/')
        # Si comienza con letra de unidad, mapeamos a /music
        import re
        m = re.match(r'^([A-Za-z]):/(.*)', p)
        if m:
            drive = m.group(1)
            rest = m.group(2)
            alt = '/music/' + rest
            tried_paths.append(alt)
            if os.path.exists(alt):
                print(f"Serving audio (mapped from {original_path} -> {alt})")
                return send_file(alt, mimetype=_mime_for(alt))
    except Exception as e:
        print('Error mapping audio path:', e)

    # Último intento: comprobar si la ruta es relativa dentro del proyecto
    rel = os.path.join(os.getcwd(), original_path)
    tried_paths.append(rel)
    if os.path.exists(rel):
        print(f"Serving audio (relative): {rel}")
        return send_file(rel, mimetype=_mime_for(rel))

    print(f"Audio not found for id={cancion_id}. Tried: {tried_paths}")
    return "Archivo de audio no encontrado", 404


@app.route('/lyrics/<int:cancion_id>')
def servir_lyrics(cancion_id):
    """Sirve el archivo .lrc de una canción, intentando descargarlo si no existe localmente"""
    from lyrics_fetcher import obtener_o_descargar_letra
    
    cancion = Cancion.query.get_or_404(cancion_id)
    
    # Intentar obtener o descargar la letra
    resultado = obtener_o_descargar_letra(cancion_id)
    
    if resultado and resultado.get('letra'):
        # Devolver el contenido como texto plano
        from flask import Response
        return Response(resultado['letra'], mimetype='text/plain; charset=utf-8')
    
    # Si lyrics_fetcher no pudo obtenerla, intentar servir el archivo directamente (fallback)
    original_path = cancion.ruta_archivo_lrc
    tried_paths = [original_path]

    if original_path and os.path.exists(original_path):
        return send_file(original_path, mimetype='text/plain')

    # Intentar mapear rutas Windows montadas en Docker (ej: G:\...) a /music/...
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

    # Intentar ruta relativa dentro del proyecto
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        return send_file(rel, mimetype='text/plain')

    print(f"Lyrics not found for id={cancion_id}. Tried: {tried_paths}")
    return "Archivo de letras no encontrado", 404


@app.route('/album-art/<int:cancion_id>')
def servir_album_art(cancion_id):
    """Sirve la imagen del álbum de una canción"""
    cancion = Cancion.query.get_or_404(cancion_id)
    original_path = cancion.ruta_imagen_album
    tried_paths = [original_path]

    def _image_mime_for(p):
        ext = Path(p).suffix.lower()
        return {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }.get(ext, 'image/jpeg')

    if original_path and os.path.exists(original_path):
        mimetype = _image_mime_for(original_path)
        return send_file(original_path, mimetype=mimetype)

    # Intentar en ALBUM_ART_FOLDER (nueva ubicación persistente)
    if original_path:
        alt_name = Path(original_path).name
        alt_path = Config.ALBUM_ART_FOLDER / alt_name
        tried_paths.append(str(alt_path))
        if alt_path.exists():
            mimetype = _image_mime_for(str(alt_path))
            return send_file(str(alt_path), mimetype=mimetype)

    # Intentar en la ubicación antigua (MEDIA_FOLDER / 'album_art' para local)
    if hasattr(Config, 'MEDIA_FOLDER') and original_path:
        old_path = Path(str(Config.MEDIA_FOLDER)) / 'album_art' / Path(original_path).name
        tried_paths.append(str(old_path))
        if old_path.exists():
            mimetype = _image_mime_for(str(old_path))
            return send_file(str(old_path), mimetype=mimetype)

    # Intentar en /music/album_art/ (Docker legacy)
    if original_path:
        docker_legacy = Path('/music/album_art') / Path(original_path).name
        tried_paths.append(str(docker_legacy))
        if docker_legacy.exists():
            mimetype = _image_mime_for(str(docker_legacy))
            return send_file(str(docker_legacy), mimetype=mimetype)

    # Intentar mapear rutas Windows montadas en Docker (ej: G:\...) a /music/...
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

    # Intentar ruta relativa dentro del proyecto
    rel = os.path.join(os.getcwd(), original_path or '')
    tried_paths.append(rel)
    if original_path and os.path.exists(rel):
        mimetype = _image_mime_for(rel)
        return send_file(rel, mimetype=mimetype)

    # Último recurso: extraer portada directamente del archivo de audio
    try:
        audio_path = cancion.ruta_archivo_audio
        if audio_path and os.path.exists(audio_path):
            from mutagen import File as MFile
            af = MFile(audio_path)
            if af and hasattr(af, 'pictures') and af.pictures:
                pic = af.pictures[0]
                img_data = pic.data
                import io
                return send_file(io.BytesIO(img_data), mimetype='image/jpeg')
    except Exception as e:
        print(f"Error extracting cover from audio file: {e}")

    # Intentar extraer desde la ruta de audio alternativa en Docker
    try:
        audio_path = cancion.ruta_archivo_audio
        if audio_path:
            p = audio_path.replace('\\\\', '/').replace(':/', ':/')
            import re
            m = re.match(r'^([A-Za-z]):/(.*)', p)
            if m:
                alt_audio = '/music/' + m.group(2)
                tried_paths.append(f"audio_fallback:{alt_audio}")
                if os.path.exists(alt_audio):
                    from mutagen import File as MFile
                    af = MFile(alt_audio)
                    if af and hasattr(af, 'pictures') and af.pictures:
                        pic = af.pictures[0]
                        import io
                        return send_file(io.BytesIO(pic.data), mimetype='image/jpeg')
    except Exception as e:
        print(f"Error extracting cover from Docker audio path: {e}")

    print(f"Album art not found for id={cancion_id}. Tried: {tried_paths}")
    # Devolver placeholder SVG con icono de nota musical (sólido, sin emoji)
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
        <rect width="300" height="300" fill="#2a2a33" rx="12"/>
        <circle cx="150" cy="150" r="70" fill="none" stroke="#9ca3af" stroke-width="2" opacity="0.3"/>
        <text x="150" y="172" font-size="90" text-anchor="middle" fill="#9ca3af" font-family="sans-serif" opacity="0.5">&#9835;</text>
    </svg>'''
    return placeholder_svg, 200, {'Content-Type': 'image/svg+xml'}


@app.route('/service-worker.js')
def service_worker():
    """Sirve el service worker desde la raíz para que tenga scope sobre toda la app"""
    from flask import send_from_directory
    return send_from_directory('static/js', 'service-worker.js', mimetype='application/javascript')

@app.route('/api/canciones')
def api_canciones():
    """API endpoint para obtener todas las canciones en JSON"""
    canciones = Cancion.query.all()
    return jsonify([c.to_dict() for c in canciones])


@app.route('/api/cancion/<int:cancion_id>')
def api_cancion(cancion_id):
    """API endpoint para obtener una canción específica"""
    cancion = Cancion.query.get_or_404(cancion_id)
    return jsonify(cancion.to_dict())


if __name__ == '__main__':
    print("=" * 60)
    print("🎵 PLATAFORMA DE STREAMING DE MÚSICA CON KARAOKE 🎵")
    print("DuckSound - v" + Config.APP_VERSION)
    print("Servidor iniciado en: http://0.0.0.0:8604")
    
    # Waitress multi-hilo para desarrollo local en Windows
    try:
        from waitress import serve
        print("Usando Waitress (8 threads)...")
        serve(app, host='0.0.0.0', port=8604, threads=8)
    except ImportError:
        print("Waitress no encontrado, usando servidor de desarrollo Flask...")
        app.run(host='0.0.0.0', port=8604, debug=False)
