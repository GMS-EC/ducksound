import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import client from "../api/client";

export default function AlbumsPage() {
  const navigate = useNavigate();
  const [albums, setAlbums] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/albums")
      .then((res) => setAlbums(res.data.albums_data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">\u00c1lbumes</h1>
        <p className="page-subtitle">{albums.length} \u00e1lbumes en la biblioteca</p>
      </div>
      <div className="section-header" style={{ paddingTop: 32 }}></div>
      <div className="card-grid">
        {albums.map((al: any) => (
          <div key={al.album_id} className="album-card" onClick={() => navigate("/album/" + al.album_id)}>
            <div className="album-card-cover">
              {al.cover_url ? <img src={al.cover_url} alt={al.titulo} /> : <span className="album-card-placeholder">\u266b</span>}
              <div className="album-card-overlay">
                <button className="album-card-play" onClick={(e) => { e.stopPropagation(); }}>
                  <Play size={18} fill="currentColor" />
                </button>
              </div>
            </div>
            <div className="album-card-info">
              <div className="album-card-title">{al.titulo}</div>
              <div className="album-card-meta">{al.track_count} canciones{al.total_duration ? " \u2022 " + Math.floor(al.total_duration / 60) + " min" : ""}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
