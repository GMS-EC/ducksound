// Entorno de ejecución del Reproductor (Iframe Sandbox)
// Este script corre en un entorno aislado (iframe) para proteger el contexto de audio principal
// y evitar interrupciones de reproducción al navegar por la SPA.
(function(){
    // =========================================================================
    // 1. CONSTRUCCIÓN DE LA INTERFAZ DE USUARIO (DOM) DENTRO DEL IFRAME
    // =========================================================================
    document.body.style.margin = '0';
    const container = document.createElement('div');
    container.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--surface);color:var(--text);height:100%;box-sizing:border-box;border-top:1px solid rgba(0,0,0,0.08);';

    // Contenedor para la portada del álbum
    const cover = document.createElement('div');
    cover.style.cssText = 'width:56px;height:56px;background:#222;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px';
    cover.textContent = '🎵';

    // Contenedor para metadatos del tema actual
    const meta = document.createElement('div');
    meta.style.cssText = 'flex:1;min-width:0';
    const titleEl = document.createElement('div');
    titleEl.style.fontWeight = '600';
    titleEl.textContent = 'Sin canción seleccionada';
    const artistEl = document.createElement('div');
    artistEl.style.fontSize = '12px';
    artistEl.style.color = 'rgba(255,255,255,0.7)';
    artistEl.textContent = '';
    meta.appendChild(titleEl); meta.appendChild(artistEl);

    // Controles físicos del reproductor embebido
    const controls = document.createElement('div');
    controls.style.display = 'flex'; controls.style.gap='8px';
    const btnPrev = document.createElement('button'); btnPrev.textContent='⏮';
    const btnPlay = document.createElement('button'); btnPlay.textContent='▶';
    const btnNext = document.createElement('button'); btnNext.textContent='⏭';
    controls.appendChild(btnPrev); controls.appendChild(btnPlay); controls.appendChild(btnNext);

    container.appendChild(cover); container.appendChild(meta); container.appendChild(controls);
    document.body.appendChild(container);

    // =========================================================================
    // 2. CONFIGURACIÓN DE WEB AUDIO API Y SISTEMA DE BUFFER DUAL (GAPLESS)
    // =========================================================================
    // El Buffer Dual utiliza dos elementos de audio independientes que se alternan.
    // Esto permite cargar en segundo plano la siguiente canción antes de que termine
    // la actual, garantizando transiciones cruzadas (crossfade) perfectas.
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContext();

    // Crear los dos elementos de audio HTML5 de forma programática
    const audio1 = document.createElement('audio'); audio1.preload='auto'; audio1.crossOrigin='anonymous'; audio1.style.cssText='position:fixed;left:-9999px;width:0;height:0;opacity:0'; document.body.appendChild(audio1);
    const audio2 = document.createElement('audio'); audio2.preload='auto'; audio2.crossOrigin='anonymous'; audio2.style.cssText='position:fixed;left:-9999px;width:0;height:0;opacity:0'; document.body.appendChild(audio2);

    // Enlazar las fuentes de los elementos HTML5 al flujo gráfico de Web Audio API
    const source1 = audioCtx.createMediaElementSource(audio1);
    const source2 = audioCtx.createMediaElementSource(audio2);
    
    // Nodos de Ganancia independientes para controlar los volumenes individuales (fundidos)
    const gainNode1 = audioCtx.createGain();
    const gainNode2 = audioCtx.createGain();
    
    // Nodo de Ganancia maestro para el control de volumen global del reproductor
    const masterGain = audioCtx.createGain();

    // Estructura de conexiones del grafo de audio:
    // audio1 -> source1 -> gainNode1 -\
    //                                  +-> masterGain -> Altavoces (audioCtx.destination)
    // audio2 -> source2 -> gainNode2 -/
    source1.connect(gainNode1); gainNode1.connect(masterGain);
    source2.connect(gainNode2); gainNode2.connect(masterGain);
    masterGain.connect(audioCtx.destination);

    // Punteros dinámicos para conmutar entre el reproductor ACTIVO y el SIGUIENTE
    let activeAudio = audio1;
    let activeGain = gainNode1;
    let nextAudio = audio2;
    let nextGain = gainNode2;

    // =========================================================================
    // 3. ESTADOS DE LA MÁQUINA DE REPRODUCCIÓN
    // =========================================================================
    let playlist = [];
    let queuedSongs = [];
    let currentIndex = -1;
    let isPlaying = false;
    let isShuffled = false;
    let shuffledOrder = [];
    let repeatMode = 'none'; // 'none', 'one', 'all'
    let _lastSentTime = 0;
    let _volume = 1.0;
    let _lastVolumeBeforeMute = 1.0;
    let crossfadeEnabled = true;
    let crossfadeDuration = 3; // segundos
    let nextSongPrepared = false;
    let crossfadeTriggered = false;
    let _seekTo = 0;
    let _seekListener = null;

    // Aplicar curva exponencial al volumen maestro para una respuesta perceptiva natural
    masterGain.gain.value = _volume * _volume;

    function savePlayerState(updates) {
        try {
            const saved = JSON.parse(localStorage.getItem('player_state') || '{}');
            const newState = { ...saved, ...updates };
            localStorage.setItem('player_state', JSON.stringify(newState));
        } catch (e) {
            console.error('[Player] Error saving state:', e);
        }
    }

    function clampVolume(value) {
        const n = Number(value);
        return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 1.0;
    }

    function applyMasterVolume(value, options = {}) {
        const vol = clampVolume(value);
        _volume = vol;
        masterGain.gain.value = vol * vol;

        if (vol > 0) _lastVolumeBeforeMute = vol;
        if (options.persist) {
            savePlayerState({
                volume: _volume,
                prevVolume: _lastVolumeBeforeMute
            });
        }
        if (options.notify) {
            parent.postMessage({type:'volumeChange', volume: _volume}, window.location.origin);
        }
    }

    function normalizeSong(song){
        if (!song) return song;
        const normalized = {...song};
        if ((!normalized.cover || String(normalized.cover).trim() === '') && normalized.id){
            normalized.cover = `/album-art/${normalized.id}`;
        }
        if ((!normalized.lyrics || String(normalized.lyrics).trim() === '') && normalized.id){
            normalized.lyrics = `/lyrics/${normalized.id}`;
        }
        if ((!normalized.audio || String(normalized.audio).trim() === '') && normalized.id){
            normalized.audio = `/audio/${normalized.id}`;
        }
        return normalized;
    }

    function persistQueue(){
        try{ localStorage.setItem('player_queue', JSON.stringify(queuedSongs)); }catch(e){}
    }

    function placeQueuedSongAfterCurrent(song){
        const queued = normalizeSong(song);
        if (!queued || !queued.id) return currentIndex;

        const existingIdx = playlist.findIndex(s => s && s.id === queued.id);
        if (existingIdx !== -1) return existingIdx;

        const insertAt = Math.max(0, currentIndex + 1);
        playlist.splice(insertAt, 0, queued);
        if (insertAt <= currentIndex) currentIndex += 1;
        return insertAt;
    }

    function getNextIndex(options = {}){
        if (repeatMode === 'one') return currentIndex;
        if (queuedSongs.length > 0){
            const nextQueued = options.consumeQueue ? queuedSongs.shift() : queuedSongs[0];
            if (options.consumeQueue) persistQueue();
            return placeQueuedSongAfterCurrent(nextQueued);
        }
        if (isShuffled){
            if (!shuffledOrder.length) rebuildShuffleOrder();
            const nextIdx = shuffledOrder[0] ?? currentIndex;
            if (options.consumeQueue && shuffledOrder.length) shuffledOrder.shift();
            return nextIdx;
        }
        const nextIdx = currentIndex + 1;
        if (repeatMode === 'none' && nextIdx >= playlist.length) return currentIndex;
        return nextIdx % playlist.length;
    }

    function rebuildShuffleOrder(){
        if (!playlist.length) { shuffledOrder = []; return; }
        shuffledOrder = [];
        for (let i = 0; i < playlist.length; i++){
            if (i !== currentIndex) shuffledOrder.push(i);
        }
        for (let i = shuffledOrder.length - 1; i > 0; i--){
            const j = Math.floor(Math.random() * (i + 1));
            [shuffledOrder[i], shuffledOrder[j]] = [shuffledOrder[j], shuffledOrder[i]];
        }
    }

    /**
     * Consulta el nivel de ganancia acústico (ReplayGain) y ajusta el volumen para estandarizar a -14 dBFS.
     */
    async function fetchReplayGain(songId) {
        try {
            const res = await fetch('/api/audio-info/' + songId);
            const data = await res.json();
            if (data.rms_level != null) {
                const offset_db = -14 - data.rms_level;
                const safe_offset = Math.min(offset_db, 12);
                return Math.pow(10, safe_offset / 20);
            }
        } catch(e) {}
        return 1.0;
    }

    function extractColor(coverUrl) {
        if (!window.ColorThief || !coverUrl) return;
        const img = new Image();
        img.crossOrigin = 'Anonymous';
        img.onload = () => {
            try {
                const colorThief = new ColorThief();
                const color = colorThief.getColor(img);
                window.parent.postMessage({type: 'themeColor', color: color}, '*');
            } catch(e) {}
        };
        img.src = coverUrl;
    }

    /**
     * Función que activa y reproduce un tema, gestionando el crossfade entre el buffer activo y el siguiente.
     */
    async function playIndex(idx, isCrossfading = false){
        if (idx < 0 || idx >= playlist.length) return;
        
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }

        const s = normalizeSong(playlist[idx]);
        playlist[idx] = s;

        if (isShuffled) {
            const pos = shuffledOrder.indexOf(idx);
            if (pos !== -1) shuffledOrder.splice(pos, 1);
        }

        titleEl.textContent = s.titulo || 'Sin título';
        artistEl.textContent = s.artista || '';
        if (s.cover) {
            cover.innerHTML = `<img src="${s.cover}" style="width:100%;height:100%;object-fit:cover;border-radius:6px">`;
            extractColor(s.cover);
        } else {
            cover.innerHTML = '🎵';
            window.parent.postMessage({type: 'themeColor', color: [30, 215, 96]}, '*');
        }

        const replayGainPromise = fetchReplayGain(s.id);
        replayGainPromise.then(gain => {
            activeGain.gain.setTargetAtTime(gain, audioCtx.currentTime, 1.5);
        });

        if (_seekListener) {
            activeAudio.removeEventListener('loadedmetadata', _seekListener);
            _seekListener = null;
        }

        if (!isCrossfading) {
            // Si el siguiente audio ya está preparado con esta misma canción,
            // simplemente conmutamos para aprovechar la precarga gapless
            if (nextSongPrepared && nextAudio.src && nextAudio.src.includes(s.audio)) {
                const tempA = activeAudio; activeAudio = nextAudio; nextAudio = tempA;
                const tempG = activeGain; activeGain = nextGain; nextGain = tempG;
                
                activeGain.gain.setValueAtTime(1.0, audioCtx.currentTime);
                activeAudio.play().catch(()=>{});
                nextAudio.pause();
            } else {
                activeAudio.pause();
                activeAudio.src = s.audio;
                activeGain.gain.setValueAtTime(1.0, audioCtx.currentTime);
                activeAudio.play().catch(()=>{});
            }
            currentIndex = idx;
        } else {
            // TRANSICIÓN CRUZADA (CROSSFADE): Conmutar nodos y aplicar fundidos (fades)
            const tempA = activeAudio; activeAudio = nextAudio; nextAudio = tempA;
            const tempG = activeGain; activeGain = nextGain; nextGain = tempG;

            activeAudio.play().catch(()=>{});
            
            // Fade out canción antigua
            nextGain.gain.setTargetAtTime(0, audioCtx.currentTime, crossfadeDuration / 3);
            setTimeout(() => { nextAudio.pause(); }, crossfadeDuration * 1000);
            
            // Fade in canción nueva hasta alcanzar ReplayGain
            activeGain.gain.setValueAtTime(0, audioCtx.currentTime);
            activeGain.gain.setTargetAtTime(1.0, audioCtx.currentTime, crossfadeDuration / 3);
            currentIndex = idx;
        }

        _lastSentTime = 0;
        isPlaying = true;
        btnPlay.textContent = '⏸';
        crossfadeTriggered = false;
        nextSongPrepared = false;
        
        try{
            const saved = JSON.parse(localStorage.getItem('player_state')||'{}');
            saved.currentIndex = currentIndex;
            saved.currentTime = 0;
            localStorage.setItem('player_state', JSON.stringify(saved));
        }catch(e){}
        
        updateMediaSession(s);
        postState();

        try { fetch('/api/play/' + s.id, {method: 'POST'}); } catch(e) {}
    }

    function prepareNextSong() {
        if (nextSongPrepared || playlist.length === 0) return;
        const nextIdx = getNextIndex();
        const nextS = normalizeSong(playlist[nextIdx]);
        nextAudio.src = nextS.audio;
        nextSongPrepared = true;
    }

    function postState(){
        const nextSongs = [];
        try{
            const queuedIds = new Set();
            const currentSong = normalizeSong(playlist[currentIndex] || null);
            if (currentSong && currentSong.id) {
                nextSongs.push({id: currentSong.id, titulo: currentSong.titulo, artista: currentSong.artista, cover: currentSong.cover, current: true});
                queuedIds.add(currentSong.id);
            }
            queuedSongs.forEach(song => {
                const s = normalizeSong(song);
                if (!s || !s.id || queuedIds.has(s.id)) return;
                queuedIds.add(s.id);
                nextSongs.push({id: s.id, titulo: s.titulo, artista: s.artista, cover: s.cover, queued: true});
            });
            const maxTotal = 20;
            if (isShuffled){
                if (!shuffledOrder.length) rebuildShuffleOrder();
                for (let i = 0; i < shuffledOrder.length; i++){
                    const idx = shuffledOrder[i];
                    const s = normalizeSong(playlist[idx]);
                    if (!s) continue;
                    if (queuedIds.has(s.id)) continue;
                    nextSongs.push({id: s.id, titulo: s.titulo, artista: s.artista, cover: s.cover});
                    if (nextSongs.length >= maxTotal) break;
                }
            } else {
                for(let i=1;i<=maxTotal;i++){
                    const idx = currentIndex + i;
                    if (idx >= playlist.length) break;
                    const s = normalizeSong(playlist[idx]);
                    if (!s) break;
                    if (queuedIds.has(s.id)) continue;
                    nextSongs.push({id: s.id, titulo: s.titulo, artista: s.artista, cover: s.cover});
                    if (nextSongs.length >= maxTotal) break;
                }
            }
        }catch(e){}
        const currentSong = normalizeSong(playlist[currentIndex] || null);
        if ('mediaSession' in navigator) {
            navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused';
        }
        const currentTime = activeAudio.currentTime || _seekTo || 0;
        const duration = activeAudio.duration || 0;
        parent.postMessage({type:'state', state:{currentIndex, isPlaying, song: currentSong, upnext: nextSongs, shuffled: isShuffled, repeat: repeatMode, volume: _volume, currentTime, duration}}, window.location.origin);
    }

    // =========================================================================
    // 4. CONTROLADORES DE EVENTOS Y BINDINGS DE AUDIO
    // =========================================================================
    btnPlay.addEventListener('click', ()=>{
        if (!activeAudio.src) return;
        if (audioCtx.state === 'suspended') audioCtx.resume();
        if (isPlaying){ activeAudio.pause(); isPlaying=false; btnPlay.textContent='▶'; }
        else { activeAudio.play().catch(()=>{}); isPlaying=true; btnPlay.textContent='⏸'; }
        postState();
    });
    btnNext.addEventListener('click', ()=>{ if (playlist.length || queuedSongs.length) playIndex(getNextIndex({consumeQueue: true})).catch(()=>{}); });
    btnPrev.addEventListener('click', ()=>{ if (playlist.length) playIndex(currentIndex<=0?playlist.length-1:currentIndex-1).catch(()=>{}); });

    function bindAudioEvents(aud) {
        aud.addEventListener('loadedmetadata', ()=>{
            if (aud === activeAudio) {
                const t = aud.currentTime || _seekTo || 0;
                parent.postMessage({type:'timeupdate', currentTime: t, duration: aud.duration || 0, currentIndex}, window.location.origin);
                postState();
            }
        });

        aud.addEventListener('ended', ()=>{
            if (aud !== activeAudio) return;
            if (repeatMode === 'one') {
                aud.currentTime = 0;
                aud.play().catch(()=>{});
                return;
            }
            if (playlist.length && !crossfadeTriggered) {
                const nextIdx = getNextIndex({consumeQueue: true});
                if (nextIdx !== currentIndex) playIndex(nextIdx).catch(()=>{});
            }
        });

        aud.addEventListener('timeupdate', ()=>{
            if (aud !== activeAudio) return;
            try{
                const t = aud.currentTime || 0;
                const d = aud.duration || 0;

                // Lógica de detección automática para crossfade (Gapless)
                if (crossfadeEnabled && d > 0 && !crossfadeTriggered && (d - t) <= crossfadeDuration) {
                    crossfadeTriggered = true;
                    if (playlist.length && repeatMode !== 'one') {
                        const nextIdx = getNextIndex({consumeQueue: true});
                        if (nextIdx !== currentIndex) playIndex(nextIdx, true).catch(()=>{});
                    }
                }
                
                if (d > 0 && ((t / d) >= 0.90 || (d - t) <= crossfadeDuration + 5) && !nextSongPrepared) {
                    prepareNextSong();
                }

                if (Math.abs(t - _lastSentTime) > 0.15){
                    _lastSentTime = t;
                    parent.postMessage({type:'timeupdate', currentTime: t, duration: d, currentIndex}, window.location.origin);
                    
                    // Sincronizar barra de progreso con el sistema operativo
                    if ('mediaSession' in navigator && 'setPositionState' in navigator.mediaSession) {
                        try {
                            navigator.mediaSession.setPositionState({
                                duration: d || 0,
                                playbackRate: aud.playbackRate || 1.0,
                                position: t || 0
                            });
                        } catch(e) {}
                    }
                }
                
                if (!window._lastPlaybackSave || Date.now() - window._lastPlaybackSave > 3000) {
                    window._lastPlaybackSave = Date.now();
                    savePlayerState({ currentIndex, currentTime: t, duration: d });
                }
            }catch(e){}
        });
    }

    bindAudioEvents(audio1);
    bindAudioEvents(audio2);

    // =========================================================================
    // 5. COMUNICACIÓN Y PERSISTENCIA
    // =========================================================================
    window.addEventListener('message', (ev)=>{
        if (ev.origin !== window.location.origin) return;
        const msg = ev.data || {};
            if (msg.type === 'playSong'){
                const song = normalizeSong(msg.song);
                const idx = playlist.findIndex(s=>s.id===song.id);
                if (idx === -1){ playlist.unshift(song); playIndex(0).catch(()=>{}); }
                else { playIndex(idx).catch(()=>{}); }
                queuedSongs = queuedSongs.filter(s => s && s.id !== song.id);
            try{
                localStorage.setItem('player_playlist', JSON.stringify(playlist));
                localStorage.setItem('player_queue', JSON.stringify(queuedSongs));
                savePlayerState({ currentIndex, isPlaying: true });
            }catch(e){}
        } else if (msg.type === 'setPlaylist'){
            playlist = (msg.playlist || []).map(normalizeSong);
            if (isShuffled) rebuildShuffleOrder();
            try{ localStorage.setItem('player_playlist', JSON.stringify(playlist)); }catch(e){}
            // Precargar la primera canción de la playlist para reducir latencia
            if (playlist.length > 0 && !activeAudio.src) {
                const first = normalizeSong(playlist[0]);
                activeAudio.src = first.audio;
                currentIndex = 0;
            }
        } else if (msg.type === 'queueSong'){
            const song = normalizeSong(msg.song);
            if (song && song.id) {
                queuedSongs = queuedSongs.filter(s => s && s.id !== song.id);
                if (msg.position === 'next') queuedSongs.unshift(song);
                else queuedSongs.push(song);
                nextSongPrepared = false;
                try{ localStorage.setItem('player_queue', JSON.stringify(queuedSongs)); }catch(e){}
                postState();
            }
        } else if (msg.type === 'command'){
            const cmd = msg.cmd;
            if (cmd === 'toggle'){
                btnPlay.click();
            } else if (cmd === 'next'){
                if (playlist.length || queuedSongs.length) playIndex(getNextIndex({consumeQueue: true})).catch(()=>{});
            } else if (cmd === 'prev'){
                if (playlist.length) playIndex(currentIndex<=0?playlist.length-1:currentIndex-1).catch(()=>{});
            } else if (cmd === 'playSong'){
                const idx = parseInt(msg.index);
                if (!isNaN(idx) && idx >= 0 && idx < playlist.length) playIndex(idx).catch(()=>{});
            } else if (cmd === 'seek'){
                const sec = Number(msg.seconds) || 0;
                try{ activeAudio.currentTime = Math.max(0, (activeAudio.currentTime || 0) + sec); }catch(e){}
            } else if (cmd === 'seekTo'){
                const at = Number(msg.seconds) || 0;
                try{ activeAudio.currentTime = Math.max(0, at); activeAudio.play().catch(()=>{}); isPlaying = true; btnPlay.textContent = '⏸'; postState(); }catch(e){}
            } else if (cmd === 'shuffle'){
                isShuffled = !isShuffled;
                if (isShuffled) rebuildShuffleOrder();
                else shuffledOrder = [];
                parent.postMessage({type:'shuffleChange', shuffled: isShuffled}, window.location.origin);
                postState();
            } else if (cmd === 'repeat'){
                const modes = ['none', 'one', 'all'];
                const curIdx = modes.indexOf(repeatMode);
                repeatMode = modes[(curIdx + 1) % modes.length];
                parent.postMessage({type:'repeatChange', repeat: repeatMode}, window.location.origin);
            } else if (cmd === 'volume'){
                applyMasterVolume(msg.value, {persist: true, notify: true});
            } else if (cmd === 'toggleMute'){
                if (_volume > 0){
                    _lastVolumeBeforeMute = _volume;
                    applyMasterVolume(0, {persist: true, notify: true});
                } else {
                    let restoreVolume = _lastVolumeBeforeMute;
                    try {
                        const saved = JSON.parse(localStorage.getItem('player_state') || '{}');
                        restoreVolume = saved.prevVolume || restoreVolume || 1.0;
                    } catch(e) {}
                    applyMasterVolume(restoreVolume, {persist: true, notify: true});
                }
            } else if (cmd === 'setCrossfade'){
                crossfadeEnabled = msg.enabled === true;
            } else if (cmd === 'settings'){
                if (typeof msg.crossfade_enabled !== 'undefined') {
                    crossfadeEnabled = msg.crossfade_enabled === true;
                }
            } else if (cmd === 'setSpeed'){
                const speed = Number(msg.speed) || 1.0;
                try {
                    audio1.playbackRate = speed;
                    audio2.playbackRate = speed;
                } catch(e){}
            } else if (cmd === 'getState'){
                postState();
            }
        }
    });

    try {
        fetch('/api/profile')
            .then(r => r.json())
            .then(p => {
                if (typeof p.crossfade_enabled !== 'undefined') {
                    crossfadeEnabled = p.crossfade_enabled === true;
                }
            })
            .catch(() => {});
    } catch(e) {}

    try{
        const raw = localStorage.getItem('player_playlist');
        if (raw) playlist = (JSON.parse(raw) || []).map(normalizeSong);
        const rawQueue = localStorage.getItem('player_queue');
        if (rawQueue) queuedSongs = (JSON.parse(rawQueue) || []).map(normalizeSong);
        const st = JSON.parse(localStorage.getItem('player_state')||'null');
        if (st) {
            if (typeof st.volume === 'number') {
                _lastVolumeBeforeMute = clampVolume(st.prevVolume || st.volume || 1.0);
                applyMasterVolume(st.volume, {persist: false, notify: false});
            }
            if (typeof st.currentIndex==='number'){
                currentIndex = st.currentIndex;
                if (playlist[currentIndex]){
                    playlist[currentIndex] = normalizeSong(playlist[currentIndex]);
                    activeAudio.src = playlist[currentIndex].audio;
                    titleEl.textContent = playlist[currentIndex].titulo || 'Sin título';
                    artistEl.textContent = playlist[currentIndex].artista || '';
                    if (playlist[currentIndex].cover) {
                        cover.innerHTML = `<img src="${playlist[currentIndex].cover}" style="width:100%;height:100%;object-fit:cover;border-radius:6px">`;
                        extractColor(playlist[currentIndex].cover);
                    }
                    
                    // Inicializar sesión multimedia con la canción actual al arrancar
                    updateMediaSession(playlist[currentIndex]);
                    if ('mediaSession' in navigator) {
                        navigator.mediaSession.playbackState = 'paused';
                    }
                    
                    fetchReplayGain(playlist[currentIndex].id).then(gain => {
                        activeGain.gain.value = gain;
                    });
                    
                    if (typeof st.currentTime === 'number' && st.currentTime > 0) {
                        _seekTo = st.currentTime;
                        _seekListener = () => {
                            try{
                                activeAudio.currentTime = Math.min(_seekTo, activeAudio.duration || 0);
                            }catch(e){}
                        };
                        activeAudio.addEventListener('loadedmetadata', _seekListener);
                    }
                }
            }
        }
    }catch(e){console.error(e)}
    setTimeout(postState, 200);

    function updateMediaSession(s) {
        if (!('mediaSession' in navigator)) return;
        try {
            const artworkUrl = s.cover ? (s.cover.startsWith('http') ? s.cover : window.location.origin + s.cover) : window.location.origin + '/static/img/default-cover.png';
            navigator.mediaSession.metadata = new MediaMetadata({
                title: s.titulo || 'Sin título',
                artist: s.artista || 'Artista desconocido',
                album: s.album || 'Álbum desconocido',
                artwork: [
                    { src: artworkUrl, sizes: '96x96', type: 'image/jpeg' },
                    { src: artworkUrl, sizes: '128x128', type: 'image/jpeg' },
                    { src: artworkUrl, sizes: '192x192', type: 'image/jpeg' },
                    { src: artworkUrl, sizes: '256x256', type: 'image/jpeg' },
                    { src: artworkUrl, sizes: '384x384', type: 'image/jpeg' },
                    { src: artworkUrl, sizes: '512x512', type: 'image/jpeg' }
                ]
            });
            navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused';
        } catch(e) {
            console.error('[MediaSession] Error actualizando metadatos:', e);
        }
    }

    function setupMediaSessionHandlers() {
        if (!('mediaSession' in navigator)) return;
        try {
            navigator.mediaSession.setActionHandler('play', () => {
                if (!activeAudio.src) return;
                if (audioCtx.state === 'suspended') audioCtx.resume();
                activeAudio.play().catch(()=>{});
                isPlaying = true;
                btnPlay.textContent = '⏸';
                navigator.mediaSession.playbackState = 'playing';
                postState();
            });

            navigator.mediaSession.setActionHandler('pause', () => {
                activeAudio.pause();
                isPlaying = false;
                btnPlay.textContent = '▶';
                navigator.mediaSession.playbackState = 'paused';
                postState();
            });

            navigator.mediaSession.setActionHandler('previoustrack', () => {
                if (playlist.length) {
                    playIndex(currentIndex <= 0 ? playlist.length - 1 : currentIndex - 1).catch(()=>{});
                }
            });

            navigator.mediaSession.setActionHandler('nexttrack', () => {
                if (playlist.length || queuedSongs.length) {
                    playIndex(getNextIndex({consumeQueue: true})).catch(()=>{});
                }
            });

            navigator.mediaSession.setActionHandler('seekbackward', (details) => {
                const offset = details.seekOffset || 10;
                try {
                    activeAudio.currentTime = Math.max(0, activeAudio.currentTime - offset);
                } catch(e) {}
            });

            navigator.mediaSession.setActionHandler('seekforward', (details) => {
                const offset = details.seekOffset || 10;
                try {
                    activeAudio.currentTime = Math.min(activeAudio.duration || 0, activeAudio.currentTime + offset);
                } catch(e) {}
            });

            navigator.mediaSession.setActionHandler('seekto', (details) => {
                if (details.fastSeek && 'fastSeek' in activeAudio) {
                    activeAudio.fastSeek(details.seekTime);
                    return;
                }
                try {
                    activeAudio.currentTime = details.seekTime;
                } catch(e) {}
            });
        } catch (e) {
            console.error('[MediaSession] Error configurando manejadores:', e);
        }
    }

    // Inicializar manejadores de Media Session al inicio
    setupMediaSessionHandlers();

    // Notificar al parent que el iframe está listo para recibir comandos
    parent.postMessage({type: 'ready'}, window.location.origin);

})();
