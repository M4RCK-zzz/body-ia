import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import "./auth.css";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, retry } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <p role="status" className="bv-auth-status">
        Verificando sesión…
      </p>
    );
  }
  if (status === "unavailable") {
    return (
      <div className="bv-auth-status" role="alert">
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={retry}>
          Reintentar
        </button>
      </div>
    );
  }
  if (status === "anonymous") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <>{children}</>;
}