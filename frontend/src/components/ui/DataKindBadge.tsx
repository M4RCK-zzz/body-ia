import { DATA_KIND_META, type DataKind } from '@/types/dataKind'

export function DataKindBadge({ kind }: { kind: DataKind }) {
  const { label, description } = DATA_KIND_META[kind]
  return (
    <span className={`kind-badge kind-badge--${kind}`} title={description}>
      {label}
    </span>
  )
}