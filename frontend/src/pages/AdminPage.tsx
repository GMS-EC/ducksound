import { useState, useEffect, useRef } from "react";
import {
  BarChart3, Scan, Users, FileText, RefreshCw, Activity, User, Disc, Music, Check,
  Play, Pause, Undo, Trash2,
} from "lucide-react";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion } from "../types";

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
type MainTab = "stats" | "musicas" | "users" | "system";
type MusicSubTab = "scan" | "artists" | "albums" | "lyrics";

export default function AdminPage() {
  const [mainTab, setMainTab] = useState<MainTab>("stats");
  const [musicSubTab, setMusicSubTab] = useState<MusicSubTab>("scan");
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);

  useEffect(() => {
    client.get("/profile")
      .then((res) => {
        if (res.data && res.data.usuario) {
          setCurrentUserId(res.data.usuario.id);
        }
      })
      .catch(console.error);
  }, []);

  const mainTabs = [
    { id: "stats", label: "Estadísticas", icon: BarChart3 },
    { id: "musicas", label: "Músicas", icon: Music },
    { id: "users", label: "Usuarios", icon: Users },
    { id: "system", label: "Sistema", icon: RefreshCw },
  ] as const;

  const musicSubTabs = [
    { id: "scan", label: "Escaneo", icon: Scan },
    { id: "artists", label: "Artistas", icon: User },
    { id: "albums", label: "Álbumes", icon: Disc },
    { id: "lyrics", label: "Letras", icon: FileText },
  ] as const;

  return (
    <div className="page-wrapper" style={{ maxWidth: 1000, margin: "0 auto" }}>
      <div className="page-header" style={{ paddingBottom: 0 }}>
        <h1 className="page-title" style={{ marginBottom: 24 }}>Panel de administración</h1>
      </div>
      <div style={{ padding: "0 32px 32px" }}>
        <div className="admin-tabs" style={{ display: "flex", gap: 12, marginBottom: 24 }}>
          {mainTabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setMainTab(t.id)}
              className={"admin-tab" + (mainTab === t.id ? " active" : "")}
            >
              <t.icon size={16} />
              {t.label}
            </button>
          ))}
        </div>

        {mainTab === "stats" && <StatsTab />}
        
        {mainTab === "musicas" && (
          <div>
            <div className="admin-subtabs" style={{ display: "flex", gap: 8, marginBottom: 20, borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: 12 }}>
              {musicSubTabs.map((st) => (
                <button
                  key={st.id}
                  onClick={() => setMusicSubTab(st.id)}
                  className={"admin-subtab" + (musicSubTab === st.id ? " active" : "")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 12px",
                    borderRadius: "20px",
                    fontSize: "13px",
                    fontWeight: 500,
                    cursor: "pointer",
                    background: musicSubTab === st.id ? "rgba(217,88,64,0.12)" : "transparent",
                    color: musicSubTab === st.id ? "#d95840" : "#9ca3af",
                    border: musicSubTab === st.id ? "1px solid #d95840" : "1px solid rgba(255,255,255,0.06)",
                    transition: "all 0.2s ease",
                  }}
                >
                  <st.icon size={14} />
                  {st.label}
                </button>
              ))}
            </div>
            {musicSubTab === "scan" && <ScanTab />}
            {musicSubTab === "artists" && <ArtistsTab />}
            {musicSubTab === "albums" && <AlbumsTab />}
            {musicSubTab === "lyrics" && <LyricsTab />}
          </div>
        )}

        {mainTab === "users" && <UsersTab currentUserId={currentUserId} />}
        {mainTab === "system" && <SystemTab />}
      </div>
    </div>
  );
}

