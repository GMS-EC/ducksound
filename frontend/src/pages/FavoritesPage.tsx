import { useState, useEffect } from "react";
import { Heart, Play } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion } from "../types";

export default function FavoritesPage() {
  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loading, setLoading] = useState(true);
  const { play } = usePlayer();

  const fetchFavorites = () => {
    client.get("/favoritos")
      .then((res) => setSongs(res.data.favoritos || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchFavorites(); }, []);

  const toggleLike = async (cancionId: number) => {
    try {
      await client.post("/api/favoritos/toggle/" + cancionId);
      setSongs((prev) => prev.filter((s) => s.id !== cancionId));
    } catch (e) { console.error(e); }
  };

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
          {songs.map((c, i) => (
            <div key={c.id} className="track-item-grid" onClick={() => play(songs, i)}>
              <span className="track-num-sm">{i + 1}</span>
              <div className="track-info">
                <div className="track-title">{c.titulo}</div>
                <div className="track-artist">{c.artista}</div>
              </div>
              <div className="track-duration">
                {c.duracion ? Math.floor(c.duracion / 60) + ":" + String(c.duracion % 60).padStart(2, "0") : "—"}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); toggleLike(c.id); }}
                style={{ background: "none", border: "none", color: "#d95840", cursor: "pointer", padding: 4, justifySelf: "end" }}
                title="Quitar de favoritos"
              >
                <Heart size={16} fill="currentColor" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
