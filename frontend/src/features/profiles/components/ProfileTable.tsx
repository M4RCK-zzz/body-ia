import { Link } from "react-router-dom";
import { AccessBadge } from "@/features/access/AccessBadge";
import { formatDate } from "@/features/measurements/format";
import { PROFILE_STATUS_LABEL, type Profile } from "@/types/profile";

export function ProfileTable({ rows }: { rows: Profile[] }) {
  if (rows.length === 0) return <p className="bv-muted">No hay expedientes en esta vista.</p>;

  return (
    <table className="bv-table">
      <thead>
        <tr>
          <th>Código</th>
          <th>Estado</th>
          <th>Tu acceso</th>
          <th>Creado</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr key={p.id}>
            <td>
              <strong>{p.display_code}</strong>
            </td>
            <td>
              <span className="bv-tag bv-tag--status">
                {PROFILE_STATUS_LABEL[p.status].toUpperCase()}
              </span>
            </td>
            <td>
              <AccessBadge level={p.my_access} />
            </td>
            <td>{formatDate(p.created_at)}</td>
            <td>
              <Link className="bv-btn bv-btn--small" to={`/expedientes/${p.id}`}>
                Abrir
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
