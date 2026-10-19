import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ListMusic, MoreVertical } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Coleccion, Cancion } from "../types";
import Equalizer from "../components/Equalizer";
import { useContextMenu } from "../contexts/ContextMenuContext";

export default function ColeccionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();
  const [coleccion, setColeccion] = useState<Coleccion | null>(null);
  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

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
          <div style={{ display: "flex", justifyContent: "flex-end", padding: "0 12px 16px" }}>
            <input
              type="text"
              placeholder="Buscar en esta colección..."
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
