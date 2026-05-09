// Album Card Player
// Permite reproducir álbumes directamente desde las tarjetas

function playAlbum(albumId) {
    fetch(`/api/album/${albumId}/canciones`)
        .then(r => r.json())
        .then(songs => {
            if (songs && songs.length > 0) {
                // Send playlist to player
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    // Play first song
                    setTimeout(() => {
                        iframe.contentWindow.postMessage({
                            type: 'command', 
                            cmd: 'playSong', 
                            index: 0
                        }, window.location.origin);
                    }, 100);
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
                // Send playlist to player
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    // Play first song
                    setTimeout(() => {
                        iframe.contentWindow.postMessage({
                            type: 'command', 
                            cmd: 'playSong', 
                            index: 0
                        }, window.location.origin);
                    }, 100);
                }
            }
        })
        .catch(err => console.error('Error playing daily mix:', err));
}

function setupAlbumCardPlayButtons() {
    document.querySelectorAll('.album-card-play').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const albumId = this.dataset.albumId;
            const mixId = this.dataset.mixId;
            
            if (albumId) {
                playAlbum(albumId);
            } else if (mixId) {
                playDailyMix(mixId);
            }
        });
    });
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    setupAlbumCardPlayButtons();
});

// También inicializar después de navegación SPA
window.addEventListener('load', () => {
    setTimeout(setupAlbumCardPlayButtons, 500);
});

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
