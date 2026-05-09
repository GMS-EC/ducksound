// Player frame: runs inside iframe, manages audio and UI, communicates with parent via postMessage
(function(){
    // Create UI inside body
    document.body.style.margin = '0';
    const container = document.createElement('div');
    container.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--surface);color:var(--text);height:100%;box-sizing:border-box;border-top:1px solid rgba(0,0,0,0.08);';

    const cover = document.createElement('div');
    cover.style.cssText = 'width:56px;height:56px;background:#222;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px';
    cover.textContent = '🎵';

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

    const controls = document.createElement('div');
    controls.style.display = 'flex'; controls.style.gap='8px';
    const btnPrev = document.createElement('button'); btnPrev.textContent='⏮';
    const btnPlay = document.createElement('button'); btnPlay.textContent='▶';
    const btnNext = document.createElement('button'); btnNext.textContent='⏭';
    controls.appendChild(btnPrev); controls.appendChild(btnPlay); controls.appendChild(btnNext);

    container.appendChild(cover); container.appendChild(meta); container.appendChild(controls);
    document.body.appendChild(container);

    // === WEB AUDIO API & DUAL BUFFER SETUP ===
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContext();

    const audio1 = document.createElement('audio'); audio1.preload='auto'; audio1.crossOrigin='anonymous'; audio1.style.display='none'; document.body.appendChild(audio1);
    const audio2 = document.createElement('audio'); audio2.preload='auto'; audio2.crossOrigin='anonymous'; audio2.style.display='none'; document.body.appendChild(audio2);

    const source1 = audioCtx.createMediaElementSource(audio1);
    const source2 = audioCtx.createMediaElementSource(audio2);
    const gainNode1 = audioCtx.createGain();
    const gainNode2 = audioCtx.createGain();
    const masterGain = audioCtx.createGain();

    source1.connect(gainNode1); gainNode1.connect(masterGain);
    source2.connect(gainNode2); gainNode2.connect(masterGain);
    masterGain.connect(audioCtx.destination);

    let activeAudio = audio1;
    let activeGain = gainNode1;
    let nextAudio = audio2;
    let nextGain = gainNode2;

    let playlist = [];
    let queuedSongs = [];
    let currentIndex = -1;
    let isPlaying = false;
    let isShuffled = false;
    let repeatMode = 'none'; // 'none', 'one', 'all'
    let _lastSentTime = 0;
    let _volume = 1.0;
    let crossfadeEnabled = true;
    let crossfadeDuration = 3; // seconds
    let nextSongPrepared = false;
    let crossfadeTriggered = false;

    masterGain.gain.value = _volume;

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

        // Buscar la canción en el playlist sin moverla
        const existingIdx = playlist.findIndex(s => s && s.id === queued.id);
        if (existingIdx !== -1) return existingIdx;

        // No existe en el playlist, agregarla después de la actual
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
            let idx;
            do { idx = Math.floor(Math.random() * playlist.length); } while (idx === currentIndex && playlist.length > 1);
            return idx;
        }
        return (currentIndex + 1) % playlist.length;
    }

    async function fetchReplayGain(songId) {
        try {
            const res = await fetch('/api/audio-info/' + songId);
            const data = await res.json();
            if (data.rms_level != null) {
                // Target loudness -14 dBFS
                const offset_db = -14 - data.rms_level;
                // Limit amplification to +12dB to prevent clipping
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

    async function playIndex(idx, isCrossfading = false){
        if (idx < 0 || idx >= playlist.length) return;
        
        // If AudioContext is suspended (browser policy), resume it
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }

        const s = normalizeSong(playlist[idx]);
        playlist[idx] = s;

        // Visual updates
        titleEl.textContent = s.titulo || 'Sin título';
        artistEl.textContent = s.artista || '';
        if (s.cover) {
            cover.innerHTML = `<img src="${s.cover}" style="width:100%;height:100%;object-fit:cover;border-radius:6px">`;
            extractColor(s.cover);
        } else {
            cover.innerHTML = '🎵';
            window.parent.postMessage({type: 'themeColor', color: [30, 215, 96]}, '*'); // Default green
        }

        // Fetch ReplayGain offset
        const replayGainValue = await fetchReplayGain(s.id);

        if (!isCrossfading) {
            // Hard stop current
            activeAudio.pause();
            activeAudio.src = s.audio;
            activeGain.gain.setValueAtTime(replayGainValue, audioCtx.currentTime);
            activeAudio.play().catch(()=>{});
            currentIndex = idx;
        } else {
            // We are crossfading: Swap active/next pointers
            const tempA = activeAudio; activeAudio = nextAudio; nextAudio = tempA;
            const tempG = activeGain; activeGain = nextGain; nextGain = tempG;

            // activeAudio is already preloaded with s.audio!
            activeAudio.play().catch(()=>{});
            
            // Fade out the old track (now nextAudio)
            nextGain.gain.setTargetAtTime(0, audioCtx.currentTime, crossfadeDuration / 3);
            setTimeout(() => { nextAudio.pause(); }, crossfadeDuration * 1000);
            
            // Fade in the new track (activeAudio) to its ReplayGain target
            activeGain.gain.setValueAtTime(0, audioCtx.currentTime);
            activeGain.gain.setTargetAtTime(replayGainValue, audioCtx.currentTime, crossfadeDuration / 3);
            currentIndex = idx;
        }

        _lastSentTime = 0;
        isPlaying = true;
        btnPlay.textContent = '⏸';
        crossfadeTriggered = false;
        nextSongPrepared = false;
        
        // Resetear tiempo guardado al iniciar canción nueva
        try{
            const saved = JSON.parse(localStorage.getItem('player_state')||'{}');
            saved.currentIndex = currentIndex;
            saved.currentTime = 0;
            localStorage.setItem('player_state', JSON.stringify(saved));
        }catch(e){}
        
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
            
            // Current song first (so the user can see where they are)
            const currentSong = normalizeSong(playlist[currentIndex] || null);
            if (currentSong && currentSong.id) {
                nextSongs.push({id: currentSong.id, titulo: currentSong.titulo, artista: currentSong.artista, cover: currentSong.cover, current: true});
                queuedIds.add(currentSong.id);
            }
            
            // Queued songs
            queuedSongs.forEach(song => {
                const s = normalizeSong(song);
                if (!s || !s.id || queuedIds.has(s.id)) return;
                queuedIds.add(s.id);
                nextSongs.push({id: s.id, titulo: s.titulo, artista: s.artista, cover: s.cover, queued: true});
            });
            
            // Upcoming playlist songs (up to 20 total)
            const maxTotal = 20;
            for(let i=1;i<=maxTotal;i++){
                const idx = currentIndex + i;
                if (idx >= playlist.length) break;
                const s = normalizeSong(playlist[idx]);
                if (!s) break;
                if (queuedIds.has(s.id)) continue;
                nextSongs.push({id: s.id, titulo: s.titulo, artista: s.artista, cover: s.cover});
                if (nextSongs.length >= maxTotal) break;
            }
        }catch(e){}
        const currentSong = normalizeSong(playlist[currentIndex] || null);
        parent.postMessage({type:'state', state:{currentIndex, isPlaying, song: currentSong, upnext: nextSongs, shuffled: isShuffled, repeat: repeatMode, volume: _volume}}, window.location.origin);
    }

    btnPlay.addEventListener('click', ()=>{
        if (!activeAudio.src) return;
        if (audioCtx.state === 'suspended') audioCtx.resume();
        if (isPlaying){ activeAudio.pause(); isPlaying=false; btnPlay.textContent='▶'; }
        else { activeAudio.play().catch(()=>{}); isPlaying=true; btnPlay.textContent='⏸'; }
        postState();
    });
    btnNext.addEventListener('click', ()=>{ if (playlist.length || queuedSongs.length) playIndex(getNextIndex({consumeQueue: true})); });
    btnPrev.addEventListener('click', ()=>{ if (playlist.length) playIndex(currentIndex<=0?playlist.length-1:currentIndex-1); });

    function bindAudioEvents(aud) {
        aud.addEventListener('loadedmetadata', ()=>{
            if (aud === activeAudio) {
                parent.postMessage({type:'timeupdate', currentTime: 0, duration: aud.duration || 0, currentIndex}, window.location.origin);
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
                playIndex(getNextIndex({consumeQueue: true}));
            }
        });

        aud.addEventListener('timeupdate', ()=>{
            if (aud !== activeAudio) return;
            try{
                const t = aud.currentTime || 0;
                const d = aud.duration || 0;

                // Gapless/Crossfade trigger
                if (crossfadeEnabled && d > 0 && !crossfadeTriggered && (d - t) <= crossfadeDuration) {
                    crossfadeTriggered = true;
                    if (playlist.length && repeatMode !== 'one') {
                        playIndex(getNextIndex({consumeQueue: true}), true); // True = isCrossfading
                    }
                }
                
                // Preload next track early
                if (d > 0 && (d - t) <= crossfadeDuration + 5 && !nextSongPrepared) {
                    prepareNextSong();
                }

                if (Math.abs(t - _lastSentTime) > 0.15){
                    _lastSentTime = t;
                    parent.postMessage({type:'timeupdate', currentTime: t, duration: d, currentIndex}, window.location.origin);
                }
                
                // Persistir estado cada ~3 segundos
                if (!window._lastPlaybackSave || Date.now() - window._lastPlaybackSave > 3000) {
                    window._lastPlaybackSave = Date.now();
                    try{
                        const saved = JSON.parse(localStorage.getItem('player_state')||'{}');
                        saved.currentIndex = currentIndex;
                        saved.currentTime = t;
                        localStorage.setItem('player_state', JSON.stringify(saved));
                    }catch(e){}
                }
            }catch(e){}
        });
    }

    bindAudioEvents(audio1);
    bindAudioEvents(audio2);

    window.addEventListener('message', (ev)=>{
        if (ev.origin !== window.location.origin) return;
        const msg = ev.data || {};
        if (msg.type === 'playSong'){
            const song = normalizeSong(msg.song);
            const idx = playlist.findIndex(s=>s.id===song.id);
            if (idx === -1){ playlist.unshift(song); playIndex(0); }
            else { playIndex(idx); }
            queuedSongs = queuedSongs.filter(s => s && s.id !== song.id);
            try{
                localStorage.setItem('player_playlist', JSON.stringify(playlist));
                localStorage.setItem('player_queue', JSON.stringify(queuedSongs));
                localStorage.setItem('player_state', JSON.stringify({currentIndex, isPlaying:true}));
            }catch(e){}
        } else if (msg.type === 'setPlaylist'){
            playlist = (msg.playlist || []).map(normalizeSong);
            try{ localStorage.setItem('player_playlist', JSON.stringify(playlist)); }catch(e){}
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
                if (playlist.length || queuedSongs.length) playIndex(getNextIndex({consumeQueue: true}));
            } else if (cmd === 'prev'){
                if (playlist.length) playIndex(currentIndex<=0?playlist.length-1:currentIndex-1);
            } else if (cmd === 'playSong'){
                const idx = parseInt(msg.index);
                if (!isNaN(idx) && idx >= 0 && idx < playlist.length) playIndex(idx);
            } else if (cmd === 'seek'){
                const sec = Number(msg.seconds) || 0;
                try{ activeAudio.currentTime = Math.max(0, (activeAudio.currentTime || 0) + sec); }catch(e){}
            } else if (cmd === 'seekTo'){
                const at = Number(msg.seconds) || 0;
                try{ activeAudio.currentTime = Math.max(0, at); activeAudio.play().catch(()=>{}); isPlaying = true; btnPlay.textContent = '⏸'; postState(); }catch(e){}
            } else if (cmd === 'shuffle'){
                isShuffled = !isShuffled;
                parent.postMessage({type:'shuffleChange', shuffled: isShuffled}, window.location.origin);
            } else if (cmd === 'repeat'){
                const modes = ['none', 'one', 'all'];
                const curIdx = modes.indexOf(repeatMode);
                repeatMode = modes[(curIdx + 1) % modes.length];
                parent.postMessage({type:'repeatChange', repeat: repeatMode}, window.location.origin);
            } else if (cmd === 'volume'){
                const vol = Math.max(0, Math.min(1, Number(msg.value) || 0));
                _volume = vol;
                masterGain.gain.value = vol; // Apply directly to master GainNode
                parent.postMessage({type:'volumeChange', volume: vol}, window.location.origin);
            } else if (cmd === 'toggleMute'){
                if (masterGain.gain.value > 0){
                    masterGain.gain.dataset = masterGain.gain.dataset || {};
                    masterGain.gain.dataset.prevVolume = masterGain.gain.value;
                    masterGain.gain.value = 0;
                } else {
                    masterGain.gain.value = parseFloat(masterGain.gain.dataset.prevVolume) || 1.0;
                }
                parent.postMessage({type:'volumeChange', volume: masterGain.gain.value}, window.location.origin);
            } else if (cmd === 'setCrossfade'){
                crossfadeEnabled = msg.enabled === true;
            } else if (cmd === 'settings'){
                if (typeof msg.crossfade_enabled !== 'undefined') {
                    crossfadeEnabled = msg.crossfade_enabled === true;
                }
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
        if (st && typeof st.currentIndex==='number'){
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
                fetchReplayGain(playlist[currentIndex].id).then(gain => {
                    activeGain.gain.value = gain;
                });
                
                // Restaurar tiempo de reproducción si estaba guardado
                if (typeof st.currentTime === 'number' && st.currentTime > 0) {
                    const seekTo = st.currentTime;
                    const onMeta = () => {
                        activeAudio.removeEventListener('loadedmetadata', onMeta);
                        try{
                            activeAudio.currentTime = Math.min(seekTo, activeAudio.duration || 0);
                        }catch(e){}
                    };
                    activeAudio.addEventListener('loadedmetadata', onMeta);
                }
                
                // No reproducir automáticamente al recargar la página
        // if (st.isPlaying){ activeAudio.play().catch(()=>{}); isPlaying=true; btnPlay.textContent='⏸'; }
            }
            setTimeout(postState, 200);
        }
    }catch(e){console.error(e)}

})();
