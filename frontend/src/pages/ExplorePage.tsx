import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import client from "../api/client";
import type { Artista, AlbumData } from "../types";
import { usePlayer } from "../contexts/PlayerContext";

export default function ExplorePage() {
  const navigate = useNavigate();
  const { play } = usePlayer();
  const [artists, setArtists] = useState<Artista[]>([]);
  const [albums, setAlbums] = useState<AlbumData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/explore")
      .then((res) => {
        setArtists(res.data.artists);
        setAlbums(res.data.albums_data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;
  }

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Explorar</h1>
      </div>

      <div className="section-header" style={{ paddingTop: 32 }}>
        <h2 className="section-title">Artistas</h2>
      </div>
      <div className="card-grid">
        {artists.map((a) => (
          <div key={a.id} className="artist-card-big" onClick={() => navigate("/artist/" + a.id)}>
            <div className="artist-card-big-cover">
              {a.foto_url ? (
                <img src={a.foto_url} alt={a.nombre} />
              ) : (
                <span className="artist-card-big-placeholder">{a.nombre.charAt(0)}</span>
              )}
            </div>
            <div className="artist-card-big-name">{a.nombre}</div>
          </div>
        ))}
      </div>

      <div className="section-header" style={{ paddingTop: 32 }}>
        <h2 className="section-title">Álbumes</h2>
      </div>
      <div className="card-grid">
        {albums.map((al) => (
          <div key={al.album_id} className="album-card" onClick={() => navigate("/album/" + al.album_id)}>
            <div className="album-card-cover">
              {al.cover_url ? (
                <img src={al.cover_url} alt={al.titulo} />
              ) : (
                <span className="album-card-placeholder">♫</span>
              )}
              <div className="album-card-overlay">
                <button className="album-card-play" onClick={(e) => { e.stopPropagation(); /* play album */ }}>
                  <Play size={18} fill="currentColor" />
                </button>
              </div>
            </div>
            <div className="album-card-info">
              <div className="album-card-title">{al.titulo}</div>
              <div className="album-card-meta">{al.track_count} canciones</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
