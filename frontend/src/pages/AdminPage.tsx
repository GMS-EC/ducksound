import { useState, useEffect } from "react";
import {
  BarChart3, Scan, Users, FileText, RefreshCw, Activity,
} from "lucide-react";
import client from "../api/client";

type Tab = "stats" | "scan" | "users" | "lyrics" | "system";

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
    { id: "users", label: "Usuarios", icon: Users },
    { id: "lyrics", label: "Letras", icon: FileText },
    { id: "system", label: "Sistema", icon: RefreshCw },
  ];

  return (
    <div className="page-wrapper" style={{ padding: "24px 32px" }}>
      <h1 className="page-title" style={{ marginBottom: 24 }}>Panel de administración</h1>
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
      {tab === "users" && <UsersTab />}
      {tab === "lyrics" && <LyricsTab />}
      {tab === "system" && <SystemTab />}
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
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
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
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
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
