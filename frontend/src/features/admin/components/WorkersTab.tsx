import { formatDateTime } from "@/features/measurements/format";
import { WORKER_LABELS, WORKER_ORDER, type WorkerHealth } from "@/types/admin";
import { humanAge, orderedWorkers } from "../format";
import { useWorkersHealth } from "../hooks/useAdmin";

export function WorkerStatusBadge({ worker }: { worker: WorkerHealth }) {
  if (!worker.continuous) {
    return (
      <span className="badge badge--neutral" title="Worker one-shot: se ejecuta bajo demanda">
        Bajo demanda
      </span>
    );
  }
  if (!worker.alive) {
    return (
      <span className="badge badge--error" title="Sin latidos dentro del umbral">
        Sin latido
      </span>
    );
  }
  if (worker.last_error) {
    return (
      <span className="badge badge--warn" title={worker.last_error}>
        Vivo con error
      </span>
    );
  }
  return <span className="badge badge--ok">Vivo</span>;
}

export function WorkersTab() {
  const query = useWorkersHealth();
  const hasContinuous = Boolean(query.data?.workers.some((worker) => worker.continuous));

  return (
    <div className="admin-tab">
      <section className="bv-panel" aria-labelledby="admin-workers-title">
        <h2 id="admin-workers-title">Estado de los workers</h2>
        <p className="bv-muted">
          Latidos registrados en base de datos. Un worker <strong>continuo</strong> se considera vivo
          si ha latido dentro del umbral configurado (<code>WORKER_STALE_SECONDS</code>); la
          retención es <strong>bajo demanda</strong> y su último latido solo se informa. Esta vista se
          refresca sola cada 30 s.
        </p>

        {query.isLoading ? <p className="bv-muted">Consultando latidos…</p> : null}
        {query.error ? (
          <p className="bv-alert bv-alert--error" role="alert">
            {query.error.message}
          </p>
        ) : null}

        {query.data ? (
          <>
            <p className="admin-workers__summary">
              <span
                className={`badge ${
                  query.data.status === "ok"
                    ? "badge--ok"
                    : query.data.status === "degraded"
                      ? "badge--warn"
                      : "badge--neutral"
                }`}
              >
                {query.data.status === "ok"
                  ? "Todo en orden"
                  : query.data.status === "degraded"
                    ? "Atención requerida"
                    : "Sin datos"}
              </span>
              <span className="bv-muted">
                Umbral {Math.round(query.data.stale_after_seconds / 60)} min · actualizado{" "}
                {formatDateTime(query.data.timestamp)}
              </span>
            </p>

            {query.data.workers.length === 0 ? (
              <p className="bv-alert bv-alert--warn">
                Ningún worker ha registrado latidos todavía. Los workers aparecen aquí en cuanto
                arrancan (perfil <code>docker compose ... up -d</code>).
              </p>
            ) : (
              <div className="admin-table-scroll">
                <table className="bv-table">
                  <caption className="bv-sr-only">
                    Workers: estado, último latido, iteraciones y último error
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Worker</th>
                      <th scope="col">Estado</th>
                      <th scope="col">Último latido</th>
                      <th scope="col">Iteraciones</th>
                      <th scope="col">Último error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orderedWorkers(query.data.workers).map((worker) => (
                      <tr key={worker.name}>
                        <th scope="row">
                          {WORKER_LABELS[worker.name] ?? worker.name}
                          <code className="admin-worker-name">{worker.name}</code>
                        </th>
                        <td>
                          <WorkerStatusBadge worker={worker} />
                          <small className="bv-muted">v{worker.version}</small>
                        </td>
                        <td>
                          {formatDateTime(worker.last_seen_at)}
                          <small className="bv-muted"> {humanAge(worker.age_seconds)}</small>
                        </td>
                        <td>{worker.iterations}</td>
                        <td className="admin-cell-summary">
                          {worker.last_error ? (
                            <span className="bv-inline-error">{worker.last_error}</span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {hasContinuous &&
            orderedWorkers(query.data.workers).length < WORKER_ORDER.length ? (
              <p className="bv-muted">
                Faltan latidos de algún worker: puede que no esté desplegado en esta instalación (el
                de retención corre bajo demanda, perfil <code>ops</code>).
              </p>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}
