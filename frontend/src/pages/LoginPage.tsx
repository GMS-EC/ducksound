import { useState } from "react";
import { Lock, User } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

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
      setError("Credenciales inválidas");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit} className="login-card">
        <div className="login-brand">
          <img src="/logo.svg" alt="DuckSound" className="login-logo" />
          <h1 className="login-title">DuckSound</h1>
          <p className="login-subtitle">Inicia sesión para escuchar tu biblioteca</p>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <div className="form-group">
          <label className="form-label">Usuario</label>
          <div className="input-shell">
            <User size={16} />
            <input
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Contraseña</label>
          <div className="input-shell">
            <Lock size={16} />
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
