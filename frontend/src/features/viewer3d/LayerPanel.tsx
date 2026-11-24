import type { AnatomyLayerId, AnatomyLayerManifest } from '@/types/viewer3d'

export interface LayerPanelEntry {
  manifest: AnatomyLayerManifest
  visible: boolean
  opacity: number
  mounted: boolean
  ready: boolean
  error: string | null
}

interface LayerPanelProps {
  layers: LayerPanelEntry[]
  wireframe: boolean
  onToggleLayer: (id: AnatomyLayerId, visible: boolean) => void
  onOpacityChange: (id: AnatomyLayerId, opacity: number) => void
  onWireframeChange: (wireframe: boolean) => void
  onIsolate: (id: AnatomyLayerId) => void
  onShowAll: () => void
  onShowOnlySkin: () => void
}

function LayerStatus({ entry }: { entry: LayerPanelEntry }) {
  if (entry.error) return <span className="viewer3d__layer-state viewer3d__layer-state--error">Error</span>
  if (!entry.mounted) return <span className="viewer3d__layer-state">Sin cargar</span>
  if (!entry.ready) return <span className="viewer3d__layer-state">Cargando…</span>
  return <span className="viewer3d__layer-state viewer3d__layer-state--ok">Listo</span>
}

export function LayerPanel({
  layers,
  wireframe,
  onToggleLayer,
  onOpacityChange,
  onWireframeChange,
  onIsolate,
  onShowAll,
  onShowOnlySkin,
}: LayerPanelProps) {
  const sorted = [...layers].sort((a, b) => a.manifest.order - b.manifest.order)

  return (
    <section className="viewer3d__panel" aria-label="Capas anatómicas">
      <header className="viewer3d__panel-header">
        <h2>Capas</h2>
        <div className="viewer3d__panel-actions">
          <button type="button" className="bv-btn bv-btn--small" onClick={onShowAll}>
            Todo
          </button>
          <button type="button" className="bv-btn bv-btn--small" onClick={onShowOnlySkin}>
            Solo piel
          </button>
        </div>
      </header>

      <div className="viewer3d__global-toggle">
        <label htmlFor="viewer3d-wireframe">
          <input
            id="viewer3d-wireframe"
            type="checkbox"
            checked={wireframe}
            onChange={(event) => onWireframeChange(event.target.checked)}
          />{' '}
          Wireframe real (malla de todas las capas)
        </label>
        <p className="viewer3d__hint">
          Alterna la geometría real entre superficie y aristas. No es un contorno simulado: cambia
          el modo de render de los triángulos cargados.
        </p>
      </div>

      <ul className="viewer3d__layers">
        {sorted.map((entry) => {
          const { manifest } = entry
          const inputId = `viewer3d-layer-${manifest.id}`
          return (
            <li key={manifest.id} className={`viewer3d__layer${entry.visible ? ' is-visible' : ''}`}>
              <div className="viewer3d__layer-row">
                <label htmlFor={inputId} className="viewer3d__layer-label">
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={entry.visible}
                    onChange={(event) => onToggleLayer(manifest.id, event.target.checked)}
                  />
                  <span
                    className="viewer3d__swatch"
                    style={{ background: manifest.color }}
                    aria-hidden="true"
                  />
                  <span className="viewer3d__layer-name">{manifest.label}</span>
                </label>
                <LayerStatus entry={entry} />
              </div>

              <div className="viewer3d__layer-controls">
                <label htmlFor={`${inputId}-opacity`} className="viewer3d__sr-only">
                  Opacidad de {manifest.label}
                </label>
                <input
                  id={`${inputId}-opacity`}
                  type="range"
                  min={0.05}
                  max={1}
                  step={0.05}
                  value={entry.opacity}
                  disabled={!entry.visible}
                  onChange={(event) => onOpacityChange(manifest.id, Number(event.target.value))}
                />
                <span className="viewer3d__opacity-value">{Math.round(entry.opacity * 100)}%</span>
                <button
                  type="button"
                  className="viewer3d__link-button"
                  onClick={() => onIsolate(manifest.id)}
                  disabled={!entry.ready}
                >
                  Aislar
                </button>
              </div>

              <p className="viewer3d__layer-meta">
                {manifest.meshes.toLocaleString('es-ES')} piezas ·{' '}
                {manifest.triangles.toLocaleString('es-ES')} triángulos ·{' '}
                {(manifest.bytes / 1024 / 1024).toFixed(2)} MB
              </p>
              {entry.error ? (
                <p className="viewer3d__layer-error" role="alert">
                  {entry.error}
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
