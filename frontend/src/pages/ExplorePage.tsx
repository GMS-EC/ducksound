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
          <div key={al.album.id} className="album-card" onClick={() => navigate("/album/" + al.album.id)}>
            <div className="album-card-cover">
              {al.cover_url ? (
                <img src={al.cover_url} alt={al.album.titulo} />
              ) : (
                <span className="album-card-placeholder">♫</span>
              )}
              <div className="album-card-overlay">
                <button className="album-card-play" onClick={(e) => handlePlayAlbum(e, al.album.id)}>
                  <Play size={18} fill="currentColor" />
                </button>
              </div>
            </div>
            <div className="album-card-info">
              <div className="album-card-title">{al.album.titulo}</div>
              <div className="album-card-meta">{al.track_count} canciones</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
