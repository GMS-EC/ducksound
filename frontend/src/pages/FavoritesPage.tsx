import { useState, useEffect } from "react";
import { Heart, MoreVertical } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion } from "../types";
import Equalizer from "../components/Equalizer";
import { useContextMenu } from "../contexts/ContextMenuContext";

export default function FavoritesPage() {
  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();

  const fetchFavorites = () => {
    client.get("/favoritos")
      .then((res) => setSongs(res.data.favoritos || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFavorites();
    const handleFavsChanged = () => {
      fetchFavorites();
    };
    window.addEventListener("ducksound:favorites_changed", handleFavsChanged);
    return () => window.removeEventListener("ducksound:favorites_changed", handleFavsChanged);
  }, []);


  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">Favoritos</h1>
          <p className="page-subtitle">{songs.length} canciones</p>
        </div>
      </div>

      {songs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><Heart size={48} /></div>
          <h2 className="empty-title">No tienes canciones favoritas</h2>
          <p className="empty-text">Presiona el corazón en cualquier canción para agregarla</p>
        </div>
      ) : (
        <div className="tracklist-standalone" style={{ paddingTop: 24 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", padding: "0 12px 16px" }}>
            <input
              type="text"
              placeholder="Buscar en favoritos..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                background: "#222229",
                border: "1px solid var(--color-border)",
                color: "#fff",
                padding: "6px 12px",
                borderRadius: "16px",
                fontSize: "13px",
                width: "200px",
                outline: "none"
              }}
            />
          </div>
          <div className="tracklist-header-grid-with-cover">
            <div className="tracklist-header-item text-center">#</div>
            <div className="tracklist-header-item"></div>
            <div className="tracklist-header-item">Título</div>
            <div className="tracklist-header-item">Duración</div>
            <div className="tracklist-header-item"></div>
          </div>
          {songs.filter(c => 
            c.titulo.toLowerCase().includes(searchTerm.toLowerCase()) || 
            (c.artista && c.artista.toLowerCase().includes(searchTerm.toLowerCase()))
          ).map((c, i, filtered) => {
            const isCurrent = currentSong?.id === c.id;
            return (
              <div
                key={c.id}
                className={`track-item-with-cover ${isCurrent ? `playing ${playing ? "" : "paused"}` : ""}`}
                onClick={() => play(filtered, i)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  showMenu(e, c);
                }}
              >
                {isCurrent ? (
                  <Equalizer />
                ) : (
                  <span className="track-num-sm">{i + 1}</span>
                )}
                <div className="track-cover-sm" style={{ width: 32, height: 32, borderRadius: 4, overflow: "hidden", background: "#2a2a33", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <img
                    src={`/album-art/${c.id}?size=small`}
                    alt={c.titulo}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                      const sibling = e.currentTarget.nextElementSibling as HTMLElement;
                      if (sibling) sibling.style.display = "block";
                    }}
                  />
                  <span style={{ display: "none" }}>♪</span>
                </div>
                <div className="track-info">
                  <div className="track-title">{c.titulo}</div>
                  <div className="track-artist">{c.artista}</div>
                </div>
                <div className="track-duration">
                  {c.duracion ? Math.floor(c.duracion / 60) + ":" + String(c.duracion % 60).padStart(2, "0") : "—"}
                </div>
                <div className="track-options">
                  <button
                    className="btn-options"
                    onClick={(e) => {
                      e.stopPropagation();
                      showMenu(e, c);
                    }}
                    title="Opciones"
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
