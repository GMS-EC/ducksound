import { useEffect, useState } from "react";
import { X, Loader2, Info } from "lucide-react";
import client from "../api/client";
import { useContextMenu } from "../contexts/ContextMenuContext";

interface AudioInfo {
  id: number;
  titulo: string;
  sample_rate: number | null;
  bit_depth: number | null;
  channels: number | null;
  duration: number | null;
  nyquist_freq: number | null;
  dynamic_range: number | null;
  peak_level: number | null;
  rms_level: number | null;
  total_samples: number | null;
  bit_rate: number | null;
  genero: string | null;
  bpm: number | null;
}

export default function AudioInfoModal() {
  const { infoSong, closeInfoModal } = useContextMenu();
  const [data, setData] = useState<AudioInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!infoSong) {
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);
    client
      .get(`/api/audio-info/${infoSong.id}`)
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        console.error("Error fetching audio info:", err);
        setError("No se pudieron cargar los detalles técnicos de esta pista.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [infoSong]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeInfoModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeInfoModal]);

  if (!infoSong) return null;

  const fmtSampleRate = (sr: number | null) => {
    if (!sr) return "—";
    return sr >= 1000 ? `${(sr / 1000).toFixed(1)} kHz` : `${sr} Hz`;
  };

  const fmtBitRate = (br: number | null) => {
    if (!br) return "—";
    return `${Math.round(br / 1000)} kbps`;
  };

  const fmtDecibels = (dbVal: number | null) => {
    if (dbVal === null || dbVal === undefined) return "—";
    return `${dbVal.toFixed(2)} dB`;
  };

  const fmtBpm = (bpmVal: number | null) => {
    if (!bpmVal) return "—";
    return `${Math.round(bpmVal)} BPM`;
  };

  const fmtChannels = (ch: number | null) => {
    if (ch === null) return "—";
    if (ch === 1) return "Mono (1 ch)";
    if (ch === 2) return "Estéreo (2 ch)";
    return `${ch} ch`;
  };

  return (
    <div className="modal-overlay" onClick={closeInfoModal}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Info size={18} className="text-accent" style={{ color: "var(--color-accent, #d95840)" }} />
            <h3 className="modal-title">Ficha Técnica: {infoSong.titulo}</h3>
          </div>
          <button className="modal-close-btn" onClick={closeInfoModal}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0", gap: 12, color: "var(--color-muted)" }}>
              <Loader2 className="animate-spin" size={24} />
              <span style={{ fontSize: 13 }}>Analizando especificaciones de audio...</span>
            </div>
          ) : error ? (
            <div style={{ color: "#ef4444", fontSize: 13, textAlign: "center", padding: "24px 0" }}>{error}</div>
          ) : data ? (
            <div className="tech-spec-grid">
              <div className="tech-spec-card">
                <span className="tech-spec-label">Frecuencia de Muestreo</span>
                <span className="tech-spec-value">{fmtSampleRate(data.sample_rate)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Resolución de Bits</span>
                <span className="tech-spec-value">{data.bit_depth ? `${data.bit_depth}-bit` : "—"}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Tasa de Bits (Bitrate)</span>
                <span className="tech-spec-value">{fmtBitRate(data.bit_rate)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Canales</span>
                <span className="tech-spec-value">{fmtChannels(data.channels)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Frecuencia Nyquist</span>
                <span className="tech-spec-value">{fmtSampleRate(data.nyquist_freq)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Tempo (Ritmo)</span>
                <span className="tech-spec-value">{fmtBpm(data.bpm)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Rango Dinámico</span>
                <span className="tech-spec-value">{fmtDecibels(data.dynamic_range)}</span>
              </div>
              <div className="tech-spec-card">
                <span className="tech-spec-label">Nivel de Pico (Peak)</span>
                <span className="tech-spec-value">{fmtDecibels(data.peak_level)}</span>
              </div>
              <div className="tech-spec-card" style={{ gridColumn: "span 2" }}>
                <span className="tech-spec-label">Nivel Promedio RMS</span>
                <span className="tech-spec-value">{fmtDecibels(data.rms_level)}</span>
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--color-muted)", fontSize: 13, textAlign: "center", padding: "24px 0" }}>Sin información disponible.</div>
          )}
        </div>
      </div>
    </div>
  );
}
