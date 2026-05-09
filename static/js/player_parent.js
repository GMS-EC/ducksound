// Parent bridge: forwards play commands to the iframe player and binds song-card clicks
(function(){
    function resolveCoverUrl(song){
        if (!song) return '';
        if (song.cover && String(song.cover).trim() !== '') return song.cover;
        if (song.id) return `/album-art/${song.id}`;
        return '';
    }

    function setMiniCoverImage(miniCover, song){
        if (!miniCover) return;
        const coverUrl = resolveCoverUrl(song);
        if (!coverUrl){
            miniCover.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='8' fill='%23222'/%3E%3Ctext x='50' y='58' font-size='42' text-anchor='middle' fill='%239ca3af'%3E%E2%99%AA%3C/text%3E%3C/svg%3E";
            miniCover.style.opacity = '0.7';
            return;
        }
        miniCover.onerror = () => {
            miniCover.onerror = null;
            if (song && song.id && miniCover.src.indexOf(`/album-art/${song.id}`) === -1){
                miniCover.src = `/album-art/${song.id}`;
                miniCover.style.opacity = '1';
                return;
            }
            miniCover.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='8' fill='%23222'/%3E%3Ctext x='50' y='58' font-size='42' text-anchor='middle' fill='%239ca3af'%3E%E2%99%AA%3C/text%3E%3C/svg%3E";
            miniCover.style.opacity = '0.7';
        };
        miniCover.src = coverUrl;
        miniCover.style.opacity = '1';
    }

    function sendToPlayer(msg){
        const iframe = document.getElementById('player-frame');
        if (!iframe || !iframe.contentWindow) return;
        iframe.contentWindow.postMessage(msg, window.location.origin);
    }

    function updateLikeButton(song){
        if (!song || !song.id) return;
        
        fetch('/api/favoritos')
            .then(r => r.json())
            .then(favIds => {
                const btnLike = document.getElementById('btn-like');
                if (btnLike) {
                    const icon = btnLike.querySelector('i');
                    const liked = favIds.includes(song.id);
                    icon.className = liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                    btnLike.style.color = liked ? 'var(--accent)' : '';
                    icon.style.color = liked ? 'var(--accent)' : '';
                }
            })
            .catch(() => {});
    }

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

    function ensureContextMenu(){
        let menu = document.getElementById('song-context-menu');
        if (menu) return menu;

        menu = document.createElement('div');
        menu.id = 'song-context-menu';
        menu.className = 'song-context-menu';
        menu.innerHTML = `
            <button type="button" data-action="play-next"><i class="fa-solid fa-forward-step"></i><span>Reproducir a continuación</span></button>
            <button type="button" data-action="add-queue"><i class="fa-solid fa-list-ul"></i><span>Añadir a la cola</span></button>
            <button type="button" data-action="add-playlist"><i class="fa-solid fa-plus"></i><span>Añadir a playlist</span></button>
            <button type="button" data-action="go-album" class="context-album"><i class="fa-regular fa-circle-dot"></i><span>Ir al álbum</span></button>
            <button type="button" data-action="go-artist" class="context-artist"><i class="fa-regular fa-user"></i><span>Ir al artista</span></button>
        `;
        document.body.appendChild(menu);

        menu.addEventListener('click', (event) => {
            const button = event.target.closest('button[data-action]');
            if (!button || !menu._targetCard) return;
            const card = menu._targetCard;
            const song = songFromCard(card);
            const action = button.dataset.action;
            hideContextMenu();

            if (!song) return;
            if (action === 'play-next') {
                sendToPlayer({type: 'queueSong', song, position: 'next'});
                selectRightTab('upnext');
            } else if (action === 'add-queue') {
                sendToPlayer({type: 'queueSong', song, position: 'end'});
                selectRightTab('upnext');
            } else if (action === 'add-playlist') {
                if (window.openCollectionModal) window.openCollectionModal('cancion', song.id);
            } else if (action === 'go-album' && card.dataset.albumId) {
                window.location.href = `/album/${card.dataset.albumId}`;
            } else if (action === 'go-artist' && card.dataset.artistId) {
                window.location.href = `/artist/${card.dataset.artistId}`;
            }
        });

        document.addEventListener('click', hideContextMenu);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') hideContextMenu();
        });
        window.addEventListener('scroll', hideContextMenu, true);
        window.addEventListener('resize', hideContextMenu);
        return menu;
    }

    function hideContextMenu(){
        const menu = document.getElementById('song-context-menu');
        if (!menu) return;
        menu.classList.remove('visible');
        menu._targetCard = null;
    }

    function showContextMenu(event, card){
        const menu = ensureContextMenu();
        menu._targetCard = card;
        menu.querySelector('.context-album').style.display = (card.dataset.context === 'album' && card.dataset.albumId) ? '' : 'none';
        menu.querySelector('.context-artist').style.display = (card.dataset.context === 'artist' && card.dataset.artistId) ? '' : 'none';

        menu.style.left = '0px';
        menu.style.top = '0px';
        menu.classList.add('visible');
        const rect = menu.getBoundingClientRect();
        const x = Math.min(event.clientX, window.innerWidth - rect.width - 10);
        const y = Math.min(event.clientY, window.innerHeight - rect.height - 10);
        menu.style.left = Math.max(10, x) + 'px';
        menu.style.top = Math.max(10, y) + 'px';
    }

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
        
        // Scroll to current song
        const currentEl = container.querySelector('.upnext-item.current-song');
        if (currentEl) {
            currentEl.scrollIntoView({block: 'nearest', behavior: 'smooth'});
        }
    }

    function bindSongCards(){
        document.querySelectorAll('.song-card, .track-item').forEach(card => {
            if (!card.dataset.contextMenuBound) {
                card.dataset.contextMenuBound = '1';
                card.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showContextMenu(e, card);
                });
            }
            if (card.dataset.playerClickBound) return;
            card.dataset.playerClickBound = '1';
            card.addEventListener('click', (e) => {
                // Ensure audio is unlocked by user gesture (fix autoplay blocking)
                tryUnlockAudio();

                if (e.target.classList.contains('btn-play-song') || e.target.closest('.btn-play-song')) {
                    e.stopPropagation();
                }
                const id = parseInt(card.dataset.cancionId);
                const song = songFromCard(card);
                
                // Check if song has a context (artist or album)
                const context = card.dataset.context;
                if (context === 'artist'){
                    const artistId = parseInt(card.dataset.artistId);
                    loadArtistPlaylist(artistId, id);
                } else if (context === 'album'){
                    const albumId = parseInt(card.dataset.albumId);
                    loadAlbumPlaylist(albumId, id);
                } else {
                    // No context: play song directly
                    sendToPlayer({type:'playSong', song});
                }
            });
        });
    }

    function tryUnlockAudio(){
        if (window._audioUnlocked) return;
        try{
            const C = window.AudioContext || window.webkitAudioContext;
            if (!C) { window._audioUnlocked = true; return; }
            const ctx = new C();
            // resume() must be called on user gesture
            ctx.resume().then(()=>{ window._audioUnlocked = true; try{ ctx.close(); }catch(e){} }).catch(()=>{});
        }catch(e){}
    }

    function loadArtistPlaylist(artistId, songId){
        // Fetch all songs by artist and create a playlist
        fetch(`/api/artist/${artistId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                // Send playlist to iframe
                sendToPlayer({type:'setPlaylist', playlist: songs});
                // Find the clicked song in the playlist and play it
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong){
                    sendToPlayer({type:'playSong', song: clickedSong});
                }
            })
            .catch(err => {
                console.error('Error loading artist playlist:', err);
                // Fallback: just play the song
                const song = {
                    id: songId,
                    titulo: document.querySelector(`[data-cancion-id="${songId}"]`)?.dataset.titulo || 'Unknown',
                    artista: document.querySelector(`[data-cancion-id="${songId}"]`)?.dataset.artista || '',
                    audio: `/audio/${songId}`,
                    cover: `/album-art/${songId}`,
                    lyrics: `/lyrics/${songId}`
                };
                sendToPlayer({type:'playSong', song});
            });
    }

    function loadAlbumPlaylist(albumId, songId){
        // Fetch all songs by album and create a playlist
        fetch(`/api/album/${albumId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                // Send playlist to iframe
                sendToPlayer({type:'setPlaylist', playlist: songs});
                // Find the clicked song in the playlist and play it
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong){
                    sendToPlayer({type:'playSong', song: clickedSong});
                }
            })
            .catch(err => {
                console.error('Error loading album playlist:', err);
                // Fallback: just play the song
                const song = {
                    id: songId,
                    titulo: document.querySelector(`[data-cancion-id="${songId}"]`)?.dataset.titulo || 'Unknown',
                    artista: document.querySelector(`[data-cancion-id="${songId}"]`)?.dataset.artista || '',
                    audio: `/audio/${songId}`,
                    cover: `/album-art/${songId}`,
                    lyrics: `/lyrics/${songId}`
                };
                sendToPlayer({type:'playSong', song});
            });
    }

    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        const data = event.data || {};
        
        // Manejar evento de colores dinámicos
        if (data.type === 'themeColor' && data.color) {
            let [r, g, b] = data.color;
            
            // Ajustar luminiscencia para asegurar legibilidad
            const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
            if (luminance < 80) {
                // Muy oscuro, aclararlo
                const factor = 90 / Math.max(luminance, 1);
                r = Math.min(255, Math.round(r * factor));
                g = Math.min(255, Math.round(g * factor));
                b = Math.min(255, Math.round(b * factor));
            } else if (luminance > 180) {
                // Muy claro, oscurecerlo
                const factor = 160 / luminance;
                r = Math.round(r * factor);
                g = Math.round(g * factor);
                b = Math.round(b * factor);
            }
            
            // Actualizar la variable CSS global
            document.documentElement.style.setProperty('--accent', `rgb(${r}, ${g}, ${b})`);
            // Crear una variable secundaria más suave para fondos (opcional)
            document.documentElement.style.setProperty('--accent-soft', `rgba(${r}, ${g}, ${b}, 0.15)`);
            document.documentElement.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.3)`);
        }

        // Update right-panel UI based on iframe state
        if (data.type === 'state' && data.state){
            const st = data.state;
            const song = st.song;
            const currentSongId = window._currentSongId;
            const newSongId = song ? song.id : null;
            const songChanged = currentSongId !== newSongId;

            if (songChanged) {
                window._currentSongId = newSongId;

                // Update lyrics
                const lyricsPanel = document.getElementById('lyrics-content-panel');
                if (lyricsPanel){
                    if (song && song.lyrics){
                        fetch(song.lyrics).then(r=>{
                            if (!r.ok) throw new Error('no lyrics');
                            return r.text();
                        }).then(txt=>{
                            const cues = parseLRC(txt);
                            renderLyrics(cues, song.id);
                            selectRightTab('lyrics');
                        }).catch(()=>{
                            lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Letra no encontrada</p>';
                        });
                    } else {
                        lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Selecciona una canción para ver la letra</p>';
                        window._currentLyrics = null;
                    }
                }

                // Update similar songs
                if (song && song.id){
                    const relatedDiv = document.getElementById('related-content');
                    if (relatedDiv){
                        relatedDiv.innerHTML = '<p class="muted" style="text-align:center">Cargando similares...</p>';
                        fetch(`/api/similares/${song.id}`).then(r=>{
                            if (!r.ok) throw new Error('no similares');
                            return r.json();
                        }).then(similares=>{
                            window._currentSimilar = similares || [];
                            renderSimilar(similares);
                        }).catch(()=>{
                            window._currentSimilar = [];
                            relatedDiv.innerHTML = '<p class="muted">No hay similares disponibles</p>';
                        });
                    }
                }

                // Update mini-player static UI
                const miniTitle = document.getElementById('mini-title');
                const miniArtist = document.getElementById('mini-artist');
                const miniCover = document.getElementById('mini-cover');
                if (miniTitle){
                    miniTitle.textContent = song ? song.titulo : 'Sin canción seleccionada';
                    if (song && song.id) miniTitle.dataset.songId = song.id;
                }
                if (miniArtist){ miniArtist.textContent = song ? (song.artista||'Artista desconocido') : 'Artista desconocido'; }
                setMiniCoverImage(miniCover, song);

                // Check if current song is liked
                if (song && song.id) {
                    fetch('/api/favoritos')
                        .then(r => r.json())
                        .then(favIds => {
                            const btnLike = document.getElementById('btn-like');
                            if (btnLike) {
                                const icon = btnLike.querySelector('i');
                                const liked = favIds.includes(song.id);
                                icon.className = liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                                btnLike.style.color = liked ? 'var(--accent)' : '';
                                icon.style.color = liked ? 'var(--accent)' : '';
                            }
                        })
                        .catch(() => {});
                }

                // Reset progress bar for new song
                updateProgressBar(0, 0);
                
                // Update now-playing highlight on track items
                document.querySelectorAll('.track-item.playing, .song-card.playing').forEach(el => el.classList.remove('playing'));
                if (newSongId) {
                    const playingItem = document.querySelector(`.track-item[data-cancion-id="${newSongId}"], .song-card[data-cancion-id="${newSongId}"]`);
                    if (playingItem) playingItem.classList.add('playing');
                }
            }

            // Update upnext
            const upnextDiv = document.getElementById('upnext-content');
            if (upnextDiv){
                const items = (st.upnext || []);
                const upnextStr = JSON.stringify(items.map(it=>[it.id, !!it.queued, !!it.current]));
                if (window._lastUpNextStr !== upnextStr) {
                    window._lastUpNextStr = upnextStr;
                    window._currentUpNext = items; // Save for restoration after SPA nav
                    if (items.length === 0) {
                        upnextDiv.innerHTML = '<p class="muted">No hay canciones en cola</p>';
                    } else {
                        renderUpNextList(upnextDiv, items);
                        // Add click listeners to upnext items
                        upnextDiv.querySelectorAll('.upnext-item').forEach(item => {
                            item.addEventListener('click', ()=>{
                                const id = parseInt(item.dataset.id);
                                const clickedSong = {
                                    id: id,
                                    titulo: item.querySelector('strong').textContent,
                                    artista: item.querySelector('.muted').textContent,
                                    audio: `/audio/${id}`,
                                    cover: `/album-art/${id}`,
                                    lyrics: `/lyrics/${id}`
                                };
                                sendToPlayer({type:'playSong', song: clickedSong});
                            });
                            item.addEventListener('mouseenter', ()=> item.style.background = 'rgba(255,64,64,0.1)');
                            item.addEventListener('mouseleave', ()=> item.style.background = 'rgba(255,255,255,0.02)');
                        });
                    }
                }
            }

            // Update mini-player dynamic state
            const miniPlay = document.getElementById('mini-play');
            if (miniPlay && miniPlay.querySelector('i')){
                miniPlay.querySelector('i').className = st.isPlaying ? 'fa-solid fa-pause' : 'fa-solid fa-play';
            }
            // Update shuffle/repeat UI state
            updateShuffleRepeatUI(st.shuffled, st.repeat);
            // Update volume UI
            const volSlider = document.getElementById('volume-slider');
            if (volSlider && typeof st.volume === 'number'){ volSlider.value = st.volume; updateVolumeIcon(st.volume); }
            }
    });

    function selectRightTab(name){
        document.querySelectorAll('#right-panel .tab').forEach(b=>b.classList.toggle('active', b.dataset.tab===name));
        document.querySelectorAll('#right-panel .tab-content').forEach(c=>c.classList.toggle('active', c.id===name+'-content' || (name==='lyrics' && c.id==='lyrics-content-panel')));
        // Save active tab
        window._activeRightTab = name;
    }

    function escapeHtml(s){
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // Parse LRC content into cues [{start, text}]
    function parseLRC(txt){
        const lines = txt.split(/\r?\n/);
        const timeTag = /\[(\d+):(\d{2})(?:\.(\d{1,3}))?\]/g;
        const cues = [];
        for (let raw of lines){
            let match;
            const tags = [];
            while ((match = timeTag.exec(raw)) !== null){
                const m = parseInt(match[1],10);
                const s = parseInt(match[2],10);
                const ms = match[3] ? parseInt((match[3]+'00').slice(0,3),10) : 0;
                tags.push(m*60 + s + ms/1000);
            }
            const text = raw.replace(timeTag, '').trim();
            if (tags.length){
                for (const t of tags) cues.push({start: t, text: text});
            } else if (raw.trim()){
                // no timestamps: create pseudo-cues spaced 3s apart
                const parts = raw.split(/\s{2,}| \\|\|/).filter(Boolean);
                if (parts.length > 1){
                    parts.forEach((p,i)=> cues.push({start: i*3, text: p.trim()}));
                } else {
                    cues.push({start: 0, text: raw.trim()});
                }
            }
        }
        // sort by start
        cues.sort((a,b)=>a.start - b.start);
        return cues;
    }

    let _translatedLyrics = null;
    let _isShowingTranslation = false;

    function renderLyrics(cues, songId){
        const lyricsPanel = document.getElementById('lyrics-content-panel');
        if (!lyricsPanel) return;
        if (!cues || cues.length===0){
            lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Letra vacía</p>';
            window._currentLyrics = null;
            _translatedLyrics = null;
            return;
        }
        const html = cues.map((c, i)=>`<div class="lyric-line" data-start="${c.start}" data-index="${i}">${escapeHtml(c.text)}</div>`).join('');
        // Añadir botón de traducción
        lyricsPanel.innerHTML =
            '<div class="lyrics-toolbar" style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--border-color);margin-bottom:8px;flex-shrink:0">' +
                '<span style="font-size:11px;color:var(--muted)"><i class="fa-regular fa-message"></i></span>' +
                '<button id="btn-translate-lyrics" class="lyrics-translate-btn" style="background:transparent;border:1px solid var(--border-color);color:var(--muted);font-size:11px;padding:4px 10px;border-radius:var(--radius-sm);cursor:pointer;transition:all var(--transition);display:flex;align-items:center;gap:6px">' +
                    '<i class="fa-solid fa-language"></i> <span>Traducir</span>' +
                '</button>' +
            '</div>' +
            '<div class="lyrics-lines">' + html + '</div>';
        window._currentLyrics = {songId: songId, cues: cues, index: -1};
        _translatedLyrics = null;
        _isShowingTranslation = false;

        // Bind translate button
        const btnTranslate = document.getElementById('btn-translate-lyrics');
        if (btnTranslate) {
            btnTranslate.addEventListener('click', function(){
                if (_isShowingTranslation && _translatedLyrics) {
                    restoreOriginalLyrics(cues);
                    return;
                }
                translateLyrics(cues);
            });
        }
    }

    function restoreOriginalLyrics(cues){
        const container = document.querySelector('#lyrics-content-panel .lyrics-lines');
        if (!container) return;
        const html = cues.map((c, i)=>`<div class="lyric-line" data-start="${c.start}" data-index="${i}">${escapeHtml(c.text)}</div>`).join('');
        container.innerHTML = html;
        _isShowingTranslation = false;
        const btn = document.getElementById('btn-translate-lyrics');
        if (btn) btn.querySelector('span').textContent = 'Traducir';
        // Re-highlight active lyric
        if (window._currentLyrics && window._currentLyrics.index >= 0) {
            const el = container.querySelector('[data-index="'+window._currentLyrics.index+'"]');
            if (el) el.classList.add('active');
        }
    }

    function translateLyrics(cues){
        const btn = document.getElementById('btn-translate-lyrics');
        if (btn) {
            btn.querySelector('span').textContent = 'Traduciendo...';
            btn.style.opacity = '0.6';
            btn.disabled = true;
        }

        // Obtener idioma preferido del usuario desde /api/profile
        fetch('/api/profile')
            .then(r => r.json())
            .then(profile => {
                const targetLang = profile.idioma_preferido || 'es';
                const allText = cues.map(c => c.text).join('\n---\n');
                return fetch('/api/translate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: allText, target: targetLang})
                });
            })
            .then(r => r.json())
            .then(data => {
                if (data.translated) {
                    const lines = data.translated.split('\n---\n');
                    const container = document.querySelector('#lyrics-content-panel .lyrics-lines');
                    if (!container) return;
                    // Mostrar original + traducción como subtexto
                    const html = cues.map((c, i) => {
                        const translation = (lines[i] || '').trim();
                        const transHtml = translation && translation !== c.text
                            ? `<div class="lyric-subline">${escapeHtml(translation)}</div>`
                            : '';
                        return `<div class="lyric-line" data-start="${c.start}" data-index="${i}">
                            <span class="lyric-main-text">${escapeHtml(c.text)}</span>
                            ${transHtml}
                        </div>`;
                    }).join('');
                    container.innerHTML = html;
                    _translatedLyrics = lines;
                    _isShowingTranslation = true;
                    if (btn) {
                        btn.querySelector('span').textContent = 'Ocultar traducción';
                        btn.style.opacity = '1';
                        btn.disabled = false;
                    }
                    // Re-highlight
                    if (window._currentLyrics && window._currentLyrics.index >= 0) {
                        const el = container.querySelector('[data-index="'+window._currentLyrics.index+'"]');
                        if (el) el.classList.add('active');
                    }
                } else {
                    throw new Error(data.error || 'Error');
                }
            })
            .catch(() => {
                if (btn) {
                    btn.querySelector('span').textContent = 'Error';
                    btn.style.opacity = '0.5';
                    btn.disabled = false;
                    setTimeout(() => {
                        btn.querySelector('span').textContent = 'Traducir';
                        btn.style.opacity = '1';
                    }, 2000);
                }
            });
    }

    function renderSimilar(similares){
        const relatedDiv = document.getElementById('related-content');
        if (!relatedDiv) return;
        if (!similares || similares.length===0){
            relatedDiv.innerHTML = '<p class="muted">No hay similares disponibles</p>';
            return;
        }
        const html = similares.map(s=>`<div class="similar-item" data-cancion-id="${s.id}" data-titulo="${escapeHtml(s.titulo)}" data-artista="${escapeHtml(s.artista||'')}" style="padding:8px;border-radius:4px;background:rgba(255,255,255,0.02);margin-bottom:6px;cursor:pointer;transition:all 0.2s ease;border:1px solid transparent; display:flex; justify-content:space-between; align-items:center; gap: 10px;">
            ${s.cover ? `<img src="${s.cover}" style="width:36px;height:36px;border-radius:4px;object-fit:cover;flex-shrink:0;">` : `<div style="width:36px;height:36px;border-radius:4px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;flex-shrink:0;"><i class="fa-solid fa-music" style="font-size:14px;color:rgba(255,255,255,0.3)"></i></div>`}
            <div style="min-width:0;flex:1;">
                <strong style="font-size:12px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:rgba(255,255,255,0.95);">${escapeHtml(s.titulo)}</strong>
                <div class="muted" style="font-size:11px;color:rgba(232,234,237,0.6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(s.artista||'Desconocido')}</div>
            </div>
            <div style="font-size:10px;color:rgba(255,255,255,0.8);background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:10px;font-weight:600;flex-shrink:0;">${(s.similarity*100).toFixed(0)}%</div>
        </div>`).join('');
        relatedDiv.innerHTML = html;
        
        // Add click listeners to similar items
        relatedDiv.querySelectorAll('.similar-item').forEach(item => {
            item.addEventListener('click', ()=>{
                const id = parseInt(item.dataset.cancionId);
                const song = {
                    id: id,
                    titulo: item.dataset.titulo,
                    artista: item.dataset.artista,
                    audio: `/audio/${id}`,
                    cover: `/album-art/${id}`,
                    lyrics: `/lyrics/${id}`
                };
                sendToPlayer({type:'playSong', song});
            });
            item.addEventListener('mouseenter', ()=> item.style.background = 'rgba(255,64,64,0.1)');
            item.addEventListener('mouseleave', ()=> item.style.background = 'rgba(255,255,255,0.03)');
        });
    }

    function highlightLyricAt(time){
        const L = window._currentLyrics;
        if (!L || !L.cues || L.cues.length===0) return;
        // find largest cue.start <= time
        let idx = -1;
        for (let i=0;i<L.cues.length;i++){
            if (time >= L.cues[i].start) idx = i; else break;
        }
        if (idx === L.index) return; // no change
        // update DOM
        const container = document.querySelector('#lyrics-content-panel .lyrics-lines');
        if (!container) return;
        if (L.index >= 0){
            const prev = container.querySelector('[data-index="'+L.index+'"]');
            if (prev) prev.classList.remove('active');
        }
        const el = container.querySelector('[data-index="'+idx+'"]');
        if (el){ el.classList.add('active'); el.scrollIntoView({behavior:'smooth', block:'center'}); }
        L.index = idx;
    }

    // handle periodic time updates from iframe
    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        const msg = event.data || {};
        if (msg.type === 'timeupdate' && typeof msg.currentTime === 'number'){
            highlightLyricAt(msg.currentTime);
            // Update progress bar
            updateProgressBar(msg.currentTime, msg.duration || 0);
        }
        if (msg.type === 'volumeChange' && typeof msg.volume === 'number'){
            const volSlider = document.getElementById('volume-slider');
            if (volSlider) volSlider.value = msg.volume;
            updateVolumeIcon(msg.volume);
        }
        if (msg.type === 'shuffleChange'){
            updateShuffleRepeatUI(msg.shuffled, null);
        }
        if (msg.type === 'repeatChange'){
            updateShuffleRepeatUI(null, msg.repeat);
        }
    });

    function formatTime(seconds){
        if (!Number.isFinite(seconds)) return '0:00';
        const s = Math.floor(seconds);
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${String(sec).padStart(2, '0')}`;
    }

    let _currentDuration = 0; // duración actual de la canción

    function updateProgressBar(currentTime, duration){
        _currentDuration = duration;
        const progressBar = document.getElementById('mini-progress-bar');
        const timeCurrent = document.getElementById('mini-time-current');
        const timeDuration = document.getElementById('mini-time-duration');
        if (progressBar){
            const pct = duration > 0 ? (currentTime / duration) * 100 : 0;
            progressBar.style.width = pct + '%';
        }
        if (timeCurrent) timeCurrent.textContent = formatTime(currentTime);
        if (timeDuration) timeDuration.textContent = formatTime(duration);
    }

    function seekViaProgressBar(event){
        const container = document.getElementById('mini-progress-container');
        if (!container) return;
        const rect = container.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const pct = Math.max(0, Math.min(1, clickX / rect.width));
        const seekTime = pct * (_currentDuration || 100);
        sendToPlayer({type:'command', cmd:'seekTo', seconds: seekTime});
    }

    function initRightPanel(){
        // Reinitialize right panel tabs listeners
        const tabs = document.querySelectorAll('#right-panel .tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', ()=> selectRightTab(tab.dataset.tab));
        });
        
        // Restore active tab (default: lyrics)
        const activeTab = window._activeRightTab || 'lyrics';
        selectRightTab(activeTab);
        
        // Restore lyrics if they were previously loaded
        const lyricsPanel = document.getElementById('lyrics-content-panel');
        if (lyricsPanel && window._currentLyrics && window._currentLyrics.cues){
            renderLyrics(window._currentLyrics.cues, window._currentLyrics.songId);
        }
        
        // Restore upnext if it was previously loaded
        const upnextDiv = document.getElementById('upnext-content');
        if (upnextDiv && window._currentUpNext){
            const items = window._currentUpNext;
            if (items.length === 0) {
                upnextDiv.innerHTML = '<p class="muted">No hay canciones en cola</p>';
            } else {
                renderUpNextList(upnextDiv, items);
                // Add click listeners to upnext items
                upnextDiv.querySelectorAll('.upnext-item').forEach(item => {
                    item.addEventListener('click', ()=>{
                        const id = parseInt(item.dataset.id);
                        const song = {
                            id: id,
                            titulo: item.querySelector('strong').textContent,
                            artista: item.querySelector('.muted').textContent,
                            audio: `/audio/${id}`,
                            cover: `/album-art/${id}`,
                            lyrics: `/lyrics/${id}`
                        };
                        sendToPlayer({type:'playSong', song});
                    });
                    item.addEventListener('mouseenter', ()=> item.style.background = 'rgba(255,64,64,0.1)');
                    item.addEventListener('mouseleave', ()=> item.style.background = 'rgba(255,255,255,0.02)');
                });
            }
        }
        
        // Restore similar if they were previously loaded
        const relatedDiv = document.getElementById('related-content');
        if (relatedDiv && window._currentSimilar && window._currentSimilar.length > 0){
            renderSimilar(window._currentSimilar);
        }
        
        // Rebind click en letra
        if (lyricsPanel){
            lyricsPanel.addEventListener('click', (ev)=>{
                const line = ev.target.closest('.lyric-line');
                if (!line) return;
                const t = parseFloat(line.dataset.start);
                if (isNaN(t)) return;
                sendToPlayer({type:'command', cmd:'seekTo', seconds: t});
            });
        }
        
        // Rebind progress bar click
        const progressContainer = document.getElementById('mini-progress-container');
        if (progressContainer){
            progressContainer.addEventListener('click', seekViaProgressBar);
        }
    }

    function updateShuffleRepeatUI(shuffled, repeat){
        const btnShuffle = document.getElementById('mini-shuffle');
        const btnRepeat = document.getElementById('mini-repeat');
        if (btnShuffle){
            btnShuffle.style.color = shuffled ? 'var(--accent)' : '';
            btnShuffle.style.opacity = shuffled ? '1' : '';
        }
        if (btnRepeat){
            const colors = {'none': '', 'one': 'var(--accent)', 'all': 'var(--accent)'};
            btnRepeat.style.color = colors[repeat] || '';
            btnRepeat.style.opacity = repeat !== 'none' ? '1' : '';
        }
    }

    function updateVolumeIcon(value){
        const icon = document.getElementById('volume-icon');
        if (!icon) return;
        if (value === 0 || value === '0') icon.className = 'fa-solid fa-volume-xmark';
        else if (value < 0.5) icon.className = 'fa-solid fa-volume-low';
        else icon.className = 'fa-solid fa-volume-high';
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindSongCards();
        initRightPanel();
        
        // Mini-player controls
        const btnPlay = document.getElementById('mini-play');
        const btnNext = document.getElementById('mini-next');
        const btnPrev = document.getElementById('mini-prev');
        const btnBack10 = document.getElementById('mini-back10');
        const btnForward10 = document.getElementById('mini-forward10');
        const btnShuffle = document.getElementById('mini-shuffle');
        const btnRepeat = document.getElementById('mini-repeat');
        const btnLike = document.getElementById('btn-like');
        const btnQueue = document.getElementById('btn-queue');
        const volSlider = document.getElementById('volume-slider');
        const volIcon = document.getElementById('volume-icon');

        if (btnPlay) btnPlay.addEventListener('click', ()=>{ tryUnlockAudio(); sendToPlayer({type:'command', cmd:'toggle'}); });
        if (btnNext) btnNext.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'next'}));
        if (btnPrev) btnPrev.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'prev'}));
        if (btnBack10) btnBack10.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'seek', seconds:-10}));
        if (btnForward10) btnForward10.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'seek', seconds:10}));
        
        // Shuffle toggle
        if (btnShuffle) btnShuffle.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'shuffle'}));
        
        // Repeat toggle (none → one → all)
        if (btnRepeat) btnRepeat.addEventListener('click', ()=> sendToPlayer({type:'command', cmd:'repeat'}));
        
        // Like button toggle — llama a la API
        if (btnLike) {
            btnLike.addEventListener('click', function(){
                const songIdEl = document.getElementById('mini-title');
                if (!songIdEl || !songIdEl.dataset.songId) return;
                const cancionId = parseInt(songIdEl.dataset.songId);
                if (!cancionId) return;

                const icon = this.querySelector('i');
                fetch('/api/favoritos/toggle/' + cancionId, {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.liked) {
                            icon.className = 'fa-solid fa-heart';
                            btnLike.style.color = 'var(--accent)';
                            icon.style.color = 'var(--accent)';
                        } else {
                            icon.className = 'fa-regular fa-heart';
                            btnLike.style.color = '';
                            icon.style.color = '';
                        }
                    })
                    .catch(() => {});
            });
        }
        
        // Queue button – scrolls the right panel to "upnext" tab
        if (btnQueue) {
            btnQueue.addEventListener('click', ()=>{
                const tab = document.querySelector('#right-panel .tab[data-tab="upnext"]');
                if (tab) tab.click();
            });
        }
        
        // Volume slider
        if (volSlider) {
            volSlider.addEventListener('input', function(){
                const val = parseFloat(this.value);
                updateVolumeIcon(val);
                sendToPlayer({type:'command', cmd:'volume', value: val});
            });
        }
        
        // Volume icon click toggles mute
        if (volIcon) {
            volIcon.addEventListener('click', function(){
                sendToPlayer({type:'command', cmd:'toggleMute'});
            });
        }
        
        // Re-bind after SPA navigation
        window.initPageBindings = function(){ 
            bindSongCards(); 
            initRightPanel();
            // Solicitar estado actual al reproductor para refrescar indicadores
            sendToPlayer({type:'command', cmd:'getState'});
        };
    });
})();
