import { useState, useEffect } from "react";
import {
  BarChart3, Scan, Users, FileText, RefreshCw, Activity, User, Disc, Music, Check,
} from "lucide-react";
import client from "../api/client";

type Tab = "stats" | "scan" | "users" | "lyrics" | "artists" | "albums" | "system";

interface ScanTask {
  task_id: string;
  status: string;
  percent: number;
  message: string;
  processed: number;
  total: number;
  current_file?: string;
  summary?: any;
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("stats");
  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: "stats", label: "Estadísticas", icon: BarChart3 },
    { id: "scan", label: "Escaneo", icon: Scan },
    { id: "artists", label: "Artistas", icon: User },
    { id: "albums", label: "Álbumes", icon: Disc },
    { id: "users", label: "Usuarios", icon: Users },
    { id: "lyrics", label: "Letras", icon: FileText },
    { id: "system", label: "Sistema", icon: RefreshCw },
  ];

  return (
    <div className="page-wrapper">
      <div className="page-header" style={{ paddingBottom: 0 }}>
        <h1 className="page-title" style={{ marginBottom: 24 }}>Panel de administración</h1>
      </div>
      <div style={{ padding: "0 32px 32px" }}>
        <div className="admin-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={"admin-tab" + (tab === t.id ? " active" : "")}
            >
              <t.icon size={16} />
              {t.label}
            </button>
          ))}
        </div>
        {tab === "stats" && <StatsTab />}
        {tab === "scan" && <ScanTab />}
        {tab === "artists" && <ArtistsTab />}
        {tab === "albums" && <AlbumsTab />}
        {tab === "users" && <UsersTab />}
        {tab === "lyrics" && <LyricsTab />}
        {tab === "system" && <SystemTab />}
      </div>
    </div>
  );
}

