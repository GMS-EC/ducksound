import { useState, useEffect } from "react";
import { Play, Shuffle } from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion, DailyMix, Album, Artista } from "../types";

interface DashboardData {
  daily_mixes: DailyMix[];
  spotlight_mix: DailyMix | null;
  albumes_recientes: Album[];
  artistas_recientes: Artista[];
  canciones_recientes: Cancion[];
  top_canciones: { cancion: Cancion; plays: number }[];
  dashboard_stats: { canciones: number; albumes: number; artistas: number };
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { play } = usePlayer();

  useEffect(() => {
    client.get("/dashboard")
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>
        Cargando...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-state">
        <div className="empty-icon">♪</div>
        <h2 className="empty-title">No hay música disponible</h2>
        <p className="empty-text">Agrega canciones a la biblioteca para empezar</p>
      </div>
    );
  }

  const { spotlight_mix, albumes_recientes, artistas_recientes, top_canciones, dashboard_stats } = data;

  return (
    <div>
      {/* Spotlight */}
      {spotlight_mix && (
        <>
          <div className="spotlight">
            <div className="spotlight-cover">
              <span style={{ fontSize: 48, color: "#666" }}>♪</span>
            </div>
            <div>
              <div className="spotlight-kicker">
                {spotlight_mix.nombre.includes("Morning") ? "☀️ BUENOS DÍAS" :
                 spotlight_mix.nombre.includes("Afternoon") ? "🌤️ BUENAS TARDES" :
                 "🌙 BUENAS NOCHES"}
              </div>
              <h1 className="spotlight-title">{spotlight_mix.nombre}</h1>
              <p className="spotlight-description">
                {spotlight_mix.canciones.length} canciones • Mezcla diaria personalizada
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
                  onClick={() => play(spotlight_mix.canciones, Math.floor(Math.random() * spotlight_mix.canciones.length))}
                >
                  <Shuffle size={14} style={{ marginRight: 6 }} />
                  Aleatorio
                </button>
              </div>
            </div>
          </div>

          <div className="stat-strip">
            <div className="stat-item">
              <strong>{dashboard_stats.canciones}</strong>
              <span>Canciones</span>
            </div>
            <div className="stat-item">
              <strong>{dashboard_stats.albumes}</strong>
              <span>Álbumes</span>
            </div>
            <div className="stat-item">
              <strong>{dashboard_stats.artistas}</strong>
              <span>Artistas</span>
            </div>
          </div>
        </>
      )}

      {/* Daily Mixes */}
      {data.daily_mixes && data.daily_mixes.length > 0 && (
        <div className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Tus mixes</h2>
          </div>
          <div className="scroll-grid">
            {data.daily_mixes.map((mix) => (
              <div key={mix.id} className="card" onClick={() => play(mix.canciones, 0)}>
                <div className="card-cover" style={{ background: "linear-gradient(135deg, #d95840, #1a1a1f)" }}>
                  <span style={{ fontSize: 28, opacity: 0.6 }}>♪</span>
                  <div className="card-overlay">
                    <button className="card-play-btn">
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
        </div>
      )}

      {/* Recently Added Albums */}
      {albumes_recientes.length > 0 && (
        <div className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Álbumes recientes</h2>
          </div>
          <div className="scroll-grid">
            {albumes_recientes.map((al) => (
              <div key={al.id} className="card">
                <div className="card-cover">
                  {al.portada_url ? (
                    <img src={al.portada_url} alt={al.titulo} />
                  ) : (
                    <span style={{ fontSize: 24, color: "#666" }}>♪</span>
                  )}
                  <div className="card-overlay">
                    <button className="card-play-btn">
                      <Play size={18} fill="currentColor" />
                    </button>
                  </div>
                </div>
                <div className="card-info">
                  <div className="card-title">{al.titulo}</div>
                  <div className="card-subtitle">{al.anio || "—"}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Artists */}
      {artistas_recientes.length > 0 && (
        <div className="shelf">
          <div className="shelf-header">
            <h2 className="shelf-title">Artistas</h2>
          </div>
          <div className="scroll-grid">
            {artistas_recientes.map((a) => (
              <div key={a.id} className="artist-card">
                <div className="artist-cover">
                  {a.foto_url ? (
                    <img src={a.foto_url} alt={a.nombre} />
                  ) : (
                    <span style={{ fontSize: 28, color: "#666" }}>{a.nombre.charAt(0)}</span>
                  )}
                </div>
                <div className="artist-name">{a.nombre}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Songs */}
      {top_canciones.length > 0 && (
        <div className="tracklist">
          <div className="shelf-header" style={{ padding: 0, marginBottom: 16 }}>
            <h2 className="shelf-title">Más escuchadas</h2>
          </div>
          {top_canciones.map((item, i) => (
            <div
              key={item.cancion.id}
              className="track-item"
              onClick={() => play(top_canciones.map((t) => t.cancion), i)}
            >
              <span className="track-num">{i + 1}</span>
              <div className="track-cover-sm">
                <span style={{ fontSize: 14, color: "#666" }}>♪</span>
              </div>
              <div className="track-info">
                <div className="track-title">{item.cancion.titulo}</div>
                <div className="track-artist">{item.cancion.artista}</div>
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af" }}>{item.plays} plays</div>
              <div className="track-duration">
                {item.cancion.duracion
                  ? Math.floor(item.cancion.duracion / 60) + ":" + String(item.cancion.duracion % 60).padStart(2, "0")
                  : "—"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
