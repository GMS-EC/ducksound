import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { Play, Plus, Heart, Music2, Info, ArrowRight, Loader2 } from "lucide-react";
import client from "../api/client";
import { useContextMenu } from "../contexts/ContextMenuContext";
import { usePlayer } from "../contexts/PlayerContext";
import type { Coleccion } from "../types";

export default function ContextMenu() {
  const { menuPosition, menuSong, closeMenu, showInfoModal } = useContextMenu();
  const { play, addToQueue } = usePlayer();

  const [isLiked, setIsLiked] = useState(false);
  const [collections, setCollections] = useState<Coleccion[]>([]);
  const [loadingCollections, setLoadingCollections] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Position adjustments to prevent off-screen rendering
  const [adjustedPos, setAdjustedPos] = useState({ left: 0, top: 0 });

  useEffect(() => {
    if (!menuPosition) return;

    // Viewport coordinates
    const { x, y } = menuPosition;
    const menuWidth = 200;
    const menuHeight = 220; // approximate main menu height
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;

    let left = x;
    let top = y;

    if (x + menuWidth > screenWidth) {
      left = screenWidth - menuWidth - 10;
    }
    if (y + menuHeight > screenHeight) {
      top = screenHeight - menuHeight - 10;
    }

    setAdjustedPos({ left: Math.max(0, left), top: Math.max(0, top) });
  }, [menuPosition]);

  // Fetch favorite status and collections
  useEffect(() => {
    if (!menuSong) return;

    // Check if song is liked
    client
      .get("/api/favoritos")
      .then((res) => {
        if (Array.isArray(res.data)) {
          setIsLiked(res.data.includes(menuSong.id));
        }
      })
      .catch(console.error);

    // Fetch user playlists/collections
    setLoadingCollections(true);
    client
      .get("/api/coleccion-lista")
      .then((res) => {
        setCollections(res.data || []);
      })
      .catch(console.error)
      .finally(() => {
        setLoadingCollections(false);
      });
  }, [menuSong]);

  // Handle clicking outside and Escape key
  useEffect(() => {
    if (!menuPosition) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeMenu();
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuPosition, closeMenu]);

  if (!menuPosition || !menuSong) return null;

  const handlePlay = () => {
    play([menuSong], 0);
    closeMenu();
  };

  const handleAddToQueue = () => {
    addToQueue([menuSong]);
    closeMenu();
  };

  const handleToggleLike = async () => {
    try {
      await client.post(`/api/favoritos/toggle/${menuSong.id}`);
      setIsLiked(!isLiked);
      // Optional: if we are on the Favorites page, we might want to let the page reload,
      // but since toggle is a clean action, we'll let the user see the change instantly.
      // We can also trigger a window event or simple state reload if we want page integration,
      // but for general tracklists, updating the like state is enough.
      if (window.location.pathname.includes("/favorites")) {
        // Simple reload or custom event to notify FavoritesPage
        window.dispatchEvent(new Event("ducksound:favorites_changed"));
      }
      closeMenu();
    } catch (err) {
      console.error("Error toggling like status:", err);
    }
  };

  const handleAddToCollection = async (colId: number) => {
    try {
      await client.post(`/api/colecciones/${colId}/add-cancion/${menuSong.id}`);
      alert(`Canción añadida a la colección.`);
      closeMenu();
    } catch (err) {
      console.error("Error adding to collection:", err);
      alert("Error al añadir la canción a la colección.");
    }
  };

  const handleCreateAndAddCollection = async () => {
    const nombre = window.prompt("Ingresa el nombre para la nueva colección:");
    if (!nombre || !nombre.trim()) return;

    try {
      const res = await client.post("/api/colecciones/crear", {
        nombre: nombre.trim(),
        descripcion: "",
      });
      if (res.data && res.data.id) {
        await client.post(`/api/colecciones/${res.data.id}/add-cancion/${menuSong.id}`);
        alert(`Colección creada y canción añadida.`);
        // Notify sidebar or page to refresh playlists
        window.dispatchEvent(new Event("ducksound:collections_changed"));
      }
      closeMenu();
    } catch (err) {
      console.error("Error creating collection:", err);
      alert("Error al crear la colección.");
    }
  };

  return createPortal(
    <div
      ref={menuRef}
      className="context-menu-wrapper"
      style={{
        left: `${adjustedPos.left}px`,
        top: `${adjustedPos.top}px`,
      }}
    >
      <button className="context-menu-item" onClick={handlePlay}>
        <div className="context-menu-item-content">
          <Play size={14} fill="currentColor" />
          <span>Reproducir ahora</span>
        </div>
      </button>

      <button className="context-menu-item" onClick={handleAddToQueue}>
        <div className="context-menu-item-content">
          <Plus size={14} />
          <span>Añadir a la cola</span>
        </div>
      </button>

      <button className="context-menu-item" onClick={handleToggleLike}>
        <div className="context-menu-item-content">
          <Heart size={14} fill={isLiked ? "currentColor" : "none"} style={{ color: isLiked ? "var(--color-accent)" : "inherit" }} />
          <span>{isLiked ? "Quitar de favoritos" : "Añadir a favoritos"}</span>
        </div>
      </button>

      {/* Submenu for adding to collection/playlist */}
      <div className="context-menu-item context-menu-submenu-trigger">
        <div className="context-menu-item-content">
          <Music2 size={14} />
          <span>Añadir a colección</span>
        </div>
        <ArrowRight size={12} />
        
        <div className="context-menu-submenu">
          {loadingCollections ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "8px 0" }}>
              <Loader2 className="animate-spin" size={14} style={{ color: "var(--color-muted)" }} />
            </div>
          ) : (
            <>
              {collections.map((col) => (
                <button
                  key={col.id}
                  className="context-menu-item"
                  onClick={() => handleAddToCollection(col.id)}
                >
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {col.nombre}
                  </span>
                </button>
              ))}
              <div style={{ height: "1px", background: "rgba(255,255,255,0.06)", margin: "4px 0" }} />
              <button className="context-menu-item" onClick={handleCreateAndAddCollection}>
                <div className="context-menu-item-content">
                  <Plus size={12} />
                  <span style={{ fontWeight: 600 }}>+ Nueva colección</span>
                </div>
              </button>
            </>
          )}
        </div>
      </div>

      <div style={{ height: "1px", background: "rgba(255,255,255,0.06)", margin: "4px 0" }} />

      <button className="context-menu-item" onClick={() => showInfoModal(menuSong)}>
        <div className="context-menu-item-content">
          <Info size={14} />
          <span>Información de la música</span>
        </div>
      </button>
    </div>,
    document.body
  );
}
