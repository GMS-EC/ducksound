import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Play, Clock, ArrowLeft, MoreVertical, Plus } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Album, Cancion } from "../types";
import Equalizer from "../components/Equalizer";
import { useContextMenu } from "../contexts/ContextMenuContext";

interface Disco { disc_num: number; songs: Cancion[]; }

export default function AlbumDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();
  const [album, setAlbum] = useState<Album | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  
  const [showAddDropdown, setShowAddDropdown] = useState(false);
  const [collections, setCollections] = useState<any[]>([]);

  const fetchCollections = () => {
    client.get("/api/coleccion-lista")
      .then((res) => setCollections(res.data || []))
      .catch(console.error);
  };

  const handleAddAlbumToCollection = async (colId: number) => {
    if (!id) return;
    try {
      await client.post(`/api/colecciones/${colId}/add-album/${id}`);
      alert("Álbum añadido a la colección.");
      setShowAddDropdown(false);
    } catch (err) {
      console.error(err);
      alert("Error al añadir el álbum.");
    }
  };

  const handleCreateAndAddAlbum = async () => {
    const nombre = window.prompt("Ingresa el nombre para la nueva colección:");
    if (!nombre || !nombre.trim()) return;
    try {
      const res = await client.post("/api/colecciones/crear", {
        nombre: nombre.trim(),
        descripcion: "",
      });
      if (res.data && res.data.id && id) {
        await client.post(`/api/colecciones/${res.data.id}/add-album/${id}`);
        alert("Colección creada y álbum añadido.");
        window.dispatchEvent(new Event("ducksound:collections_changed"));
      }
      setShowAddDropdown(false);
    } catch (err) {
      console.error(err);
      alert("Error al crear la colección.");
    }
  };

  const toggleAddDropdown = () => {
    if (!showAddDropdown) {
      fetchCollections();
    }
    setShowAddDropdown(!showAddDropdown);
  };

  useEffect(() => {
    if (!showAddDropdown) return;
    const handleOutsideClick = () => {
      setShowAddDropdown(false);
    };
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [showAddDropdown]);
  const [discos, setDiscos] = useState<Disco[]>([]);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [totalDuration, setTotalDuration] = useState(0);
  const [trackCount, setTrackCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    client.get("/album/" + id)
      .then((res) => {
        setAlbum(res.data.album);
        setDiscos(res.data.discos);
        setCoverUrl(res.data.cover_url);
        setTotalDuration(res.data.total_duration);
        setTrackCount(res.data.track_count);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const fmt = (s: number) => {
    if (!s || !isFinite(s)) return "0:00";
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    if (h > 0) return h + "h " + m + "m";
    return m + ":" + (sec < 10 ? "0" : "") + sec;
  };

  const playAll = () => { const all = discos.flatMap((d) => d.songs); if (all.length > 0) play(all, 0); };

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;
  if (!album) return <div style={{ padding: 32, color: "#9ca3af" }}>Álbum no encontrado</div>;

  const allSongs = discos.flatMap((d) => d.songs);

  return (
    <div className="album-detail">
      <button className="btn-back" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Volver</button>

      <div className="album-header">
        <div className="album-header-cover">
          {coverUrl ? (
            <img src={coverUrl} alt={album.titulo} />
          ) : (
            <span className="album-header-placeholder">♫</span>
          )}
        </div>
        <div>
          <div className="album-header-label">Álbum</div>
          <h1 className="album-header-title">{album.titulo}</h1>
          {album.anio && <div className="album-header-meta">{album.anio}</div>}
          <div className="album-header-meta">
            <span>{trackCount} canciones</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={14} />{fmt(totalDuration)}</span>
          </div>
          <div className="album-header-actions" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn-play-now" onClick={playAll} title="Reproducir">
              <Play size={22} fill="currentColor" />
            </button>
            <div style={{ position: "relative" }}>
              <button 
                className="btn-secondary" 
                onClick={(e) => { e.stopPropagation(); toggleAddDropdown(); }} 
                title="Añadir a playlist"
                style={{ display: "flex", alignItems: "center", gap: 6, height: 44, padding: "0 16px", borderRadius: 22, border: "1px solid var(--color-border)", background: "#222229", color: "#fff", cursor: "pointer", fontWeight: 500, transition: "background 0.15s" }}
              >
                <Plus size={18} />
                <span>Añadir a playlist</span>
              </button>
              {showAddDropdown && (
                <div className="album-add-dropdown" onClick={(e) => e.stopPropagation()}>
                  {collections.map((col) => (
                    <button key={col.id} className="dropdown-item" onClick={() => handleAddAlbumToCollection(col.id)}>
                      {col.nombre}
                    </button>
                  ))}
                  <div className="dropdown-divider" />
                  <button className="dropdown-item" onClick={handleCreateAndAddAlbum} style={{ fontWeight: 600 }}>
                    + Nueva colección
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="tracklist-standalone">
        <div style={{ display: "flex", justifyContent: "flex-end", padding: "0 12px 16px" }}>
          <input
            type="text"
            placeholder="Buscar en el álbum..."
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
        <div className="tracklist-header-grid">
          <div className="tracklist-header-item text-center">#</div>
          <div className="tracklist-header-item">Título</div>
          <div className="tracklist-header-item">Duración</div>
          <div className="tracklist-header-item"></div>
        </div>
        {(() => {
          const filteredAllSongs = allSongs.filter(c =>
            c.titulo.toLowerCase().includes(searchTerm.toLowerCase())
          );
          return discos.map((disco) => {
            const filteredDiscoSongs = disco.songs.filter(c =>
              c.titulo.toLowerCase().includes(searchTerm.toLowerCase())
            );
            if (filteredDiscoSongs.length === 0) return null;
            return (
              <div key={disco.disc_num}>
                {discos.length > 1 && (
                  <div className="section-header" style={{ padding: "16px 0 8px" }}>
                    <h2 className="section-title" style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.05em", color: "#9ca3af" }}>
                      Disco {disco.disc_num}
                    </h2>
                  </div>
                )}
                {filteredDiscoSongs.map((c, i) => {
                  const isCurrent = currentSong?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      className={`track-item-grid ${isCurrent ? `playing ${playing ? "" : "paused"}` : ""}`}
                      onClick={() => play(filteredAllSongs, filteredAllSongs.indexOf(c))}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        showMenu(e, c);
                      }}
                    >
                      {isCurrent ? (
                        <Equalizer />
                      ) : (
                        <span className="track-num-sm">{c.numero_pista || i + 1}</span>
                      )}
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
            );
          });
        })()}
      </div>
    </div>
  );
}
