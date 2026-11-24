interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
  /** Nombre del recurso para el texto ("usuarios", "eventos"). */
  noun?: string;
  disabled?: boolean;
}

/**
 * Paginación por `limit`/`offset`, igual que el resto de la API.
 *
 * Se calcula sobre `total` (que el backend devuelve ya filtrado), así que el
 * rango mostrado siempre coincide con lo que hay en pantalla.
 */
export function Pagination({
  total,
  limit,
  offset,
  onChange,
  noun = "resultados",
  disabled = false,
}: PaginationProps) {
  if (total === 0) return null;

  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <nav className="admin-pagination" aria-label={`Paginación de ${noun}`}>
      <p className="bv-muted">
        Mostrando <strong>{from}</strong>–<strong>{to}</strong> de <strong>{total}</strong> {noun}
      </p>
      <div className="bv-actions">
        <button
          type="button"
          className="bv-btn bv-btn--small"
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={disabled || !hasPrev}
        >
          Anterior
        </button>
        <button
          type="button"
          className="bv-btn bv-btn--small"
          onClick={() => onChange(offset + limit)}
          disabled={disabled || !hasNext}
        >
          Siguiente
        </button>
      </div>
    </nav>
  );
}
