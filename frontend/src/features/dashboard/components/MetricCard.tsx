import { Card } from '@/components/ui/Card'

interface MetricCardProps {
  label: string
  value: number | null
  note: string
}

export function MetricCard({ label, value, note }: MetricCardProps) {
  return (
    <Card>
      <div className="metric__label">{label}</div>
      <div className="metric__value">{value ?? '—'}</div>
      <div className="metric__note">{note}</div>
    </Card>
  )
}