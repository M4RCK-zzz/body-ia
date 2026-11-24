import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/features/auth/useAuth";

/**
 * Guard de ruta para `/admin`.
 *
 * No es una medida de seguridad (eso lo hace el backend con `require_admin`,
 * que responde 403): es para no ofrecer una pantalla que no va a funcionar y
 * para no filtrar por la UI qué existe. Se comprueba el rol en el cliente y se
 * muestra un 403 explícito, no una redirección silenciosa.
 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, status, hasRole } = useAuth();

  if (status === "loading") {
    return (
      <p role="status" className="bv-muted">
        Verificando permisos…
      </p>
    );
  }

  if (!user || !hasRole("admin")) {
    return (
      <section className="bv-panel admin-denied" role="alert">
        <h1>Acceso denegado</h1>
        <p>
          Esta sección requiere el rol <strong>Administrador</strong>. La cuenta con la que has
          iniciado sesión no lo incluye.
        </p>
        <p className="bv-muted">
          El rol se concede desde el panel de administración a otra persona con permisos. Si crees
          que es un error, contacta con quien gestione las cuentas de tu organización.
        </p>
        <Link className="bv-btn" to="/">
          Volver al dashboard
        </Link>
      </section>
    );
  }

  return <>{children}</>;
}
