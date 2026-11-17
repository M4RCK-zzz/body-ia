import { Card } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { API_BASE_URL } from '@/services/api/config'
import { useHealth } from '../hooks/useHealth'

export function ApiStatusCard() {
  const { data, isPending, isError } = useHealth()

  return (
    <Card title="Estado del sistema">
      {isPending && <p className="muted">Comprobando API…</p>}

      {isError && (
        <>
          <StatusBadge variant="error">API no disponible</StatusBadge>
          <p className="muted">
            No hay respuesta de <code>{API_BASE_URL}</code>. Verifica que el backend esté en
            ejecución y que CORS permita este origen.
          </p>
        </>
      )}

      {data && (
        <>
          <div className="status-row">
            <StatusBadge variant={data.status === 'ok' ? 'ok' : 'warn'}>
              {data.status === 'ok' ? 'Operativo' : 'Degradado'}
            </StatusBadge>
            <StatusBadge variant={data.database === 'up' ? 'ok' : 'error'}>
              {data.database === 'up' ? 'Base de datos: conectada' : 'Base de datos: sin conexión'}
            </StatusBadge>
          </div>
          <dl className="kv">
            <dt>Servicio</dt>
            <dd>{data.service}</dd>
            <dt>Versión</dt>
            <dd>{data.version}</dd>
            <dt>Entorno</dt>
            <dd>{data.environment}</dd>
          </dl>
        </>
      )}
    </Card>
  )
}