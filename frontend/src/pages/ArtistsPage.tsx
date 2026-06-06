import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";

export default function ArtistsPage() {
  const navigate = useNavigate();
  const [artists, setArtists] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/artists")
      .then((res) => setArtists(res.data.artists_data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Artistas</h1>
        <p className="page-subtitle">{artists.length} artistas en la biblioteca</p>
      </div>
      <div className="section-header" style={{ paddingTop: 32 }}></div>
      <div className="card-grid">
        {artists.map((item: any) => (
          <div key={item.artist.id} className="artist-card-big" onClick={() => navigate("/artist/" + item.artist.id)}>
            <div className="artist-card-big-cover">
              {item.artist.foto_url ? (
                <img src={item.artist.foto_url} alt={item.artist.nombre} />
              ) : (
                <span className="artist-card-big-placeholder">{item.artist.nombre.charAt(0)}</span>
              )}
            </div>
            <div className="artist-card-big-name">{item.artist.nombre}</div>
            <div className="artist-card-big-meta">{item.album_count} álbumes • {item.song_count} canciones</div>
          </div>
        ))}
      </div>
    </div>
  );
}
