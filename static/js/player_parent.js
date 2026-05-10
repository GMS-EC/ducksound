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
            <button type="button" data-action="add-fav"><i class="fa-regular fa-heart"></i><span>Añadir a favoritos</span></button>
            <button type="button" data-action="add-playlist"><i class="fa-solid fa-plus"></i><span>Añadir a playlist</span></button>
            <div class="context-divider"></div>
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
            } else if (action === 'add-fav') {
                fetch('/api/favoritos/toggle/' + song.id, {method:'POST'}).then(r=>r.json()).then(d=>{
                    const label = button.querySelector('span');
                    if (label) label.textContent = d.liked ? 'Quitar de favoritos' : 'Añadir a favoritos';
                    button.querySelector('i').className = d.liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                });
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
            ctx.resume().then(()=>{ window._audioUnlocked = true; try{ ctx.close(); }catch(e){} }).catch(()=>{});
        }catch(e){}
    }

    function loadArtistPlaylist(artistId, songId){
        fetch(`/api/artist/${artistId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                sendToPlayer({type:'setPlaylist', playlist: songs});
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong) sendToPlayer({type:'playSong', song: clickedSong});
            })
            .catch(err => {
                console.error('Error loading artist playlist:', err);
                const song = { id: songId, titulo: 'Unknown', audio: `/audio/${songId}` };
                sendToPlayer({type:'playSong', song});
            });
    }

    function loadAlbumPlaylist(albumId, songId){
        fetch(`/api/album/${albumId}/canciones`)
            .then(r => r.json())
            .then(songs => {
                sendToPlayer({type:'setPlaylist', playlist: songs});
                const clickedSong = songs.find(s => s.id === songId);
                if (clickedSong) sendToPlayer({type:'playSong', song: clickedSong});
            })
            .catch(err => {
                console.error('Error loading album playlist:', err);
                const song = { id: songId, titulo: 'Unknown', audio: `/audio/${songId}` };
                sendToPlayer({type:'playSong', song});
            });
    }

    // MAIN MESSAGE HANDLER
    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        const data = event.data || {};
        
        // Dynamic Theme Colors
        if (data.type === 'themeColor' && data.color) {
            let [r, g, b] = data.color;
            const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
            if (luminance < 80) {
                const factor = 90 / Math.max(luminance, 1);
                r = Math.min(255, Math.round(r * factor));
                g = Math.min(255, Math.round(g * factor));
                b = Math.min(255, Math.round(b * factor));
            } else if (luminance > 180) {
                const factor = 160 / luminance;
                r = Math.round(r * factor);
                g = Math.round(g * factor);
                b = Math.round(b * factor);
            }
            document.documentElement.style.setProperty('--accent', `rgb(${r}, ${g}, ${b})`);
            document.documentElement.style.setProperty('--accent-soft', `rgba(${r}, ${g}, ${b}, 0.15)`);
            document.documentElement.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.3)`);
        }

        // Periodic time updates
        if (data.type === 'timeupdate' && typeof data.currentTime === 'number'){
            highlightLyricAt(data.currentTime);
            updateProgressBar(data.currentTime, data.duration || 0);
        }

        // Volume updates
        if (data.type === 'volumeChange' && typeof data.volume === 'number'){
            const volSlider = document.getElementById('volume-slider');
            if (volSlider) volSlider.value = data.volume;
            updateVolumeIcon(data.volume);
        }

        // Shuffle/Repeat updates
        if (data.type === 'shuffleChange') updateShuffleRepeatUI(data.shuffled, null);
        if (data.type === 'repeatChange') updateShuffleRepeatUI(null, data.repeat);

        // Player State updates
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
                const lyricsScroll = lyricsPanel ? lyricsPanel.querySelector('.lyrics-content-scroll') : null;
                if (lyricsPanel && lyricsScroll){
                    if (song && song.lyrics){
                        fetch(song.lyrics).then(r=> r.ok ? r.text() : Promise.reject())
                        .then(txt=>{
                            const cues = parseLRC(txt);
                            renderLyrics(cues, song.id);
                            if (window._activeRightTab !== 'upnext') selectRightTab('lyrics');
                        }).catch(()=>{
                            lyricsScroll.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Letra no encontrada</p>';
                            window._currentLyrics = null;
                        });
                    } else {
                        lyricsScroll.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Selecciona una canción</p>';
                    }
                }

                // Update similar
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

                // Mini-player UI
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
            updateProgressBar(0, 0);

            // Sync playback indicators (EQ animation and active highlights)
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

            // Update upnext
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

            // Play/Pause icon
            const miniPlay = document.getElementById('mini-play');
            if (miniPlay && miniPlay.querySelector('i')) {
                miniPlay.querySelector('i').className = st.isPlaying ? 'fa-solid fa-pause' : 'fa-solid fa-play';
            }
            updateShuffleRepeatUI(st.shuffled, st.repeat);
            const volSlider = document.getElementById('volume-slider');
            if (volSlider && typeof st.volume === 'number'){ volSlider.value = st.volume; updateVolumeIcon(st.volume); }
        }
    });

    function selectRightTab(name){
        document.querySelectorAll('#right-panel .tab').forEach(b=>b.classList.toggle('active', b.dataset.tab===name));
        document.querySelectorAll('#right-panel .tab-content').forEach(c=>c.classList.toggle('active', c.id===name+'-content' || (name==='lyrics' && c.id==='lyrics-content-panel')));
        window._activeRightTab = name;
    }

    function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

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
            if (tags.length) for (const t of tags) cues.push({start: t, text: text});
            else if (raw.trim()) cues.push({start: 0, text: raw.trim()});
        }
        return cues.sort((a,b)=>a.start - b.start);
    }

    function updateTranslateBtn(enabled) {
        const btn = document.getElementById('btn-translate-lyrics');
        if (!btn) return;
        btn.disabled = !enabled;
        // No sobrescribir "Traducido" si ya lo está
        if (enabled && btn.innerHTML.includes('Traducido')) return;
        btn.innerHTML = '<i class="fa-solid fa-language"></i> Traducir';
        btn.style.opacity = enabled ? '1' : '0.4';
    }

    function renderLyrics(cues, songId){
        const lyricsPanel = document.getElementById('lyrics-content-panel');
        if (!lyricsPanel) return;
        const scrollDiv = lyricsPanel.querySelector('.lyrics-content-scroll');
        if (!scrollDiv) return;
        
        // Si ya tenemos traducción cacheada para esta misma canción, no re-renderizar
        if (window._translatedHtml && window._currentLyrics && window._currentLyrics.songId === songId) {
            return;
        }
        window._translatedHtml = null; // Limpiar para canción nueva
        
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
    }

    function translateLyrics(cues){
        const btn = document.getElementById('btn-translate-lyrics');
        if (!btn) return;
        
        // Verificar que las cues sigan siendo válidas
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
                const html = cues.map((c,i)=> `<div class="lyric-line" data-start="${c.start}" data-index="${i}"><div class="lyric-main-text">${escapeHtml(c.text)}</div><div class="lyric-subline">${escapeHtml(lines[i]||'')}</div></div>`).join('');
                linesDiv.innerHTML = html;
                window._translatedHtml = html;
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
        relatedDiv.querySelectorAll('.similar-item').forEach(item => {
            item.addEventListener('click', ()=>{
                const id = parseInt(item.dataset.cancionId);
                sendToPlayer({type:'playSong', song: {id, titulo: item.dataset.titulo, artista: item.dataset.artista, audio:`/audio/${id}`}});
            });
        });
    }

    function highlightLyricAt(time){
        const L = window._currentLyrics;
        if (!L || !L.cues) return;
        let idx = -1;
        for (let i=0;i<L.cues.length;i++) if (time >= L.cues[i].start) idx = i; else break;
        if (idx === L.index) return;
        const container = document.querySelector('.lyrics-lines');
        if (!container) return;
        if (L.index >= 0) { const p = container.querySelector(`[data-index="${L.index}"]`); if (p) p.classList.remove('active'); }
        const el = container.querySelector(`[data-index="${idx}"]`);
        if (el){ el.classList.add('active'); el.scrollIntoView({behavior:'smooth', block:'center'}); }
        L.index = idx;
    }

    function formatTime(s){ if (!Number.isFinite(s)) return '0:00'; const min = Math.floor(s/60), sec = Math.floor(s%60); return `${min}:${String(sec).padStart(2,'0')}`; }

    let _currentDuration = 0;
    function updateProgressBar(cur, dur){
        _currentDuration = dur;
        const bar = document.getElementById('mini-progress-bar'), tCur = document.getElementById('mini-time-current'), tDur = document.getElementById('mini-time-duration');
        if (bar) bar.style.width = (dur > 0 ? (cur/dur)*100 : 0) + '%';
        if (tCur) tCur.textContent = formatTime(cur);
        if (tDur) tDur.textContent = formatTime(dur);

        // Update circular progress for active track item
        const activeTrack = document.querySelector('.track-item.playing');
        if (activeTrack) {
            const circle = activeTrack.querySelector('.progress-ring__circle');
            if (circle) {
                const circumference = 2 * Math.PI * 12; // r=12
                const offset = circumference - (dur > 0 ? (cur / dur) : 0) * circumference;
                circle.style.strokeDashoffset = offset;
            }
            // Update time text next to animation
            const timeText = activeTrack.querySelector('.duration-text');
            if (timeText) {
                timeText.textContent = formatTime(dur);
            }
        }
    }

    function seekViaProgressBar(e){
        const container = document.getElementById('mini-progress-container'); if (!container) return;
        const pct = (e.clientX - container.getBoundingClientRect().left) / container.offsetWidth;
        sendToPlayer({type:'command', cmd:'seekTo', seconds: pct * (_currentDuration || 0)});
    }

    function initRightPanel(){
        document.querySelectorAll('#right-panel .tab').forEach(t => t.addEventListener('click', ()=> selectRightTab(t.dataset.tab)));
        selectRightTab(window._activeRightTab || 'lyrics');
        if (window._currentLyrics) {
            const scrollDiv = document.querySelector('.lyrics-content-scroll');
            // Restaurar traducción cachead si existe
            if (window._translatedHtml && scrollDiv) {
                scrollDiv.innerHTML = '<div class="lyrics-lines">' + window._translatedHtml + '</div>';
                const btn = document.getElementById('btn-translate-lyrics');
                if (btn) { btn.innerHTML = '<i class="fa-solid fa-language"></i> Traducido'; btn.disabled = false; }
            } else {
                renderLyrics(window._currentLyrics.cues, window._currentLyrics.songId);
            }
        } else updateTranslateBtn(false);
        if (window._currentUpNext) renderUpNextList(document.getElementById('upnext-content'), window._currentUpNext);
        if (window._currentSimilar) renderSimilar(window._currentSimilar);
        const lP = document.getElementById('lyrics-content-panel');
        if (lP) lP.addEventListener('click', (ev)=>{
            const line = ev.target.closest('.lyric-line');
            if (line) sendToPlayer({type:'command', cmd:'seekTo', seconds: parseFloat(line.dataset.start)});
        });
        const pC = document.getElementById('mini-progress-container');
        if (pC) pC.addEventListener('click', seekViaProgressBar);
    }

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
            // fa-repeat-1 no existe en Font Awesome Free, usar alternativa
            bR.querySelector('i').className = 'fa-solid fa-repeat';
            // Badge "1" solo para repeat-one
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

    function updateVolumeIcon(v){
        const i = document.getElementById('volume-icon'); if (!i) return;
        i.className = v == 0 ? 'fa-solid fa-volume-xmark' : (v < 0.5 ? 'fa-solid fa-volume-low' : 'fa-solid fa-volume-high');
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindSongCards(); initRightPanel();
        
        // Cachear idioma del usuario para traducción
        fetch('/api/profile').then(r=>r.json()).then(p=>{
            window._userLang = p.idioma_preferido || 'es';
        }).catch(()=>{ window._userLang = 'es'; });
        
        const ctrls = {
            'mini-play': ()=> { tryUnlockAudio(); sendToPlayer({type:'command', cmd:'toggle'}); },
            'mini-next': ()=> sendToPlayer({type:'command', cmd:'next'}),
            'mini-prev': ()=> sendToPlayer({type:'command', cmd:'prev'}),
            'mini-back10': ()=> sendToPlayer({type:'command', cmd:'seek', seconds:-10}),
            'mini-forward10': ()=> sendToPlayer({type:'command', cmd:'seek', seconds:10}),
            'mini-shuffle': ()=> sendToPlayer({type:'command', cmd:'shuffle'}),
            'mini-repeat': ()=> sendToPlayer({type:'command', cmd:'repeat'}),
            'volume-icon': ()=> sendToPlayer({type:'command', cmd:'toggleMute'})
        };
        for (let id in ctrls) { const el = document.getElementById(id); if (el) el.addEventListener('click', ctrls[id]); }
        const vS = document.getElementById('volume-slider');
        if (vS) vS.addEventListener('input', function(){ updateVolumeIcon(this.value); sendToPlayer({type:'command', cmd:'volume', value: parseFloat(this.value)}); });
        
        // Botón de traducir letras (permanente)
        const btnTrans = document.getElementById('btn-translate-lyrics');
        if (btnTrans) {
            btnTrans.addEventListener('click', function(){
                const L = window._currentLyrics;
                if (L && L.cues && L.cues.length > 0) {
                    translateLyrics(L.cues);
                } else {
                    // Feedback visual: flash el botón para indicar que no hay letras
                    btnTrans.style.borderColor = 'var(--accent)';
                    setTimeout(() => { btnTrans.style.borderColor = ''; }, 1000);
                }
            });
        }

        window.initPageBindings = function(){
            bindSongCards(); initRightPanel();
            if (window._currentSongId) {
                document.querySelectorAll('.track-item.playing, .song-card.playing').forEach(el=> el.classList.remove('playing'));
                const it = document.querySelector(`.track-item[data-cancion-id="${window._currentSongId}"], .song-card[data-cancion-id="${window._currentSongId}"]`);
                if (it) it.classList.add('playing');
            }
            sendToPlayer({type:'command', cmd:'getState'});
        };
    });
})();
