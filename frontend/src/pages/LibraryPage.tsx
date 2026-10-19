import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Heart, BookMarked, MoreVertical, Disc3, Play,
  ListMusic, Plus, Music2, Clock, ChevronRight
} from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion, Coleccion } from "../types";
import Equalizer from "../components/Equalizer";
import { useContextMenu } from "../contexts/ContextMenuContext";

interface AlbumGuardado {
  id: number;
  titulo: string;
  anio: number | null;
  artista: string | null;
  artista_id: number | null;
  cancion_id: number | null;
  fecha_guardado: string | null;
}

type Section = "songs" | "albums" | "playlists";

function getInitialSection(search: string): Section {
  const params = new URLSearchParams(search);
  const tab = params.get("tab");
  if (tab === "playlists") return "playlists";
  if (tab === "albums") return "albums";
  return "songs";
}

function fmtDur(s: number | null) {
  if (!s) return "—";
  const m = Math.floor(s / 60);
  const sec = String(s % 60).padStart(2, "0");
  return `${m}:${sec}`;
}

function totalDuration(songs: Cancion[]) {
  const total = songs.reduce((acc, c) => acc + (c.duracion || 0), 0);
  if (!total) return "";
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m} min`;
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [section, setSection] = useState<Section>(() => getInitialSection(location.search));

  const [songs, setSongs] = useState<Cancion[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(true);
  const [songSearch, setSongSearch] = useState("");

  const [albums, setAlbums] = useState<AlbumGuardado[]>([]);
  const [loadingAlbums, setLoadingAlbums] = useState(true);
  const [albumSearch, setAlbumSearch] = useState("");

  const [playlists, setPlaylists] = useState<Coleccion[]>([]);
  const [loadingPlaylists, setLoadingPlaylists] = useState(true);
  const [showCreatePlaylist, setShowCreatePlaylist] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState("");

  const { currentSong, playing, play } = usePlayer();
  const { showMenu } = useContextMenu();

  const fetchFavorites = () => {
    setLoadingSongs(true);
    client.get("/favoritos").then((res) => setSongs(res.data.favoritos || [])).catch(console.error).finally(() => setLoadingSongs(false));
  };
  const fetchAlbums = () => {
    setLoadingAlbums(true);
    client.get("/api/biblioteca/albums").then((res) => setAlbums(res.data || [])).catch(console.error).finally(() => setLoadingAlbums(false));
  };
  const fetchPlaylists = () => {
    setLoadingPlaylists(true);
    client.get("/colecciones").then((res) => setPlaylists(res.data.colecciones || [])).catch(console.error).finally(() => setLoadingPlaylists(false));
  };
  const createPlaylist = async () => {
    if (!newPlaylistName.trim()) return;
    try {
      await client.post("/api/colecciones/crear", { nombre: newPlaylistName.trim() });
      setNewPlaylistName(""); setShowCreatePlaylist(false); fetchPlaylists();
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    fetchFavorites(); fetchAlbums(); fetchPlaylists();
    const onFavs = () => fetchFavorites();
    const onAlbums = () => fetchAlbums();
    const onPlaylists = () => fetchPlaylists();
    window.addEventListener("ducksound:favorites_changed", onFavs);
    window.addEventListener("ducksound:library_changed", onAlbums);
    window.addEventListener("ducksound:collections_changed", onPlaylists);
    return () => {
      window.removeEventListener("ducksound:favorites_changed", onFavs);
      window.removeEventListener("ducksound:library_changed", onAlbums);
      window.removeEventListener("ducksound:collections_changed", onPlaylists);
    };
  }, []);

  useEffect(() => { setSection(getInitialSection(location.search)); }, [location.search]);

  const filteredSongs = songs.filter(c =>
    c.titulo.toLowerCase().includes(songSearch.toLowerCase()) ||
    (c.artista && c.artista.toLowerCase().includes(songSearch.toLowerCase()))
  );
  const filteredAlbums = albums.filter(a =>
    a.titulo.toLowerCase().includes(albumSearch.toLowerCase()) ||
    (a.artista && a.artista.toLowerCase().includes(albumSearch.toLowerCase()))
  );

  const sectionConfig = [
    { id: "songs" as Section, label: "Favoritos", icon: Heart, count: songs.length, sub: fmtDur(songs.reduce((a, c) => a + (c.duracion || 0), 0)) || `${songs.length} pistas` },
    { id: "albums" as Section, label: "Álbumes", icon: Disc3, count: albums.length, sub: `${albums.length} guardados` },
    { id: "playlists" as Section, label: "Playlists", icon: ListMusic, count: playlists.length, sub: `${playlists.length} listas` },
  ];

  return (
    <div className="lib-page">

      {/* ── Hero Header ── */}
      <div className="lib-hero">
        <div className="lib-hero-icon">
          <BookMarked size={36} strokeWidth={1.5} />
        </div>
        <div className="lib-hero-text">
          <div className="lib-hero-label">Tu colección personal</div>
          <h1 className="lib-hero-title">Biblioteca</h1>
          <div className="lib-hero-stats">
            <span><Music2 size={13} /> {songs.length} favoritos</span>
            <span className="lib-hero-dot">·</span>
            <span><Disc3 size={13} /> {albums.length} álbumes</span>
            <span className="lib-hero-dot">·</span>
            <span><ListMusic size={13} /> {playlists.length} playlists</span>
          </div>
        </div>
      </div>

      {/* ── Section cards ── */}
      <div className="lib-section-cards">
        {sectionConfig.map(({ id, label, icon: Icon, count, sub }) => (
          <button
            key={id}
            onClick={() => setSection(id)}
            className={`lib-section-card ${section === id ? "active" : ""}`}
          >
            <div className="lib-section-card-icon">
              <Icon size={22} />
            </div>
            <div className="lib-section-card-body">
              <div className="lib-section-card-label">{label}</div>
              <div className="lib-section-card-sub">{sub}</div>
            </div>
            {count > 0 && <div className="lib-section-card-badge">{count}</div>}
            <ChevronRight size={14} className="lib-section-card-arrow" />
          </button>
        ))}
      </div>

      {/* ── Separator ── */}
      <div className="lib-separator" />

      {/* ══════════ FAVORITOS ══════════ */}
      {section === "songs" && (
        <div className="lib-content">
          {loadingSongs ? (
            <div className="lib-loading">Cargando favoritos…</div>
          ) : songs.length === 0 ? (
            <div className="lib-empty">
              <div className="lib-empty-icon"><Heart size={52} strokeWidth={1} /></div>
              <h2>Sin canciones favoritas</h2>
              <p>Presiona el corazón en cualquier pista para agregarla aquí</p>
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="lib-toolbar">
                <div className="lib-toolbar-info">
                  <Clock size={14} />
                  <span>{totalDuration(filteredSongs)} · {filteredSongs.length} pistas</span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="lib-play-all" onClick={() => play(filteredSongs, 0)}>
                    <Play size={15} fill="currentColor" /> Reproducir todo
                  </button>
                  <input
                    type="text"
                    placeholder="Buscar…"
                    value={songSearch}
                    onChange={(e) => setSongSearch(e.target.value)}
                    className="lib-search-input"
                  />
                </div>
              </div>

              {/* Header row */}
              <div className="lib-track-header">
                <div className="lib-col-num">#</div>
                <div style={{ gridColumn: "2 / 4" }}>Título</div>
                <div>Álbum</div>
                <div className="lib-col-dur"><Clock size={13} /></div>
                <div />
              </div>

              {/* Tracks */}
              <div className="lib-track-list">
                {filteredSongs.map((c, i) => {
                  const isCurrent = currentSong?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      className={`lib-track-row ${isCurrent ? "current" : ""}`}
                      onClick={() => play(filteredSongs, i)}
                      onContextMenu={(e) => { e.preventDefault(); showMenu(e, c); }}
                    >
                      <div className="lib-col-num">
                        {isCurrent ? <Equalizer /> : <span className="lib-row-num">{i + 1}</span>}
                        <Play size={14} className="lib-row-play" fill="currentColor" />
                      </div>
                      <div className="lib-track-thumb">
                        <img
                          src={`/album-art/${c.id}?size=small`}
                          alt={c.titulo}
                          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                        />
                      </div>
                      <div className="lib-track-info">
                        <div className="lib-track-title">{c.titulo}</div>
                        <div className="lib-track-artist">{c.artista || "—"}</div>
                      </div>
                      <div className="lib-track-album">{c.album || "—"}</div>
                      <div className="lib-col-dur">{fmtDur(c.duracion)}</div>
                      <div className="lib-track-opts">
                        <button className="btn-options" onClick={(e) => { e.stopPropagation(); showMenu(e, c); }}>
                          <MoreVertical size={15} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* ══════════ ÁLBUMES ══════════ */}
      {section === "albums" && (
        <div className="lib-content">
          {loadingAlbums ? (
            <div className="lib-loading">Cargando álbumes…</div>
          ) : albums.length === 0 ? (
            <div className="lib-empty">
              <div className="lib-empty-icon"><Disc3 size={52} strokeWidth={1} /></div>
              <h2>Sin álbumes guardados</h2>
              <p>Abre un álbum y pulsa "Guardar en biblioteca"</p>
            </div>
          ) : (
            <>
              <div className="lib-toolbar">
                <div className="lib-toolbar-info">
                  <Disc3 size={14} />
                  <span>{filteredAlbums.length} álbumes guardados</span>
                </div>
                <input
                  type="text"
                  placeholder="Buscar álbumes…"
                  value={albumSearch}
                  onChange={(e) => setAlbumSearch(e.target.value)}
                  className="lib-search-input"
                />
              </div>
              <div className="lib-grid">
                {filteredAlbums.map((al) => (
                  <div key={al.id} className="lib-card" onClick={() => navigate(`/album/${al.id}`)}>
                    <div className="lib-card-cover">
                      {al.cancion_id ? (
                        <img src={`/album-art/${al.cancion_id}?size=medium`} alt={al.titulo}
                          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
                      ) : (
                        <div className="lib-card-nocover"><Disc3 size={36} /></div>
                      )}
                      <div className="lib-card-overlay">
                        <div className="lib-card-play-btn"><Play size={20} fill="#fff" color="#fff" style={{ marginLeft: 2 }} /></div>
                      </div>
                    </div>
                    <div className="lib-card-info">
                      <div className="lib-card-title">{al.titulo}</div>
                      <div className="lib-card-sub">{al.artista || "Artista desconocido"}{al.anio ? ` · ${al.anio}` : ""}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ══════════ PLAYLISTS ══════════ */}
      {section === "playlists" && (
        <div className="lib-content">
          <div className="lib-toolbar">
            <div className="lib-toolbar-info">
              <ListMusic size={14} />
              <span>{playlists.length} playlists</span>
            </div>
            <button className="lib-play-all" onClick={() => setShowCreatePlaylist(true)}>
              <Plus size={15} /> Nueva playlist
            </button>
          </div>

          {/* Create form */}
          {showCreatePlaylist && (
            <div className="lib-create-form">
              <input
                autoFocus
                type="text"
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                placeholder="Nombre de la playlist…"
                onKeyDown={(e) => e.key === "Enter" && createPlaylist()}
                className="lib-create-input"
              />
              <button className="lib-create-btn-ok" onClick={createPlaylist}>Crear</button>
              <button className="lib-create-btn-cancel" onClick={() => setShowCreatePlaylist(false)}>Cancelar</button>
            </div>
          )}

          {loadingPlaylists ? (
            <div className="lib-loading">Cargando playlists…</div>
          ) : playlists.length === 0 ? (
            <div className="lib-empty">
              <div className="lib-empty-icon"><ListMusic size={52} strokeWidth={1} /></div>
              <h2>Sin playlists</h2>
              <p>Crea tu primera playlist para organizar tu música</p>
            </div>
          ) : (
            <div className="lib-grid">
              {playlists.map((pl) => (
                <div key={pl.id} className="lib-card" onClick={() => navigate(`/coleccion/${pl.id}`)}>
                  <div className="lib-card-cover lib-card-playlist-cover">
                    <ListMusic size={40} style={{ color: "rgba(255,255,255,0.35)" }} />
                    <div className="lib-card-overlay">
                      <div className="lib-card-play-btn"><Play size={20} fill="#fff" color="#fff" style={{ marginLeft: 2 }} /></div>
                    </div>
                  </div>
                  <div className="lib-card-info">
                    <div className="lib-card-title">{pl.nombre}</div>
                    {pl.descripcion && <div className="lib-card-sub">{pl.descripcion}</div>}
                    {!pl.descripcion && <div className="lib-card-sub">Playlist</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
