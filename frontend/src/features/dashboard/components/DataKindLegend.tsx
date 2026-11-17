import { Card } from '@/components/ui/Card'
import { DataKindBadge } from '@/components/ui/DataKindBadge'
import { DATA_KIND_META, type DataKind } from '@/types/dataKind'

const KINDS = Object.keys(DATA_KIND_META) as DataKind[]

export function DataKindLegend() {
  return (
    <Card title="Cómo leer los datos">
      <ul className="legend">
        {KINDS.map((kind) => (
          <li key={kind}>
            <DataKindBadge kind={kind} />
            <span className="muted">{DATA_KIND_META[kind].description}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}