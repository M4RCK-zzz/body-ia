import { useState } from 'react'

import type { AnatomyManifest } from '@/types/viewer3d'

interface ProvenanceSheetProps {
  manifest: AnatomyManifest
}

const SOURCE_URL = 'https://github.com/SeemaBansal1/3d-human-body-anatomy'
const LICENSE_URL = 'https://creativecommons.org/licenses/by-sa/4.0/legalcode.es'

/**
 * Ficha de procedencia: obligatoria por la licencia CC BY-SA 4.0 del atlas
 * (atribución + ShareAlike) y por transparencia de producto (ADR-007).
 */
export function ProvenanceSheet({ manifest }: ProvenanceSheetProps) {
  const [open, setOpen] = useState(false)
  const pruned = manifest.layers.flatMap((layer) => layer.pruned_nc_nodes)

  return (
    <section className="viewer3d__provenance" aria-label="Procedencia y licencias del modelo">
      <div className="viewer3d__provenance-head">
        <h2>Procedencia del modelo</h2>
        <button
          type="button"
          className="bv-btn bv-btn--small"
          aria-expanded={open}
          aria-controls="viewer3d-provenance-body"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Ocultar detalle' : 'Ver licencias y atribución'}
        </button>
      </div>

      <p className="viewer3d__provenance-summary">
        Atlas genérico <strong>Z-Anatomy</strong> (geometría <strong>BodyParts3D</strong>, DBCLS)
        adaptado a BODYVISION. Distribuido bajo <strong>CC BY-SA 4.0</strong>: se exige atribución y
        compartir igual cualquier obra derivada.
      </p>

      <div id="viewer3d-provenance-body" hidden={!open} className="viewer3d__provenance-body">
        <dl className="viewer3d__kv">
          <dt>Obra de referencia</dt>
          <dd>
            <a href={SOURCE_URL} target="_blank" rel="noreferrer noopener">
              3d-human-body-anatomy
            </a>{' '}
            (commit <code>{manifest.source.commit}</code>) sobre el atlas {manifest.source.atlas}.
          </dd>
          <dt>Geometría de base</dt>
          <dd>{manifest.source.upstream}</dd>
          <dt>Licencia del modelo</dt>
          <dd>
            {manifest.licenses.model} ·{' '}
            <a href={LICENSE_URL} target="_blank" rel="noreferrer noopener">
              texto de la licencia
            </a>
          </dd>
          <dt>Licencia upstream</dt>
          <dd>{manifest.licenses.upstream_model}</dd>
          <dt>Componentes retirados</dt>
          <dd>
            Riñón (Lissie Cowley, CC BY-NC 4.0) y oído interno (Dundee, CC BY-NC-SA 4.0). El riñón
            se eliminó de la capa de órganos antes de publicar
            {pruned.length > 0 ? (
              <>
                {' '}
                (<code>{pruned.length}</code> mallas: {pruned.join(', ')})
              </>
            ) : null}
            ; el oído interno nunca se exportó a los GLB.
          </dd>
          <dt>Volumen</dt>
          <dd>
            {manifest.totals.meshes.toLocaleString('es-ES')} piezas ·{' '}
            {manifest.totals.triangles.toLocaleString('es-ES')} triángulos ·{' '}
            {(manifest.totals.bytes / 1024 / 1024).toFixed(2)} MB
          </dd>
          <dt>Unidades y ejes</dt>
          <dd>
            {manifest.units}, eje {manifest.up_axis}, origen en {manifest.origin}
          </dd>
          <dt>Ficha completa</dt>
          <dd>
            <code>frontend/public/models/ATTRIBUTION.md</code> · ver ADR-007 en{' '}
            <code>docs/ARQUITECTURA.md</code>
          </dd>
        </dl>

        <ul className="viewer3d__layer-licenses">
          {manifest.layers.map((layer) => (
            <li key={layer.id}>
              <strong>{layer.label}</strong>: {layer.license} · sha256{' '}
              <code>{layer.sha256.slice(0, 16)}</code>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