function StatsTab() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [clearingCache, setClearingCache] = useState(false);

  const fetchStats = () => {
    client.get("/admin/estadisticas")
      .then((res) => setStats(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleClearCache = async () => {
    if (!window.confirm("¿Estás seguro de que deseas vaciar las cachés de audio? Esto eliminará todos los archivos locales copiados y transcodificados. Se volverán a generar al vuelo cuando se reproduzcan.")) return;
    setClearingCache(true);
    try {
      const res = await client.post("/admin/cache/clear");
      alert(res.data.message || "Caché vaciado con éxito");
      fetchStats();
    } catch (e: any) {
      alert(e.response?.data?.error || "Error al vaciar caché");
    } finally {
      setClearingCache(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  if (loading) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Cargando estadísticas...</div>;
  if (!stats) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Error al cargar estadísticas</div>;

  const items = [
    { label: "Usuarios", value: stats.resumen?.usuarios, icon: "👥" },
    { label: "Artistas", value: stats.resumen?.artistas, icon: "🧑‍🎤" },
    { label: "Álbumes", value: stats.resumen?.albums, icon: "💿" },
    { label: "Canciones", value: stats.resumen?.canciones, icon: "🎵" },
    { label: "Reproducciones", value: stats.resumen?.total_plays, icon: "📈" },
    { label: "Colecciones", value: stats.resumen?.colecciones, icon: "📂" },
    { label: "Favoritos", value: stats.resumen?.favoritos, icon: "❤️" },
  ];

  return (
    <div style={{ marginTop: 12 }}>
      {/* Resumen General */}
      <div className="admin-grid" style={{ marginBottom: 20 }}>
        {items.map((item) => (
          <div key={item.label} className="stat-card" style={{ display: "flex", flexDirection: "column", justifyContent: "center", position: "relative" }}>
            <span style={{ position: "absolute", top: 12, right: 12, fontSize: 16, opacity: 0.6 }}>{item.icon}</span>
            <p className="stat-value" style={{ color: "#d95840", margin: "0 0 4px", fontSize: 24 }}>{item.value ?? "—"}</p>
            <p className="stat-label" style={{ margin: 0, fontSize: 12 }}>{item.label}</p>
          </div>
        ))}
      </div>

      {/* Highlights: Top Artista & Genero */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16, marginBottom: 24 }}>
        {stats.top_artist && (
          <div className="admin-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 24 }}>👑</div>
            <div>
              <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: 0.5 }}>Artista más escuchado</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#ffffff", marginTop: 2 }}>{stats.top_artist.artista?.nombre}</div>
              <div style={{ fontSize: 12, color: "#d95840", marginTop: 2 }}>{stats.top_artist.plays} reproducciones</div>
            </div>
          </div>
        )}
        {stats.top_genre && (
          <div className="admin-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 24 }}>🔥</div>
            <div>
              <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: 0.5 }}>Género más escuchado</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#ffffff", textTransform: "capitalize", marginTop: 2 }}>{stats.top_genre.genero}</div>
              <div style={{ fontSize: 12, color: "#d95840", marginTop: 2 }}>{stats.top_genre.plays} pistas reproducidas</div>
            </div>
          </div>
        )}
      </div>

      {/* Almacenamiento y Caché */}
      {stats.disk_usage && (
        <section className="profile-section" style={{ marginTop: 24, marginBottom: 24 }}>
          <div className="admin-section-title">Almacenamiento y Caché</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20, marginTop: 12 }}>
            <div className="admin-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13, color: "#eaeaea" }}>
                <span>Uso de espacio de almacenamiento (`/data`)</span>
                <span style={{ fontWeight: 600 }}>{stats.disk_usage.percent}%</span>
              </div>
              <div className="scan-progress-bar" style={{ height: 8, marginBottom: 8, background: "rgba(255,255,255,0.06)" }}>
                <div className="scan-progress-fill" style={{ width: `${stats.disk_usage.percent}%`, background: stats.disk_usage.percent > 90 ? "#ef4444" : "#d95840" }} />
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af", display: "flex", justifyContent: "space-between" }}>
                <span>{formatBytes(stats.disk_usage.used)} usados</span>
                <span>{formatBytes(stats.disk_usage.total)} totales ({formatBytes(stats.disk_usage.free)} libres)</span>
              </div>
            </div>
            <div className="admin-card" style={{ padding: 20, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ fontSize: 13, color: "#9ca3af" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Caché de Transcodificaciones:</span>
                  <span style={{ color: "#ffffff", fontWeight: 500 }}>{formatBytes(stats.cache?.transcode_size ?? 0)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Caché de Archivos Originales:</span>
                  <span style={{ color: "#ffffff", fontWeight: 500 }}>{formatBytes(stats.cache?.original_size ?? 0)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 600, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 6, marginTop: 6 }}>
                  <span style={{ color: "#eaeaea" }}>Caché total:</span>
                  <span style={{ color: "#d95840" }}>{formatBytes(stats.cache?.total_size ?? 0)}</span>
                </div>
              </div>
              <button 
                className="admin-btn admin-btn-warning" 
                style={{ alignSelf: "flex-end", marginTop: 12, padding: "6px 12px", fontSize: 12 }}
                onClick={handleClearCache}
                disabled={clearingCache}
              >
                {clearingCache ? "Vaciando..." : "Vaciar caché"}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Actividad de escucha reciente */}
      {stats.actividad_reciente && stats.actividad_reciente.length > 0 && (
        <section className="profile-section" style={{ marginTop: 24, marginBottom: 24 }}>
          <div className="admin-section-title">Actividad de escucha reciente</div>
          <div className="admin-table-container" style={{ marginTop: 12, maxHeight: 300, overflowY: "auto", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }}>
            <table className="admin-table" style={{ fontSize: 12, borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ padding: "12px 16px" }}>Usuario</th>
                  <th>Canción</th>
                  <th>Artista</th>
                  <th>Fecha y hora</th>
                  <th style={{ textAlign: "right", padding: "12px 16px" }}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {stats.actividad_reciente.map((act: any) => (
                  <tr key={act.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                    <td style={{ fontWeight: 600, color: "#ffffff", padding: "12px 16px" }}>{act.nombre_usuario}</td>
                    <td style={{ color: "#eaeaea" }}>{act.cancion_titulo}</td>
                    <td style={{ color: "#9ca3af" }}>{act.artista_nombre}</td>
                    <td style={{ color: "#6b7280" }}>{new Date(act.reproducido_en).toLocaleString()}</td>
                    <td style={{ textAlign: "right", padding: "12px 16px" }}>
                      <span 
                        style={{
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontSize: "10px",
                          fontWeight: 700,
                          background: act.skip ? "rgba(239,68,68,0.12)" : "rgba(74,222,128,0.12)",
                          color: act.skip ? "#ef4444" : "#4ade80",
                        }}
                      >
                        {act.skip ? "SALTADA" : "COMPLETA"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Top Canciones */}
      {stats.top_songs && stats.top_songs.length > 0 && (
        <section className="profile-section" style={{ marginTop: 24 }}>
          <div className="admin-section-title">Top canciones reproducidas</div>
          <div className="admin-card" style={{ marginTop: 12, padding: 16 }}>
            {stats.top_songs.map((item: any, i: number) => (
              <div key={i} className="track-item-grid" style={{ gridTemplateColumns: "30px 1fr 100px", padding: "8px 0", borderBottom: i < stats.top_songs.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                <span className="track-num-sm" style={{ fontWeight: 700, color: i < 3 ? "#d95840" : "#6b7280" }}>{i + 1}</span>
                <div>
                  <div style={{ color: "#ffffff", fontSize: 13, fontWeight: 500 }}>{item.cancion?.titulo || "?"}</div>
                  <div style={{ color: "#9ca3af", fontSize: 11, marginTop: 2 }}>{item.cancion?.artista?.nombre || "Artista Desconocido"}</div>
                </div>
                <span style={{ color: "#d95840", fontSize: 12, fontWeight: 600, textAlign: "right", alignSelf: "center" }}>{item.plays} plays</span>
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
            <span className={`scan-status-badge ${
              task.status === "running" || task.status === "enriching" ? "running" :
              task.status === "done" ? "done" : "error"
            }`}>
              {(task.status === "running" || task.status === "enriching") && <span className="scan-pulse-dot" />}
              {task.status === "running" ? "Escaneando biblioteca..." :
               task.status === "enriching" ? "Enriqueciendo metadatos..." :
               task.status === "done" ? "Escaneo completado" : "Error de escaneo"}
            </span>
            <span style={{ fontSize: 13, color: "#ffffff", fontWeight: 700 }}>{task.percent || 0}%</span>
          </div>
          
          <div className="scan-progress-bar">
            <div 
              className={`scan-progress-fill ${task.status === "running" || task.status === "enriching" ? "active" : ""}`} 
              style={{ width: (task.percent || 0) + "%" }} 
            />
          </div>
          
          <p style={{ fontSize: 13, color: "#e5e7eb", margin: "8px 0 4px", fontWeight: 500 }}>
            {task.message || ""}
          </p>
          
          {task.current_file && (
            <div className="scan-console" title={task.current_file}>
              📂 {task.current_file}
            </div>
          )}
          
          {task.summary && (
            <div className="scan-summary-grid">
              {Object.entries(task.summary).map(([k, v]) => {
                if (typeof v === "object" && v !== null) {
                  return (
                    <div key={k} style={{ gridColumn: "1 / -1", background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.04)", borderRadius: 10, padding: 12 }}>
                      <div className="scan-summary-card-lbl" style={{ marginBottom: 8, fontWeight: 700 }}>{k}</div>
                      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                        {Object.entries(v).map(([sk, sv]) => (
                          <div key={sk} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                            <span style={{ fontSize: 10, color: "#9ca3af", textTransform: "uppercase" }}>{sk}</span>
                            <span style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>{String(sv)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                }
                
                // Capitalize key for nice display
                const label = k.charAt(0).toUpperCase() + k.slice(1);
                
                return (
                  <div key={k} className="scan-summary-card">
                    <span className="scan-summary-card-val">{String(v)}</span>
                    <span className="scan-summary-card-lbl">{label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface UsersTabProps {
  currentUserId: number | null;
}

function UsersTab({ currentUserId }: UsersTabProps) {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ nombre_usuario: "", password: "", role: "user" });
  
  // Edit User states
  const [editingUser, setEditingUser] = useState<any | null>(null);
  const [editPassword, setEditPassword] = useState("");

  const fetchUsers = () => {
    setLoading(true);
    client.get("/admin/usuarios")
      .then((res) => setUsers(res.data.usuarios || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };
  
  useEffect(() => { 
    fetchUsers(); 
  }, []);

  const createUser = async () => {
    try {
      await client.post("/admin/usuarios/crear", newUser);
      setShowCreate(false);
      setNewUser({ nombre_usuario: "", password: "", role: "user" });
      fetchUsers();
    } catch (e: any) { 
      alert(e.response?.data?.error || "Error al crear usuario"); 
    }
  };

  const handleEditUser = (user: any) => {
    setEditingUser({ ...user });
    setEditPassword("");
  };

  const saveEditedUser = async () => {
    if (!editingUser) return;
    try {
      await client.post(`/admin/usuarios/${editingUser.id}/editar`, {
        nombre_usuario: editingUser.nombre_usuario,
        password: editPassword,
        role: editingUser.role
      });
      setEditingUser(null);
      fetchUsers();
    } catch (e: any) {
      alert(e.response?.data?.error || "Error al editar usuario");
    }
  };

  const deleteUser = async (user: any) => {
    if (user.id === currentUserId) {
      alert("No puedes eliminar tu propia cuenta de administrador.");
      return;
    }
    if (!window.confirm(`¿Estás seguro de que deseas eliminar permanentemente al usuario "${user.nombre_usuario}"? Esta acción limpiará todo su historial, favoritos y sesiones.`)) {
      return;
    }
    try {
      await client.post(`/admin/usuarios/${user.id}/eliminar`);
      fetchUsers();
    } catch (e: any) {
      alert(e.response?.data?.error || "Error al eliminar usuario");
    }
  };

  if (loading) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Cargando usuarios...</div>;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: "#ffffff", margin: 0 }}>Cuentas de DuckSound</h2>
        <button className="admin-btn admin-btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancelar" : "Nuevo usuario"}
        </button>
      </div>

      {showCreate && (
        <div className="admin-card" style={{ marginBottom: 24, padding: 20, maxWidth: 480 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "#ffffff", margin: "0 0 16px" }}>Crear Nueva Cuenta</h3>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label">Nombre de usuario</label>
            <input type="text" placeholder="Usuario" className="admin-form-input"
              value={newUser.nombre_usuario} onChange={(e) => setNewUser({ ...newUser, nombre_usuario: e.target.value })} />
          </div>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label">Contraseña</label>
            <input type="password" placeholder="Contraseña (mínimo 6 caracteres)" className="admin-form-input"
              value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
          </div>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">Rol del usuario</label>
            <select className="admin-form-select"
              value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
              <option value="user">Usuario Estándar</option>
              <option value="admin">Administrador</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="admin-btn admin-btn-primary" onClick={createUser}>Crear Usuario</button>
            <button className="admin-btn admin-btn-secondary" onClick={() => setShowCreate(false)}>Cancelar</button>
          </div>
        </div>
      )}

      {/* Grid de Tarjetas de Usuario */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        {users.map((u) => {
          const initials = u.nombre_usuario.substring(0, 2).toUpperCase();
          const isSelf = u.id === currentUserId;
          return (
            <div key={u.id} className="admin-card" style={{ padding: 20, display: "flex", flexDirection: "column", justifyContent: "space-between", border: isSelf ? "1px solid #d95840" : "1px solid rgba(255,255,255,0.06)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ width: 44, height: 44, borderRadius: "50%", background: isSelf ? "rgba(217,88,64,0.15)" : "#2a2a33", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15, fontWeight: 700, color: isSelf ? "#d95840" : "#eaeaea", border: "1px solid rgba(255,255,255,0.06)" }}>
                    {initials}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontWeight: 700, color: "#ffffff", fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={u.nombre_usuario}>
                        {u.nombre_usuario}
                      </span>
                      {isSelf && (
                        <span style={{ fontSize: 10, background: "rgba(217,88,64,0.2)", color: "#d95840", padding: "1px 4px", borderRadius: 4, fontWeight: 600 }}>TÚ</span>
                      )}
                    </div>
                    <span className={"admin-badge " + (u.role === "admin" ? "admin-badge-admin" : "admin-badge-user")} style={{ marginTop: 4, display: "inline-block" }}>
                      {u.role === "admin" ? "Administrador" : "Usuario"}
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: 12, color: "#9ca3af", display: "flex", flexDirection: "column", gap: 6, borderTop: "1px solid rgba(255,255,255,0.04)", paddingTop: 12, marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Registrado:</span>
                    <span style={{ color: "#ffffff" }}>{u.fecha_creacion ? new Date(u.fecha_creacion).toLocaleDateString() : "—"}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Sesiones activas:</span>
                    <span style={{ color: u.sesiones_activas > 0 ? "#4ade80" : "#9ca3af", fontWeight: 600 }}>
                      {u.sesiones_activas} {u.sesiones_activas === 1 ? "sesión" : "sesiones"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Última actividad:</span>
                    <span style={{ color: "#ffffff", textAlign: "right" }}>
                      {u.ultima_actividad ? new Date(u.ultima_actividad).toLocaleString() : "Sin actividad"}
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, borderTop: "1px solid rgba(255,255,255,0.04)", paddingTop: 12 }}>
                <button className="admin-btn admin-btn-secondary" style={{ flex: 1, padding: "6px 0", fontSize: 12 }} onClick={() => handleEditUser(u)}>
                  Editar
                </button>
                <button 
                  className="admin-btn admin-btn-danger" 
                  style={{ flex: 1, padding: "6px 0", fontSize: 12, borderColor: isSelf ? "rgba(255,255,255,0.02)" : "", opacity: isSelf ? 0.3 : 1, cursor: isSelf ? "not-allowed" : "pointer" }}
                  onClick={() => deleteUser(u)}
                  disabled={isSelf}
                >
                  Eliminar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal de Edición de Usuario */}
      {editingUser && (
        <div className="admin-modal-overlay" onClick={() => setEditingUser(null)}>
          <div className="admin-modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="admin-modal-header">
              <h3>Editar Cuenta: {editingUser.nombre_usuario}</h3>
              <button className="admin-btn-icon" style={{ border: "none", background: "none" }} onClick={() => setEditingUser(null)}>✕</button>
            </div>
            <div className="admin-modal-body">
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Nombre de usuario</label>
                <input
                  type="text"
                  value={editingUser.nombre_usuario}
                  onChange={(e) => setEditingUser({ ...editingUser, nombre_usuario: e.target.value })}
                  className="admin-form-input"
                />
              </div>

              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Nueva contraseña</label>
                <input
                  type="password"
                  value={editPassword}
                  onChange={(e) => setEditPassword(e.target.value)}
                  placeholder="Dejar en blanco para no cambiar"
                  className="admin-form-input"
                />
              </div>

              <div className="form-group" style={{ marginBottom: 12 }}>
                <label className="form-label">Rol del usuario</label>
                <select
                  value={editingUser.role}
                  onChange={(e) => setEditingUser({ ...editingUser, role: e.target.value })}
                  className="admin-form-select"
                  disabled={editingUser.id === currentUserId}
                  style={{ opacity: editingUser.id === currentUserId ? 0.5 : 1, cursor: editingUser.id === currentUserId ? "not-allowed" : "pointer" }}
                >
                  <option value="user">Usuario Estándar</option>
                  <option value="admin">Administrador</option>
                </select>
                {editingUser.id === currentUserId && (
                  <p style={{ fontSize: 11, color: "#9ca3af", margin: "4px 0 0" }}>No puedes degradar tu propio rol de administrador.</p>
                )}
              </div>
            </div>
            <div className="admin-modal-footer">
              <button className="admin-btn admin-btn-secondary" onClick={() => setEditingUser(null)}>
                Cancelar
              </button>
              <button className="admin-btn admin-btn-primary" onClick={saveEditedUser}>
                Guardar Cambios
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface LyricLine {
  time: number | null;
  text: string;
}

const parseLrc = (lrcText: string): LyricLine[] => {
  const lines = lrcText.split(/\r?\n/);
  const result: LyricLine[] = [];
  const lrcRegex = /^\[(\d{2,}):(\d{2})(?:\.(\d{2,3}))?\](.*)$/;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      result.push({ time: null, text: "" });
      continue;
    }
    const match = trimmed.match(lrcRegex);
    if (match) {
      const min = parseInt(match[1], 10);
      const sec = parseInt(match[2], 10);
      const msStr = match[3] || "00";
      const ms = parseFloat("0." + msStr);
      const time = min * 60 + sec + ms;
      const text = match[4].trim();
      result.push({ time, text });
    } else {
      result.push({ time: null, text: trimmed });
    }
  }
  return result;
};

const serializeLrc = (lines: LyricLine[]): string => {
  return lines
    .map((line) => {
      if (line.time !== null) {
        const timeStr = formatLrcTime(line.time);
        return `${timeStr} ${line.text}`;
      } else {
        return line.text;
      }
    })
    .join("\n");
};

const formatLrcTime = (seconds: number): string => {
  if (isNaN(seconds) || seconds < 0) return "[00:00.00]";
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  
  const minStr = min.toString().padStart(2, "0");
  const secStr = sec.toString().padStart(2, "0");
  const msStr = ms.toString().padStart(2, "0");
  
  return `[${minStr}:${secStr}.${msStr}]`;
};

const formatTimeWithoutBrackets = (seconds: number): string => {
  if (isNaN(seconds) || seconds < 0) return "00:00.00";
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  
  const minStr = min.toString().padStart(2, "0");
  const secStr = sec.toString().padStart(2, "0");
  const msStr = ms.toString().padStart(2, "0");
  
  return `${minStr}:${secStr}.${msStr}`;
};

const formatTimeDisplay = (seconds: number): string => {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  return `${min.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
};

function LyricsTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [lyricContent, setLyricContent] = useState("");
  const [lyricMeta, setLyricMeta] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Sync Modal States
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState<"edit" | "sync">("edit");
  const [syncLines, setSyncLines] = useState<LyricLine[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [history, setHistory] = useState<LyricLine[][]>([]);

  // Player Context Hook
  const {
    playing, currentTime, duration, playbackRate,
    play, togglePlay, seek, setPlaybackRate, currentSong
  } = usePlayer();

  const lineRefs = useRef<{[key: number]: HTMLDivElement | null}>({});

  // Auto-scroll active line into view when activeIndex changes
  useEffect(() => {
    if (syncModalOpen && modalTab === "sync") {
      const el = lineRefs.current[activeIndex];
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [activeIndex, syncModalOpen, modalTab]);

  // Keep playback rate 1.0 when modal unmounts
  useEffect(() => {
    return () => {
      setPlaybackRate(1.0);
    };
  }, [setPlaybackRate]);

  // Sync refs to avoid stale closures in keydown listener
  const activeIndexRef = useRef(0);
  activeIndexRef.current = activeIndex;
  const syncLinesRef = useRef<LyricLine[]>([]);
  syncLinesRef.current = syncLines;
  const currentTimeRef = useRef(0);
  currentTimeRef.current = currentTime;

  // Stamping and Undo implementations
  const stampCurrentLine = () => {
    const index = activeIndexRef.current;
    const lines = syncLinesRef.current;
    const time = currentTimeRef.current;
    if (index >= lines.length) return;

    setHistory((prev) => [...prev, lines]);

    const newLines = [...lines];
    newLines[index] = { ...newLines[index], time: time };
    setSyncLines(newLines);
    setLyricContent(serializeLrc(newLines));

    if (index + 1 < lines.length) {
      setActiveIndex(index + 1);
    }
  };

  const triggerUndo = () => {
    if (history.length > 0) {
      const prevLines = history[history.length - 1];
      setSyncLines(prevLines);
      setLyricContent(serializeLrc(prevLines));
      setHistory((prev) => prev.slice(0, prev.length - 1));
      if (activeIndex > 0) {
        setActiveIndex(activeIndex - 1);
      }
    }
  };

  const clearAllTimes = () => {
    if (window.confirm("¿Seguro que quieres eliminar todas las marcas de tiempo?")) {
      setHistory((prev) => [...prev, syncLines]);
      const newLines = syncLines.map((l) => ({ ...l, time: null }));
      setSyncLines(newLines);
      setLyricContent(serializeLrc(newLines));
      setActiveIndex(0);
    }
  };

  const clearLineTime = (e: React.MouseEvent, index: number) => {
    e.stopPropagation();
    setHistory((prev) => [...prev, syncLines]);
    const newLines = [...syncLines];
    newLines[index] = { ...newLines[index], time: null };
    setSyncLines(newLines);
    setLyricContent(serializeLrc(newLines));
  };

  const handleLineClick = (index: number, line: LyricLine) => {
    setActiveIndex(index);
    if (line.time !== null) {
      seek(line.time);
    }
  };

  const startPlayingThisSong = () => {
    if (lyricMeta && selectedId !== null) {
      const mockSong: Cancion = {
        id: selectedId,
        titulo: lyricMeta.titulo,
        artista: lyricMeta.artista,
        artista_id: null,
        album: null,
        album_id: null,
        anio: null,
        duracion: null,
        ruta_audio: `/audio/${selectedId}`,
        ruta_lrc: null,
        ruta_imagen: lyricMeta.cover || null,
        genero: null,
        sample_rate: null,
        bit_depth: null,
        channels: null,
        nyquist_freq: null,
        dynamic_range: null,
        peak_level: null,
        rms_level: null,
        total_samples: null,
        bit_rate: null,
      };
      play([mockSong], 0);
    }
  };

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!syncModalOpen || modalTab !== "sync") return;

      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        return;
      }

      if (e.key === " ") {
        e.preventDefault();
        stampCurrentLine();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (activeIndexRef.current > 0) {
          setActiveIndex(activeIndexRef.current - 1);
        }
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (activeIndexRef.current + 1 < syncLinesRef.current.length) {
          setActiveIndex(activeIndexRef.current + 1);
        }
      } else if (e.key === "Backspace") {
        e.preventDefault();
        triggerUndo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [syncModalOpen, modalTab]);

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
      setSyncLines([]);
      setActiveIndex(0);
      setHistory([]);
    } catch (e) { console.error(e); }
  };

  const saveLyrics = async () => {
    if (selectedId === null) return;
    try {
      await client.post("/admin/lyrics/" + selectedId + "/save", { letra: lyricContent });
      alert("Letra guardada");
    } catch (e: any) { alert(e.response?.data?.error || "Error al guardar"); }
  };

  const saveLyricsFromModal = async () => {
    if (selectedId === null) return;
    try {
      await client.post("/admin/lyrics/" + selectedId + "/save", { letra: lyricContent });
    } catch (e: any) { alert(e.response?.data?.error || "Error al guardar"); }
  };

  const checkIfLineIsPlaying = (line: LyricLine, idx: number) => {
    if (line.time === null) return false;
    if (currentTime < line.time) return false;
    
    let nextTime = Infinity;
    for (let i = idx + 1; i < syncLines.length; i++) {
      if (syncLines[i].time !== null) {
        nextTime = syncLines[i].time!;
        break;
      }
    }
    return currentTime >= line.time && currentTime < nextTime;
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
              <div style={{ display: "flex", gap: 8 }}>
                <button className="admin-btn admin-btn-secondary" onClick={() => {
                  setSyncLines(parseLrc(lyricContent));
                  setSyncModalOpen(true);
                }}>
                  Sincronizar Letra
                </button>
                <button className="admin-btn admin-btn-primary" onClick={saveLyrics}>Guardar</button>
              </div>
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

      {syncModalOpen && (
        <div className="admin-modal-overlay" onClick={() => setSyncModalOpen(false)}>
          <div className="admin-modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 960, width: "100%", height: "85vh", display: "flex", flexDirection: "column" }}>
            <div className="admin-modal-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {lyricMeta?.cover ? (
                  <img src={lyricMeta.cover} alt="Cover" style={{ width: 40, height: 40, borderRadius: 6, objectFit: "cover" }} />
                ) : (
                  <div style={{ width: 40, height: 40, borderRadius: 6, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Music size={20} color="#9ca3af" />
                  </div>
                )}
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Sincronizador de Letra</h3>
                  <div style={{ fontSize: 12, color: "#9ca3af" }}>{lyricMeta?.titulo} — {lyricMeta?.artista}</div>
                </div>
              </div>
              <button className="admin-btn-icon" style={{ border: "none", background: "none", color: "#9ca3af", cursor: "pointer", fontSize: 18 }} onClick={() => setSyncModalOpen(false)}>✕</button>
            </div>
            
            <div className="admin-modal-body" style={{ flex: 1, display: "flex", flexDirection: "column", padding: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", background: "rgba(0, 0, 0, 0.1)" }}>
                <button 
                  onClick={() => setModalTab("edit")} 
                  style={{
                    flex: 1, padding: "12px 16px", background: "none", border: "none", 
                    color: modalTab === "edit" ? "#d95840" : "#9ca3af",
                    borderBottom: modalTab === "edit" ? "2px solid #d95840" : "2px solid transparent",
                    fontWeight: 500, cursor: "pointer", transition: "all 0.2s"
                  }}
                >
                  Editar Texto Plano
                </button>
                <button 
                  onClick={() => {
                    setModalTab("sync");
                    setSyncLines(parseLrc(lyricContent));
                  }} 
                  style={{
                    flex: 1, padding: "12px 16px", background: "none", border: "none", 
                    color: modalTab === "sync" ? "#d95840" : "#9ca3af",
                    borderBottom: modalTab === "sync" ? "2px solid #d95840" : "2px solid transparent",
                    fontWeight: 500, cursor: "pointer", transition: "all 0.2s"
                  }}
                >
                  Sincronizar Tiempos
                </button>
              </div>

              <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
                {modalTab === "edit" ? (
                  <div style={{ flex: 1, padding: 20, display: "flex", flexDirection: "column", height: "100%" }}>
                    <p style={{ margin: "0 0 10px 0", fontSize: 12, color: "#9ca3af" }}>
                      Pega la letra aquí. Un renglón por línea. Luego ve a la pestaña "Sincronizar Tiempos".
                    </p>
                    <textarea 
                      className="admin-textarea" 
                      value={lyricContent}
                      onChange={(e) => setLyricContent(e.target.value)} 
                      style={{ flex: 1, resize: "none", fontFamily: "monospace", fontSize: 13, background: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: 12, color: "#fff" }} 
                    />
                  </div>
                ) : (
                  <div style={{ flex: 1, display: "flex", overflow: "hidden", height: "100%" }}>
                    
                    <div style={{ flex: 3, borderRight: "1px solid rgba(255, 255, 255, 0.08)", overflowY: "auto", padding: "16px 0", background: "rgba(0,0,0,0.1)" }}>
                      {syncLines.length === 0 ? (
                        <div style={{ textAlign: "center", padding: 40, color: "#9ca3af", fontSize: 13 }}>
                          No hay texto que sincronizar. Ve a la pestaña "Editar Texto Plano" e ingresa la letra.
                        </div>
                      ) : (
                        syncLines.map((line, idx) => {
                          const isActive = idx === activeIndex;
                          const isCurrentPlaying = checkIfLineIsPlaying(line, idx);
                          
                          return (
                            <div 
                              key={idx}
                              ref={(el) => { lineRefs.current[idx] = el; }}
                              onClick={() => handleLineClick(idx, line)}
                              style={{
                                display: "flex", alignItems: "center", gap: 12, padding: "10px 20px",
                                cursor: "pointer", transition: "all 0.15s",
                                background: isActive 
                                  ? "rgba(217, 88, 64, 0.15)" 
                                  : isCurrentPlaying 
                                    ? "rgba(255, 255, 255, 0.03)" 
                                    : "transparent",
                                borderLeft: isActive 
                                  ? "4px solid #d95840" 
                                  : isCurrentPlaying
                                    ? "4px solid rgba(255, 255, 255, 0.4)"
                                    : "4px solid transparent",
                              }}
                              className="sync-line-row"
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{
                                  fontSize: 11, fontFamily: "monospace", padding: "3px 6px", borderRadius: 4,
                                  background: line.time !== null ? "rgba(217, 88, 64, 0.2)" : "rgba(255,255,255,0.05)",
                                  color: line.time !== null ? "#e06c55" : "#6b7280",
                                  border: line.time !== null ? "1px solid rgba(217, 88, 64, 0.3)" : "1px solid rgba(255,255,255,0.05)"
                                }}>
                                  {line.time !== null ? formatTimeWithoutBrackets(line.time) : "--:--.--"}
                                </span>
                                {line.time !== null && (
                                  <button 
                                    onClick={(e) => clearLineTime(e, idx)}
                                    title="Quitar tiempo"
                                    style={{
                                      background: "none", border: "none", color: "#ef4444", fontSize: 13,
                                      cursor: "pointer", padding: "0 2px", opacity: 0.7
                                    }}
                                    className="clear-time-btn"
                                  >
                                    ✕
                                  </button>
                                )}
                              </div>
                              <span style={{ 
                                fontSize: 13, 
                                color: isActive ? "#ffffff" : isCurrentPlaying ? "#ffffff" : "#d1d5db", 
                                fontWeight: isActive ? "600" : isCurrentPlaying ? "500" : "normal" 
                              }}>
                                {line.text || <span style={{ fontStyle: "italic", color: "#4b5563" }}>(Línea vacía)</span>}
                              </span>
                            </div>
                          );
                        })
                      )}
                    </div>
                    
                    <div style={{ flex: 2, display: "flex", flexDirection: "column", padding: 20, background: "rgba(0,0,0,0.2)", justifyContent: "space-between" }}>
                      
                      <div style={{ textAlign: "center", marginTop: 10 }}>
                        <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                          Línea Activa ({activeIndex + 1} / {syncLines.length})
                        </div>
                        <div style={{ 
                          fontSize: 14, fontWeight: 600, color: "#fff", background: "rgba(255,255,255,0.03)", 
                          padding: 12, borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)", minHeight: 44,
                          display: "flex", alignItems: "center", justifyContent: "center"
                        }}>
                          {syncLines[activeIndex]?.text || <span style={{ color: "#4b5563" }}>- Fin de letra -</span>}
                        </div>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", margin: "20px 0" }}>
                        <button
                          onClick={stampCurrentLine}
                          disabled={activeIndex >= syncLines.length}
                          style={{
                            width: 140, height: 140, borderRadius: "50%", border: "none",
                            background: activeIndex >= syncLines.length ? "#374151" : "linear-gradient(135deg, #d95840, #f07e69)",
                            color: "#fff", fontSize: 15, fontWeight: "bold", cursor: activeIndex >= syncLines.length ? "not-allowed" : "pointer",
                            boxShadow: activeIndex >= syncLines.length ? "none" : "0 8px 24px rgba(217, 88, 64, 0.4)",
                            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                            gap: 6, transition: "transform 0.1s, box-shadow 0.2s"
                          }}
                          className="stamp-button"
                          onMouseDown={(e) => {
                            e.currentTarget.style.transform = "scale(0.95)";
                          }}
                          onMouseUp={(e) => {
                            e.currentTarget.style.transform = "scale(1)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "scale(1)";
                          }}
                        >
                          <Activity size={28} />
                          <span>ESTAMPAR</span>
                          <span style={{ fontSize: 10, fontWeight: "normal", opacity: 0.8 }}>(Barra Espac.)</span>
                        </button>
                      </div>

                      <div style={{ background: "rgba(0,0,0,0.15)", borderRadius: 10, padding: 16, border: "1px solid rgba(255,255,255,0.05)" }}>
                        
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#9ca3af" }}>{formatTimeDisplay(currentTime)}</span>
                          <input 
                            type="range" 
                            min={0} 
                            max={duration || 100} 
                            value={currentTime} 
                            onChange={(e) => seek(parseFloat(e.target.value))}
                            style={{ flex: 1, accentColor: "#d95840", height: 4, borderRadius: 2, cursor: "pointer" }}
                          />
                          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#9ca3af" }}>{formatTimeDisplay(duration)}</span>
                        </div>

                        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 16, marginBottom: 12 }}>
                          <button 
                            className="admin-btn admin-btn-secondary" 
                            style={{ padding: "6px 10px" }} 
                            title="Retroceder 5s"
                            onClick={() => seek(Math.max(0, currentTime - 5))}
                          >
                            -5s
                          </button>
                          
                          <button 
                            onClick={() => {
                              const isCurrent = currentSong && Number(currentSong.id) === Number(selectedId);
                              if (!isCurrent) {
                                startPlayingThisSong();
                              } else {
                                togglePlay();
                              }
                            }}
                            style={{
                              width: 44, height: 44, borderRadius: "50%", border: "none",
                              background: "#d95840", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                              cursor: "pointer", boxShadow: "0 4px 12px rgba(217, 88, 64, 0.3)"
                            }}
                          >
                            {(currentSong && Number(currentSong.id) === Number(selectedId) && playing) ? <Pause size={20} /> : <Play size={20} style={{ marginLeft: 2 }} />}
                          </button>
                          
                          <button 
                            className="admin-btn admin-btn-secondary" 
                            style={{ padding: "6px 10px" }} 
                            title="Adelantar 5s"
                            onClick={() => seek(Math.min(duration, currentTime + 5))}
                          >
                            +5s
                          </button>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                          <span style={{ color: "#9ca3af" }}>Velocidad:</span>
                          <select 
                            value={playbackRate} 
                            onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
                            style={{ background: "#222229", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", borderRadius: 4, padding: "2px 6px", fontSize: 12, cursor: "pointer" }}
                          >
                            <option value="0.5">0.50x (Muy Lento)</option>
                            <option value="0.75">0.75x (Lento)</option>
                            <option value="1.0">1.00x (Normal)</option>
                            <option value="1.25">1.25x (Rápido)</option>
                            <option value="1.5">1.50x (Muy Rápido)</option>
                          </select>
                        </div>

                      </div>

                      <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                        <button 
                          className="admin-btn admin-btn-secondary" 
                          style={{ flex: 1, fontSize: 12, padding: "8px 12px" }}
                          onClick={triggerUndo}
                          disabled={history.length === 0}
                        >
                          <Undo size={14} style={{ marginRight: 6 }} /> Deshacer
                        </button>
                        <button 
                          className="admin-btn admin-btn-secondary" 
                          style={{ flex: 1, fontSize: 12, padding: "8px 12px", color: "#f87171" }}
                          onClick={clearAllTimes}
                          disabled={syncLines.length === 0}
                        >
                          <Trash2 size={14} style={{ marginRight: 6 }} /> Limpiar
                        </button>
                      </div>

                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="admin-modal-footer">
              <button 
                className="admin-btn admin-btn-secondary" 
                onClick={() => setSyncModalOpen(false)}
              >
                Cancelar
              </button>
              <button 
                className="admin-btn admin-btn-primary" 
                onClick={async () => {
                  await saveLyricsFromModal();
                  setSyncModalOpen(false);
                }}
              >
                Guardar y Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
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

  if (loading) return <div style={{ color: "#9ca3af", marginTop: 24 }}>Cargando información del sistema...</div>;

  return (
    <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24 }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.9); }
        }
      `}</style>
      {/* Columna Izquierda: Información de Versión y Donación */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Tarjeta de Versión */}
        <div className="admin-card" style={{ padding: 24, position: "relative", overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#9ca3af", textTransform: "uppercase", letterSpacing: 0.5 }}>Estado del Sistema</span>
            {updateInfo && (
              <span style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                color: updateInfo.update_available ? "#d95840" : "#4ade80"
              }}>
                <span className="pulse-dot" style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: updateInfo.update_available ? "#d95840" : "#4ade80",
                  display: "inline-block",
                  animation: "pulse 1.8s infinite ease-in-out"
                }} />
                {updateInfo.update_available ? "Actualización disponible" : "Sistema al día"}
              </span>
            )}
          </div>

          {updateInfo && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontSize: 36, fontWeight: 800, color: "#ffffff" }}>{updateInfo.current}</span>
                <span style={{ fontSize: 13, color: "#6b7280" }}>versión activa</span>
              </div>

              {updateInfo.update_available ? (
                <div style={{ marginTop: 12, padding: "12px 14px", background: "rgba(217, 88, 64, 0.06)", border: "1px solid rgba(217, 88, 64, 0.15)", borderRadius: 8 }}>
                  <p style={{ color: "#d95840", fontSize: 12, margin: 0, fontWeight: 500 }}>
                    La versión {updateInfo.latest} ya está disponible para su descarga.
                  </p>
                  {updateInfo.url && (
                    <a href={updateInfo.url} target="_blank" rel="noopener noreferrer"
                      className="admin-btn admin-btn-secondary"
                      style={{ display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none", marginTop: 8, padding: "4px 10px", fontSize: 11 }}>
                      Ver Release Notes ↗
                    </a>
                  )}
                </div>
              ) : (
                <p style={{ color: "#9ca3af", fontSize: 12, margin: "8px 0 0" }}>
                  ¡Felicidades! Tienes instalada la versión oficial más reciente.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Tarjeta de Apoyo / Sponsor */}
        <div className="admin-card" style={{ 
          padding: 24, 
          background: "linear-gradient(145deg, #222229 0%, #1a1a20 100%)", 
          border: "1px solid rgba(255, 255, 255, 0.06)",
          position: "relative",
          overflow: "hidden"
        }}>
          {/* Brillo decorativo */}
          <div style={{ 
            position: "absolute", 
            top: "-30px", 
            right: "-30px", 
            width: 90, 
            height: 90, 
            borderRadius: "50%", 
            background: "rgba(217, 88, 64, 0.12)", 
            filter: "blur(20px)",
            pointerEvents: "none"
          }} />

          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 20 }}>💖</span>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: "#ffffff", margin: 0 }}>Apoyar a DuckSound</h3>
          </div>

          <p style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.6, margin: "0 0 18px" }}>
            DuckSound es un software libre e independiente desarrollado con cariño. Si te gusta la plataforma y te resulta útil, considera hacer un aporte voluntario para apoyar el desarrollo y mantenimiento del proyecto.
          </p>

          <a 
            href="https://app.takenos.com/pay/b6515307-a660-446d-8117-3214a4a89a80" 
            target="_blank" 
            rel="noopener noreferrer"
            className="admin-btn"
            style={{ 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center", 
              gap: 8, 
              textDecoration: "none", 
              background: "linear-gradient(135deg, #e66740 0%, #d95840 100%)", 
              color: "#ffffff", 
              fontWeight: 600, 
              padding: "10px 16px", 
              borderRadius: 8,
              fontSize: 13,
              boxShadow: "0 4px 12px rgba(217, 88, 64, 0.2)",
              transition: "transform 0.2s ease, box-shadow 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-1.5px)";
              e.currentTarget.style.boxShadow = "0 6px 16px rgba(217, 88, 64, 0.3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "none";
              e.currentTarget.style.boxShadow = "0 4px 12px rgba(217, 88, 64, 0.2)";
            }}
          >
            <span>Apoyar en Takenos</span>
            <span>💝</span>
          </a>
        </div>
      </div>

      {/* Columna Derecha: Changelog Completo */}
      <div className="admin-card" style={{ display: "flex", flexDirection: "column", height: "fit-content", maxHeight: 520 }}>
        <div className="admin-card-header" style={{ padding: "16px 20px", borderBottom: "1px solid rgba(255, 255, 255, 0.06)" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#ffffff" }}>Historial de versiones (Changelog)</div>
        </div>
        <div style={{ padding: "0 20px", overflowY: "auto", flex: 1 }} className="admin-changelog-scroll">
          {versions.map((v, idx) => (
            <div key={v.number} style={{ 
              borderBottom: idx < versions.length - 1 ? "1px solid rgba(255,255,255,0.06)" : "none", 
              padding: "16px 0" 
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#ffffff" }}>v{v.number}</span>
                  {v.status === "current" && (
                    <span className="admin-badge admin-badge-admin" style={{ fontSize: 10, padding: "1px 6px" }}>Activa</span>
                  )}
                  {v.status === "newer" && (
                    <span className="admin-badge" style={{ background: "rgba(217,88,64,0.12)", color: "#d95840", fontSize: 10, padding: "1px 6px", border: "1px solid rgba(217,88,64,0.2)" }}>Nuevo</span>
                  )}
                </div>
                {v.date && <span style={{ fontSize: 11, color: "#6b7280" }}>{v.date}</span>}
              </div>

              {v.sections?.map((s: any, i: number) => (
                <div key={i} style={{ marginTop: 8 }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: "#eaeaea", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: 0.5 }}>{s.title}</p>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#9ca3af", lineHeight: 1.5 }}>
                    {s.entries?.map((e: string, j: number) => (
                      <li key={j} style={{ marginBottom: 3 }}>{e}</li>
                    ))}
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