function StatsTab() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    client.get("/admin/estadisticas")
      .then((res) => setStats(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <div style={{ color: "#9ca3af" }}>Cargando...</div>;
  if (!stats) return <div style={{ color: "#9ca3af" }}>Error al cargar estadísticas</div>;
  const items = [
    { label: "Usuarios", value: stats.resumen?.usuarios },
    { label: "Artistas", value: stats.resumen?.artistas },
    { label: "Álbumes", value: stats.resumen?.albums },
    { label: "Canciones", value: stats.resumen?.canciones },
    { label: "Reproducciones", value: stats.resumen?.total_plays },
    { label: "Colecciones", value: stats.resumen?.colecciones },
    { label: "Favoritos", value: stats.resumen?.favoritos },
  ];
  return (
    <div style={{ marginTop: 24 }}>
      <div className="admin-grid">
        {items.map((item) => (
          <div key={item.label} className="stat-card">
            <p className="stat-value" style={{ color: "#d95840" }}>{item.value ?? "—"}</p>
            <p className="stat-label">{item.label}</p>
          </div>
        ))}
      </div>
      {stats.top_songs && stats.top_songs.length > 0 && (
        <section className="profile-section" style={{ marginTop: 20 }}>
          <div className="admin-section-title">Top canciones</div>
          <div>
            {stats.top_songs.map((item: any, i: number) => (
              <div key={i} className="track-item-grid" style={{ gridTemplateColumns: "20px 1fr 60px" }}>
                <span className="track-num-sm">{i + 1}</span>
                <span style={{ color: "#eaeaea", fontSize: 13 }}>{item.cancion?.titulo || "?"}</span>
                <span style={{ color: "#9ca3af", fontSize: 12, textAlign: "right" }}>{item.plays} plays</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ScanTab() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<ScanTask | null>(null);
  const [polling, setPolling] = useState(false);

  const startScan = async (type: "full" | "quick") => {
    try {
      const endpoint = type === "full" ? "/admin/escanear/start" : "/admin/escanear/quick";
      const res = await client.post(endpoint);
      setTaskId(res.data.task_id);
      setPolling(true);
    } catch (e: any) {
      const errData = e.response?.data;
      if (errData?.error === "scan_in_progress") {
        setTaskId(errData.task_id);
        setPolling(true);
      } else {
        alert(errData?.error || "Error al iniciar escaneo");
      }
    }
  };

  const cleanMetadata = async () => {
    try {
      const res = await client.post("/admin/clean_metadata");
      setTaskId(res.data.task_id);
      setPolling(true);
    } catch (e: any) {
      const errData = e.response?.data;
      if (errData?.error === "scan_in_progress") {
        setTaskId(errData.task_id);
        setPolling(true);
      } else {
        alert(errData?.error || "Error al limpiar metadatos");
      }
    }
  };

  useEffect(() => {
    client.get("/admin/escanear/active")
      .then((res) => {
        if (res.data && res.data.task_id) {
          setTaskId(res.data.task_id);
          setPolling(true);
        }
      })
      .catch((err) => {
        console.error("Error al obtener tarea activa:", err);
      });
  }, []);

  useEffect(() => {
    if (!polling || !taskId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await client.get("/admin/escanear/status/" + taskId);
        if (!cancelled) {
          setTask(res.data);
          if (res.data.status === "done" || res.data.status === "error") {
            setPolling(false);
          }
        }
      } catch {
        if (!cancelled) setPolling(false);
      }
    };
    poll();
    const interval = setInterval(poll, 1000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [polling, taskId]);

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        <button className="admin-btn admin-btn-primary" onClick={() => startScan("full")}>
          <Scan size={16} />
          Escaneo completo
        </button>
        <button className="admin-btn admin-btn-secondary" onClick={() => startScan("quick")}>
          <Activity size={16} />
          Escaneo rápido
        </button>
        <button className="admin-btn admin-btn-warning" onClick={cleanMetadata}>
          <RefreshCw size={16} />
          Limpiar metadatos
        </button>
      </div>
      {task && (
        <div className="scan-progress">
          <div className="scan-progress-header">
            <span style={{ fontSize: 14, color: task.status === "done" ? "#4ade80" : task.status === "error" ? "#d95840" : "#eaeaea" }}>
              {task.status === "running" || task.status === "enriching" ? "En progreso..." :
               task.status === "done" ? "Completado" : "Error"}
            </span>
            <span style={{ fontSize: 12, color: "#9ca3af" }}>{task.percent || 0}%</span>
          </div>
          <div className="scan-progress-bar">
            <div className="scan-progress-fill" style={{ width: (task.percent || 0) + "%" }} />
          </div>
          <p style={{ fontSize: 13, color: "#9ca3af", margin: "4px 0" }}>{task.message || ""}</p>
          {task.current_file && (
            <p style={{ fontSize: 11, color: "#666", margin: "2px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {task.current_file}
            </p>
          )}
          {task.summary && (
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
              {Object.entries(task.summary).map(([k, v]) => {
                if (typeof v === "object" && v !== null) {
                  return (
                    <div key={k} style={{ marginBottom: 8 }}>
                      <strong style={{ color: "#eaeaea" }}>{k}:</strong>
                      <div style={{ marginLeft: 12, marginTop: 2 }}>
                        {Object.entries(v).map(([sk, sv]) => (
                          <span key={sk} style={{ marginRight: 12 }}>
                            {sk}: {String(sv)}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                }
                return (
                  <span key={k} style={{ marginRight: 16 }}>
                    <strong style={{ color: "#eaeaea" }}>{k}:</strong> {String(v)}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ nombre_usuario: "", password: "", role: "user" });

  const fetchUsers = () => {
    client.get("/admin/usuarios")
      .then((res) => setUsers(res.data.usuarios || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };
  useEffect(() => { fetchUsers(); }, []);

  const createUser = async () => {
    try {
      await client.post("/admin/usuarios/crear", newUser);
      setShowCreate(false);
      setNewUser({ nombre_usuario: "", password: "", role: "user" });
      fetchUsers();
    } catch (e: any) { alert(e.response?.data?.error || "Error al crear usuario"); }
  };

  if (loading) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Cargando...</div>;

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button className="admin-btn admin-btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancelar" : "Nuevo usuario"}
        </button>
      </div>
      {showCreate && (
        <div className="profile-section" style={{ marginBottom: 20 }}>
          <input type="text" placeholder="Usuario" className="admin-form-input" style={{ marginBottom: 12 }}
            value={newUser.nombre_usuario} onChange={(e) => setNewUser({ ...newUser, nombre_usuario: e.target.value })} />
          <input type="password" placeholder="Contraseña (6+ caracteres)" className="admin-form-input" style={{ marginBottom: 12 }}
            value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
          <select className="admin-form-select" style={{ marginBottom: 12, display: "block" }}
            value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
            <option value="user">Usuario</option>
            <option value="admin">Administrador</option>
          </select>
          <button className="admin-btn admin-btn-primary" onClick={createUser}>Crear</button>
        </div>
      )}
      <div className="admin-card">
        {users.map((u) => (
          <div key={u.id} className="admin-user-row">
            <div>
              <p style={{ fontSize: 14, color: "#ffffff", margin: 0 }}>{u.nombre_usuario}</p>
              <p style={{ fontSize: 12, color: "#9ca3af", margin: "2px 0 0" }}>{u.role === "admin" ? "Administrador" : "Usuario"}</p>
            </div>
            <span className={"admin-badge " + (u.role === "admin" ? "admin-badge-admin" : "admin-badge-user")}>
              {u.role}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LyricsTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [lyricContent, setLyricContent] = useState("");
  const [lyricMeta, setLyricMeta] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await client.get("/admin/lyrics/search", { params: { q: query } });
      setResults(res.data || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const selectSong = async (id: number) => {
    setSelectedId(id);
    try {
      const res = await client.get("/admin/lyrics/" + id);
      setLyricMeta(res.data);
      setLyricContent(res.data.letra || "");
    } catch (e) { console.error(e); }
  };

  const saveLyrics = async () => {
    if (selectedId === null) return;
    try {
      await client.post("/admin/lyrics/" + selectedId + "/save", { letra: lyricContent });
      alert("Letra guardada");
    } catch (e: any) { alert(e.response?.data?.error || "Error al guardar"); }
  };

  return (
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
      <div>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="Buscar canción por título o artista..."
            className="admin-form-input" style={{ flex: 1 }} />
          <button className="admin-btn admin-btn-primary" onClick={search}>Buscar</button>
        </div>
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          {loading ? (
            <div style={{ color: "#9ca3af", fontSize: 13 }}>Buscando...</div>
          ) : results.length === 0 ? (
            <div style={{ color: "#666", fontSize: 13 }}>Sin resultados</div>
          ) : (
            results.map((r: any) => (
              <div key={r.id}
                className={"track-item-grid " + (selectedId === r.id ? "active" : "")}
                style={{ gridTemplateColumns: "1fr", cursor: "pointer", background: selectedId === r.id ? "rgba(217,88,64,0.1)" : "" }}
                onClick={() => selectSong(r.id)}>
                <div>
                  <div style={{ fontSize: 13, color: "#ffffff" }}>{r.titulo}</div>
                  <div style={{ fontSize: 11, color: "#9ca3af" }}>{r.artista} {r.tiene_letra ? "- " + r.sincronizada : ""}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      <div>
        {lyricMeta ? (
          <div className="admin-card">
            <div className="admin-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 500 }}>{lyricMeta.titulo}</div>
                <div style={{ fontSize: 12, color: "#9ca3af", fontWeight: 400 }}>{lyricMeta.artista}</div>
              </div>
              <button className="admin-btn admin-btn-primary" onClick={saveLyrics}>Guardar</button>
            </div>
            <div className="admin-card-body">
              <textarea className="admin-textarea" value={lyricContent}
                onChange={(e) => setLyricContent(e.target.value)} />
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", paddingTop: 60, color: "#9ca3af" }}>
            <div style={{ fontSize: 32, marginBottom: 16, opacity: 0.3 }}>♫</div>
            <p style={{ fontSize: 14 }}>Selecciona una canción para editar la letra</p>
          </div>
        )}
      </div>
    </div>
  );
}

function SystemTab() {
  const [versions, setVersions] = useState<any[]>([]);
  const [updateInfo, setUpdateInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      client.get("/admin"),
      client.get("/admin/check-update"),
    ])
      .then(([adminRes, updateRes]) => {
        setVersions(adminRes.data.changelog_versions || []);
        setUpdateInfo(updateRes.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Cargando...</div>;

  return (
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
      <div className="admin-card">
        <div className="admin-card-header">Versión actual</div>
        <div className="admin-card-body">
          {updateInfo && (
            <div>
              <p style={{ fontSize: 24, fontWeight: 700, color: "#ffffff", margin: "0 0 8px" }}>{updateInfo.current}</p>
              {updateInfo.update_available ? (
                <p style={{ color: "#d95840", fontSize: 13 }}>⚠ Actualización disponible: {updateInfo.latest}</p>
              ) : (
                <p style={{ color: "#4ade80", fontSize: 13 }}>✔ Última versión</p>
              )}
              {updateInfo.url && (
                <a href={updateInfo.url} target="_blank" rel="noopener noreferrer"
                  style={{ color: "#d95840", fontSize: 13, textDecoration: "none", display: "inline-block", marginTop: 8 }}>
                  Ver release
                </a>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="admin-card" style={{ maxHeight: 400, overflowY: "auto" }}>
        <div className="admin-card-header">Changelog</div>
        <div className="admin-card-body">
          {versions.map((v) => (
            <div key={v.number} style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "8px 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: "#ffffff" }}>{v.number}</span>
                {v.date && <span style={{ fontSize: 12, color: "#9ca3af" }}>{v.date}</span>}
                {v.status === "current" && <span className="admin-badge admin-badge-admin">Actual</span>}
                {v.status === "newer" && <span className="admin-badge" style={{ background: "rgba(217,88,64,0.15)", color: "#d95840" }}>Nuevo</span>}
              </div>
              {v.sections?.map((s: any, i: number) => (
                <div key={i} style={{ marginLeft: 8 }}>
                  <p style={{ fontSize: 12, color: "#9ca3af", margin: "4px 0 2px" }}>{s.title}</p>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: "#666" }}>
                    {s.entries?.map((e: string, j: number) => <li key={j}>{e}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ArtistsTab() {
  const [artists, setArtists] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [total, setTotal] = useState(0);
  const [conMbid, setConMbid] = useState(0);
  const [selectedArtist, setSelectedArtist] = useState<any | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editNombre, setEditNombre] = useState("");
  const [editMbid, setEditMbid] = useState("");
  const [editDeezerId, setEditDeezerId] = useState("");
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const fetchArtists = (searchQuery = "") => {
    setLoading(true);
    client.get("/admin/artistas", { params: { q: searchQuery } })
      .then((res) => {
        setArtists(res.data.artistas || []);
        setTotal(res.data.total || 0);
        setConMbid(res.data.con_mbid || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchArtists();
  }, []);

  const handleSearch = () => {
    fetchArtists(query);
  };

  const handleEdit = (artist: any) => {
    setSelectedArtist(artist);
    setEditNombre(artist.nombre || "");
    setEditMbid(artist.musicbrainz_id || "");
    setEditDeezerId("");
    setPreviewData(null);
    setError("");
    setModalOpen(true);
  };

  const handlePreview = async () => {
    if (!editMbid.trim() && !editDeezerId.trim()) {
      setError("Introduce un MBID o Deezer ID para previsualizar");
      return;
    }
    setPreviewLoading(true);
    setError("");
    setPreviewData(null);
    try {
      const res = await client.post("/admin/artistas/preview-metadata", {
        mbid: editMbid.trim(),
        deezer_id: editDeezerId.trim()
      });
      if (res.data.success && res.data.metadata) {
        setPreviewData(res.data.metadata);
      } else {
        setError(res.data.message || "No se encontró el artista");
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "Error de red al previsualizar");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedArtist) return;
    setSaving(true);
    setError("");
    try {
      const res = await client.post(`/admin/artistas/${selectedArtist.id}/update-mbid`, {
        mbid: editMbid.trim(),
        deezer_id: editDeezerId.trim(),
        nombre: editNombre.trim()
      });
      if (res.data.success) {
        setModalOpen(false);
        fetchArtists(query);
      } else {
        setError(res.data.error || "Error al guardar");
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "Error de red al guardar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div style={{ fontSize: 13, color: "#9ca3af" }}>
          {conMbid} de {total} artistas tienen MusicBrainz ID
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Buscar artista..."
            className="admin-form-input"
            style={{ width: 220 }}
          />
          <button className="admin-btn admin-btn-primary" onClick={handleSearch}>
            Buscar
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: "#9ca3af" }}>Cargando artistas...</div>
      ) : artists.length === 0 ? (
        <div style={{ color: "#9ca3af" }}>No se encontraron artistas</div>
      ) : (
        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: 60 }}>ID</th>
                <th style={{ minWidth: 160 }}>Artista</th>
                <th style={{ width: 220 }}>MusicBrainz ID (MBID)</th>
                <th style={{ width: 100 }}>Metadatos</th>
                <th style={{ width: 80, textAlign: "center" }}>Álbumes</th>
                <th style={{ width: 90, textAlign: "center" }}>Canciones</th>
                <th style={{ width: 70, textAlign: "right" }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {artists.map((a) => (
                <tr key={a.id}>
                  <td style={{ fontFamily: "monospace", color: "#6b7280" }}>#{a.id}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div className="admin-avatar-mini">
                        {a.foto_url ? (
                          <img src={a.foto_url} alt={a.nombre} />
                        ) : (
                          <User size={16} />
                        )}
                      </div>
                      <span style={{ fontWeight: 600, color: "#ffffff" }}>{a.nombre}</span>
                    </div>
                  </td>
                  <td>
                    {a.musicbrainz_id ? (
                      <span className="admin-mbid-badge admin-mbid-active" title={a.musicbrainz_id}>
                        <Music size={11} />
                        <code>{a.musicbrainz_id.substring(0, 18)}...</code>
                      </span>
                    ) : (
                      <span className="admin-mbid-badge admin-mbid-none">
                        Sin MBID
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="admin-info-indicators">
                      <span className={a.biografia ? "admin-info-indicator-active" : ""} title={a.biografia ? "Tiene biografía" : "Sin biografía"}>📝</span>
                      <span className={a.foto_url ? "admin-info-indicator-active" : ""} title={a.foto_url ? "Tiene foto" : "Sin foto"}>🖼️</span>
                    </div>
                  </td>
                  <td style={{ textAlign: "center", color: "#9ca3af", fontWeight: 500 }}>{a.albums_count ?? (a.albums ? a.albums.length : 0)}</td>
                  <td style={{ textAlign: "center", color: "#9ca3af", fontWeight: 500 }}>{a.canciones_count ?? (a.canciones ? a.canciones.length : 0)}</td>
                  <td style={{ textAlign: "right" }}>
                    <button className="admin-btn-icon" onClick={() => handleEdit(a)} title="Editar artista">
                      ✏️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalOpen && (
        <div className="admin-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="admin-modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="admin-modal-header">
              <h3>Editar Artista</h3>
              <button className="admin-btn-icon" style={{ border: "none", background: "none" }} onClick={() => setModalOpen(false)}>✕</button>
            </div>
            <div className="admin-modal-body">
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <div style={{ width: 80, height: 80, borderRadius: "50%", background: "#2a2a33", display: "flex", alignItems: "center", justifyContent: "center", border: "2px solid rgba(255,255,255,0.06)", overflow: "hidden", flexShrink: 0 }}>
                  {selectedArtist?.foto_url ? (
                    <img src={selectedArtist.foto_url} alt="Preview" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <User size={32} style={{ color: "#9ca3af" }} />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Nombre del Artista</label>
                    <input
                      type="text"
                      value={editNombre}
                      onChange={(e) => setEditNombre(e.target.value)}
                      className="admin-form-input"
                    />
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">MusicBrainz ID (MBID)</label>
                <input
                  type="text"
                  value={editMbid}
                  onChange={(e) => setEditMbid(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="admin-form-input"
                  style={{ fontFamily: "monospace" }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Deezer ID</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    value={editDeezerId}
                    onChange={(e) => setEditDeezerId(e.target.value)}
                    placeholder="Ej: 123456"
                    className="admin-form-input"
                    style={{ flex: 1 }}
                  />
                  <button className="admin-btn admin-btn-secondary" onClick={handlePreview} disabled={previewLoading}>
                    {previewLoading ? "Buscando..." : "Previsualizar"}
                  </button>
                </div>
              </div>

              {previewData && (
                <div className="admin-preview-card">
                  {previewData.foto_url && (
                    <img src={previewData.foto_url} alt="Preview" className="admin-preview-img" />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#ffffff" }}>{previewData.nombre}</div>
                    <div style={{ fontSize: 12, color: "#9ca3af", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.4 }}>
                      {previewData.biografia || "Sin biografía disponible"}
                    </div>
                  </div>
                  <Check size={20} style={{ color: "#d95840", flexShrink: 0 }} />
                </div>
              )}

              {error && (
                <div style={{ color: "#d95840", fontSize: 13, fontWeight: 500 }}>
                  ⚠️ {error}
                </div>
              )}
            </div>
            <div className="admin-modal-footer">
              <button className="admin-btn admin-btn-secondary" onClick={() => setModalOpen(false)}>
                Cancelar
              </button>
              <button className="admin-btn admin-btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? "Guardando..." : "Guardar Cambios"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AlbumsTab() {
  const [albums, setAlbums] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [total, setTotal] = useState(0);
  const [conMbid, setConMbid] = useState(0);
  const [conPortada, setConPortada] = useState(0);
  const [selectedAlbum, setSelectedAlbum] = useState<any | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editTitulo, setEditTitulo] = useState("");
  const [editAnio, setEditAnio] = useState("");
  const [editMbid, setEditMbid] = useState("");
  const [editDeezerId, setEditDeezerId] = useState("");
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const fetchAlbums = (searchQuery = "") => {
    setLoading(true);
    client.get("/admin/albumes", { params: { q: searchQuery } })
      .then((res) => {
        setAlbums(res.data.albumes || []);
        setTotal(res.data.total || 0);
        setConMbid(res.data.con_mbid || 0);
        setConPortada(res.data.con_portada || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAlbums();
  }, []);

  const handleSearch = () => {
    fetchAlbums(query);
  };

  const handleEdit = (album: any) => {
    setSelectedAlbum(album);
    setEditTitulo(album.titulo || "");
    setEditAnio(album.anio ? String(album.anio) : "");
    setEditMbid(album.musicbrainz_id || "");
    setEditDeezerId("");
    setPreviewData(null);
    setError("");
    setModalOpen(true);
  };

  const handlePreview = async () => {
    if (!editMbid.trim() && !editDeezerId.trim()) {
      setError("Introduce un MBID o Deezer ID para previsualizar");
      return;
    }
    setPreviewLoading(true);
    setError("");
    setPreviewData(null);
    try {
      const res = await client.post("/admin/albumes/preview-metadata", {
        mbid: editMbid.trim(),
        deezer_id: editDeezerId.trim()
      });
      if (res.data.success && res.data.metadata) {
        setPreviewData(res.data.metadata);
      } else {
        setError(res.data.message || "No se encontró el álbum");
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "Error de red al previsualizar");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedAlbum) return;
    setSaving(true);
    setError("");
    try {
      const res = await client.post(`/admin/albumes/${selectedAlbum.id}/update-metadata`, {
        mbid: editMbid.trim(),
        deezer_id: editDeezerId.trim(),
        titulo: editTitulo.trim(),
        anio: editAnio.trim()
      });
      if (res.data.success) {
        setModalOpen(false);
        fetchAlbums(query);
      } else {
        setError(res.data.error || "Error al guardar");
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "Error de red al guardar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div style={{ fontSize: 13, color: "#9ca3af" }}>
          {conMbid} de {total} con MBID | {conPortada} de {total} con Portada Oficial
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Buscar álbum..."
            className="admin-form-input"
            style={{ width: 220 }}
          />
          <button className="admin-btn admin-btn-primary" onClick={handleSearch}>
            Buscar
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: "#9ca3af" }}>Cargando álbumes...</div>
      ) : albums.length === 0 ? (
        <div style={{ color: "#9ca3af" }}>No se encontraron álbumes</div>
      ) : (
        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: 60 }}>ID</th>
                <th style={{ width: 70, textAlign: "center" }}>Portada</th>
                <th style={{ minWidth: 160 }}>Álbum</th>
                <th style={{ minWidth: 140 }}>Artista</th>
                <th style={{ width: 80, textAlign: "center" }}>Año</th>
                <th style={{ width: 220 }}>MusicBrainz ID (MBID)</th>
                <th style={{ width: 70, textAlign: "right" }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {albums.map((al) => {
                // Determine cover art
                let coverUrl = al.portada_url;
                if (!coverUrl && al.canciones && al.canciones.length > 0) {
                  coverUrl = `/album-art/${al.canciones[0].id}?size=small`;
                }
                return (
                  <tr key={al.id}>
                    <td style={{ fontFamily: "monospace", color: "#6b7280" }}>#{al.id}</td>
                    <td style={{ textAlign: "center" }}>
                      <div className="admin-art-mini">
                        {coverUrl ? (
                          <img src={coverUrl} alt={al.titulo} />
                        ) : (
                          <Disc size={16} />
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600, color: "#ffffff" }}>{al.titulo}</span>
                    </td>
                    <td>
                      <span style={{ color: "#eaeaea" }}>{al.artista?.nombre || "Desconocido"}</span>
                    </td>
                    <td style={{ textAlign: "center", color: "#9ca3af", fontWeight: 500 }}>
                      {al.anio || "-"}
                    </td>
                    <td>
                      {al.musicbrainz_id ? (
                        <span className="admin-mbid-badge admin-mbid-active" title={al.musicbrainz_id}>
                          <Music size={11} />
                          <code>{al.musicbrainz_id.substring(0, 18)}...</code>
                        </span>
                      ) : (
                        <span className="admin-mbid-badge admin-mbid-none">
                          Sin MBID
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button className="admin-btn-icon" onClick={() => handleEdit(al)} title="Editar álbum">
                        ✏️
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalOpen && (
        <div className="admin-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="admin-modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="admin-modal-header">
              <h3>Editar Álbum</h3>
              <button className="admin-btn-icon" style={{ border: "none", background: "none" }} onClick={() => setModalOpen(false)}>✕</button>
            </div>
            <div className="admin-modal-body">
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <div style={{ width: 80, height: 80, borderRadius: 8, background: "#2a2a33", display: "flex", alignItems: "center", justifyContent: "center", border: "2px solid rgba(255,255,255,0.06)", overflow: "hidden", flexShrink: 0 }}>
                  {selectedAlbum?.portada_url ? (
                    <img src={selectedAlbum.portada_url} alt="Cover" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : selectedAlbum?.canciones && selectedAlbum.canciones.length > 0 ? (
                    <img src={`/album-art/${selectedAlbum.canciones[0].id}?size=medium`} alt="Cover" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <Disc size={32} style={{ color: "#9ca3af" }} />
                  )}
                </div>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Título del Álbum</label>
                    <input
                      type="text"
                      value={editTitulo}
                      onChange={(e) => setEditTitulo(e.target.value)}
                      className="admin-form-input"
                    />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Artista</label>
                    <input
                      type="text"
                      value={selectedAlbum?.artista?.nombre || "Desconocido"}
                      readOnly
                      className="admin-form-input"
                      style={{ background: "rgba(255,255,255,0.02)", color: "#9ca3af", borderColor: "rgba(255,255,255,0.03)", cursor: "not-allowed" }}
                    />
                  </div>
                </div>
              </div>

              <div className="form-group" style={{ width: 120 }}>
                <label className="form-label">Año de Lanzamiento</label>
                <input
                  type="number"
                  value={editAnio}
                  onChange={(e) => setEditAnio(e.target.value)}
                  placeholder="Ej: 2026"
                  className="admin-form-input"
                  min="1800"
                  max="2100"
                />
              </div>

              <div className="form-group">
                <label className="form-label">MusicBrainz ID (MBID)</label>
                <input
                  type="text"
                  value={editMbid}
                  onChange={(e) => setEditMbid(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="admin-form-input"
                  style={{ fontFamily: "monospace" }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Deezer Album ID</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    value={editDeezerId}
                    onChange={(e) => setEditDeezerId(e.target.value)}
                    placeholder="Ej: 302127"
                    className="admin-form-input"
                    style={{ flex: 1 }}
                  />
                  <button className="admin-btn admin-btn-secondary" onClick={handlePreview} disabled={previewLoading}>
                    {previewLoading ? "Buscando..." : "Previsualizar"}
                  </button>
                </div>
              </div>

              {previewData && (
                <div className="admin-preview-card">
                  {previewData.portada_url && (
                    <img src={previewData.portada_url} alt="Cover Preview" className="admin-preview-img-rect" />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#ffffff" }}>{previewData.titulo}</div>
                    <div style={{ fontSize: 12, color: "#9ca3af" }}>
                      {previewData.artista_nombre || "Artista Desconocido"} {previewData.anio ? `• ${previewData.anio}` : ""}
                    </div>
                  </div>
                  <Check size={20} style={{ color: "#d95840", flexShrink: 0 }} />
                </div>
              )}

              {error && (
                <div style={{ color: "#d95840", fontSize: 13, fontWeight: 500 }}>
                  ⚠️ {error}
                </div>
              )}
            </div>
            <div className="admin-modal-footer">
              <button className="admin-btn admin-btn-secondary" onClick={() => setModalOpen(false)}>
                Cancelar
              </button>
              <button className="admin-btn admin-btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? "Guardando..." : "Guardar Cambios"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
