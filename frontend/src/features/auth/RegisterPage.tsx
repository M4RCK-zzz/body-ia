import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { HttpError } from "@/services/api/apiClient";
import { useAuth } from "./useAuth";
import "./auth.css";

function passwordProblem(password: string): string | null {
  if (password.length < 10) return "La contraseña debe tener al menos 10 caracteres.";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
    return "La contraseña debe incluir al menos una letra y un número.";
  }
  return null;
}

export function RegisterPage() {
  const { status, register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const problem = passwordProblem(password);
    if (problem) return setError(problem);
    if (password !== confirm) return setError("Las contraseñas no coinciden.");

    setBusy(true);
    try {
      await register({ email: email.trim(), password, full_name: fullName.trim() });
    } catch (err) {
      setError(err instanceof HttpError ? err.message : "No se pudo crear la cuenta.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="bv-auth-page">
      <form className="bv-auth-card" onSubmit={onSubmit} noValidate>
        <h1>BODYVISION AI</h1>
        <p className="bv-auth-sub">Crear cuenta</p>

        <label>
          Nombre completo
          <input
            value={fullName}
            autoComplete="name"
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </label>
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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <label>
          Repite la contraseña
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </label>

        {error && (
          <p className="bv-auth-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy || !fullName || !email || !password}>
          {busy ? "Creando…" : "Crear cuenta"}
        </button>
        <p className="bv-auth-switch">
          ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
        </p>
      </form>
    </main>
  );
}