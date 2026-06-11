import { useState, useEffect, useRef } from "react";
import { usePlayer } from "../contexts/PlayerContext";
import client from "../api/client";
import { Globe, Music, Loader2 } from "lucide-react";
import type { Cancion } from "../types";

type Tab = "upnext" | "lyrics" | "related";

interface LyricCue {
  start: number | null;
  text: string;
  translation?: string;
}

export default function RightPanel() {
  const [tab, setTab] = useState<Tab>("lyrics");
  const { currentSong, currentTime, seek, queue, currentIndex, play } = usePlayer();

  const [lyrics, setLyrics] = useState<LyricCue[] | null>(null);
  const [lyricType, setLyricType] = useState<"lrc" | "txt" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [similarSongs, setSimilarSongs] = useState<any[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  
  const [targetLang, setTargetLang] = useState("es");
  const [translating, setTranslating] = useState(false);
  const [translated, setTranslated] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Fetch user profile language once on mount
  useEffect(() => {
    client.get("/api/profile")
      .then((res) => {
        if (res.data && res.data.idioma_preferido) {
          setTargetLang(res.data.idioma_preferido);
        }
      })
      .catch(() => {
        setTargetLang("es");
      });
  }, []);

  // Fetch lyrics when currentSong changes
  useEffect(() => {
    if (!currentSong) {
      setLyrics(null);
      setLyricType(null);
      setTranslated(false);
      setShowTranslation(false);
      return;
    }

    setLoading(true);
    setError(null);
    setLyrics(null);
    setLyricType(null);
    setTranslated(false);
    setShowTranslation(false);

    client.get(`/api/cancion/${currentSong.id}/lyrics?_t=${Date.now()}`)
      .then((res) => {
        if (res.data && res.data.letra) {
          const cues = parseLRC(res.data.letra);
          setLyrics(cues);
          setLyricType(res.data.tipo || "txt");
        } else {
          setError("Letra no disponible");
        }
      })
      .catch((err) => {
        console.error("Error fetching lyrics:", err);
        setError("Error al cargar la letra");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [currentSong]);

  // Fetch similar songs when currentSong changes
  useEffect(() => {
    if (!currentSong) {
      setSimilarSongs([]);
      return;
    }

    setLoadingSimilar(true);
    client.get(`/api/similares/${currentSong.id}`)
      .then((res) => {
        setSimilarSongs(res.data || []);
      })
      .catch((err) => {
        console.error("Error fetching similar songs:", err);
      })
      .finally(() => {
        setLoadingSimilar(false);
      });
  }, [currentSong]);

  // Parse LRC Helper
  const parseLRC = (txt: string): LyricCue[] => {
    const lines = txt.split(/\r?\n/);
    const timeTag = /\[(\d+):(\d{2})(?:\.(\d{1,3}))?\]/g;
    
    let hasTimestamps = false;
    for (const raw of lines) {
      if (raw.match(/\[\d+:\d{2}/)) {
        hasTimestamps = true;
        break;
      }
    }
    
    const cues: LyricCue[] = [];
    
    if (hasTimestamps) {
      for (const raw of lines) {
        let match;
        const tags: number[] = [];
        timeTag.lastIndex = 0;
        while ((match = timeTag.exec(raw)) !== null) {
          const m = parseInt(match[1], 10);
          const s = parseInt(match[2], 10);
          const ms = match[3] ? parseInt((match[3] + '00').slice(0, 3), 10) : 0;
          tags.push(m * 60 + s + ms / 1000);
        }
        const text = raw.replace(timeTag, '').trim();
        if (!tags.length) continue;
        if (!text) continue;
        if (/contribuciones/i.test(text)) continue;
        for (const t of tags) {
          cues.push({ start: t, text: text });
        }
      }
      return cues.sort((a, b) => (a.start || 0) - (b.start || 0));
    } else {
      for (let i = 0; i < lines.length; i++) {
        const text = lines[i].trim();
        if (!text) continue;
        if (/contribuciones/i.test(text)) continue;
        cues.push({ start: null, text: text });
      }
      return cues;
    }
  };

  // Translate handler
  const handleTranslate = async () => {
    if (!lyrics || lyrics.length === 0 || translating) return;
    
    if (translated) {
      setShowTranslation(!showTranslation);
      return;
    }

    setTranslating(true);
    try {
      const text = lyrics.map((c) => c.text || "").join("\n---\n");
      const res = await client.post("/api/translate", { text, target: targetLang });
      if (res.data && res.data.translated) {
        const lines = res.data.translated.split("\n---\n");
        const updatedLyrics = lyrics.map((c, i) => ({
          ...c,
          translation: lines[i] || ""
        }));
        setLyrics(updatedLyrics);
        setTranslated(true);
        setShowTranslation(true);
      }
    } catch (err) {
      console.error("Translation error:", err);
    } finally {
      setTranslating(false);
    }
  };

  // Active line detection
  let activeIndex = -1;
  if (lyrics && lyricType === "lrc") {
    for (let i = 0; i < lyrics.length; i++) {
      if (currentTime >= (lyrics[i].start ?? 0)) {
        activeIndex = i;
      } else {
        break;
      }
    }
  }

  // Centered scrolling when active line changes
  useEffect(() => {
    if (scrollContainerRef.current) {
      const activeEl = scrollContainerRef.current.querySelector(".lyric-line.active");
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [activeIndex]);

  const handleLineClick = (start: number | null) => {
    if (start !== null) {
      seek(start);
    }
  };

  return (
    <aside className="right-panel">
      <div className="right-tabs">
        {(["upnext", "lyrics", "related"] as Tab[]).map((t) => (
          <button
            key={t}
            className={"right-tab" + (tab === t ? " active" : "")}
            onClick={() => setTab(t)}
          >
            {t === "upnext" ? "A CONTINUACIÓN" : t === "lyrics" ? "LETRA" : "SIMILARES"}
          </button>
        ))}
      </div>
      <div className="right-content">
        {tab === "upnext" && (
          <div className="upnext-container" style={{ padding: 12 }}>
            {queue.length === 0 ? (
              <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
                <p>No hay canciones en cola</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {queue.map((s, idx) => {
                  const isCurrent = idx === currentIndex;
                  return (
                    <div
                      key={s.id + "-" + idx}
                      onClick={() => play(queue, idx)}
                      style={{
                        display: "flex",
                        gap: 12,
                        padding: 8,
                        borderRadius: 6,
                        cursor: "pointer",
                        background: isCurrent ? "rgba(255,255,255,0.06)" : "transparent",
                        borderLeft: isCurrent ? "3px solid var(--color-accent, #d95840)" : "3px solid transparent",
                      }}
                    >
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 4,
                          overflow: "hidden",
                          background: "#2a2a33",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <img
                          src={`/album-art/${s.id}?size=small`}
                          alt={s.titulo}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).style.display = "none";
                            const sibling = e.currentTarget.nextElementSibling as HTMLElement;
                            if (sibling) sibling.style.display = "block";
                          }}
                        />
                        <span style={{ display: "none" }}>♪</span>
                      </div>
                      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: 13,
                            color: isCurrent ? "var(--color-accent, #d95840)" : "#fff",
                          }}
                        >
                          {s.titulo}
                        </div>
                        <div style={{ fontSize: 11, color: "#9ca3af" }}>{s.artista}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {tab === "lyrics" && (
          <div className="lyrics-container">
            {currentSong ? (
              <>
                <div className="lyrics-toolbar">
                  <button
                    className="lyrics-translate-btn"
                    disabled={!lyrics || translating}
                    onClick={handleTranslate}
                  >
                    {translating ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>Traduciendo...</span>
                      </>
                    ) : showTranslation ? (
                      <>
                        <Globe size={14} />
                        <span>Ver Original</span>
                      </>
                    ) : (
                      <>
                        <Globe size={14} />
                        <span>Traducir</span>
                      </>
                    )}
                  </button>
                </div>
                <div className="lyrics-content-scroll" ref={scrollContainerRef}>
                  {loading && (
                    <div className="no-lyrics">
                      <span className="no-lyrics-icon">
                        <Loader2 className="animate-spin" style={{ margin: "0 auto" }} />
                      </span>
                      Buscando letra...
                    </div>
                  )}
                  {error && (
                    <div className="no-lyrics">
                      <span className="no-lyrics-icon">
                        <Music />
                      </span>
                      {error}
                    </div>
                  )}
                  {lyrics && (
                    <div className="lyrics-lines">
                      {lyrics.map((c, i) => {
                        const isActive = i === activeIndex;
                        return (
                          <div
                            key={i}
                            className={`lyric-line ${isActive ? "active" : ""}`}
                            data-start={c.start}
                            data-index={i}
                            onClick={() => handleLineClick(c.start)}
                          >
                            <div className="lyric-main-text">{c.text}</div>
                            {showTranslation && c.translation && (
                              <div className="lyric-subline">{c.translation}</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", paddingTop: 60, color: "#9ca3af" }}>
                <div style={{ fontSize: 32, marginBottom: 16, opacity: 0.3 }}>♫</div>
                <p style={{ fontSize: 14 }}>Selecciona una canción para ver la letra</p>
              </div>
            )}
          </div>
        )}

        {tab === "related" && (
          <div className="related-container" style={{ padding: 12 }}>
            {!currentSong ? (
              <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
                <p>Reproduce una canción para ver temas similares</p>
              </div>
            ) : loadingSimilar ? (
              <div className="no-lyrics" style={{ paddingTop: 40 }}>
                <span className="no-lyrics-icon">
                  <Loader2 className="animate-spin" style={{ margin: "0 auto" }} />
                </span>
                Calculando similitud acústica...
              </div>
            ) : similarSongs.length === 0 ? (
              <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
                <p>No se encontraron canciones similares</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {similarSongs.map((s) => {
                  const pct = Math.round((s.similarity || 0) * 100);
                  const songObj: Cancion = {
                    id: s.id,
                    titulo: s.titulo,
                    artista: s.artista,
                    album: s.album,
                    duracion: null,
                    ruta_audio: "",
                    ruta_lrc: null,
                    ruta_imagen: null,
                    genero: null,
                    sample_rate: null,
                    bit_depth: null,
                    channels: null,
                    nyquist_freq: null,
                    dynamic_range: null,
                    peak_level: null,
                    rms_level: null,
                    total_samples: null,
                    bit_rate: null
                  };
                  return (
                    <div
                      key={s.id}
                      onClick={() => play([songObj], 0)}
                      className="group"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        padding: 8,
                        borderRadius: 6,
                        cursor: "pointer",
                        background: "transparent",
                        transition: "background 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 4,
                          overflow: "hidden",
                          background: "#2a2a33",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <img
                          src={`/album-art/${s.id}?size=small`}
                          alt={s.titulo}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).style.display = "none";
                            const sibling = e.currentTarget.nextElementSibling as HTMLElement;
                            if (sibling) sibling.style.display = "block";
                          }}
                        />
                        <span style={{ display: "none" }}>♪</span>
                      </div>
                      <div style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: 13,
                            color: "#fff",
                            transition: "color 0.2s"
                          }}
                        >
                          {s.titulo}
                        </div>
                        <div style={{ fontSize: 11, color: "#9ca3af" }}>{s.artista}</div>
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: "bold",
                          padding: "2px 6px",
                          borderRadius: 10,
                          background: pct > 80 ? "rgba(16, 185, 129, 0.15)" : pct > 60 ? "rgba(245, 158, 11, 0.15)" : "rgba(255, 255, 255, 0.1)",
                          color: pct > 80 ? "#10b981" : pct > 60 ? "#f59e0b" : "#9ca3af",
                          flexShrink: 0
                        }}
                      >
                        {pct}%
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
