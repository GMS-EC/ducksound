// ============================================
// REPRODUCTOR PERSISTENTE
// ============================================

// DOM elements (initialized after DOMContentLoaded)
let audioPlayer, btnPlay, btnPrev, btnNext, btnVolume, volumeSlider,
    progressFill, progressBar, currentTimeEl, totalTimeEl,
    playerTitle, playerArtist, playerCover;

// Estado del reproductor
let currentSongIndex = -1;
let playlist = [];
let isPlaying = false;

// Lyrics state for the right panel - manejado por player_parent.js
// let panelLyricsData = [];
// let panelLyricElements = [];
// let activePanelLyricIndex = -1;

// ============================================
// FUNCIONES DE FORMATO
// ============================================

function formatTime(seconds) {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ============================================
// PARSEO DE ARCHIVOS LRC
// ============================================

function parseLRC(lrcText) {
    const lines = lrcText.split('\n');
    const lyrics = [];
    const timeRegex = /\[(\d+):(\d+(?:\.\d+)?)\](.*)/;
    
    for (const line of lines) {
        const match = line.match(timeRegex);
        if (match) {
            const minutes = parseInt(match[1]);
            const seconds = parseFloat(match[2]);
            const text = match[3].trim();
            const totalSeconds = (minutes * 60) + seconds;
            
            lyrics.push({
                time: totalSeconds,
                text: text || '♪'
            });
        }
    }
    
    return lyrics;
}

// ============================================
// FUNCIONES DE CONTROL
// ============================================

function playSong(index) {
    if (index < 0 || index >= playlist.length) return;
    
    currentSongIndex = index;
    const song = playlist[index];
    
    // Actualizar fuente de audio
    audioPlayer.src = song.audio;
    
    // Actualizar información del reproductor
    playerTitle.textContent = song.titulo;
    playerArtist.textContent = song.artista;
    
    // Actualizar imagen del álbum
    if (song.cover) {
        playerCover.innerHTML = `<img src="${song.cover}" alt="${song.titulo}">`;
    } else {
        playerCover.innerHTML = '<span class="cover-icon"><i class="fa-solid fa-music"></i></span>';
    }
    
    // Marcar la tarjeta activa
    document.querySelectorAll('.song-card').forEach((card, i) => {
        card.classList.toggle('playing', i === index);
    });
    
    // Cargar letras en el panel derecho
    loadPanelLyrics(song);
    
    // Reproducir
    audioPlayer.play()
        .then(() => {
            isPlaying = true;
            updatePlayButton();
        })
        .catch(err => {
            console.error('Error al reproducir:', err);
        });
}

function togglePlay() {
    if (!audioPlayer.src) {
        if (playlist.length > 0) {
            playSong(0);
        }
        return;
    }
    
    if (isPlaying) {
        audioPlayer.pause();
        isPlaying = false;
    } else {
        audioPlayer.play();
        isPlaying = true;
    }
    
    updatePlayButton();
}

function updatePlayButton() {
    if (btnPlay && btnPlay.querySelector('i')) {
        btnPlay.querySelector('i').className = isPlaying ? 'fa-solid fa-pause' : 'fa-solid fa-play';
    } else {
        btnPlay.textContent = isPlaying ? '\u23F8' : '\u25B6';
    }
}

function playNext() {
    if (playlist.length === 0) return;
    const nextIndex = (currentSongIndex + 1) % playlist.length;
    playSong(nextIndex);
}

function playPrev() {
    if (playlist.length === 0) return;
    const prevIndex = currentSongIndex <= 0 ? playlist.length - 1 : currentSongIndex - 1;
    playSong(prevIndex);
}

function setVolume(value) {
    audioPlayer.volume = value;
    updateVolumeIcon(value);
}

function updateVolumeIcon(value) {
    if (!btnVolume) return;
    const icon = btnVolume.querySelector('i');
    if (icon) {
        if (value === 0) icon.className = 'fa-solid fa-volume-xmark';
        else if (value < 0.5) icon.className = 'fa-solid fa-volume-low';
        else icon.className = 'fa-solid fa-volume-high';
    }
}

function seekTo(e) {
    const rect = progressBar.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    audioPlayer.currentTime = percent * audioPlayer.duration;
}

// ============================================
// LETRAS — Panel Derecho
// ============================================

async function loadPanelLyrics(song) {
    const lyricsPanel = document.getElementById('lyrics-content-panel');
    if (!lyricsPanel) return;

    // Reset
    panelLyricsData = [];
    panelLyricElements = [];
    activePanelLyricIndex = -1;

    if (!song.lyrics) {
        lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Esta canción no tiene letra disponible</p>';
        return;
    }

    try {
        const response = await fetch(song.lyrics);
        const lrcText = await response.text();
        panelLyricsData = parseLRC(lrcText);

        if (panelLyricsData.length === 0) {
            lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon"><i class="fa-solid fa-music"></i></span>Esta canción no tiene letra disponible</p>';
            return;
        }

        // Render lyrics in the right panel (no timestamps)
        lyricsPanel.innerHTML = '';

        // Add top spacer so first lyric can be centered
        const topSpacer = document.createElement('div');
        topSpacer.className = 'lyrics-spacer';
        lyricsPanel.appendChild(topSpacer);

        panelLyricsData.forEach((line, idx) => {
            const div = document.createElement('div');
            div.className = 'lyric-line';
            div.dataset.index = idx;
            div.textContent = line.text;

            // Click to seek
            div.addEventListener('click', () => {
                audioPlayer.currentTime = line.time;
                if (!isPlaying) {
                    audioPlayer.play();
                    isPlaying = true;
                    updatePlayButton();
                }
            });

            lyricsPanel.appendChild(div);
            panelLyricElements.push(div);
        });

        // Add bottom spacer so last lyric can be centered
        const bottomSpacer = document.createElement('div');
        bottomSpacer.className = 'lyrics-spacer';
        lyricsPanel.appendChild(bottomSpacer);

        // Auto-switch to lyrics tab
        showTab('lyrics');

    } catch (error) {
        console.error('Error al cargar letras:', error);
        lyricsPanel.innerHTML = '<p class="no-lyrics"><span class="no-lyrics-icon">⚠️</span>Error al cargar la letra</p>';
    }
}

function syncPanelLyrics() {
    if (panelLyricsData.length === 0 || panelLyricElements.length === 0) return;

    const currentTime = audioPlayer.currentTime;
    let newIndex = -1;

    // Find the current lyric line
    for (let i = panelLyricsData.length - 1; i >= 0; i--) {
        if (currentTime >= panelLyricsData[i].time) {
            newIndex = i;
            break;
        }
    }

    // Update if active line changed
    if (newIndex !== activePanelLyricIndex && newIndex !== -1) {
        // Remove previous active
        if (activePanelLyricIndex !== -1 && panelLyricElements[activePanelLyricIndex]) {
            panelLyricElements[activePanelLyricIndex].classList.remove('active');
        }

        // Set new active
        const newEl = panelLyricElements[newIndex];
        if (newEl) {
            newEl.classList.add('active');
            activePanelLyricIndex = newIndex;

            // Auto-center: the panel itself is the scroll container
            const panel = document.getElementById('lyrics-content-panel');
            if (panel) {
                const scrollTarget = newEl.offsetTop - (panel.clientHeight / 2) + (newEl.offsetHeight / 2);
                panel.scrollTo({ top: scrollTarget, behavior: 'smooth' });
            }
        }
    }
}

// ============================================
// TABS (Right panel)
// ============================================

function showTab(name) {
    const rightTabs = document.querySelectorAll('.right-tabs .tab');
    const tabContents = document.querySelectorAll('.tab-content');

    rightTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    tabContents.forEach(tc => {
        const contentId = tc.id;
        const isMatch = contentId === name + '-content' ||
                        (name === 'lyrics' && contentId === 'lyrics-content-panel');
        tc.classList.toggle('active', isMatch);
    });
}

// Particle effects removed for a clean, professional look

// ============================================
// UP NEXT
// ============================================

function renderUpNext() {
    const upnextEl = document.getElementById('upnext-content');
    if (!upnextEl || !playlist || playlist.length === 0) return;
    upnextEl.innerHTML = '';
    
    // Mostrar todas las canciones de la playlist, marcando la actual
    for (let i = 0; i < playlist.length; i++) {
        const item = playlist[i];
        const div = document.createElement('div');
        
        // Determinar si esta es la canción actual
        const isCurrentSong = (i === currentSongIndex);
        const isPlaying = isCurrentSong && isPlaying;
        
        // Clases CSS según estado
        let classes = 'upnext-item';
        if (isCurrentSong) {
            classes += ' current-song';
        }
        if (isPlaying) {
            classes += ' playing';
        }
        
        div.className = classes;
        
        // Icono de estado
        let statusIcon = '';
        if (isCurrentSong && isPlaying) {
            statusIcon = '<div class="playing-indicator">🎵</div>';
        } else if (isCurrentSong && !isPlaying) {
            statusIcon = '<div class="current-indicator">⏸</div>';
        } else {
            statusIcon = '<div class="track-number">' + (i + 1) + '</div>';
        }
        
        div.innerHTML = `
            <div class="track-status">${statusIcon}</div>
            <div class="cover">
                <img src="${item.cover}" style="width:100%;height:100%;object-fit:cover" alt="${item.titulo}">
            </div>
            <div class="meta">
                <strong class="song-title ${isCurrentSong ? 'current-title' : ''}">${item.titulo}</strong>
                <div class="muted">${item.artista}</div>
            </div>
        `;
        
        div.addEventListener('click', () => playSong(i));
        upnextEl.appendChild(div);
    }
}

// ============================================
// EXPORTAR API
// ============================================

function exposePlayerAPI() {
    window.playerAPI = {
        playSong,
        togglePlay,
        getCurrentSong: () => playlist[currentSongIndex],
        getAudioPlayer: () => audioPlayer
    };
}

function initPageBindings() {
    // Prefer server-provided cancionesDisponibles array when present
    if (typeof cancionesDisponibles !== 'undefined' && Array.isArray(cancionesDisponibles) && cancionesDisponibles.length > 0) {
        playlist = cancionesDisponibles;
        document.querySelectorAll('.song-card').forEach((card, index) => {
            // remove previous listeners to avoid duplicates
            card.replaceWith(card.cloneNode(true));
        });
        document.querySelectorAll('.song-card').forEach((card, index) => {
            card.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-play-song') || e.target.closest('.btn-play-song')) {
                    e.stopPropagation();
                }
                playSong(index);
            });
        });
    } else {
        // Build playlist from DOM data attributes
        const cards = Array.from(document.querySelectorAll('.song-card'));
        if (cards.length > 0) {
            playlist = cards.map(card => ({
                id: parseInt(card.dataset.cancionId),
                titulo: card.dataset.titulo,
                artista: card.dataset.artista,
                audio: card.dataset.audio,
                cover: card.dataset.cover || null,
                lyrics: card.dataset.lyrics || null
            }));

            cards.forEach((card, index) => {
                // remove previous listeners to avoid duplicates
                const newCard = card.cloneNode(true);
                card.parentNode.replaceChild(newCard, card);
                newCard.addEventListener('click', (e) => {
                    if (e.target.classList.contains('btn-play-song') || e.target.closest('.btn-play-song')) {
                        e.stopPropagation();
                    }
                    playSong(index);
                });
            });
        }
    }

    // Re-render upnext now that playlist may have changed
    renderUpNext();
}

