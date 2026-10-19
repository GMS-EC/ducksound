import { useState, useRef, useEffect } from "react";
import { Search, X, Music2, User, Disc3 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import { usePlayer } from "../contexts/PlayerContext";
import type { Cancion, Artista, Album } from "../types";

interface SearchResult {
  songs: (Cancion & { audio: string; cover: string; lyrics: string })[];
  artists: (Artista & { foto: string })[];
  albums: (Album & { artista: string })[];
}

export default function SearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { play } = usePlayer();

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setQuery("");
      setResult(null);
    }
  }, [open]);

  useEffect(() => {
    if (!query || query.length < 2) {
      setResult(null);
      return;
    }
    const timer = setTimeout(() => {
      setLoading(true);
      client.get("/api/search", { params: { q: query } })
        .then((res) => setResult(res.data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-24">
      <div className="w-full max-w-lg bg-gray-900 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
          <Search size={18} className="text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar canciones, artistas, álbumes..."
            className="flex-1 bg-transparent text-white text-sm placeholder-gray-500 outline-none"
          />
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-96 overflow-y-auto p-2">
          {loading && <p className="text-sm text-gray-400 px-2 py-4 text-center">Buscando...</p>}
          {result && !loading && (
            <div className="space-y-3">
              {result.songs.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 px-2 mb-1">Canciones</p>
                  {result.songs.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => { play([s], 0); onClose(); }}
                      className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-800 transition text-left"
                    >
                      <Music2 size={16} className="text-gray-400 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-white truncate">{s.titulo}</div>
                        <div className="text-xs text-gray-400 truncate">{s.artista}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {result.artists.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 px-2 mb-1">Artistas</p>
                  {result.artists.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => { navigate("/artist/" + a.id); onClose(); }}
                      className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-800 transition text-left"
                    >
                      <User size={16} className="text-gray-400 flex-shrink-0" />
                      <span className="text-sm text-white truncate">{a.nombre}</span>
                    </button>
                  ))}
                </div>
              )}
              {result.albums.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 px-2 mb-1">Álbumes</p>
                  {result.albums.map((al) => (
                    <button
                      key={al.id}
                      onClick={() => { navigate("/album/" + al.id); onClose(); }}
                      className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-800 transition text-left"
                    >
                      <Disc3 size={16} className="text-gray-400 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-white truncate">{al.titulo}</div>
                        <div className="text-xs text-gray-400 truncate">{al.artista}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {result.songs.length === 0 && result.artists.length === 0 && result.albums.length === 0 && (
                <p className="text-sm text-gray-500 px-2 py-4 text-center">Sin resultados</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
