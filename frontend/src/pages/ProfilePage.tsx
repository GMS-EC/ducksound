import { useState, useEffect } from "react";
import {
  User, Clock, Heart, Music2, Headphones, Activity,
  LogOut, Monitor, Smartphone, Laptop,
} from "lucide-react";
import client from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import type { Cancion } from "../types";

interface TopSongItem {
  cancion: Cancion;
  plays: number;
}

interface TopArtistItem {
  nombre: string;
  id: number;
  plays: number;
}

interface SessionItem {
  id: number;
  navegador: string;
  sistema: string;
  dispositivo: string;
  ip: string;
  fecha_creacion: string;
  ultima_actividad: string;
  es_actual: boolean;
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [topSongs, setTopSongs] = useState<TopSongItem[]>([]);
  const [topArtists, setTopArtists] = useState<TopArtistItem[]>([]);
  const [totalPlays, setTotalPlays] = useState(0);
  const [totalHours, setTotalHours] = useState(0);
  const [last24h, setLast24h] = useState(0);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Settings state
  const [nombrePublico, setNombrePublico] = useState("");
  const [crossfade, setCrossfade] = useState(true);
  const [tracking, setTracking] = useState(true);
  const [idioma, setIdioma] = useState("es");
  const [audioQuality, setAudioQuality] = useState("lossless");
  const [newPassword, setNewPassword] = useState("");
  const [revokePassword, setRevokePassword] = useState("");