// Make available globally
window.initPageBindings = initPageBindings;

// ============================================
// INICIALIZACIÓN
// ============================================

window.addEventListener('DOMContentLoaded', () => {
    // Elementos del DOM
    audioPlayer = document.getElementById('audio-player');
    btnPlay = document.getElementById('btn-play');
    btnPrev = document.getElementById('btn-prev');
    btnNext = document.getElementById('btn-next');
    btnVolume = document.getElementById('btn-volume');
    volumeSlider = document.getElementById('volume-slider');
    progressFill = document.getElementById('progress-fill');
    progressBar = document.querySelector('.progress-bar');
    currentTimeEl = document.getElementById('current-time');
    totalTimeEl = document.getElementById('total-time');
    playerTitle = document.getElementById('player-title');
    playerArtist = document.getElementById('player-artist');
    playerCover = document.getElementById('player-cover');

    // Controles del reproductor
    if (btnPlay) btnPlay.addEventListener('click', togglePlay);
    if (btnNext) btnNext.addEventListener('click', playNext);
    if (btnPrev) btnPrev.addEventListener('click', playPrev);

    if (btnVolume) {
        btnVolume.addEventListener('click', () => {
            if (audioPlayer.volume > 0) {
                audioPlayer.dataset.prevVolume = audioPlayer.volume;
                setVolume(0);
                volumeSlider.value = 0;
            } else {
                const prevVolume = parseFloat(audioPlayer.dataset.prevVolume) || 1;
                setVolume(prevVolume);
                volumeSlider.value = prevVolume;
            }
        });
    }

    if (volumeSlider) volumeSlider.addEventListener('input', (e) => setVolume(parseFloat(e.target.value)));
    if (progressBar) progressBar.addEventListener('click', seekTo);

    // Eventos del audio
    if (audioPlayer) {
        audioPlayer.addEventListener('timeupdate', () => {
            if (audioPlayer.duration) {
                const percent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
                if (progressFill) progressFill.style.width = `${percent}%`;
                if (currentTimeEl) currentTimeEl.textContent = formatTime(audioPlayer.currentTime);
                // Sincronizar letras en el panel derecho - manejado por player_parent.js
                // syncPanelLyrics();
            }
        });

        // Guardar estado periódicamente para persistencia entre navegaciones
        audioPlayer.addEventListener('timeupdate', () => {
            try {
                const state = {
                    songId: playlist[currentSongIndex] ? playlist[currentSongIndex].id : null,
                    currentTime: audioPlayer.currentTime,
                    isPlaying: !audioPlayer.paused,
                    volume: audioPlayer.volume
                };
                localStorage.setItem('player_state', JSON.stringify(state));
            } catch (e) {
                // ignore
            }
        });

        // Restaurar estado previo si existe
        try {
            const raw = localStorage.getItem('player_state');
            if (raw) {
                const prev = JSON.parse(raw);
                if (prev && prev.songId && typeof cancionesDisponibles !== 'undefined') {
                    // Buscar índice de la canción en el playlist actual
                    const idx = cancionesDisponibles.findIndex(s => s.id === prev.songId);
                    if (idx !== -1) {
                        // Preparar playlist y comenzar en la posición guardada
                        playlist = cancionesDisponibles;
                        currentSongIndex = idx;
                        const song = playlist[idx];
                        audioPlayer.src = song.audio;
                        playerTitle.textContent = song.titulo;
                        playerArtist.textContent = song.artista;
                        if (song.cover) playerCover.innerHTML = `<img src="${song.cover}" alt="${song.titulo}">`;
                        audioPlayer.currentTime = prev.currentTime || 0;
                        setVolume(prev.volume || 1);
                        if (prev.isPlaying) {
                            audioPlayer.play().catch(()=>{});
                        }
                    }
                }
            }
        } catch (e) {
            console.error('Error restaurando estado de player:', e);
        }

        audioPlayer.addEventListener('loadedmetadata', () => {
            if (totalTimeEl) totalTimeEl.textContent = formatTime(audioPlayer.duration);
        });

        audioPlayer.addEventListener('ended', playNext);
        audioPlayer.addEventListener('play', () => { isPlaying = true; updatePlayButton(); renderUpNext(); });
        audioPlayer.addEventListener('pause', () => { isPlaying = false; updatePlayButton(); renderUpNext(); });
    }

    // Integración con el dashboard: enlazar clicks a tarjetas de canciones
    if (typeof cancionesDisponibles !== 'undefined') {
        playlist = cancionesDisponibles;
        document.querySelectorAll('.song-card').forEach((card, index) => {
            card.addEventListener('click', (e) => {
                // Evitar doble acción si se hace click en el botón play
                if (e.target.classList.contains('btn-play-song') || e.target.closest('.btn-play-song')) {
                    e.stopPropagation();
                }
                playSong(index);
            });
        });
    }

    // Tabs del panel derecho
    const rightTabs = document.querySelectorAll('.right-tabs .tab');
    if (rightTabs) {
        rightTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                showTab(tab.dataset.tab);
            });
        });
    }

    // Override playSong to also update upnext
    const origPlaySong = playSong;
    playSong = function(index) {
        origPlaySong(index);
        setTimeout(renderUpNext, 150);
    };

    renderUpNext();
    exposePlayerAPI();
});
