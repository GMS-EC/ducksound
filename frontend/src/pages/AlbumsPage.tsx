import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { AlbumData } from "../types";

export default function AlbumsPage() {
  const navigate = useNavigate();
  const { play } = usePlayer();
  const [albums, setAlbums] = useState<AlbumData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/albums")
      .then((res) => setAlbums(res.data.albums_data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handlePlayAlbum = async (e: React.MouseEvent, albumId: number) => {
    e.stopPropagation();
    try {
      const res = await client.get(`/api/album/${albumId}/canciones`);
      if (res.data && res.data.length > 0) {
        play(res.data, 0);
      }
    } catch (err) {
      console.error("Error playing album:", err);
    }
  };

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Álbumes</h1>
        <p className="page-subtitle">{albums.length} álbumes en la biblioteca</p>
      </div>
      <div className="section-header" style={{ paddingTop: 32 }}></div>
      <div className="card-grid">
        {albums.map((al) => (
          <div key={al.album.id} className="album-card" onClick={() => navigate("/album/" + al.album.id)}>
            <div className="album-card-cover">
              {al.cover_url ? <img src={al.cover_url} alt={al.album.titulo} /> : <span className="album-card-placeholder">♫</span>}
              <div className="album-card-overlay">
                <button className="album-card-play" onClick={(e) => handlePlayAlbum(e, al.album.id)}>
                  <Play size={18} fill="currentColor" />
                </button>
              </div>
            </div>
            <div className="album-card-info">
              <div className="album-card-title">{al.album.titulo}</div>
              <div className="album-card-meta">{al.track_count} canciones{al.total_duration ? " • " + Math.floor(al.total_duration / 60) + " min" : ""}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
