import { useState } from "react";
import { usePlayer } from "../contexts/PlayerContext";

type Tab = "upnext" | "lyrics" | "related";

export default function RightPanel() {
  const [tab, setTab] = useState<Tab>("lyrics");
  const { currentSong } = usePlayer();

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
          <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
            <p>Cola de reproducción</p>
          </div>
        )}
        {tab === "lyrics" && (
          <div>
            {currentSong ? (
              <div className="lyrics-placeholder" style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
                <p style={{ marginBottom: 12, fontSize: 14 }}>{currentSong.titulo}</p>
                <p style={{ fontSize: 12 }}>{currentSong.artista}</p>
              </div>
            ) : (
              <div style={{ textAlign: "center", paddingTop: 60, color: "#9ca3af" }}>
                <div style={{ fontSize: 32, marginBottom: 16, opacity: 0.3 }}>♫</div>
                <p style={{ fontSize: 14 }}>Selecciona una canción para ver la letra</p>
              </div>
            )}
          </div>
        )}
        {tab === "related" && (
          <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 40 }}>
            <p>Canciones similares</p>
          </div>
        )}
      </div>
    </aside>
  );
}
