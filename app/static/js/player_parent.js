/**
 * Puente del Reproductor Padre (Parent Bridge)
 * 
 * Este script actúa como el controlador principal en la ventana superior (parent).
 * Se encarga de gestionar la interfaz de usuario externa (controles del mini-reproductor,
 * panel lateral de letras, lista de cola, recomendaciones), capturar interacciones del DOM
 * (clics en tarjetas de canciones, menús contextuales, atajos de teclado) y comunicarse
 * bidireccionalmente con el iframe aislado (`player_frame.js`) mediante `postMessage` para
 * sincronizar el estado de la reproducción de audio sin interrumpir la navegación.
 */
(function(){
    // ===== Toast notificaciones globales =====
    /**
     * Muestra un mensaje de notificación flotante (toast) en la pantalla.
     * Si el contenedor de notificaciones no existe, lo crea dinámicamente.
     * 
     * @param {string} message - El texto de la notificación a mostrar.
     * @param {string} [type='info'] - Tipo de notificación ('success', 'error', 'info').
     */
    function showToast(message, type) {
        type = type || 'info';
        const container = document.getElementById('toast-container');
        if (!container) {
            const c = document.createElement('div');
            c.id = 'toast-container';
            c.className = 'toast-container';
            document.body.appendChild(c);
        }
        const el = document.createElement('div');
        el.className = 'toast toast-' + type;
        const icons = {success: 'fa-regular fa-circle-check', error: 'fa-regular fa-circle-xmark', info: 'fa-regular fa-circle'};
        el.innerHTML = '<i class="' + (icons[type] || icons.info) + '"></i><span>' + message + '</span>';
        document.getElementById('toast-container').appendChild(el);
        // Configura el desvanecimiento y la eliminación automática del elemento tras 3 segundos
        setTimeout(() => { el.classList.add('toast-out'); setTimeout(() => el.remove(), 300); }, 3000);
    }
    window.showToast = showToast;

    /**
     * Resuelve la URL de la portada de una canción.
     * Retorna la ruta específica o una por defecto basada en el ID.
     * 
     * @param {Object} song - Objeto de datos de la canción.
     * @returns {string} URL de la carátula o cadena vacía.
     */
    function resolveCoverUrl(song){
        if (!song) return '';
        if (song.cover && String(song.cover).trim() !== '') return song.cover;
        if (song.id) return `/album-art/${song.id}`;
        return '';
    }

    /**
     * Establece la carátula pequeña en el mini-reproductor o lista,
     * aplicando un fallback de SVG en caso de error de carga o ausencia de URL.
     * 
     * @param {HTMLImageElement} miniCover - Elemento de imagen del DOM.
     * @param {Object} song - Objeto de datos de la canción.
     */
    function setMiniCoverImage(miniCover, song){
        if (!miniCover) return;
        const coverUrl = resolveCoverUrl(song);
        if (!coverUrl){
            // SVG por defecto con símbolo musical en caso de no contar con carátula
            miniCover.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='8' fill='%23222'/%3E%3Ctext x='50' y='58' font-size='42' text-anchor='middle' fill='%239ca3af'%3E%E2%99%AA%3C/text%3E%3C/svg%3E";
            miniCover.style.opacity = '0.7';
            return;
        }
        miniCover.onerror = () => {
            miniCover.onerror = null;
            // Si falla la URL customizada, intenta cargar la ruta estándar basada en el ID
            if (song && song.id && miniCover.src.indexOf(`/album-art/${song.id}`) === -1){
                miniCover.src = `/album-art/${song.id}`;
                miniCover.style.opacity = '1';
                return;
            }
            // Fallback final si todo falla
            miniCover.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='8' fill='%23222'/%3E%3Ctext x='50' y='58' font-size='42' text-anchor='middle' fill='%239ca3af'%3E%E2%99%AA%3C/text%3E%3C/svg%3E";
            miniCover.style.opacity = '0.7';
        };
        miniCover.src = coverUrl;
        miniCover.style.opacity = '1';
    }

    /**
     * Envía un mensaje estructurado al iframe del reproductor
     * para controlar la reproducción de audio mediante `postMessage`.
     * 
     * @param {Object} msg - Carga útil (payload) del mensaje a transmitir.
     */
    function sendToPlayer(msg){
        const iframe = document.getElementById('player-frame');
        if (!iframe || !iframe.contentWindow) return;
        iframe.contentWindow.postMessage(msg, window.location.origin);
    }

    /**
     * Construye un objeto de canción limpio a partir de los atributos de datos (dataset)
     * de una tarjeta o fila del DOM.
     * 
     * @param {HTMLElement} card - Elemento HTML que representa la canción.
     * @returns {Object|null} Objeto con la información formateada de la canción o null.
     */
    function songFromCard(card){
        if (!card) return null;
        const id = parseInt(card.dataset.cancionId, 10);
        if (!id) return null;
        return {
            id: id,
            titulo: card.dataset.titulo || 'Sin titulo',
            artista: card.dataset.artista || '',
            audio: card.dataset.audio || `/audio/${id}`,
            cover: card.dataset.cover || `/album-art/${id}`,
            lyrics: card.dataset.lyrics || `/lyrics/${id}`
        };
    }

    /**
     * Asegura la existencia del menú contextual personalizado de la aplicación,
     * creándolo en el cuerpo del documento si no existía previamente, y
     * vinculando sus manejadores de eventos.
     * 
     * @returns {HTMLElement} El elemento contenedor del menú contextual.
     */
    function ensureContextMenu(){
        let menu = document.getElementById('song-context-menu');
        if (menu) return menu;

        menu = document.createElement('div');
        menu.id = 'song-context-menu';
        menu.className = 'song-context-menu';
        menu.innerHTML = `
            <button type="button" data-action="play-next"><i class="fa-solid fa-forward-step"></i><span>Reproducir a continuación</span></button>
            <button type="button" data-action="add-queue"><i class="fa-solid fa-list-ul"></i><span>Añadir a la cola</span></button>
            <button type="button" data-action="add-fav"><i class="fa-regular fa-heart"></i><span>Añadir a favoritos</span></button>
            <button type="button" data-action="add-playlist"><i class="fa-solid fa-plus"></i><span>Añadir a playlist</span></button>
            <div class="context-divider"></div>
            <button type="button" data-action="go-album" class="context-album"><i class="fa-regular fa-circle-dot"></i><span>Ir al álbum</span></button>
            <button type="button" data-action="go-artist" class="context-artist"><i class="fa-regular fa-user"></i><span>Ir al artista</span></button>
        `;
        document.body.appendChild(menu);

        // Delegación de eventos para las opciones del menú contextual
        menu.addEventListener('click', (event) => {
            const button = event.target.closest('button[data-action]');
            if (!button || !menu._targetCard) return;
            const card = menu._targetCard;
            const song = songFromCard(card);
            const action = button.dataset.action;
            hideContextMenu();

            if (!song) return;
            if (action === 'play-next') {
                // Inserta la canción justo después de la actual en la cola del reproductor
                sendToPlayer({type: 'queueSong', song, position: 'next'});
                selectRightTab('upnext');
                showToast('Reproduciendo a continuación', 'info');
            } else if (action === 'add-queue') {
                // Añade la canción al final de la cola
                sendToPlayer({type: 'queueSong', song, position: 'end'});
                selectRightTab('upnext');
                showToast('Añadido a la cola', 'info');
            } else if (action === 'add-fav') {
                // Alterna el estado de favoritos llamando a la API del servidor
                fetch('/api/favoritos/toggle/' + song.id, {method:'POST'}).then(r=>r.json()).then(d=>{
                    const label = button.querySelector('span');
                    if (label) label.textContent = d.liked ? 'Quitar de favoritos' : 'Añadir a favoritos';
                    button.querySelector('i').className = d.liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                    showToast(d.liked ? '♥ Añadido a favoritos' : '♡ Quitado de favoritos', 'success');
                });
            } else if (action === 'add-playlist') {
                // Abre el modal de colecciones/playlists si está disponible globalmente
                if (window.openCollectionModal) window.openCollectionModal('cancion', song.id);
            } else if (action === 'go-album' && card.dataset.albumId) {
                window.location.href = `/album/${card.dataset.albumId}`;
            } else if (action === 'go-artist' && card.dataset.artistId) {
                window.location.href = `/artist/${card.dataset.artistId}`;
            }
        });

        // Ocultar menú en clics fuera, scroll, redimensionamiento o tecla escape
        document.addEventListener('click', hideContextMenu);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') hideContextMenu();
        });
        window.addEventListener('scroll', hideContextMenu, true);
        window.addEventListener('resize', hideContextMenu);
        return menu;
    }

    /**
     * Oculta el menú contextual activo y elimina la referencia a la tarjeta objetivo.
     */
    function hideContextMenu(){
        const menu = document.getElementById('song-context-menu');
        if (!menu) return;
        menu.classList.remove('visible');
        menu._targetCard = null;
    }

    /**
     * Posiciona y despliega dinámicamente el menú contextual adaptándolo a las dimensiones
     * de la pantalla para evitar desbordamientos visuales.
     * 
     * @param {MouseEvent} event - Evento original del clic derecho.
     * @param {HTMLElement} card - Elemento DOM asociado a la canción sobre el cual se hizo clic.
     */
    function showContextMenu(event, card){
        const menu = ensureContextMenu();
        menu._targetCard = card;
        
        // Mostrar u ocultar enlaces de navegación del menú según el contexto del DOM
        menu.querySelector('.context-album').style.display = (card.dataset.context === 'album' && card.dataset.albumId) ? '' : 'none';
        menu.querySelector('.context-artist').style.display = (card.dataset.context === 'artist' && card.dataset.artistId) ? '' : 'none';

        menu.style.left = '0px';
        menu.style.top = '0px';
        menu.classList.add('visible');
        
        // Ajuste inteligente de coordenadas para que el menú no se dibuje fuera del viewport
        const rect = menu.getBoundingClientRect();
        const x = Math.min(event.clientX, window.innerWidth - rect.width - 10);
        const y = Math.min(event.clientY, window.innerHeight - rect.height - 10);
        menu.style.left = Math.max(10, x) + 'px';
        menu.style.top = Math.max(10, y) + 'px';
    }

    /**
     * Renderiza la lista de canciones en cola ("A continuación") dentro del panel correspondiente.
     * Implementa scroll automático para mantener visible la canción que está sonando actualmente.
     * 
     * @param {HTMLElement} container - Contenedor DOM donde se inyectará la lista.
     * @param {Array<Object>} items - Array de canciones en cola con sus estados de reproducción.
     */
    function renderUpNextList(container, items){
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = '<p class="muted">No hay canciones en cola</p>';
            return;
        }
        container.innerHTML = items.map(it => {
            const cover = it.cover || `/album-art/${it.id}`;
            let badge = '';
            let extraClass = '';
            
            if (it.current) {
                badge = '<span style="font-size:10px;color:#4ade80;font-weight:700;text-transform:uppercase;letter-spacing:.3px"><i class="fa-solid fa-play"></i> Reproduciendo</span>';
                extraClass = 'current-song';
            } else if (it.queued) {
                badge = '<span style="font-size:10px;color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:.3px">Cola</span>';
                extraClass = 'queued';
            }
            
            return `<div class="upnext-item ${extraClass}" data-id="${it.id}" data-current="${it.current ? 'true' : 'false'}">
                <div class="cover"><img src="${escapeHtml(cover)}" alt=""></div>
                <div class="meta">
                    <strong>${escapeHtml(it.titulo || 'Sin titulo')}</strong>
                    <div class="muted">${escapeHtml(it.artista || '')}</div>
                    ${badge}
                </div>
            </div>`;
        }).join('');
        
        // Scroll suave automático hasta la canción actual
        const currentEl = container.querySelector('.upnext-item.current-song');
        if (currentEl) {
            currentEl.scrollIntoView({block: 'nearest', behavior: 'smooth'});
        }
    }

    /**
     * Vincula manejadores de eventos (menú contextual, clic de reproducción)
     * a todas las tarjetas de canciones o filas de pistas disponibles en el DOM.
     * Utiliza banderas para evitar la doble vinculación en transiciones SPA.
     */
    function bindSongCards(){
        document.querySelectorAll('.song-card, .track-item').forEach(card => {
            // Vinculación del menú contextual personalizado
            if (!card.dataset.contextMenuBound) {
                card.dataset.contextMenuBound = '1';
                card.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showContextMenu(e, card);
                });
            }
            // Vinculación de eventos de reproducción al hacer clic
            if (card.dataset.playerClickBound) return;
            card.dataset.playerClickBound = '1';
            card.addEventListener('click', (e) => {
                // Desbloquea restricciones del AudioContext
                tryUnlockAudio();

                // Intercepta solo si se hizo clic en el botón de reproducción (play icon)
                if (!e.target.closest('.track-play-btn')) return;

                const id = parseInt(card.dataset.cancionId);
                const song = songFromCard(card);
                
                // Determina la carga de cola contextualizada según la procedencia
                const context = card.dataset.context;
                if (context === 'artist'){
                    const artistId = parseInt(card.dataset.artistId);
                    loadArtistPlaylist(artistId, id);
                } else if (context === 'album'){
                    const albumId = parseInt(card.dataset.albumId);
                    loadAlbumPlaylist(albumId, id);
                } else {
                    // Reproducción directa e individual si no cuenta con un contexto definido
                    sendToPlayer({type:'playSong', song});
                }
            });
        });
    }

    /**
     * Desbloquea las restricciones modernas de seguridad de los navegadores (User Gesture)
     * para el AudioContext, inicializando de forma efímera un contexto silencioso.
     */
    function tryUnlockAudio(){
        if (window._audioUnlocked) return;
        try{
            const C = window.AudioContext || window.webkitAudioContext;
            if (!C) { window._audioUnlocked = true; return; }
            const ctx = new C();
            ctx.resume().then(()=>{ window._audioUnlocked = true; try{ ctx.close(); }catch(e){} }).catch(()=>{});
        }catch(e){}
    }

    /**
     * Obtiene y establece como lista de reproducción actual la discografía completa de un artista,
     * iniciando de inmediato la canción sobre la cual se interactuó.
     * 
     * @param {number} artistId - ID numérico del artista.
     * @param {number} songId - ID de la canción inicial.
     */
    function loadArtistPlaylist(artistId, songId){
        fetch(`/api/artist/${artistId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                sendToPlayer({type:'setPlaylist', playlist: songs});
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong) sendToPlayer({type:'playSong', song: clickedSong});
            })
            .catch(err => {
                console.error('Error al cargar la playlist del artista:', err);
                const song = { id: songId, titulo: 'Unknown', audio: `/audio/${songId}` };
                sendToPlayer({type:'playSong', song});
            });
    }

    /**
     * Obtiene y establece como lista de reproducción activa el álbum completo seleccionado,
     * reproduciendo la canción elegida por el usuario.
     * 
     * @param {number} albumId - ID del álbum.
     * @param {number} songId - ID de la canción que inicia la reproducción.
     */
    function loadAlbumPlaylist(albumId, songId){
        fetch(`/api/album/${albumId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                sendToPlayer({type:'setPlaylist', playlist: songs});
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong) sendToPlayer({type:'playSong', song: clickedSong});
            })
            .catch(err => {
                console.error('Error al cargar la playlist del álbum:', err);
                const song = { id: songId, titulo: 'Unknown', audio: `/audio/${songId}` };
                sendToPlayer({type:'playSong', song});
            });
    }

    // ===== MANEJADOR PRINCIPAL DE MENSAJES (postMessage Listener) =====
    // Escucha eventos originados por el iframe del reproductor
    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        const data = event.data || {};
        
        // 1. Sincronización del Color de Acento Dinámico (Extraído de carátulas vía ColorThief)
        if (data.type === 'themeColor' && data.color) {
            let [r, g, b] = data.color;
            // Cálculo de luminancia para asegurar accesibilidad y legibilidad del tema
            const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
            if (luminance < 80) {
                // Fuerza aclarado si el color dominante es demasiado oscuro
                const factor = 90 / Math.max(luminance, 1);
                r = Math.min(255, Math.round(r * factor));
                g = Math.min(255, Math.round(g * factor));
                b = Math.min(255, Math.round(b * factor));
            } else if (luminance > 180) {
                // Suaviza o atenúa si el color es excesivamente chillón
                const factor = 160 / luminance;
                r = Math.round(r * factor);
                g = Math.round(g * factor);
                b = Math.round(b * factor);
            }
            // Inyecta variables personalizadas CSS en el DOM raíz de la aplicación principal
            document.documentElement.style.setProperty('--accent', `rgb(${r}, ${g}, ${b})`);
            document.documentElement.style.setProperty('--accent-soft', `rgba(${r}, ${g}, ${b}, 0.15)`);
            document.documentElement.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.3)`);
        }

        // 2. Actualización periódica de tiempos y sincronización de letras
        if (data.type === 'timeupdate' && typeof data.currentTime === 'number'){
            highlightLyricAt(data.currentTime);
            updateProgressBar(data.currentTime, data.duration || 0);
        }

        // 3. Sincronización del nivel de volumen en los controles deslizantes
        if (data.type === 'volumeChange' && typeof data.volume === 'number'){
            const volSlider = document.getElementById('volume-slider');
            if (volSlider) volSlider.value = data.volume;
            updateVolumeIcon(data.volume);
        }

        // 4. Cambios en estados de aleatoriedad (Shuffle) y repetición (Repeat)
        if (data.type === 'shuffleChange') updateShuffleRepeatUI(data.shuffled, null);
        if (data.type === 'repeatChange') updateShuffleRepeatUI(null, data.repeat);

        // 5. Actualizaciones de Estado General del Reproductor
        if (data.type === 'state' && data.state){
            const st = data.state;
            const song = st.song;
            const currentSongId = window._currentSongId;
            const newSongId = song ? song.id : null;
            const songChanged = currentSongId !== newSongId;

            // Procesos disparados únicamente cuando se detecta un cambio de pista activa
            if (songChanged) {
                window._currentSongId = newSongId;

                // Actualizar Letra de Canción
                const lyricsPanel = document.getElementById('lyrics-content-panel');
                const lyricsScroll = lyricsPanel ? lyricsPanel.querySelector('.lyrics-content-scroll') : null;
                if (lyricsPanel && lyricsScroll){
                    if (song && song.lyrics){
                        // Consulta la letra sincronizada (.lrc)
                        fetch(song.lyrics).then(r=> r.ok ? r.text() : Promise.reject())
                        .then(txt=>{
                            const cues = parseLRC(txt);
                            renderLyrics(cues, song.id);
                            // Auto-selecciona la pestaña de letras si no se está visualizando la cola
                            if (window._activeRightTab !== 'upnext') selectRightTab('lyrics');
                        }).catch(()=>{
                            lyricsScroll.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Letra no encontrada</p>';
                            window._currentLyrics = null;
                        });
                    } else {
                        lyricsScroll.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Selecciona una canción</p>';
                    }
                }

                // Actualizar lista de Canciones Similares Recomendadas (Recommender System)
                if (song && song.id){
                    const relatedDiv = document.getElementById('related-content');
                    if (relatedDiv){
                        fetch(`/api/similares/${song.id}`).then(r=>r.json()).then(similares=>{
                            window._currentSimilar = similares || [];
                            renderSimilar(similares);
                        }).catch(()=> {
                            window._currentSimilar = [];
                            relatedDiv.innerHTML = '<p class="muted">No hay similares</p>';
                        });
                    }
                }

                // Sincronizar UI del Mini-Reproductor inferior
                const miniTitle = document.getElementById('mini-title');
                const miniArtist = document.getElementById('mini-artist');
                const miniCover = document.getElementById('mini-cover');
                if (miniTitle){
                    miniTitle.textContent = song ? song.titulo : 'DuckSound';
                    if (song) miniTitle.dataset.songId = song.id;
                }
                if (miniArtist) miniArtist.textContent = song ? (song.artista||'Artista') : '';
                setMiniCoverImage(miniCover, song);
            }
            updateProgressBar(st.currentTime || 0, st.duration || 0);

            // Sincronizar indicadores activos de reproducción (ecualizadores circulares, clases css)
            document.querySelectorAll('.track-item.playing, .song-card.playing').forEach(el => {
                const dText = el.querySelector('.duration-text');
                if (dText && el.dataset.originalDuration) dText.textContent = el.dataset.originalDuration;
                el.classList.remove('playing');
                el.classList.remove('paused');
            });
            if (newSongId) {
                const items = document.querySelectorAll(`.track-item[data-cancion-id="${newSongId}"], .song-card[data-cancion-id="${newSongId}"]`);
                items.forEach(item => {
                    item.classList.add('playing');
                    if (!st.isPlaying) item.classList.add('paused');
                    const dText = item.querySelector('.duration-text');
                    if (dText && !item.dataset.originalDuration) item.dataset.originalDuration = dText.textContent.trim();
                    if (songChanged && item.classList.contains('track-item')) {
                        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                });
            }

            // Sincronizar la Cola "A continuación" (Up Next)
            const upnextDiv = document.getElementById('upnext-content');
            if (upnextDiv){
                const items = (st.upnext || []);
                const upnextStr = JSON.stringify(items.map(it=>[it.id, !!it.queued, !!it.current]));
                if (window._lastUpNextStr !== upnextStr) {
                    window._lastUpNextStr = upnextStr;
                    window._currentUpNext = items;
                    if (items.length === 0) upnextDiv.innerHTML = '<p class="muted">Cola vacía</p>';
                    else {
                        renderUpNextList(upnextDiv, items);
                        // Añadir manejadores para reproducción directa desde elementos de la cola
                        upnextDiv.querySelectorAll('.upnext-item').forEach(it => {
                            it.addEventListener('click', ()=>{
                                const sid = parseInt(it.dataset.id);
                                const sdata = { id: sid, titulo: it.querySelector('strong').textContent, artista: it.querySelector('.muted').textContent, audio: `/audio/${sid}`, cover: `/album-art/${sid}`, lyrics: `/lyrics/${sid}` };
                                sendToPlayer({type:'playSong', song: sdata});
                            });
                        });
                    }
                }
            }

            // Alternar estado visual del icono de Play/Pausa
            const miniPlay = document.getElementById('mini-play');
            if (miniPlay && miniPlay.querySelector('i')) {
                miniPlay.querySelector('i').className = st.isPlaying ? 'fa-solid fa-pause' : 'fa-solid fa-play';
            }
            updateShuffleRepeatUI(st.shuffled, st.repeat);
            const volSlider = document.getElementById('volume-slider');
            if (volSlider && typeof st.volume === 'number'){ volSlider.value = st.volume; updateVolumeIcon(st.volume); }
        }
    });

    /**
     * Alterna la visualización activa de las pestañas en el panel derecho de la aplicación.
     * 
     * @param {string} name - Nombre de la pestaña ('lyrics', 'upnext', 'related').
     */
    function selectRightTab(name){
        document.querySelectorAll('#right-panel .tab').forEach(b=>b.classList.toggle('active', b.dataset.tab===name));
        document.querySelectorAll('#right-panel .tab-content').forEach(c=>c.classList.toggle('active', c.id===name+'-content' || (name==='lyrics' && c.id==='lyrics-content-panel')));
        window._activeRightTab = name;
    }

    /**
     * Sanitiza cadenas HTML sencillas para evitar inyecciones XSS en componentes dinámicos.
     * 
     * @param {string} s - Texto crudo a sanitizar.
     * @returns {string} Texto seguro apto para inyectar en innerHTML.
     */
    function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    /**
     * Analiza y parsea texto en formato LRC (letra sincronizada con marcas de tiempo).
     * Soporta múltiples marcas de tiempo por línea e ignora créditos o etiquetas meta sin timestamp.
     * 
     * @param {string} txt - Contenido en crudo del archivo de letras .lrc.
     * @returns {Array<Object>} Lista ordenada de líneas de letras parseadas con {start: segundos, text: contenido}.
     */
    function parseLRC(txt){
        const lines = txt.split(/\r?\n/);
        const timeTag = /\[(\d+):(\d{2})(?:\.(\d{1,3}))?\]/g;
        const cues = [];
        for (let raw of lines){
            let match; const tags = [];
            while ((match = timeTag.exec(raw)) !== null){
                const m = parseInt(match[1],10), s = parseInt(match[2],10);
                const ms = match[3] ? parseInt((match[3]+'00').slice(0,3),10) : 0;
                tags.push(m*60 + s + ms/1000);
            }
            const text = raw.replace(timeTag, '').trim();
            if (!tags.length) continue;
            if (!text) continue;
            if (/contribuciones/i.test(text)) continue;
            for (const t of tags) cues.push({start: t, text: text});
        }
        return cues.sort((a,b)=>a.start - b.start);
    }

    /**
     * Cambia el estado visual y desactiva/activa el botón de traducción según disponibilidad.
     * 
     * @param {boolean} enabled - Indica si hay letras sincronizadas activas y traducibles.
     */
    function updateTranslateBtn(enabled) {
        const btn = document.getElementById('btn-translate-lyrics');
        if (!btn) return;
        btn.disabled = !enabled;
        if (enabled && btn.innerHTML.includes('Traducido')) return;
        btn.innerHTML = '<i class="fa-solid fa-language"></i> Traducir';
        btn.style.opacity = enabled ? '1' : '0.4';
    }

    /**
     * Renderiza en el DOM las letras estructuradas de una canción.
     * Evita renders innecesarios reutilizando datos traducidos en memoria.
     * 
     * @param {Array<Object>} cues - Estructuras de letra con timestamps.
     * @param {number} songId - ID de la canción en reproducción.
     */
    function renderLyrics(cues, songId){
        const lyricsPanel = document.getElementById('lyrics-content-panel');
        if (!lyricsPanel) return;
        const scrollDiv = lyricsPanel.querySelector('.lyrics-content-scroll');
        if (!scrollDiv) return;
        
        // Evita re-dibujar si ya existe el contenido traducido para esta canción en memoria
        if (window._translatedHtml && window._currentLyrics && window._currentLyrics.songId === songId) {
            return;
        }
        window._translatedHtml = null; // Reiniciar traducción al cambiar de canción
        
        if (!cues || cues.length===0){
            scrollDiv.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Letra no encontrada</p>';
            window._currentLyrics = null;
            updateTranslateBtn(false);
            return;
        }
        const html = cues.map((c, i)=>`<div class="lyric-line" data-start="${c.start}" data-index="${i}">${escapeHtml(c.text)}</div>`).join('');
        scrollDiv.innerHTML = '<div class="lyrics-lines">' + html + '</div>';
        window._currentLyrics = {songId: songId, cues: cues, index: -1};
        updateTranslateBtn(true);
        scrollDiv.scrollTop = 0; // Reinicia el scroll al inicio de las letras
    }

    /**
     * Consume la API de traducción de letras para traducir el contenido actual al idioma preferido del usuario.
     * Realiza un mapeo paralelo e inserta subtítulos con micro-traducciones en tiempo real bajo cada línea.
     * 
     * @param {Array<Object>} cues - Colección de cues musicales de la canción.
     */
    function translateLyrics(cues){
        const btn = document.getElementById('btn-translate-lyrics');
        if (!btn) return;
        
        if (!cues || !window._currentLyrics || window._currentLyrics.cues !== cues) {
            setBtnReady(btn);
            return;
        }
        
        setBtnLoading(btn);
        
        const targetLang = (window._userLang) || 'es';
        
        if (!Array.isArray(cues) || cues.length === 0) {
            setBtnReady(btn);
            return;
        }
        
        // Concatena todas las líneas usando un delimitador único para procesarlo en una sola consulta de API
        const text = cues.map(c=>c.text || '').join('\n---\n');
        let timedOut = false;
        const timer = setTimeout(() => { timedOut = true; setBtnReady(btn); }, 12000);
        
        fetch('/api/translate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text, target: targetLang}) })
        .then(r=>r.json()).then(data=>{
            clearTimeout(timer);
            if (timedOut) return;
            if (!data.translated) throw new Error('no translation');
            const lines = data.translated.split('\n---\n');
            const linesDiv = document.querySelector('.lyrics-lines');
            if (linesDiv && window._currentLyrics && window._currentLyrics.cues === cues) {
                // Genera HTML enriquecido con la letra original y su respectiva sublínea traducida
                const html = cues.map((c,i)=> `<div class="lyric-line" data-start="${c.start}" data-index="${i}"><div class="lyric-main-text">${escapeHtml(c.text)}</div><div class="lyric-subline">${escapeHtml(lines[i]||'')}</div></div>`).join('');
                linesDiv.innerHTML = html;
                window._translatedHtml = html; // Almacena traducción en caché volátil de sesión
                setBtnDone(btn);
            }
        }).catch(()=> {
            clearTimeout(timer);
            if (!timedOut) setBtnReady(btn);
        });
        
        function setBtnLoading(b) { b.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; b.disabled = true; }
        function setBtnReady(b) { b.innerHTML = '<i class="fa-solid fa-language"></i> Traducir'; b.disabled = false; b.style.opacity = '1'; }
        function setBtnDone(b) { b.innerHTML = '<i class="fa-solid fa-language"></i> Traducido'; b.disabled = false; }
    }

    /**
     * Renderiza la lista de recomendaciones similares basadas en algoritmos de recomendación.
     * 
     * @param {Array<Object>} similares - Canciones similares provistas por el backend.
     */
    function renderSimilar(similares){
        const relatedDiv = document.getElementById('related-content');
        if (!relatedDiv) return;
        relatedDiv.innerHTML = similares.map(s=>{
            const cover = s.cover || '/album-art/' + s.id;
            const pct = s.similarity != null ? Math.round(s.similarity * 100) : null;
            return `<div class="similar-item" data-cancion-id="${s.id}" data-titulo="${escapeHtml(s.titulo)}" data-artista="${escapeHtml(s.artista||'')}">
                <div class="cover"><img src="${escapeHtml(cover)}" alt=""></div>
                <div class="meta">
                    <strong>${escapeHtml(s.titulo)}</strong>
                    <div class="muted">${escapeHtml(s.artista)}</div>
                </div>
                ${pct !== null ? '<span class="similarity-badge">' + pct + '%</span>' : ''}
            </div>`;
        }).join('');
        
        // Asigna click a las recomendaciones similares para iniciar reproducción al pulsar
        relatedDiv.querySelectorAll('.similar-item').forEach(item => {
            item.addEventListener('click', ()=>{
                const id = parseInt(item.dataset.cancionId);
                sendToPlayer({type:'playSong', song: {id, titulo: item.dataset.titulo, artista: item.dataset.artista, audio:`/audio/${id}`}});
            });
        });
    }

    /**
     * Resalta la línea de letra correspondiente según el segundo actual de reproducción
     * y ejecuta un scroll automático suave y centrado al elemento activo.
     * 
     * @param {number} time - Tiempo transcurrido de la canción en segundos.
     */
    function highlightLyricAt(time){
        const L = window._currentLyrics;
        if (!L || !L.cues) return;
        let idx = -1;
        // Búsqueda binaria o lineal secuencial para emparejar la línea correspondiente
        for (let i=0;i<L.cues.length;i++) if (time >= L.cues[i].start) idx = i; else break;
        if (idx === L.index) return;
        const container = document.querySelector('.lyrics-lines');
        if (!container) return;
        if (L.index >= 0) { const p = container.querySelector(`[data-index="${L.index}"]`); if (p) p.classList.remove('active'); }
        const el = container.querySelector(`[data-index="${idx}"]`);
        if (el){ el.classList.add('active'); el.scrollIntoView({behavior:'smooth', block:'center'}); }
        L.index = idx;
    }

    /**
     * Formatea segundos flotantes/enteros a una representación visual limpia de formato MM:SS.
     * 
     * @param {number} s - Segundos.
     * @returns {string} Tiempo formateado "M:SS".
     */
    function formatTime(s){ if (!Number.isFinite(s)) return '0:00'; const min = Math.floor(s/60), sec = Math.floor(s%60); return `${min}:${String(sec).padStart(2,'0')}`; }

    let _currentDuration = 0;
    
    /**
     * Sincroniza todas las barras de progreso, marcadores de tiempo de la interfaz
     * y los indicadores SVG SVG progress rings de las filas individuales del DOM.
     * 
     * @param {number} cur - Tiempo transcurrido de la pista.
     * @param {number} dur - Duración total de la pista.
     */
    function updateProgressBar(cur, dur){
        _currentDuration = dur;
        const bar = document.getElementById('mini-progress-bar'), tCur = document.getElementById('mini-time-current'), tDur = document.getElementById('mini-time-duration');
        if (bar) bar.style.width = (dur > 0 ? (cur/dur)*100 : 0) + '%';
        if (tCur) tCur.textContent = formatTime(cur);
        if (tDur) tDur.textContent = formatTime(dur);

        // Actualiza el círculo de progreso animado (progress-ring) en la fila de la lista activa
        const activeTrack = document.querySelector('.track-item.playing');
        if (activeTrack) {
            const circle = activeTrack.querySelector('.progress-ring__circle');
            if (circle) {
                const circumference = 2 * Math.PI * 12; // Radio r=12
                const offset = circumference - (dur > 0 ? (cur / dur) : 0) * circumference;
                circle.style.strokeDashoffset = offset;
            }
            const timeText = activeTrack.querySelector('.duration-text');
            if (timeText) {
                timeText.textContent = formatTime(dur);
            }
        }
    }

    /**
     * Procesa clics manuales sobre la barra de progreso general para realizar
     * saltos de tiempo (Seeking) en la reproducción del archivo de audio.
     * 
     * @param {MouseEvent} e - Evento de clic en la barra.
     */
    function seekViaProgressBar(e){
        const container = document.getElementById('mini-progress-container'); if (!container) return;
        const pct = (e.clientX - container.getBoundingClientRect().left) / container.offsetWidth;
        sendToPlayer({type:'command', cmd:'seekTo', seconds: pct * (_currentDuration || 0)});
    }

    /**
     * Inicializa componentes, pestañas laterales, eventos de clic directo en letras
     * y clics sobre contenedores de progreso en el panel de detalles derecho.
     */
    function initRightPanel(){
        document.querySelectorAll('#right-panel .tab').forEach(t => t.addEventListener('click', ()=> selectRightTab(t.dataset.tab)));
        selectRightTab(window._activeRightTab || 'lyrics');
        if (window._currentLyrics) {
            const scrollDiv = document.querySelector('.lyrics-content-scroll');
            // Restaura de manera limpia el estado traducido anterior si existe
            if (window._translatedHtml && scrollDiv) {
                scrollDiv.innerHTML = '<div class="lyrics-lines">' + window._translatedHtml + '</div>';
                const btn = document.getElementById('btn-translate-lyrics');
                if (btn) { btn.innerHTML = '<i class="fa-solid fa-language"></i> Traducido'; btn.disabled = false; }
            } else if (!scrollDiv.querySelector('.lyrics-lines')) {
                // Solo renderizar si no hay letras ya cargadas (evita resetear el índice sincronizado)
                renderLyrics(window._currentLyrics.cues, window._currentLyrics.songId);
            }
        } else updateTranslateBtn(false);
        
        // Recupera elementos sincronizados si la UI se recarga mediante navegación SPA
        if (window._currentUpNext) renderUpNextList(document.getElementById('upnext-content'), window._currentUpNext);
        if (window._currentSimilar) renderSimilar(window._currentSimilar);
        
        // Permite realizar saltos de reproducción (seeking) directo al hacer clic en una línea de letra
        const lP = document.getElementById('lyrics-content-panel');
        if (lP) lP.addEventListener('click', (ev)=>{
            const line = ev.target.closest('.lyric-line');
            if (line) sendToPlayer({type:'command', cmd:'seekTo', seconds: parseFloat(line.dataset.start)});
        });
        const pC = document.getElementById('mini-progress-container');
        if (pC) pC.addEventListener('click', seekViaProgressBar);
    }

    /**
     * Actualiza y sincroniza los estilos CSS y títulos informativos de los botones de
     * aleatorio (shuffle) y repetición (repeat) basándose en las variables globales del reproductor.
     * 
     * @param {boolean} s - Indica si está activo el modo aleatorio.
     * @param {string} r - Tipo de repetición activa ('none', 'one', 'all').
     */
    function updateShuffleRepeatUI(s, r){
        const bS = document.getElementById('mini-shuffle'), bR = document.getElementById('mini-repeat');
        if (bS) {
            bS.style.color = s ? 'var(--accent)' : '';
            bS.style.opacity = s ? '1' : '0.6';
            bS.title = s ? 'Aleatorio activo' : 'Aleatorio';
        }
        if (bR) {
            const isActive = r === 'one' || r === 'all';
            bR.style.color = isActive ? 'var(--accent)' : '';
            bR.style.opacity = isActive ? '1' : '0.6';
            bR.querySelector('i').className = 'fa-solid fa-repeat';
            
            // Administra el distintivo numérico "1" para la repetición individual de una sola pista
            let badge = bR.querySelector('.repeat-badge');
            if (r === 'one') {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'repeat-badge';
                    badge.textContent = '1';
                    bR.appendChild(badge);
                }
                badge.style.display = 'inline';
            } else if (badge) {
                badge.style.display = 'none';
            }
            bR.title = r === 'none' ? 'Repetir' : (r === 'one' ? 'Repetir: una canción' : 'Repetir: todas');
        }
    }

    /**
     * Alterna iconos visuales de volumen basados en el nivel sonoro actual.
     * 
     * @param {number} v - Nivel de volumen entre 0.0 y 1.0.
     */
    function updateVolumeIcon(v){
        const i = document.getElementById('volume-icon'); if (!i) return;
        i.className = v == 0 ? 'fa-solid fa-volume-xmark' : (v < 0.5 ? 'fa-solid fa-volume-low' : 'fa-solid fa-volume-high');
    }

    // ===== CARGA INICIAL Y VINCULACIÓN GENERAL DE COMPONENTES =====
    document.addEventListener('DOMContentLoaded', () => {
        bindSongCards(); initRightPanel();
        
        // Obtiene y almacena el idioma del perfil de usuario para los requests de traducción
        fetch('/api/profile').then(r=>r.json()).then(p=>{
            window._userLang = p.idioma_preferido || 'es';
        }).catch(()=>{ window._userLang = 'es'; });
        
        // Guardia para evitar clics repetitivos (rebounce) en saltos de pistas continuos
        let skipGuard = false;
        const guardSkip = (fn) => {
            if (skipGuard) return;
            skipGuard = true;
            try { fn(); } finally { setTimeout(() => { skipGuard = false; }, 250); }
        };
        
        // Mapeo directo de elementos controladores visuales del mini reproductor
        const ctrls = {
            'mini-play': ()=> { tryUnlockAudio(); sendToPlayer({type:'command', cmd:'toggle'}); },
            'mini-next': ()=> guardSkip(() => sendToPlayer({type:'command', cmd:'next'})),
            'mini-prev': ()=> guardSkip(() => sendToPlayer({type:'command', cmd:'prev'})),
            'mini-back10': ()=> sendToPlayer({type:'command', cmd:'seek', seconds:-10}),
            'mini-forward10': ()=> sendToPlayer({type:'command', cmd:'seek', seconds:10}),
            'mini-shuffle': ()=> sendToPlayer({type:'command', cmd:'shuffle'}),
            'mini-repeat': ()=> sendToPlayer({type:'command', cmd:'repeat'}),
            'volume-icon': ()=> sendToPlayer({type:'command', cmd:'toggleMute'})
        };
        for (let id in ctrls) {
            const el = document.getElementById(id);
            if (el) {
                if (el.dataset.boundMiniControls === '1') continue;
                el.dataset.boundMiniControls = '1';
                el.addEventListener('click', ctrls[id]);
            }
        }
        
        // Listener del deslizador de volumen
        const vS = document.getElementById('volume-slider');
        if (vS) vS.addEventListener('input', function(){ updateVolumeIcon(this.value); sendToPlayer({type:'command', cmd:'volume', value: parseFloat(this.value)}); });

        sendToPlayer({type:'command', cmd:'getState'});
        
        // Evento permanente asociado al botón del traductor automático
        const btnTrans = document.getElementById('btn-translate-lyrics');
        if (btnTrans) {
            btnTrans.addEventListener('click', function(){
                const L = window._currentLyrics;
                if (L && L.cues && L.cues.length > 0) {
                    translateLyrics(L.cues);
                } else {
                    // Flash visual de error si no hay letras disponibles
                    btnTrans.style.borderColor = 'var(--accent)';
                    setTimeout(() => { btnTrans.style.borderColor = ''; }, 1000);
                }
            });
        }

        /**
         * Re-vincula manejadores al realizar navegaciones SPA (cambios parciales del DOM)
         * para garantizar que las nuevas canciones inyectadas tengan funcionalidad.
         */
        window.initPageBindings = function(){
            bindSongCards(); initRightPanel();
            if (window._currentSongId) {
                document.querySelectorAll('.track-item.playing, .song-card.playing').forEach(el=> el.classList.remove('playing'));
                const it = document.querySelector(`.track-item[data-cancion-id="${window._currentSongId}"], .song-card[data-cancion-id="${window._currentSongId}"]`);
                if (it) it.classList.add('playing');
            }
            sendToPlayer({type:'command', cmd:'getState'});
        };

        // ===== ACCESIBILIDAD Y TECLAS DE ACCESO RÁPIDO (Keyboard Shortcuts) =====
        document.addEventListener('keydown', function(e) {
            // No interviene si el usuario escribe en elementos de entrada de texto
            if (e.target.matches('input, textarea, select')) return;

            switch (e.code) {
                case 'Space':
                    e.preventDefault();
                    document.getElementById('mini-play')?.click();
                    break;
                case 'ArrowRight':
                    if (e.ctrlKey) { document.getElementById('mini-next')?.click(); }
                    else { document.getElementById('mini-forward10')?.click(); }
                    break;
                case 'ArrowLeft':
                    if (e.ctrlKey) { document.getElementById('mini-prev')?.click(); }
                    else { document.getElementById('mini-back10')?.click(); }
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    const vol = document.getElementById('volume-slider');
                    if (vol) { vol.value = Math.min(1, parseFloat(vol.value) + 0.05); vol.dispatchEvent(new Event('input')); }
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    const vold = document.getElementById('volume-slider');
                    if (vold) { vold.value = Math.max(0, parseFloat(vold.value) - 0.05); vold.dispatchEvent(new Event('input')); }
                    break;
                case 'KeyM':
                    document.getElementById('volume-icon')?.click();
                    break;
                case 'KeyS':
                    document.getElementById('mini-shuffle')?.click();
                    break;
                case 'KeyR':
                    document.getElementById('mini-repeat')?.click();
                    break;
                case 'KeyL':
                    // Acceso directo a letras (tab)
                    const tab = document.querySelector('#right-panel .tab[data-tab="lyrics"]');
                    if (tab) tab.click();
                    break;
                case 'KeyU':
                    // Acceso directo a cola (tab)
                    const tabU = document.querySelector('#right-panel .tab[data-tab="upnext"]');
                    if (tabU) tabU.click();
                    break;
            }
        });
    });
})();
