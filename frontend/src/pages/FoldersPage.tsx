import { useState, useEffect } from "react";
import { Folder, FolderUp, Play, ShieldAlert, Loader2, HardDrive } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { usePlayer } from "../contexts/PlayerContext";
import client from "../api/client";
import type { Cancion } from "../types";

interface FolderItem {
  name: string;
  path: string;
  track_count: number;
}

interface FileItem {
  name: string;
  path: string;
  extension: string;
  size: number;
  song: Cancion | null;
}

export default function FoldersPage() {
  const { user } = useAuth();
  const { play } = usePlayer();

  const [currentPath, setCurrentPath] = useState("");
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [folderName, setFolderName] = useState("Música");
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingFolder, setPlayingFolder] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") return;

    setLoading(true);
    client
      .get(`/api/admin/folders?path=${encodeURIComponent(currentPath)}`)
      .then((res) => {
        setFolders(res.data.folders || []);
        setFiles(res.data.files || []);
        setParentPath(res.data.parent_path);
        setFolderName(res.data.folder_name || "Música");
      })
      .catch((err) => {
        console.error("Error cargando carpetas:", err);
      })
      .finally(() => setLoading(false));
  }, [currentPath, user]);

  // Si el usuario no es admin, denegar acceso visualmente
  if (user?.role !== "admin") {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#9ca3af" }}>
        <ShieldAlert size={56} style={{ color: "var(--color-accent)", margin: "0 auto 16px auto" }} />
        <h2 style={{ fontSize: 22, color: "#fff", marginBottom: 8 }}>Acceso Exclusivo para Administradores</h2>
        <p style={{ maxWidth: 450, margin: "0 auto", fontSize: 14 }}>
          El explorador de carpetas físicas del servidor está restringido a administradores para proteger la estructura del sistema.
        </p>
      </div>
    );
  }

  const navigateTo = (path: string) => {
    setCurrentPath(path);
  };

  const handlePlayFolder = async () => {
    setPlayingFolder(true);
    try {
      const res = await client.post("/api/admin/folders/play", { path: currentPath });
      if (res.data && res.data.songs && res.data.songs.length > 0) {
        play(res.data.songs, 0);
      } else {
        alert("No se encontraron canciones reproducibles en esta carpeta.");
      }
    } catch (err) {
      console.error(err);
      alert("Error al reproducir carpeta.");
    } finally {
      setPlayingFolder(false);
    }
  };

  const handlePlayFile = (file: FileItem) => {
    if (file.song) {
      play([file.song], 0);
    } else {
      // Canción no indexada aún, usar fallback
      const tempSong: Cancion = {
        id: -1,
        titulo: file.name.replace(/\.[^/.]+$/, ""),
        artista: "Archivo Local",
        artista_id: null,
        album: folderName,
        album_id: null,
        anio: null,
        duracion: null,
        ruta_audio: `/audio/direct?path=${encodeURIComponent(file.path)}`,
        ruta_lrc: null,
        ruta_imagen: null,
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
      play([tempSong], 0);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  // Breadcrumbs builder
  const pathParts = currentPath ? currentPath.split("/").filter(Boolean) : [];

  return (
    <div className="page-wrapper" style={{ padding: "28px 36px" }}>
      {/* Top Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <HardDrive size={22} style={{ color: "var(--color-accent)" }} />
            <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: "#fff" }}>
              Explorador de Carpetas
            </h1>
            <span style={{ fontSize: 11, background: "rgba(217,88,64,0.18)", color: "var(--color-accent)", padding: "2px 8px", borderRadius: 12, fontWeight: 700 }}>
              Admin
            </span>
          </div>
          <p style={{ margin: "4px 0 0 0", color: "#9ca3af", fontSize: 13 }}>
            Navega directamente por la estructura física de tu disco o servidor
          </p>
        </div>

        {(folders.length > 0 || files.length > 0) && (
          <button
            onClick={handlePlayFolder}
            disabled={playingFolder}
            style={{
              background: "var(--color-accent)",
              border: "none",
              borderRadius: 8,
              padding: "10px 18px",
              color: "#fff",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              fontWeight: 700,
              boxShadow: "0 4px 16px rgba(217,88,64,0.35)",
              transition: "transform 0.15s ease",
            }}
            onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.96)")}
            onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
          >
            {playingFolder ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} fill="currentColor" />}
            <span>Reproducir Esta Carpeta</span>
          </button>
        )}
      </div>

      {/* Breadcrumb Path Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "rgba(255, 255, 255, 0.04)",
          padding: "10px 16px",
          borderRadius: 8,
          marginBottom: 24,
          fontSize: 13,
          color: "#9ca3af",
          flexWrap: "wrap",
        }}
      >
        <span
          onClick={() => navigateTo("")}
          style={{ cursor: "pointer", color: currentPath === "" ? "#fff" : "var(--color-accent)", fontWeight: 600 }}
        >
          Raíz (Música)
        </span>
        {pathParts.map((part, index) => {
          const partPath = pathParts.slice(0, index + 1).join("/");
          const isLast = index === pathParts.length - 1;
          return (
            <span key={partPath} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span>/</span>
              <span
                onClick={() => !isLast && navigateTo(partPath)}
                style={{
                  cursor: isLast ? "default" : "pointer",
                  color: isLast ? "#fff" : "var(--color-accent)",
                  fontWeight: isLast ? 700 : 500,
                }}
              >
                {part}
              </span>
            </span>
          );
        })}
      </div>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 60, color: "#9ca3af", gap: 10 }}>
          <Loader2 className="animate-spin" size={20} />
          <span>Explorando carpeta...</span>
        </div>
      ) : (
        <>
          {/* Subcarpetas */}
          {parentPath !== null && (
            <div
              onClick={() => navigateTo(parentPath)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 14px",
                background: "rgba(255,255,255,0.06)",
                borderRadius: 6,
                color: "#fff",
                cursor: "pointer",
                marginBottom: 16,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              <FolderUp size={16} />
              <span>Subir de nivel</span>
            </div>
          )}

          {folders.length > 0 && (
            <div style={{ marginBottom: 32 }}>
              <h3 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: 1, color: "#9ca3af", marginBottom: 12 }}>
                Carpetas ({folders.length})
              </h3>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                  gap: 12,
                }}
              >
                {folders.map((f) => (
                  <div
                    key={f.path}
                    onClick={() => navigateTo(f.path)}
                    style={{
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      borderRadius: 8,
                      padding: "14px 16px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      transition: "all 0.2s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(255, 255, 255, 0.08)";
                      e.currentTarget.style.borderColor = "rgba(217,88,64,0.4)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                      e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.06)";
                    }}
                  >
                    <Folder size={24} style={{ color: "var(--color-accent)", flexShrink: 0 }} />
                    <div style={{ flex: 1, overflow: "hidden" }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", textOverflow: "ellipsis", whiteSpace: "nowrap", overflow: "hidden" }}>
                        {f.name}
                      </div>
                      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                        {f.track_count > 0 ? `${f.track_count} canciones` : "Carpeta"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Archivos de Música */}
          <div>
            <h3 style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: 1, color: "#9ca3af", marginBottom: 12 }}>
              Pistas en esta carpeta ({files.length})
            </h3>
            {files.length === 0 ? (
              <p style={{ color: "#9ca3af", fontSize: 13 }}>No hay archivos de audio sueltos en este directorio.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {files.map((file) => {
                  const song = file.song;
                  return (
                    <div
                      key={file.path}
                      onClick={() => handlePlayFile(file)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 14,
                        padding: "10px 14px",
                        borderRadius: 6,
                        cursor: "pointer",
                        background: "rgba(255, 255, 255, 0.02)",
                        transition: "background 0.2s ease",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.06)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.02)")}
                    >
                      <button
                        style={{
                          background: "none",
                          border: "none",
                          color: "var(--color-accent)",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          padding: 0,
                        }}
                      >
                        <Play size={16} fill="currentColor" />
                      </button>

                      <div style={{ flex: 1, overflow: "hidden" }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", textOverflow: "ellipsis", whiteSpace: "nowrap", overflow: "hidden" }}>
                          {song ? song.titulo : file.name}
                        </div>
                        <div style={{ fontSize: 11, color: "#9ca3af" }}>
                          {song ? `${song.artista} • ${song.album || "Sencillo"}` : file.name}
                        </div>
                      </div>

                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: file.extension === "flac" ? "rgba(217,88,64,0.18)" : "rgba(255,255,255,0.08)",
                          color: file.extension === "flac" ? "var(--color-accent)" : "#9ca3af",
                          textTransform: "uppercase",
                        }}
                      >
                        {file.extension}
                      </span>

                      <span style={{ fontSize: 12, color: "#9ca3af", minWidth: 60, textAlign: "right" }}>
                        {formatSize(file.size)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
