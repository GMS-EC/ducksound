import { useEffect, useState } from "react";
import { X, Loader2, Tag, Save } from "lucide-react";
import client from "../api/client";
import { useContextMenu } from "../contexts/ContextMenuContext";

export default function EditTagsModal() {
  const { editSong, closeEditModal } = useContextMenu();

  const [titulo, setTitulo] = useState("");
  const [artista, setArtista] = useState("");
  const [album, setAlbum] = useState("");
  const [numeroPista, setNumeroPista] = useState("");
  const [anio, setAnio] = useState("");
  const [genero, setGenero] = useState("");
  const [filepath, setFilepath] = useState("");

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!editSong) return;

    setLoading(true);
    setError(null);
    setSuccess(null);

    client
      .get(`/api/track/${editSong.id}/tags`)
      .then((res) => {
        const d = res.data;
        setTitulo(d.titulo || "");
        setArtista(d.artista || "");
        setAlbum(d.album || "");
        setNumeroPista(d.numero_pista ? String(d.numero_pista) : "");
        setAnio(d.anio ? String(d.anio) : "");
        setGenero(d.genero || "");
        setFilepath(d.filepath || "");
      })
      .catch((err) => {
        console.error("Error al cargar etiquetas:", err);
        setError("No se pudieron cargar las etiquetas del archivo.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [editSong]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeEditModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeEditModal]);

  if (!editSong) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo.trim()) {
      setError("El título no puede estar vacío.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await client.post(`/api/track/${editSong.id}/tags`, {
        titulo: titulo.trim(),
        artista: artista.trim(),
        album: album.trim(),
        numero_pista: numeroPista.trim() ? parseInt(numeroPista.trim(), 10) : null,
        anio: anio.trim() ? parseInt(anio.trim(), 10) : null,
        genero: genero.trim(),
      });

      setSuccess("¡Metadatos guardados con éxito en el archivo y base de datos!");
      window.dispatchEvent(new Event("ducksound:library_updated"));

      setTimeout(() => {
        closeEditModal();
      }, 900);
    } catch (err: any) {
      console.error("Error al guardar etiquetas:", err);
      setError(err?.response?.data?.error || "Error al escribir los metadatos en el archivo.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={closeEditModal} style={{ zIndex: 1100 }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Tag size={18} style={{ color: "var(--color-accent, #d95840)" }} />
            <h3 className="modal-title">Editar Etiquetas: {editSong.titulo}</h3>
          </div>
          <button className="modal-close-btn" onClick={closeEditModal}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0", gap: 12, color: "var(--color-muted)" }}>
              <Loader2 className="animate-spin" size={24} />
              <span style={{ fontSize: 13 }}>Leyendo etiquetas del archivo físico...</span>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {error && (
                <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#ef4444", padding: "8px 12px", borderRadius: 6, fontSize: 13 }}>
                  {error}
                </div>
              )}
              {success && (
                <div style={{ background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.3)", color: "#22c55e", padding: "8px 12px", borderRadius: 6, fontSize: 13 }}>
                  {success}
                </div>
              )}

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                  Título de la canción
                </label>
                <input
                  type="text"
                  value={titulo}
                  onChange={(e) => setTitulo(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#222229",
                    border: "1px solid var(--color-border)",
                    color: "#fff",
                    padding: "8px 12px",
                    borderRadius: 6,
                    fontSize: 14,
                    outline: "none"
                  }}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                    Artista
                  </label>
                  <input
                    type="text"
                    value={artista}
                    onChange={(e) => setArtista(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#222229",
                      border: "1px solid var(--color-border)",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 6,
                      fontSize: 14,
                      outline: "none"
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                    Álbum
                  </label>
                  <input
                    type="text"
                    value={album}
                    onChange={(e) => setAlbum(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#222229",
                      border: "1px solid var(--color-border)",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 6,
                      fontSize: 14,
                      outline: "none"
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                    Nº de Pista
                  </label>
                  <input
                    type="number"
                    value={numeroPista}
                    onChange={(e) => setNumeroPista(e.target.value)}
                    placeholder="1"
                    style={{
                      width: "100%",
                      background: "#222229",
                      border: "1px solid var(--color-border)",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 6,
                      fontSize: 14,
                      outline: "none"
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                    Año
                  </label>
                  <input
                    type="number"
                    value={anio}
                    onChange={(e) => setAnio(e.target.value)}
                    placeholder="2024"
                    style={{
                      width: "100%",
                      background: "#222229",
                      border: "1px solid var(--color-border)",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 6,
                      fontSize: 14,
                      outline: "none"
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, color: "var(--color-muted)", marginBottom: 4, fontWeight: 500 }}>
                    Género
                  </label>
                  <input
                    type="text"
                    value={genero}
                    onChange={(e) => setGenero(e.target.value)}
                    placeholder="Pop, Rock..."
                    style={{
                      width: "100%",
                      background: "#222229",
                      border: "1px solid var(--color-border)",
                      color: "#fff",
                      padding: "8px 12px",
                      borderRadius: 6,
                      fontSize: 14,
                      outline: "none"
                    }}
                  />
                </div>
              </div>

              {filepath && (
                <div style={{ fontSize: 11, color: "var(--color-muted)", wordBreak: "break-all", background: "rgba(255,255,255,0.03)", padding: "6px 10px", borderRadius: 4 }}>
                  <strong>Ruta:</strong> {filepath}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={closeEditModal}
                  style={{
                    background: "transparent",
                    border: "1px solid var(--color-border)",
                    color: "#fff",
                    padding: "8px 16px",
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: "pointer"
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  style={{
                    background: "var(--color-accent, #d95840)",
                    border: "none",
                    color: "#fff",
                    padding: "8px 18px",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: saving ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6
                  }}
                >
                  {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
                  <span>{saving ? "Guardando..." : "Guardar cambios"}</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
