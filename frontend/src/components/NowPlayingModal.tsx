import { useState, useEffect, useRef } from "react";
import {
  ChevronDown, Play, Pause, SkipBack, SkipForward,
  Shuffle, Repeat, Volume2, VolumeX, Heart, Sparkles, Disc
} from "lucide-react";
import { usePlayer } from "../contexts/PlayerContext";
import client from "../api/client";

interface LyricCue {
  start: number | null;
  text: string;
}

interface NowPlayingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function NowPlayingModal({ isOpen, onClose }: NowPlayingModalProps) {
  const {
    currentSong, playing, currentTime, duration,
    togglePlay, next, prev, seek, volume, setVolume,
    muted, toggleMute, shuffle, repeat, toggleShuffle, toggleRepeat
  } = usePlayer();

  const [colorData, setColorData] = useState<{ primary: string; accent: string; gradient: string; glow: string } | null>(null);
  const [lyrics, setLyrics] = useState<LyricCue[] | null>(null);
  const [lyricType, setLyricType] = useState<"lrc" | "txt" | null>(null);
  const [isLiked, setIsLiked] = useState(false);
  const [coverError, setCoverError] = useState(false);
  const [useFallbackArt, setUseFallbackArt] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCoverError(false);
    setUseFallbackArt(false);
  }, [currentSong?.id]);

  const primaryCover = currentSong?.cover_url;
  const albumArtEndpoint = currentSong ? `/album-art/${currentSong.id}?size=large` : "";
  const coverSrc = (!useFallbackArt && primaryCover) ? primaryCover : albumArtEndpoint;

  // Fetch color when currentSong changes
  useEffect(() => {
    if (!currentSong) return;
    client.get(`/api/cancion/${currentSong.id}/color`)
      .then((res) => setColorData(res.data))
      .catch(() => {});
  }, [currentSong]);

  // Fetch lyrics when currentSong changes
  useEffect(() => {
    if (!currentSong || !isOpen) return;
    client.get(`/api/cancion/${currentSong.id}/lyrics`)
      .then((res) => {
        if (res.data && res.data.letra) {
          const cues = parseLRC(res.data.letra);
          setLyrics(cues);
          setLyricType(res.data.tipo || "txt");
        } else {
          setLyrics(null);
        }
      })
      .catch(() => setLyrics(null));

    // Favorite status
    client.get("/api/favoritos")
      .then((res) => {
        if (Array.isArray(res.data)) {
          setIsLiked(res.data.includes(currentSong.id));
        }
      })
      .catch(() => {});
  }, [currentSong, isOpen]);

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
          const ms = match[3] ? parseInt((match[3] + "00").slice(0, 3), 10) : 0;
          tags.push(m * 60 + s + ms / 1000);
        }
        const text = raw.replace(timeTag, "").trim();
        if (!tags.length || !text) continue;
        if (/\b(?:contributors|contribuciones|lyrics|embed)\b/i.test(text) && text.length < 80) continue;
        for (const t of tags) cues.push({ start: t, text });
      }
      return cues.sort((a, b) => (a.start || 0) - (b.start || 0));
    } else {
      for (const raw of lines) {
        const text = raw.trim();
        if (!text) continue;
        if (/\b(?:contributors|contribuciones|lyrics|embed)\b/i.test(text) && text.length < 80) continue;
        cues.push({ start: null, text });
      }
      return cues;
    }
  };

  // Keyboard shortcut ESC to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

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

  // Smooth centering scroll
  useEffect(() => {
    if (scrollRef.current) {
      const activeEl = scrollRef.current.querySelector(".fullscreen-lyric.active");
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [activeIndex]);

  const toggleFavorite = async () => {
    if (!currentSong) return;
    try {
      if (isLiked) {
        await client.post("/api/favoritos/quitar", { cancion_id: currentSong.id });
        setIsLiked(false);
      } else {
        await client.post("/api/favoritos/agregar", { cancion_id: currentSong.id });
        setIsLiked(true);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fmt = (s: number) => {
    if (!s || !isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return m + ":" + (sec < 10 ? "0" : "") + sec;
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!duration || !isFinite(duration) || duration <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    seek(pct * duration);
  };

  if (!isOpen || !currentSong) return null;

  const primaryColor = colorData?.primary || "rgb(217, 88, 64)";
  const ambientGradient = `radial-gradient(circle at 25% 30%, ${primaryColor.replace("rgb", "rgba").replace(")", ", 0.4)")} 0%, rgba(20, 20, 24, 0.98) 70%, #101014 100%)`;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: ambientGradient,
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        backdropFilter: "blur(20px)",
        animation: "fadeIn 0.25s ease-out",
        overflow: "hidden",
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 32px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
          flexShrink: 0,
        }}
      >
        <button
          onClick={onClose}
          style={{
            background: "rgba(255,255,255,0.08)",
            border: "none",
            borderRadius: "50%",
            width: 36,
            height: 36,
            color: "#fff",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.16)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
          title="Minimizar (Esc)"
        >
          <ChevronDown size={20} />
        </button>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 10, letterSpacing: 1.5, textTransform: "uppercase", color: "rgba(255,255,255,0.5)", fontWeight: 700 }}>
            Reproduciendo ahora
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.9)", fontWeight: 600 }}>
            {currentSong.album || "DuckSound"}
          </div>
        </div>

        {/* Audio Quality Badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "rgba(255,255,255,0.08)",
            padding: "5px 12px",
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.5,
          }}
        >
          <Sparkles size={13} style={{ color: colorData?.accent || "var(--color-accent)" }} />
          <span>
            {currentSong.sample_rate ? `${Math.round(currentSong.sample_rate / 1000)} kHz` : "FLAC"}
            {currentSong.bit_depth ? ` • ${currentSong.bit_depth} bit` : ""}
          </span>
        </div>
      </div>

      {/* Main Center Area: Left Cover, Right Lyrics */}
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "minmax(260px, 1fr) minmax(320px, 1.4fr)",
          gap: "clamp(24px, 4vw, 56px)",
          padding: "clamp(12px, 2vh, 24px) clamp(24px, 4vw, 56px)",
          alignItems: "center",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Left: Dynamic Responsive Cover Art & Metadata */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            minHeight: 0,
            justifyContent: "center",
          }}
        >
          <div
            style={{
              width: "min(330px, 40vh)",
              height: "min(330px, 40vh)",
              aspectRatio: "1 / 1",
              maxWidth: "100%",
              borderRadius: 16,
              overflow: "hidden",
              boxShadow: colorData?.glow || "0 16px 48px rgba(0,0,0,0.6)",
              background: "#18181c",
              marginBottom: "clamp(10px, 1.8vh, 18px)",
              flexShrink: 0,
              transition: "transform 0.3s ease",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {currentSong && !coverError ? (
              <img
                key={`${currentSong.id}-${useFallbackArt ? "fallback" : "primary"}`}
                src={coverSrc}
                alt={currentSong.titulo}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                onError={() => {
                  if (!useFallbackArt && primaryCover && primaryCover !== albumArtEndpoint) {
                    setUseFallbackArt(true);
                  } else {
                    setCoverError(true);
                  }
                }}
              />
            ) : (
              <span style={{ fontSize: 64, color: "#444" }}>♫</span>
            )}
          </div>

          <div
            style={{
              maxWidth: "min(380px, 100%)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              minHeight: 0,
            }}
          >
            <h1
              title={currentSong.titulo || ""}
              style={{
                fontSize: "clamp(18px, 2.4vh, 24px)",
                fontWeight: 800,
                margin: "0 0 4px 0",
                color: "#fff",
                lineHeight: 1.25,
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {currentSong.titulo}
            </h1>
            <h2
              title={currentSong.artista || ""}
              style={{
                fontSize: "clamp(13px, 1.6vh, 16px)",
                fontWeight: 500,
                margin: "0 0 10px 0",
                color: "rgba(255,255,255,0.7)",
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {currentSong.artista}
            </h2>
            <button
              onClick={toggleFavorite}
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "none",
                borderRadius: 20,
                padding: "6px 14px",
                color: isLiked ? "var(--color-accent)" : "#fff",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.2s",
                flexShrink: 0,
              }}
            >
              <Heart size={14} fill={isLiked ? "currentColor" : "none"} />
              <span>{isLiked ? "En Favoritos" : "Añadir a Favoritos"}</span>
            </button>
          </div>
        </div>

        {/* Right: Full Lyrics Display with Smooth Center Padding */}
        <div
          ref={scrollRef}
          className="fullscreen-lyrics-scroll"
          style={{
            height: "100%",
            minHeight: 0,
            overflowY: "auto",
            paddingRight: 16,
            paddingTop: "28vh",
            paddingBottom: "28vh",
            display: "flex",
            flexDirection: "column",
            gap: "clamp(12px, 1.8vh, 18px)",
            scrollbarWidth: "none",
            maskImage: "linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%)",
          }}
        >
          {lyrics && lyrics.length > 0 ? (
            lyrics.map((cue, idx) => {
              const isActive = idx === activeIndex;
              return (
                <div
                  key={idx}
                  className={`fullscreen-lyric ${isActive ? "active" : ""}`}
                  onClick={() => {
                    if (cue.start !== null && isFinite(cue.start) && cue.start >= 0) {
                      seek(cue.start);
                    }
                  }}
                  style={{
                    fontSize: isActive ? "clamp(22px, 3vh, 28px)" : "clamp(16px, 2.2vh, 20px)",
                    fontWeight: isActive ? 800 : 600,
                    color: isActive ? "#ffffff" : "rgba(255, 255, 255, 0.35)",
                    cursor: cue.start !== null ? "pointer" : "default",
                    transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                    lineHeight: 1.45,
                    textShadow: isActive ? `0 0 24px ${primaryColor}` : "none",
                    transform: isActive ? "scale(1.02)" : "scale(1)",
                    transformOrigin: "left center",
                    userSelect: "none",
                  }}
                >
                  {cue.text}
                </div>
              );
            })
          ) : (
            <div style={{ margin: "auto", textAlign: "center", color: "rgba(255,255,255,0.4)" }}>
              <Disc size={44} style={{ margin: "0 auto 14px auto", opacity: 0.3 }} />
              <p style={{ fontSize: 16, fontWeight: 600 }}>Letra instrumental o no disponible</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Compact Controls Bar */}
      <div
        style={{
          padding: "10px clamp(24px, 4vw, 48px) 14px clamp(24px, 4vw, 48px)",
          background: "rgba(0, 0, 0, 0.35)",
          backdropFilter: "blur(12px)",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          flexShrink: 0,
        }}
      >
        {/* Seek Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", minWidth: 38 }}>{fmt(currentTime)}</span>
          <div
            onClick={handleSeek}
            style={{
              flex: 1,
              height: 4,
              background: "rgba(255,255,255,0.18)",
              borderRadius: 2,
              cursor: "pointer",
              position: "relative",
              transition: "height 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.height = "6px")}
            onMouseLeave={(e) => (e.currentTarget.style.height = "4px")}
          >
            <div
              style={{
                width: duration ? `${(currentTime / duration) * 100}%` : "0%",
                height: "100%",
                background: primaryColor,
                borderRadius: 2,
                boxShadow: `0 0 10px ${primaryColor}`,
              }}
            />
          </div>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", minWidth: 38 }}>{fmt(duration)}</span>
        </div>

        {/* Buttons Control Row */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {/* Left spacing balance */}
          <div style={{ width: 120 }} />

          {/* Center Playback Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <button
              onClick={toggleShuffle}
              style={{
                background: "none",
                border: "none",
                color: shuffle ? "var(--color-accent)" : "rgba(255,255,255,0.6)",
                cursor: "pointer",
                padding: 6,
                display: "flex",
                alignItems: "center",
              }}
              title="Aleatorio"
            >
              <Shuffle size={16} />
            </button>
            <button
              onClick={prev}
              style={{
                background: "none",
                border: "none",
                color: "#fff",
                cursor: "pointer",
                padding: 6,
                display: "flex",
                alignItems: "center",
              }}
              title="Anterior"
            >
              <SkipBack size={20} />
            </button>
            <button
              onClick={togglePlay}
              style={{
                width: 44,
                height: 44,
                borderRadius: "50%",
                background: primaryColor,
                border: "none",
                color: "#fff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: `0 6px 20px rgba(0,0,0,0.4)`,
                transition: "transform 0.15s ease",
              }}
              onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.94)")}
              onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
            >
              {playing ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" style={{ marginLeft: 2 }} />}
            </button>
            <button
              onClick={next}
              style={{
                background: "none",
                border: "none",
                color: "#fff",
                cursor: "pointer",
                padding: 6,
                display: "flex",
                alignItems: "center",
              }}
              title="Siguiente"
            >
              <SkipForward size={20} />
            </button>
            <button
              onClick={toggleRepeat}
              style={{
                background: "none",
                border: "none",
                color: repeat !== "none" ? "var(--color-accent)" : "rgba(255,255,255,0.6)",
                cursor: "pointer",
                padding: 6,
                display: "flex",
                alignItems: "center",
              }}
              title="Repetir"
            >
              <Repeat size={16} />
            </button>
          </div>

          {/* Right Volume Control */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, width: 120, justifyContent: "flex-end" }}>
            <button
              onClick={toggleMute}
              style={{ background: "none", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", padding: 4 }}
            >
              {muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={muted ? 0 : volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              style={{ width: 75, accentColor: primaryColor }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
