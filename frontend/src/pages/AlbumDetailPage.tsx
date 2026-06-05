import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Play, Clock, ArrowLeft } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Album, Cancion } from "../types";

interface Disco { disc_num: number; songs: Cancion[]; }

export default function AlbumDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { play } = usePlayer();
  const [album, setAlbum] = useState<Album | null>(null);
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
          <div className="album-header-actions">
            <button className="btn-play-now" onClick={playAll} title="Reproducir">
              <Play size={22} fill="currentColor" />
            </button>
          </div>
        </div>
      </div>

      <div className="tracklist-standalone">
        {discos.map((disco) => (
          <div key={disco.disc_num}>
            {discos.length > 1 && (
              <div className="section-header" style={{ padding: "16px 0 8px" }}>
                <h2 className="section-title" style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: "0.05em", color: "#9ca3af" }}>
                  Disco {disco.disc_num}
                </h2>
              </div>
            )}
            {disco.songs.map((c, i) => (
              <div key={c.id} className="track-item-grid" onClick={() => play(allSongs, allSongs.indexOf(c))}>
                <span className="track-num-sm">{c.numero_pista || i + 1}</span>
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
        ))}
      </div>
    </div>
  );
}
