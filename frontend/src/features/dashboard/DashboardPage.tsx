import { ApiStatusCard } from './components/ApiStatusCard'
import { DataKindLegend } from './components/DataKindLegend'
import { MetricCard } from './components/MetricCard'

export function DashboardPage() {
  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p className="muted">
          Los indicadores se activarán con datos reales de la API a partir de la Fase 2.
        </p>
      </div>

      <div className="grid grid--kpi">
        <MetricCard label="Expedientes activos" value={null} note="Disponible en Fase 2" />
        <MetricCard label="Mediciones registradas" value={null} note="Disponible en Fase 2" />
        <MetricCard label="Análisis de pose" value={null} note="Disponible en Fase 5" />
      </div>

      <div className="grid grid--two">
        <ApiStatusCard />
        <DataKindLegend />
      </div>
    </>
  )
}