import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { usePlayer } from "../contexts/PlayerContext";
import client from "../api/client";
import { Globe, Music, Loader2, Disc3, Mic2 } from "lucide-react";
import Equalizer from "./Equalizer";

type Tab = "nowplaying" | "upnext";

interface LyricCue {
  start: number | null;
  text: string;
  translation?: string;
}

export default function RightPanel() {
  const [tab, setTab] = useState<Tab>("nowplaying");
  const navigate = useNavigate();
  const { currentSong, currentTime, seek, queue, currentIndex, play, playing } = usePlayer();

  const [lyrics, setLyrics] = useState<LyricCue[] | null>(null);
  const [lyricType, setLyricType] = useState<"lrc" | "txt" | null>(null);
  const [loadingLyrics, setLoadingLyrics] = useState(false);
  const [lyricError, setLyricError] = useState<string | null>(null);

  const [targetLang, setTargetLang] = useState("es");
  const [translating, setTranslating] = useState(false);
  const [translated, setTranslated] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Fetch user profile language
  useEffect(() => {
    client.get("/api/profile")
      .then((res) => {
        if (res.data?.idioma_preferido) setTargetLang(res.data.idioma_preferido);
      })
      .catch(() => setTargetLang("es"));
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

    setLoadingLyrics(true);
    setLyricError(null);
    setLyrics(null);
    setLyricType(null);
    setTranslated(false);
    setShowTranslation(false);

    client.get(`/api/cancion/${currentSong.id}/lyrics?_t=${Date.now()}`)
      .then((res) => {
        if (res.data?.letra) {
          const cues = parseLRC(res.data.letra);
          setLyrics(cues);
          setLyricType(res.data.tipo || "txt");
        } else {
          setLyricError("Letra no disponible");
        }
      })
      .catch(() => setLyricError("Error al cargar la letra"))
      .finally(() => setLoadingLyrics(false));
  }, [currentSong]);

  const parseLRC = (txt: string): LyricCue[] => {
    const lines = txt.split(/\r?\n/);
    const timeTag = /\[(\d+):(\d{2})(?:\.(\d{1,3}))?\]/g;

    let hasTimestamps = false;
    for (const raw of lines) {
      if (raw.match(/\[\d+:\d{2}/)) { hasTimestamps = true; break; }
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
          const ms = match[3] ? parseInt((match[3] + "00").slice(0, 3), 10) : 0;
          tags.push(m * 60 + s + ms / 1000);
        }
        const text = raw.replace(timeTag, "").trim();
        if (!tags.length || !text || /contribuciones/i.test(text)) continue;
        for (const t of tags) cues.push({ start: t, text });
      }
      return cues.sort((a, b) => (a.start || 0) - (b.start || 0));
    } else {
      for (const raw of lines) {
        const text = raw.trim();
        if (!text || /contribuciones/i.test(text)) continue;
        cues.push({ start: null, text });
      }
      return cues;
    }
  };

  const handleTranslate = async () => {
    if (!lyrics || lyrics.length === 0 || translating) return;
    if (translated) { setShowTranslation(!showTranslation); return; }

    setTranslating(true);
    try {
      const text = lyrics.map((c) => c.text || "").join("\n---\n");
      const res = await client.post("/api/translate", { text, target: targetLang });
      if (res.data?.translated) {
        const lines = res.data.translated.split("\n---\n");
        setLyrics(lyrics.map((c, i) => ({ ...c, translation: lines[i] || "" })));
        setTranslated(true);
        setShowTranslation(true);
      }
    } catch (err) {
      console.error("Translation error:", err);
    } finally {
      setTranslating(false);
    }
  };

  // Active lyric line detection
  let activeIndex = -1;
  if (lyrics && lyricType === "lrc") {
    for (let i = 0; i < lyrics.length; i++) {
      if (currentTime >= (lyrics[i].start ?? 0)) activeIndex = i;
      else break;
    }
  }

  // Auto-scroll to active lyric line
  useEffect(() => {
    if (scrollContainerRef.current) {
      const activeEl = scrollContainerRef.current.querySelector(".lyric-line.active");
      if (activeEl) activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeIndex]);

  const tabLabels: Record<Tab, string> = {
    nowplaying: "REPRODUCIENDO",
    upnext: "A CONTINUACIÓN",
  };

  return (
    <aside className="right-panel">
      <div className="right-tabs">
        {(["nowplaying", "upnext"] as Tab[]).map((t) => (
          <button
            key={t}
            className={"right-tab" + (tab === t ? " active" : "")}
            onClick={() => setTab(t)}
          >
            {tabLabels[t]}
          </button>
        ))}
      </div>

      <div className="right-content" style={{ padding: 0 }}>

        {/* ===== AHORA SUENA ===== */}
        {tab === "nowplaying" && (
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            {currentSong ? (
              <>
                {/* Compact header: small cover + metadata side by side */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "14px 16px",
                  flexShrink: 0,
                  borderBottom: "1px solid #25252d",
                }}>
                  {/* Small square cover */}
                  <div style={{
                    width: 64,
                    height: 64,
                    borderRadius: 8,
                    overflow: "hidden",
                    background: "#2a2a33",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
                  }}>
                    <img
                      src={`/album-art/${currentSong.id}?size=small`}
                      alt={currentSong.titulo}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = "none";
                        const sibling = e.currentTarget.nextElementSibling as HTMLElement;
                        if (sibling) sibling.style.display = "flex";
                      }}
                    />
                    <div style={{ display: "none", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", fontSize: 24, color: "#555" }}>♫</div>
                  </div>

                  {/* Metadata column */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Title + equalizer */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: "#ffffff",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flex: 1,
                      }}>
                        {currentSong.titulo}
                      </div>
                      {playing && <Equalizer />}
                    </div>

                    {/* Artist — clickable */}
                    <div
                      onClick={() => currentSong.artista_id && navigate(`/artist/${currentSong.artista_id}`)}
                      style={{
                        fontSize: 12,
                        color: currentSong.artista_id ? "#d95840" : "#9ca3af",
                        cursor: currentSong.artista_id ? "pointer" : "default",
                        fontWeight: 500,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        marginBottom: 2,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      <Mic2 size={11} style={{ flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                        {currentSong.artista || "Artista desconocido"}
                      </span>
                    </div>

                    {/* Album + year — clickable */}
                    <div
                      onClick={() => currentSong.album_id && navigate(`/album/${currentSong.album_id}`)}
                      style={{
                        fontSize: 11,
                        color: currentSong.album_id ? "#6b7280" : "#4b5563",
                        cursor: currentSong.album_id ? "pointer" : "default",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      <Disc3 size={10} style={{ flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                        {currentSong.album || "Álbum desconocido"}
                        {currentSong.anio ? ` · ${currentSong.anio}` : ""}
                      </span>
                    </div>

                    {/* Genre pill */}
                    {currentSong.genero && (
                      <div style={{
                        display: "inline-block",
                        marginTop: 5,
                        padding: "1px 8px",
                        borderRadius: 10,
                        background: "#30303b",
                        color: "#9ca3af",
                        fontSize: 10,
                        fontWeight: 600,
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                      }}>
                        {currentSong.genero}
                      </div>
                    )}
                  </div>
                </div>

                {/* Lyrics section — takes all remaining space */}
                <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                  {/* Lyrics toolbar */}
                  <div style={{ padding: "6px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, borderBottom: "1px solid #25252d" }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: "#9ca3af", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                      Letra
                    </span>
                    <button
                      className="lyrics-translate-btn"
                      disabled={!lyrics || translating}
                      onClick={handleTranslate}
                      style={{ fontSize: 11, padding: "3px 10px" }}
                    >
                      {translating ? (
                        <><Loader2 size={12} className="animate-spin" /><span>Traduciendo...</span></>
                      ) : showTranslation ? (
                        <><Globe size={12} /><span>Ver Original</span></>
                      ) : (
                        <><Globe size={12} /><span>Traducir</span></>
                      )}
                    </button>
                  </div>

                  <div className="lyrics-content-scroll" ref={scrollContainerRef} style={{ flex: 1, padding: "8px 16px 20px" }}>
                    {loadingLyrics && (
                      <div className="no-lyrics">
                        <span className="no-lyrics-icon"><Loader2 className="animate-spin" style={{ margin: "0 auto" }} /></span>
                        Buscando letra...
                      </div>
                    )}
                    {lyricError && !loadingLyrics && (
                      <div className="no-lyrics">
                        <span className="no-lyrics-icon"><Music /></span>
                        {lyricError}
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
                              onClick={() => c.start !== null && seek(c.start)}
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
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", paddingTop: 80, color: "#9ca3af" }}>
                <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.2 }}>♫</div>
                <p style={{ fontSize: 14 }}>Selecciona una canción para empezar</p>
              </div>
            )}
          </div>
        )}


        {/* ===== A CONTINUACIÓN ===== */}
        {tab === "upnext" && (
          <div className="upnext-container" style={{ padding: 12 }}>
            {queue.length === 0 ? (
              <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
                <p>No hay canciones en cola</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {queue.map((s, idx) => {
                  const isCurrent = idx === currentIndex;
                  return (
                    <div
                      key={s.id + "-" + idx}
                      onClick={() => play(queue, idx)}
                      style={{
                        display: "flex",
                        gap: 12,
                        padding: "8px 10px",
                        borderRadius: 6,
                        cursor: "pointer",
                        background: isCurrent ? "#2a2a33" : "transparent",
                        borderLeft: isCurrent ? "3px solid #d95840" : "3px solid transparent",
                        transition: "background 0.15s",
                      }}
                      onMouseEnter={(e) => { if (!isCurrent) e.currentTarget.style.background = "#24242d"; }}
                      onMouseLeave={(e) => { if (!isCurrent) e.currentTarget.style.background = "transparent"; }}
                    >
                      <div style={{
                        width: 40, height: 40, borderRadius: 4, overflow: "hidden",
                        background: "#2a2a33", display: "flex", alignItems: "center",
                        justifyContent: "center", flexShrink: 0,
                      }}>
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
                      <div style={{ overflow: "hidden", flex: 1 }}>
                        <div style={{
                          fontWeight: 600, fontSize: 13,
                          color: isCurrent ? "#d95840" : "#fff",
                          display: "flex", alignItems: "center", gap: 6,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {s.titulo}
                          {isCurrent && <Equalizer />}
                        </div>
                        <div style={{ fontSize: 11, color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {s.artista}
                        </div>
                      </div>
                      {idx !== currentIndex && (
                        <div style={{ fontSize: 11, color: "#6b7280", flexShrink: 0, alignSelf: "center" }}>
                          {s.duracion ? Math.floor(s.duracion / 60) + ":" + String(s.duracion % 60).padStart(2, "0") : ""}
                        </div>
                      )}
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
