import { Play, Pause, SkipBack, SkipForward, Shuffle, Repeat, Volume2, VolumeX } from "lucide-react";
import { usePlayer } from "../contexts/PlayerContext";

export default function PlayerBar() {
  const {
    currentSong, playing, volume, muted, shuffle, repeat,
    currentTime, duration,
    togglePlay, next, prev, seek, setVolume, toggleMute,
    toggleShuffle, toggleRepeat,
  } = usePlayer();

  const fmt = (s: number) => {
    if (!s || !isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return m + ":" + (sec < 10 ? "0" : "") + sec;
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    seek(pct * duration);
  };

  return (
    <div className="player-bar">
      <div className="player-left">
        <div className="player-cover">
          {currentSong ? (
            <>
              <img
                src={`/album-art/${currentSong.id}?size=small`}
                alt={currentSong.titulo}
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = 'none';
                  const nextEl = e.currentTarget.nextElementSibling as HTMLElement;
                  if (nextEl) nextEl.style.display = 'flex';
                }}
              />
              <span className="player-cover-icon" style={{ display: 'none' }}>♫</span>
            </>
          ) : (
            <span className="player-cover-icon">♫</span>
          )}
        </div>
        <div className="player-track-info">
          <div className="player-track-title">
            {currentSong ? currentSong.titulo : "Sin canción seleccionada"}
          </div>
          <div className="player-track-artist">
            {currentSong ? currentSong.artista : "Artista desconocido"}
          </div>
        </div>
      </div>

      <div className="player-center">
        <div className="player-controls">
          <button onClick={toggleShuffle} className={"player-control-btn" + (shuffle ? " active" : "")} title="Aleatorio">
            <Shuffle size={16} />
          </button>
          <button onClick={prev} className="player-control-btn" title="Anterior">
            <SkipBack size={18} />
          </button>
          <button onClick={togglePlay} className="player-play-btn">
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button onClick={next} className="player-control-btn" title="Siguiente">
            <SkipForward size={18} />
          </button>
          <button onClick={toggleRepeat} className={"player-control-btn" + (repeat !== "none" ? " active" : "")} title="Repetir">
            <Repeat size={16} />
          </button>
        </div>
        <div className="player-progress">
          <span className="player-progress-time">{fmt(currentTime)}</span>
          <div className="player-progress-bar" onClick={handleSeek}>
            <div
              className="player-progress-fill"
              style={{ width: duration ? ((currentTime / duration) * 100) + "%" : "0%" }}
            >
              <div className="player-progress-thumb" />
            </div>
          </div>
          <span className="player-progress-time">{fmt(duration)}</span>
        </div>
      </div>

      <div className="player-right">
        <div className="player-volume">
          <button onClick={toggleMute} className="player-control-btn">
            {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <input
            type="range"
            className="volume-slider"
            min="0"
            max="1"
            step="0.01"
            value={muted ? 0 : volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
