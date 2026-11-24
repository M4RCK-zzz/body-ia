/**
 * Tipos del visor 3D (Fase 6).
 *
 * El visor pinta un atlas anatómico genérico de referencia. NO usa datos del
 * expediente ni geometría del paciente: todo lo mostrado es
 * `approximate_reconstruction` (ver ADR-007).
 */

export type AnatomyLayerId =
  | 'skin'
  | 'skeleton'
  | 'muscles'
  | 'organs'
  | 'arteries'
  | 'veins'
  | 'nerves'

export interface AnatomyLayerManifest {
  id: AnatomyLayerId
  label: string
  /** Ruta relativa a la raíz de `public/`, p. ej. `models/skin.glb`. */
  file: string
  order: number
  color: string
  meshes: number
  triangles: number
  bytes: number
  sha256: string
  bbox: {
    min: [number, number, number]
    max: [number, number, number]
    size: [number, number, number]
  }
  /** Nodos CC BY-NC retirados del GLB publicado (riñón de Lissie Cowley). */
  pruned_nc_nodes: string[]
  license: string
}

export interface AnatomyManifest {
  schema_version: number
  kind: 'approximate_reconstruction'
  generated_at: string
  source: {
    repository: string
    commit: string
    atlas: string
    upstream: string
  }
  licenses: {
    model: string
    upstream_model: string
    removed: string[]
    note: string
  }
  units: string
  up_axis: string
  origin: string
  draco: { required: boolean; decoder_path: string; encoder: string }
  totals: { meshes: number; triangles: number; bytes: number }
  layers: AnatomyLayerManifest[]
}

/** Estado de una capa dentro del visor. */
export interface AnatomyLayerState {
  visible: boolean
  opacity: number
}

export type ViewerCameraPreset = 'frontal' | 'dorsal' | 'lateral' | 'superior'

export const VIEWER_CAMERA_PRESETS: Record<
  ViewerCameraPreset,
  { label: string; position: [number, number, number] }
> = {
  frontal: { label: 'Frontal', position: [0, 0.9, 2.9] },
  dorsal: { label: 'Dorsal', position: [0, 0.9, -2.9] },
  lateral: { label: 'Lateral', position: [2.9, 0.9, 0] },
  superior: { label: 'Superior', position: [0.01, 3.2, 0.4] },
}

export const VIEWER_TARGET: [number, number, number] = [0, 0.85, 0]
