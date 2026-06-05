import { useState } from "react";
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
        <div style={{ textAlign: "center", marginBottom: 8 }}>
          <svg width="48" height="48" viewBox="0 0 28 28" fill="none" style={{ margin: "0 auto 12px" }}>
            <rect width="28" height="28" rx="6" fill="#d95840"/>
            <text x="14" y="20" textAnchor="middle" fill="white" fontSize="16" fontWeight="bold">D</text>
          </svg>
          <h1 className="login-title">DuckSound</h1>
          <p className="login-subtitle">Inicia sesión para continuar</p>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <div className="form-group">
          <label className="form-label">Usuario</label>
          <input
            type="text"
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label className="form-label">Contraseña</label>
          <input
            type="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
