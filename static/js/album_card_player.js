// Album Card Player
// Permite reproducir álbumes directamente desde las tarjetas

function playAlbum(albumId) {
    fetch(`/api/album/${albumId}/canciones`)
        .then(r => r.json())
        .then(songs => {
            if (songs && songs.length > 0) {
                songs = songs.map(s => ({
                    id: s.id,
                    titulo: s.titulo,
                    artista: s.artista,
                    audio: s.audio,
                    cover: s.cover,
                    lyrics: s.lyrics
                }));
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    const first = songs[0];
                    if (first) {
                        setTimeout(() => {
                            iframe.contentWindow.postMessage({
                                type: 'playSong',
                                song: first
                            }, window.location.origin);
                        }, 100);
                    }
                }
            }
        })
        .catch(err => console.error('Error playing album:', err));
}

function playDailyMix(mixId) {
    fetch(`/api/daily-mix/${mixId}/songs`)
        .then(r => r.json())
        .then(songs => {
            if (songs && songs.length > 0) {
                songs = songs.map(s => ({
                    id: s.id,
                    titulo: s.titulo,
                    artista: s.artista,
                    audio: s.audio,
                    cover: s.cover,
                    lyrics: s.lyrics
                }));
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    const first = songs[0];
                    if (first) {
                        setTimeout(() => {
                            iframe.contentWindow.postMessage({
                                type: 'playSong',
                                song: first
                            }, window.location.origin);
                        }, 100);
                    }
                }
            }
        })
        .catch(err => console.error('Error playing daily mix:', err));
}

// Delegación de eventos a nivel documento para botones de play
function handleCardPlayClick(e) {
    const btn = e.target.closest('.album-card-play');
    if (!btn) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    
    const albumId = btn.dataset.albumId;
    const mixId = btn.dataset.mixId;
    
    if (albumId) {
        playAlbum(albumId);
    } else if (mixId) {
        playDailyMix(mixId);
    }
}

// Registrar delegación (solo una vez)
function setupAlbumCardPlayButtons() {
    document.removeEventListener('click', handleCardPlayClick);
    document.addEventListener('click', handleCardPlayClick);
}

// Inicializar
setupAlbumCardPlayButtons();

// Re-bind after SPA navigation
if (typeof window.initPageBindings === 'function') {
    const originalInitPageBindings = window.initPageBindings;
    window.initPageBindings = function() {
        originalInitPageBindings();
        setupAlbumCardPlayButtons();
    };
} else {
    window.initPageBindings = setupAlbumCardPlayButtons;
}

// Exportar funciones para uso global
window.playAlbum = playAlbum;
window.playDailyMix = playDailyMix;
window.setupAlbumCardPlayButtons = setupAlbumCardPlayButtons;
