/**
 * Capas del atlas anatómico y sus ausencias declaradas (Fase 6, revisado en la fase de ajustes).
 *
 * El atlas Z-Anatomy / BodyParts3D que publicamos trae **7 sistemas** y **ninguno**
 * es tejido adiposo: se verificó `frontend/public/models/` (solo `skin`, `skeleton`,
 * `muscles`, `organs`, `arteries`, `veins`, `nerves`) y el manifiesto
 * (`public/models/manifest.json`, 7 entradas).
 *
 * Regla del proyecto: **nunca** se inventa ni se genera una malla sintética para
 * "rellenar" una capa anatómica. Si no hay geometría con procedencia y licencia
 * verificables, no se dibuja: se dice por qué. Esta lista es la única fuente de
 * esas ausencias, para que el panel y las pruebas no se desincronicen.
 */

export interface MissingAnatomyLayer {
  id: 'adipose'
  label: string
  /** Color de referencia para cuando exista el activo. */
  color: string
  reason: string
  /** Qué haría falta para incorporarla, paso a paso. */
  howToAdd: string[]
}

export const MISSING_LAYERS: MissingAnatomyLayer[] = [
  {
    id: 'adipose',
    label: 'Grasa / tejido adiposo',
    color: '#f6d07a',
    reason:
      'El atlas anatómico base incluye 7 sistemas (piel, esqueleto, músculos, órganos, arterias, venas y nervios) y no trae malla de tejido adiposo.',
    howToAdd: [
      'Consigue un GLB de tejido adiposo con procedencia y licencia compatibles (CC BY-SA 4.0 o equivalente) y anótala en ATTRIBUTION.md.',
      'Añade la entrada en frontend/public/models/manifest.json con id "adipose", label "Grasa / tejido adiposo", file, order, color, meshes, triangles, bytes, sha256, bbox y license.',
      'Añade "adipose" a AnatomyLayerId en src/types/viewer3d.ts: el panel de capas, el control de opacidad y el botón Aislar se generan a partir del manifiesto, sin cambios de código adicionales.',
      'Quita la entrada de MISSING_LAYERS en este archivo y actualiza el total de sistemas en la ficha de procedencia.',
    ],
  },
]

/** Número de sistemas anatómicos que sí trae el atlas publicado. */
export const ATLAS_LAYER_COUNT = 7
