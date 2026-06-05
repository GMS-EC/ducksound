import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ListMusic } from "lucide-react";
import client from "../api/client";
import type { Coleccion } from "../types";

export default function ColeccionesPage() {
  const navigate = useNavigate();
  const [colecciones, setColecciones] = useState<Coleccion[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  const fetchColecciones = () => {
    client.get("/colecciones")
      .then((res) => setColecciones(res.data.colecciones || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchColecciones(); }, []);

  const createColeccion = async () => {
    if (!newName.trim()) return;
    try {
      await client.post("/api/colecciones/crear", { nombre: newName });
      setNewName("");
      setShowCreate(false);
      fetchColecciones();
    } catch (e) { console.error(e); }
  };

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">Colecciones</h1>
          <p className="page-subtitle">Tus playlists personalizadas</p>
        </div>
        <button className="admin-btn admin-btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={18} />
          Nueva
        </button>
      </div>

      {showCreate && (
        <div style={{ display: "flex", gap: 8, padding: "16px 32px" }}>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Nombre de la colección"
            className="admin-form-input"
            style={{ flex: 1 }}
            onKeyDown={(e) => e.key === "Enter" && createColeccion()}
          />
          <button className="admin-btn admin-btn-primary" onClick={createColeccion}>Crear</button>
        </div>
      )}

      {colecciones.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><ListMusic size={48} /></div>
          <h2 className="empty-title">No tienes colecciones</h2>
          <p className="empty-text">Crea una para empezar</p>
        </div>
      ) : (
        <div className="card-grid" style={{ paddingTop: 24 }}>
          {colecciones.map((c) => (
            <div key={c.id} className="album-card" onClick={() => navigate("/coleccion/" + c.id)}>
              <div className="album-card-cover" style={{ background: "linear-gradient(135deg, #d95840, #1a1a1f)" }}>
                <ListMusic size={32} style={{ color: "rgba(255,255,255,0.5)" }} />
              </div>
              <div className="album-card-info">
                <div className="album-card-title">{c.nombre}</div>
                {c.descripcion && <div className="album-card-meta">{c.descripcion}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
