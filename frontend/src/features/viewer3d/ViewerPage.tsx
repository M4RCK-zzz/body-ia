import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import '@/components/ui/forms.css'
import { DataKindBadge } from '@/components/ui/DataKindBadge'
import { useProfile } from '@/features/profiles/hooks/useProfiles'
import {
  VIEWER_CAMERA_PRESETS,
  type AnatomyLayerId,
  type AnatomyManifest,
  type ViewerCameraPreset,
} from '@/types/viewer3d'
import { BodyCanvas, type ViewerLayerRuntime } from './BodyCanvas'
import { LayerPanel, type LayerPanelEntry } from './LayerPanel'
import { ProvenanceSheet } from './ProvenanceSheet'
import { preloadLayer } from './assets'
import { useAnatomyManifest } from './hooks/useAnatomyManifest'
import './viewer3d.css'

/** Solo se descargan estas capas al entrar; el resto se pide al encenderlas. */
const BOOT_LAYERS: AnatomyLayerId[] = ['skeleton']

const MOBILE_QUERY = '(max-width: 900px), (pointer: coarse)'

function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(MOBILE_QUERY).matches,
  )

  useEffect(() => {
    const query = window.matchMedia(MOBILE_QUERY)
    const onChange = (event: MediaQueryListEvent) => setMobile(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return mobile
}

function initialVisibility(id: AnatomyLayerId): boolean {
  return BOOT_LAYERS.includes(id)
}

export function ViewerPage() {
  const { profileId } = useParams<{ profileId: string }>()
  const manifestQuery = useAnatomyManifest<AnatomyManifest>()
  const mobile = useIsMobile()
  const profile = useProfile(profileId ?? '')

  const [layerState, setLayerState] = useState<
    Record<string, { visible: boolean; opacity: number; mounted: boolean }>
  >({})
  const [readyCounts, setReadyCounts] = useState<Partial<Record<AnatomyLayerId, number>>>({})
  const [layerErrors, setLayerErrors] = useState<Partial<Record<AnatomyLayerId, string>>>({})
  const [wireframe, setWireframe] = useState(false)
  const [autoRotate, setAutoRotate] = useState(false)
  const [preset, setPreset] = useState<ViewerCameraPreset>('frontal')
  const [contextLost, setContextLost] = useState(false)
  const [canvasKey, setCanvasKey] = useState(0)

  const manifest = manifestQuery.data

  // Estado inicial de capas cuando llega el manifiesto.
  useEffect(() => {
    if (!manifest) return
    setLayerState((current) => {
      const next: typeof current = { ...current }
      for (const layer of manifest.layers) {
        if (next[layer.id]) continue
        next[layer.id] = {
          visible: initialVisibility(layer.id),
          opacity: 1,
          mounted: initialVisibility(layer.id),
        }
      }
      return next
    })
  }, [manifest])

  const layers: ViewerLayerRuntime[] = useMemo(() => {
    if (!manifest) return []
    return manifest.layers.map((layer) => {
      const state = layerState[layer.id]
      return {
        manifest: layer,
        visible: state?.visible ?? false,
        opacity: state?.opacity ?? 1,
        mounted: state?.mounted ?? false,
      }
    })
  }, [manifest, layerState])

  const panelEntries: LayerPanelEntry[] = useMemo(
    () =>
      layers.map((runtime) => ({
        manifest: runtime.manifest,
        visible: runtime.visible,
        opacity: runtime.opacity,
        mounted: runtime.mounted,
        ready: readyCounts[runtime.manifest.id] !== undefined,
        error: layerErrors[runtime.manifest.id] ?? null,
      })),
    [layers, readyCounts, layerErrors],
  )

  const toggleLayer = useCallback(
    (id: AnatomyLayerId, visible: boolean) => {
      setLayerState((current) => ({
        ...current,
        [id]: {
          visible,
          opacity: current[id]?.opacity ?? 1,
          // Streaming guiado: la primera vez que se enciende, se descarga.
          mounted: visible ? true : (current[id]?.mounted ?? false),
        },
      }))
      if (visible) {
        const layer = manifest?.layers.find((item) => item.id === id)
        if (layer) preloadLayer(layer.file)
        setLayerErrors((current) => ({ ...current, [id]: undefined }))
      }
    },
    [manifest],
  )

  const changeOpacity = useCallback((id: AnatomyLayerId, opacity: number) => {
    setLayerState((current) => ({
      ...current,
      [id]: {
        visible: current[id]?.visible ?? true,
        opacity,
        mounted: current[id]?.mounted ?? false,
      },
    }))
  }, [])

  const isolateLayer = useCallback((id: AnatomyLayerId) => {
    setLayerState((current) => {
      const next: typeof current = {}
      for (const [key, value] of Object.entries(current)) {
        next[key] = { ...value, visible: key === id, mounted: value.mounted || key === id }
      }
      return next
    })
    setLayerErrors((current) => ({ ...current, [id]: undefined }))
  }, [])

  const showAll = useCallback(() => {
    if (!manifest) return
    setLayerState((current) => {
      const next: typeof current = {}
      for (const layer of manifest.layers) {
        const state = current[layer.id]
        next[layer.id] = { visible: true, opacity: state?.opacity ?? 1, mounted: true }
      }
      return next
    })
    setLayerErrors({})
  }, [manifest])

  const showOnlySkin = useCallback(() => {
    setLayerState((current) => {
      const next: typeof current = {}
      for (const [key, value] of Object.entries(current)) {
        next[key] = { ...value, visible: key === 'skin', mounted: value.mounted || key === 'skin' }
      }
      return next
    })
  }, [])

  const handleLayerReady = useCallback((id: AnatomyLayerId, meshes: number) => {
    setReadyCounts((current) => (current[id] === meshes ? current : { ...current, [id]: meshes }))
  }, [])

  const handleLayerFailed = useCallback((id: AnatomyLayerId, message: string) => {
    setLayerErrors((current) => ({ ...current, [id]: message }))
  }, [])

  const handleContextLost = useCallback(() => {
    setContextLost(true)
  }, [])

  const reloadCanvas = useCallback(() => {
    setContextLost(false)
    setReadyCounts({})
    setLayerErrors({})
    setCanvasKey((key) => key + 1)
  }, [])

  const loadedLayers = Object.keys(readyCounts).length
  const failedLayers = Object.values(layerErrors).filter(Boolean).length
  const totalLayers = manifest?.layers.length ?? 7

  return (
    <div className="bv-page viewer3d">
      <header className="bv-page__header">
        <div>
          <Link to={profileId ? `/expedientes/${profileId}` : '/'} className="bv-muted">
            ← {profileId ? 'Volver al expediente' : 'Dashboard'}
          </Link>
          <h1>
            Visor 3D anatómico <DataKindBadge kind="approximate_reconstruction" />
          </h1>
          <p className="bv-muted">
            Atlas genérico de referencia{profileId ? ' abierto desde el expediente' : ''}. No usa
            imágenes, medidas ni geometría del paciente.
          </p>
        </div>
        <div className="viewer3d__header-actions">
          <button
            type="button"
            className={`bv-btn${autoRotate ? ' bv-btn--primary' : ''}`}
            aria-pressed={autoRotate}
            onClick={() => setAutoRotate((value) => !value)}
          >
            {autoRotate ? 'Detener rotación' : 'Rotación automática'}
          </button>
        </div>
      </header>

      {profileId ? (
        <p className="bv-alert bv-alert--info">
          Visor abierto para{' '}
          <strong>
            {profile.isLoading
              ? '…'
              : profile.data
                ? profile.data.display_code
                : 'el expediente solicitado'}
          </strong>
          . La geometría mostrada es la misma para todos los expedientes: <strong>no</strong> se
          superpone con landmarks ni medidas de este paciente.
        </p>
      ) : null}

      <p className="bv-alert bv-alert--warn" role="note">
        <strong>RECONSTRUCCIÓN APROXIMADA.</strong> Modelo anatómico genérico con fines educativos y
        de visualización. <strong>No es un gemelo digital</strong> del paciente, no se ha generado a
        partir de sus imágenes y <strong>no sirve para diagnóstico, medición ni decisión clínica</strong>.
      </p>

      {manifestQuery.loading ? <p className="bv-muted">Cargando manifiesto 3D…</p> : null}
      {manifestQuery.error ? (
        <p className="bv-alert bv-alert--error">{manifestQuery.error}</p>
      ) : null}

      {manifest ? (
        <div className="viewer3d__layout">
          <div className="viewer3d__stage">
            <div className="viewer3d__stage-bar">
              <div className="bv-tabs" role="group" aria-label="Vistas de cámara">
                {(Object.keys(VIEWER_CAMERA_PRESETS) as ViewerCameraPreset[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    className="bv-tab"
                    aria-pressed={preset === key}
                    onClick={() => setPreset(key)}
                  >
                    {VIEWER_CAMERA_PRESETS[key].label}
                  </button>
                ))}
              </div>
              <span className="viewer3d__progress" aria-live="polite">
                {loadedLayers}/{totalLayers} capas cargadas
                {failedLayers > 0 ? ` · ${failedLayers} con error` : ''}
              </span>
            </div>

            <div className="viewer3d__viewport">
              {contextLost ? (
                <div className="viewer3d__overlay" role="alert">
                  <p>
                    <strong>Se perdió el contexto WebGL.</strong> El navegador liberó la GPU
                    (pestaña en segundo plano, memoria insuficiente o driver reiniciado).
                  </p>
                  <button type="button" className="bv-btn bv-btn--primary" onClick={reloadCanvas}>
                    Reiniciar visor
                  </button>
                </div>
              ) : (
                <BodyCanvas
                  key={canvasKey}
                  layers={layers}
                  wireframe={wireframe}
                  autoRotate={autoRotate}
                  preset={preset}
                  lowPower={mobile}
                  onLayerReady={handleLayerReady}
                  onLayerFailed={handleLayerFailed}
                  onContextLost={handleContextLost}
                />
              )}
            </div>

            <p className="viewer3d__hint">
              Arrastra para orbitar · rueda o pinza para acercar · dos dedos para desplazar.
              {mobile ? ' Modo móvil: DPR limitado y sin sombras.' : ''}
            </p>
          </div>

          <div className="viewer3d__sidebar">
            <LayerPanel
              layers={panelEntries}
              wireframe={wireframe}
              onToggleLayer={toggleLayer}
              onOpacityChange={changeOpacity}
              onWireframeChange={setWireframe}
              onIsolate={isolateLayer}
              onShowAll={showAll}
              onShowOnlySkin={showOnlySkin}
            />
            <ProvenanceSheet manifest={manifest} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
