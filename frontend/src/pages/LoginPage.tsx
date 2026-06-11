import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { User, Lock, Music, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError("Credenciales incorrectas. Inténtalo de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div style={{ textAlign: "center", marginBottom: 8 }}>
          <div className="login-logo-wrapper">
            <img src="/logo.svg" alt="DuckSound Logo" className="login-logo-img" style={{ width: 80, height: 80 }} />
          </div>
          <h1 className="login-title">DuckSound</h1>
          <p className="login-subtitle">Inicia sesión en tu reproductor de música</p>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="login-error-alert">
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label className="login-label">Usuario</label>
            <div className="login-field-wrapper">
              <input
                type="text"
                className="login-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="Ingresa tu usuario"
              />
              <div className="login-field-icon">
                <User size={18} />
              </div>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 28 }}>
            <label className="login-label">Contraseña</label>
            <div className="login-field-wrapper">
              <input
                type="password"
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Ingresa tu contraseña"
              />
              <div className="login-field-icon">
                <Lock size={18} />
              </div>
            </div>
          </div>

          <button type="submit" className="login-btn-primary" disabled={loading}>
            {loading ? (
              <span>Ingresando...</span>
            ) : (
              <>
                <Music size={18} />
                <span>Ingresar</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
