import { useMemo, useState } from "react";
import { formatDateTime } from "@/features/measurements/format";
import { auditActionLabel, isSensitiveAction, type AuditFilters } from "@/types/admin";
import { describeEvent, requestIdOf, toDateTimeLocal, toIso } from "../format";
import { useAdminUsers, useAuditActions, useAuditEvents } from "../hooks/useAdmin";
import { Pagination } from "./Pagination";

const PAGE_SIZE = 25;

export function AuditTab() {
  const [action, setAction] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const filters = useMemo<AuditFilters>(
    () => ({
      action: action || undefined,
      actorUserId: actorUserId || undefined,
      since: toIso(since),
      until: toIso(until),
    }),
    [action, actorUserId, since, until],
  );

  const query = useAuditEvents(filters, { limit: PAGE_SIZE, offset });
  const actions = useAuditActions();
  const users = useAdminUsers({}, { limit: 200, offset: 0 });

  const actorName = (userId: string | null): string => {
    if (!userId) return "Sistema";
    const fromPage = query.data?.actors.find((actor) => actor.id === userId);
    if (fromPage) return fromPage.full_name;
    const fromList = users.data?.items.find((user) => user.id === userId);
    return fromList ? fromList.full_name : `${userId.slice(0, 8)}…`;
  };

  const resetPage = () => setOffset(0);
  const filtersActive = Boolean(action || actorUserId || since || until);
  const sinceIso = toIso(since);
  const untilIso = toIso(until);
  const rangeInverted = Boolean(sinceIso && untilIso && sinceIso > untilIso);

  return (
    <div className="admin-tab">
      <section className="bv-panel" aria-labelledby="admin-audit-title">
        <h2 id="admin-audit-title">Auditoría</h2>
        <p className="bv-muted">
          Registro append-only de acciones sensibles: quién hizo qué, sobre qué recurso y cuándo.
          No se puede editar ni borrar desde la aplicación.
        </p>

        <form
          className="bv-row admin-filters"
          onSubmit={(event) => {
            event.preventDefault();
            resetPage();
          }}
        >
          <div className="bv-field">
            <label htmlFor="admin-audit-action">Acción</label>
            <select
              id="admin-audit-action"
              className="bv-input"
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                resetPage();
              }}
            >
              <option value="">Todas</option>
              {(actions.data?.actions ?? []).map((value) => (
                <option key={value} value={value}>
                  {auditActionLabel(value)}
                </option>
              ))}
            </select>
          </div>
          <div className="bv-field">
            <label htmlFor="admin-audit-actor">Usuario</label>
            <select
              id="admin-audit-actor"
              className="bv-input"
              value={actorUserId}
              onChange={(event) => {
                setActorUserId(event.target.value);
                resetPage();
              }}
            >
              <option value="">Todos</option>
              {(users.data?.items ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name} ({user.email})
                </option>
              ))}
            </select>
          </div>
          <div className="bv-field">
            <label htmlFor="admin-audit-since">Desde</label>
            <input
              id="admin-audit-since"
              className="bv-input"
              type="datetime-local"
              value={since}
              max={toDateTimeLocal(new Date().toISOString())}
              onChange={(event) => {
                setSince(event.target.value);
                resetPage();
              }}
            />
          </div>
          <div className="bv-field">
            <label htmlFor="admin-audit-until">Hasta</label>
            <input
              id="admin-audit-until"
              className="bv-input"
              type="datetime-local"
              value={until}
              max={toDateTimeLocal(new Date().toISOString())}
              onChange={(event) => {
                setUntil(event.target.value);
                resetPage();
              }}
            />
          </div>
          <button type="submit" className="bv-btn">
            Aplicar
          </button>
          {filtersActive ? (
            <button
              type="button"
              className="bv-btn"
              onClick={() => {
                setAction("");
                setActorUserId("");
                setSince("");
                setUntil("");
                resetPage();
              }}
            >
              Limpiar
            </button>
          ) : null}
        </form>

        {rangeInverted ? (
          <p className="bv-alert bv-alert--warn">
            La fecha «desde» es posterior a «hasta»: el resultado será vacío.
          </p>
        ) : null}

        {query.error ? (
          <p className="bv-alert bv-alert--error" role="alert">
            {query.error.message}
          </p>
        ) : null}
        {query.isLoading ? <p className="bv-muted">Cargando eventos…</p> : null}

        {query.data ? (
          <>
            <div className="admin-table-scroll">
              <table className="bv-table admin-audit-table">
                <caption className="bv-sr-only">
                  Eventos de auditoría con fecha, acción, actor y recurso
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Fecha</th>
                    <th scope="col">Acción</th>
                    <th scope="col">Actor</th>
                    <th scope="col">Recurso</th>
                    <th scope="col">Resumen</th>
                    <th scope="col">Request ID</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((event) => {
                    const requestId = requestIdOf(event);
                    const sensitive = isSensitiveAction(event.action);
                    const isOpen = expanded === event.id;
                    return (
                      <tr key={event.id} className={sensitive ? "is-sensitive" : undefined}>
                        <td className="admin-cell-date">{formatDateTime(event.occurred_at)}</td>
                        <th scope="row" className="admin-cell-action">
                          <span className={sensitive ? "admin-action--sensitive" : undefined}>
                            {auditActionLabel(event.action)}
                          </span>
                          <code className="admin-action-code">{event.action}</code>
                        </th>
                        <td>{actorName(event.actor_user_id)}</td>
                        <td className="admin-cell-resource">
                          {event.resource_type ?? "—"}
                          {event.profile_id ? (
                            <small title={event.profile_id}>
                              expediente {event.profile_id.slice(0, 8)}
                            </small>
                          ) : null}
                        </td>
                        <td className="admin-cell-summary">
                          {describeEvent(event)}
                          {event.detail ? (
                            <button
                              type="button"
                              className="bv-btn bv-btn--small admin-json-toggle"
                              aria-expanded={isOpen}
                              onClick={() => setExpanded(isOpen ? null : event.id)}
                            >
                              {isOpen ? "Ocultar detalle" : "Ver detalle"}
                            </button>
                          ) : null}
                          {isOpen ? (
                            <pre className="admin-json">
                              {JSON.stringify(event.detail, null, 2)}
                            </pre>
                          ) : null}
                        </td>
                        <td className="admin-cell-request">
                          {requestId ? <code>{requestId}</code> : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {query.data.items.length === 0 ? (
              <p className="bv-muted">
                No hay eventos con estos filtros. El registro solo crece con la actividad real.
              </p>
            ) : null}

            <Pagination
              total={query.data.total}
              limit={query.data.limit}
              offset={query.data.offset}
              onChange={setOffset}
              noun="eventos"
              disabled={query.isFetching}
            />
          </>
        ) : null}
      </section>
    </div>
  );
}
