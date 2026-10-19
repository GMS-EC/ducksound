import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Play, ArrowLeft, MoreVertical } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Artista, AlbumData, Cancion } from "../types";
import Equalizer from "../components/Equalizer";
import { useContextMenu } from "../contexts/ContextMenuContext";

export default function ArtistDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();
  const [artist, setArtist] = useState<Artista | null>(null);
  const [albums, setAlbums] = useState<AlbumData[]>([]);
  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (!id) return;
    client.get("/artist/" + id)
      .then((res) => {
        setArtist(res.data.artist);
        setAlbums(res.data.albums_data);
        setSongs(res.data.songs);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const playAll = () => { if (songs.length > 0) play(songs, 0); };

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;
  if (!artist) return <div style={{ padding: 32, color: "#9ca3af" }}>Artista no encontrado</div>;

  return (
    <div className="artist-detail">
      <button className="btn-back" onClick={() => navigate(-1)}><ArrowLeft size={16} /> Volver</button>

      <div className="artist-header">
        <div className="artist-header-cover">
          {artist.foto_url ? (
            <img src={artist.foto_url} alt={artist.nombre} />
          ) : (
            <span className="artist-header-placeholder">{artist.nombre.charAt(0)}</span>
          )}
        </div>
        <div>
          <div className="artist-header-label">Artista</div>
          <h1 className="artist-header-title">{artist.nombre}</h1>
          {artist.biografia && <p className="artist-bio">{artist.biografia}</p>}
          <div className="artist-header-stats">
            <span>{albums.length} álbumes</span>
            <span>{songs.length} canciones</span>
          </div>
          <div className="artist-header-actions">
            <button className="btn-play-now" onClick={playAll} title="Reproducir todo">
              <Play size={22} fill="currentColor" />
            </button>
          </div>
        </div>
      </div>

      {albums.length > 0 && (
        <>
          <div className="section-header" style={{ padding: "0 0 16px" }}>
            <h2 className="section-title">Álbumes</h2>
          </div>
          <div className="card-grid" style={{ padding: "0 0 32px" }}>
            {albums.map((al) => (
              <div key={al.album.id} className="album-card" onClick={() => navigate("/album/" + al.album.id)}>
                <div className="album-card-cover">
                  {al.cover_url ? <img src={al.cover_url} alt={al.album.titulo} /> : <span className="album-card-placeholder">♫</span>}
                  <div className="album-card-overlay"><button className="album-card-play"><Play size={18} fill="currentColor" /></button></div>
                </div>
                <div className="album-card-info">
                  <div className="album-card-title">{al.album.titulo}</div>
                  <div className="album-card-meta">{al.track_count} canciones</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="tracklist-standalone">
        <div className="section-header" style={{ padding: "0 0 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 className="section-title">Canciones</h2>
          <input
            type="text"
            placeholder="Buscar canción..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              background: "#222229",
              border: "1px solid var(--color-border)",
              color: "#fff",
              padding: "6px 12px",
              borderRadius: "16px",
              fontSize: "13px",
              width: "180px",
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
          (c.album && c.album.toLowerCase().includes(searchTerm.toLowerCase()))
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
                <div className="track-artist">{c.album}</div>
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
    </div>
  );
}
