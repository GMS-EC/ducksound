import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Shuffle, MoreVertical } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import { useContextMenu } from "../contexts/ContextMenuContext";
import Equalizer from "../components/Equalizer";
import type { AlbumData, Artista, Cancion, DailyMix } from "../types";

interface DashboardData {
  daily_mixes: DailyMix[];
  spotlight_mix: DailyMix | null;
  albumes_recientes: AlbumData[];
  artistas_recientes: Artista[];
  canciones_recientes: Cancion[];
  top_canciones: { cancion: Cancion; plays: number }[];
  dashboard_stats: { canciones: number; albumes: number; artistas: number };
}

const formatDuration = (seconds: number | null) => {
  if (!seconds || !Number.isFinite(seconds)) return "0:00";
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${String(secs).padStart(2, "0")}`;
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();

  useEffect(() => {
    client.get("/dashboard")
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handlePlayAlbum = async (e: React.MouseEvent, albumId: number) => {
    e.stopPropagation();
    try {
      const res = await client.get(`/api/album/${albumId}/canciones`);
      if (res.data?.length) {
        play(res.data, 0);
      }
    } catch (err) {
      console.error("Error playing album:", err);
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        Cargando...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-state">
        <div className="empty-icon">♫</div>
        <h2 className="empty-title">No hay música disponible</h2>
        <p className="empty-text">Agrega canciones a la biblioteca para empezar</p>
      </div>
    );
  }

  const { spotlight_mix, albumes_recientes, artistas_recientes, top_canciones, dashboard_stats } = data;

  return (
    <div className="dashboard-page">
      {spotlight_mix && (
        <>
          <div className="spotlight">
            <div className="spotlight-cover">
              <img
                src={`/daily-mix-cover/${spotlight_mix.id}`}
                alt={spotlight_mix.nombre}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = 'none';
                  if (e.currentTarget.nextElementSibling) {
                    (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline';
                  }
                }}
              />
              <span style={{ fontSize: 48, color: "#666", display: 'none' }}>♪</span>
            </div>
            <div className="spotlight-copy">
              <div className="spotlight-kicker">Mezcla diaria</div>
              <h1 className="spotlight-title">{spotlight_mix.nombre}</h1>
              <p className="spotlight-description">
                {spotlight_mix.canciones.length} canciones seleccionadas para este momento.
              </p>
              <div className="spotlight-actions">
                <button
                  className="btn-play-now"
                  onClick={() => play(spotlight_mix.canciones, 0)}
                  title="Reproducir"
                >
                  <Play size={22} fill="currentColor" />
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    if (spotlight_mix.canciones.length) {
                      play(spotlight_mix.canciones, Math.floor(Math.random() * spotlight_mix.canciones.length));
                    }
                  }}
                >
                  <Shuffle size={14} />
                  Aleatorio
                </button>
              </div>
            </div>
          </div>

          <div className="stat-strip">
            <div className="stat-item" onClick={() => navigate("/explore")}>
              <strong>{dashboard_stats.canciones}</strong>
              <span>Canciones</span>
            </div>
            <div className="stat-item" onClick={() => navigate("/explore")}>
              <strong>{dashboard_stats.albumes}</strong>
              <span>Álbumes</span>
            </div>
            <div className="stat-item" onClick={() => navigate("/explore")}>
              <strong>{dashboard_stats.artistas}</strong>
              <span>Artistas</span>
            </div>
          </div>
        </>
      )}

      {data.daily_mixes.length > 0 && (
        <section className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Tus mixes</h2>
          </div>
          <div className="scroll-grid">
            {data.daily_mixes.map((mix) => (
              <div key={mix.id} className="card" onClick={() => play(mix.canciones, 0)}>
                <div className="card-cover">
                  <img
                    src={`/daily-mix-cover/${mix.id}`}
                    alt={mix.nombre}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'none';
                      if (e.currentTarget.nextElementSibling) {
                        (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline';
                      }
                    }}
                  />
                  <span style={{ fontSize: 28, opacity: 0.6, display: 'none' }}>♪</span>
                  <div className="card-overlay">
                    <button className="card-play-btn" onClick={(e) => { e.stopPropagation(); play(mix.canciones, 0); }}>
                      <Play size={18} fill="currentColor" />
                    </button>
                  </div>
                </div>
                <div className="card-info">
                  <div className="card-title">{mix.nombre}</div>
                  <div className="card-subtitle">{mix.canciones.length} canciones</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {albumes_recientes.length > 0 && (
        <section className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Álbumes recientes</h2>
          </div>
          <div className="scroll-grid">
            {albumes_recientes.map((album) => {
              const albumId = album.album_id || album.id || (album.album && album.album.id);
              const title = album.titulo || (album.album && album.album.titulo) || "";
              const year = album.anio ?? (album.album && album.album.anio);
              return (
                <div key={albumId} className="card" onClick={() => navigate(`/album/${albumId}`)}>
                  <div className="card-cover">
                    {album.cover_url ? (
                      <img src={album.cover_url} alt={title} />
                    ) : (
                      <span className="card-placeholder">♫</span>
                    )}
                    <div className="card-overlay">
                      <button
                        className="card-play-btn"
                        title="Reproducir álbum"
                        onClick={(e) => handlePlayAlbum(e, albumId!)}
                      >
                        <Play size={18} fill="currentColor" />
                      </button>
                    </div>
                  </div>
                  <div className="card-info">
                    <div className="card-title">{title}</div>
                    <div className="card-subtitle">
                      {album.track_count} canciones{year ? ` · ${year}` : ""}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {artistas_recientes.length > 0 && (
        <section className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Artistas</h2>
          </div>
          <div className="scroll-grid artists-row">
            {artistas_recientes.map((artist) => (
              <div key={artist.id} className="artist-card" onClick={() => navigate(`/artist/${artist.id}`)}>
                <div className="artist-cover">
                  {artist.foto_url ? (
                    <img src={artist.foto_url} alt={artist.nombre} />
                  ) : (
                    <span>{artist.nombre.charAt(0)}</span>
                  )}
                </div>
                <div className="artist-name">{artist.nombre}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {top_canciones.length > 0 && (
        <section className="tracklist">
          <div className="shelf-header" style={{ padding: 0, marginBottom: 16 }}>
            <h2 className="shelf-title">Más escuchadas</h2>
          </div>
          <div className="tracklist-header-grid-6">
            <div className="tracklist-header-item text-center">#</div>
            <div className="tracklist-header-item"></div>
            <div className="tracklist-header-item">Título</div>
            <div className="tracklist-header-item">Reproducciones</div>
            <div className="tracklist-header-item">Duración</div>
            <div className="tracklist-header-item"></div>
          </div>
          {top_canciones.map((item, index) => {
            const isCurrent = currentSong?.id === item.cancion.id;
            return (
              <div
                key={item.cancion.id}
                className={`track-item ${isCurrent ? `playing ${playing ? "" : "paused"}` : ""}`}
                onClick={() => play(top_canciones.map((track) => track.cancion), index)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  showMenu(e, item.cancion);
                }}
              >
                {isCurrent ? (
                  <Equalizer />
                ) : (
                  <span className="track-num">{index + 1}</span>
                )}
                <div className="track-cover-sm">
                  <img
                    src={`/album-art/${item.cancion.id}?size=small`}
                    alt={item.cancion.titulo}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'none';
                      if (e.currentTarget.nextElementSibling) {
                        (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline';
                      }
                    }}
                  />
                  <span style={{ fontSize: 14, color: "#666", display: 'none' }}>♪</span>
                </div>
                <div className="track-info">
                  <div className="track-title">{item.cancion.titulo}</div>
                  <div className="track-artist">{item.cancion.artista}</div>
                </div>
                <div className="track-plays">{item.plays} plays</div>
                <div className="track-duration">{formatDuration(item.cancion.duracion)}</div>
                <div className="track-options">
                  <button
                    className="btn-options"
                    onClick={(e) => {
                      e.stopPropagation();
                      showMenu(e, item.cancion);
                    }}
                    title="Opciones"
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