  useEffect(() => {
    Promise.all([
      client.get("/profile"),
      client.get("/api/sessions"),
    ])
      .then(([profileRes, sessionsRes]) => {
        const p = profileRes.data;
        setTopSongs(p.top_songs || []);
        setTopArtists(p.top_artists || []);
        setTotalPlays(p.total_plays || 0);
        setTotalHours(p.total_hours || 0);
        setLast24h(p.last_24h || 0);
        setSessions(sessionsRes.data || []);
        if (p.usuario) {
          setNombrePublico(p.usuario.nombre_publico || "");
          setCrossfade(p.usuario.crossfade_enabled ?? true);
          setTracking(p.usuario.activity_tracking ?? true);
          setIdioma(p.usuario.idioma_preferido || "es");
          setAudioQuality(p.usuario.audio_quality || "lossless");
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const updateProfile = async (field: string, value: any) => {
    try {
      await client.post("/api/profile/update", { [field]: value });
    } catch (e) {
      console.error(e);
    }
  };

  const handlePasswordChange = async () => {
    if (!newPassword || newPassword.length < 6) return;
    try {
      await client.post("/api/profile/update", { password: newPassword });
      setNewPassword("");
      alert("Contraseña actualizada");
    } catch (e) {
      console.error(e);
    }
  };

  const revokeSession = async (sessionId: number) => {
    if (!revokePassword) {
      alert("Ingresa tu contraseña para revocar la sesión");
      return;
    }
    try {
      await client.post("/api/sessions/" + sessionId + "/revoke", { password: revokePassword });
      setRevokePassword("");
      const res = await client.get("/api/sessions");
      setSessions(res.data || []);
    } catch (e: any) {
      alert(e.response?.data?.error || "Error al revocar sesión");
    }
  };

  const deviceIcon = (disp: string) => {
    if (disp === "Móvil") return <Smartphone size={14} />;
    if (disp === "Tablet") return <Monitor size={14} />;
    return <Laptop size={14} />;
  };

  if (loading) return <div className="p-6 text-gray-400">Cargando...</div>;

  return (
    <div className="p-6 space-y-8 max-w-4xl">
      <h1 className="page-title">Perfil</h1>

      <section className="profile-section">
        <h2 className="profile-section-title">
          <User size={18} className="text-purple-400" />
          Información personal
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400">Usuario</label>
            <p className="text-white">{user?.nombre_usuario}</p>
          </div>
          <div>
            <label className="text-xs text-gray-400">Rol</label>
            <p className="text-white capitalize">{user?.role}</p>
          </div>
          <div>
            <label className="text-xs text-gray-400">Nombre público</label>
            <input
              type="text"
              value={nombrePublico}
              onChange={(e) => setNombrePublico(e.target.value)}
              onBlur={() => updateProfile("nombre_publico", nombrePublico)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white text-sm mt-1"
              placeholder="Sin apodo"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400">Cambiar contraseña</label>
            <div className="flex gap-2 mt-1">
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Nueva contraseña (6+ caracteres)"
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white text-sm"
              />
              <button onClick={handlePasswordChange} className="px-3 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-500 transition">
                Guardar
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="profile-section">
        <h2 className="profile-section-title">
          <Activity size={18} className="text-purple-400" />
          Preferencias
        </h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Crossfade</p>
              <p className="profile-stat-label">Transición suave entre canciones</p>
            </div>
            <button
              onClick={() => { setCrossfade(!crossfade); updateProfile("crossfade_enabled", !crossfade); }}
              className={"w-12 h-6 rounded-full transition " + (crossfade ? "bg-purple-600" : "bg-gray-700")}
            >
              <div className={"w-4 h-4 bg-white rounded-full transition transform " + (crossfade ? "translate-x-7" : "translate-x-1")} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Registro de actividad</p>
              <p className="profile-stat-label">Guardar historial de escucha</p>
            </div>
            <button
              onClick={() => { setTracking(!tracking); updateProfile("activity_tracking", !tracking); }}
              className={"w-12 h-6 rounded-full transition " + (tracking ? "bg-purple-600" : "bg-gray-700")}
            >
              <div className={"w-4 h-4 bg-white rounded-full transition transform " + (tracking ? "translate-x-7" : "translate-x-1")} />
            </button>
          </div>
          <div>
            <label className="text-sm text-white block mb-1">Calidad de audio</label>
            <select
              value={audioQuality}
              onChange={(e) => { setAudioQuality(e.target.value); updateProfile("audio_quality", e.target.value); }}
              className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white text-sm"
            >
              <option value="lossless">Lossless (Original)</option>
              <option value="high">Alta (320k)</option>
              <option value="standard">Estándar (192k)</option>
              <option value="saver">Ahorro (96k)</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-white block mb-1">Idioma</label>
            <select
              value={idioma}
              onChange={(e) => { setIdioma(e.target.value); updateProfile("idioma_preferido", e.target.value); }}
              className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white text-sm"
            >
              <option value="es">Español</option>
              <option value="en">English</option>
              <option value="pt">Português</option>
            </select>
          </div>
        </div>
      </section>

      <section className="profile-section">
        <h2 className="profile-section-title">
          <Headphones size={18} className="text-purple-400" />
          Estadísticas
        </h2>
        <div className="profile-stats-grid">
          <div className="profile-stat">
            <Music2 size={24} className="mx-auto mb-2 text-purple-400" />
            <p className="profile-stat-value">{totalPlays}</p>
            <p className="profile-stat-label">Reproducciones</p>
          </div>
          <div className="profile-stat">
            <Clock size={24} className="mx-auto mb-2 text-blue-400" />
            <p className="profile-stat-value">{totalHours}h</p>
            <p className="profile-stat-label">Escuchadas</p>
          </div>
          <div className="profile-stat">
            <Activity size={24} className="mx-auto mb-2 text-green-400" />
            <p className="profile-stat-value">{last24h}</p>
            <p className="profile-stat-label">Últimas 24h</p>
          </div>
          <div className="profile-stat">
            <Heart size={24} className="mx-auto mb-2 text-red-400" />
            <p className="profile-stat-value">{topSongs.length}</p>
            <p className="profile-stat-label">Top canciones</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
          <div>
            <div className="profile-section-title" style={{fontSize:14}}>Top canciones</div>
            <div className="space-y-1">
              {topSongs.slice(0, 5).map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-xs text-gray-500 w-4">{i + 1}</span>
                  <span className="text-white truncate flex-1">{item.cancion.titulo}</span>
                  <span className="text-gray-400 text-xs">{item.plays} plays</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="profile-section-title" style={{fontSize:14}}>Top artistas</div>
            <div className="space-y-1">
              {topArtists.slice(0, 5).map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-xs text-gray-500 w-4">{i + 1}</span>
                  <span className="text-white truncate flex-1">{item.nombre}</span>
                  <span className="text-gray-400 text-xs">{item.plays} plays</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="profile-section">
        <h2 className="profile-section-title">
          <Monitor size={18} className="text-purple-400" />
          Sesiones activas
        </h2>
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
              <div className="flex items-center gap-3">
                {deviceIcon(s.dispositivo)}
                <div>
                  <p className="text-sm text-white">{s.navegador} {s.es_actual && "(actual)"}</p>
                  <p className="profile-stat-label">{s.sistema} - {s.dispositivo}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">{s.ip}</span>
                {!s.es_actual && (
                  <button
                    onClick={() => revokeSession(s.id)}
                    className="p-2 text-red-400 hover:text-red-300 transition"
                    title="Revocar sesión"
                  >
                    <LogOut size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        {sessions.some((s) => !s.es_actual) && (
          <div>
            <input
              type="password"
              value={revokePassword}
              onChange={(e) => setRevokePassword(e.target.value)}
              placeholder="Contraseña para revocar sesiones"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white text-sm mt-2"
            />
          </div>
        )}
        {sessions.length === 0 && <p className="text-sm text-gray-500">No hay sesiones activas</p>}
      </section>

      <button onClick={logout} className="admin-btn admin-btn-warning" style={{marginTop: 8}}>
        <LogOut size={16} />
        Cerrar sesión
      </button>
    </div>
  );
}
