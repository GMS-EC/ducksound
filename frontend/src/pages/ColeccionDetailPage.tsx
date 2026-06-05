import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ListMusic } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Coleccion, Cancion } from "../types";

export default function ColeccionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { play } = usePlayer();
  const [coleccion, setColeccion] = useState<Coleccion | null>(null);
  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    client.get("/coleccion/" + id)
      .then((res) => {
        setColeccion(res.data.coleccion);
        setSongs(res.data.songs || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;
  if (!coleccion) return <div style={{ padding: 32, color: "#9ca3af" }}>Colección no encontrada</div>;

  return (
    <div className="album-detail">
      <button className="btn-back" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Volver</button>

      <div className="album-header" style={{ marginBottom: 24 }}>
        <div className="album-header-cover" style={{ background: "linear-gradient(135deg, #d95840, #1a1a1f)" }}>
          <ListMusic size={48} style={{ color: "rgba(255,255,255,0.5)" }} />
        </div>
        <div>
          <div className="album-header-label">Colección</div>
          <h1 className="album-header-title">{coleccion.nombre}</h1>
          {coleccion.descripcion && <p style={{ color: "#9ca3af", fontSize: 14, marginTop: 4 }}>{coleccion.descripcion}</p>}
          <div className="album-header-meta">
            <span>{songs.length} canciones</span>
          </div>
        </div>
      </div>

      {songs.length > 0 ? (
        <div className="tracklist-standalone">
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
              <div></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><ListMusic size={48} /></div>
          <h2 className="empty-title">Esta colección está vacía</h2>
          <p className="empty-text">Agrega canciones desde el explorador</p>
        </div>
      )}
    </div>
  );
}
