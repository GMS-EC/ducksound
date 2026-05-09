// Dynamic Like Button Updater
// Actualiza el estado del botón de favoritos dinámicamente

function updateLikeButtonState() {
    // Obtener la canción actual del mini-player
    const songIdEl = document.getElementById('mini-title');
    if (!songIdEl || !songIdEl.dataset.songId) return;
    
    const songId = parseInt(songIdEl.dataset.songId);
    if (!songId) return;
    
    // Crear objeto song para la función updateLikeButton
    const song = {
        id: songId,
        titulo: songIdEl.textContent || 'Sin titulo'
    };
    
    // Llamar a la función existente si está disponible
    if (typeof updateLikeButton === 'function') {
        updateLikeButton(song);
        return;
    }
    
    // Si no existe, implementar la lógica directamente
    fetch('/api/favoritos')
        .then(r => r.json())
        .then(favIds => {
            const btnLike = document.getElementById('btn-like');
            if (btnLike) {
                const icon = btnLike.querySelector('i');
                const liked = favIds.includes(songId);
                icon.className = liked ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                btnLike.style.color = liked ? 'var(--accent)' : '';
                icon.style.color = liked ? 'var(--accent)' : '';
            }
        })
        .catch(() => {});
}

// Función para observar cambios en el mini-player
function setupLikeButtonObserver() {
    // Observar cambios en el título de la canción
    const miniTitle = document.getElementById('mini-title');
    if (!miniTitle) return;
    
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-song-id') {
                // La canción cambió, actualizar el botón de favoritos
                setTimeout(updateLikeButtonState, 100);
            }
            if (mutation.type === 'childList') {
                // El texto cambió, actualizar el botón de favoritos
                setTimeout(updateLikeButtonState, 100);
            }
        });
    });
    
    observer.observe(miniTitle, {
        attributes: true,
        childList: true,
        subtree: true,
        attributeFilter: ['data-song-id']
    });
}

// Función para configurar eventos de mensajes del iframe
function setupLikeButtonMessageListener() {
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'state' && event.data.state && event.data.state.song) {
            // El estado del reproductor cambió, actualizar el botón de favoritos
            setTimeout(updateLikeButtonState, 100);
        }
    });
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Configurar observador
    setupLikeButtonObserver();
    
    // Configurar listener de mensajes
    setupLikeButtonMessageListener();
    
    // Actualización inicial
    setTimeout(updateLikeButtonState, 500);
    
    // Actualización periódica como fallback
    setInterval(updateLikeButtonState, 2000);
});

// También actualizar cuando el usuario haga clic en el botón de favoritos
document.addEventListener('click', (e) => {
    if (e.target.closest('#btn-like')) {
        // Después de un breve tiempo, verificar el estado actualizado
        setTimeout(updateLikeButtonState, 300);
    }
});

// Exportar funciones para uso global
window.updateLikeButtonState = updateLikeButtonState;
window.setupLikeButtonObserver = setupLikeButtonObserver;
