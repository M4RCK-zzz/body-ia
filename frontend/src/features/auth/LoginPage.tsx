import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { HttpError } from "@/services/api/apiClient";
import { useAuth } from "./useAuth";
import "./auth.css";

function safeRedirect(from: unknown): string {
  return typeof from === "string" && from.startsWith("/") && !from.startsWith("//") ? from : "/";
}

export function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const target = safeRedirect((location.state as { from?: string } | null)?.from);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to={target} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email: email.trim(), password });
    } catch (err) {
      setError(err instanceof HttpError ? err.message : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="bv-auth-page">
      <form className="bv-auth-card" onSubmit={onSubmit} noValidate>
        <h1>BODYVISION AI</h1>
        <p className="bv-auth-sub">Inicia sesión</p>

        <label>
          Correo electrónico
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && (
          <p className="bv-auth-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy || !email || !password}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
        <p className="bv-auth-switch">
          ¿No tienes cuenta? <Link to="/registro">Regístrate</Link>
        </p>
        <p className="bv-auth-note">
          Plataforma de análisis y simulación hipotética. No es una herramienta médica ni
          emite diagnósticos. Entorno de desarrollo: no cargues datos reales de personas.
        </p>
      </form>
    </main>
  );
}