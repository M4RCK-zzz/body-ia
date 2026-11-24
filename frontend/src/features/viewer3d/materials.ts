import * as THREE from 'three'

import type { AnatomyLayerId } from '@/types/viewer3d'

/**
 * Materiales del visor 3D.
 *
 * Los GLB del atlas no traen materiales ni UVs: solo POSITION + NORMAL (+ COLOR_0
 * en algunas mallas de piel). Por eso el color se decide aquí, por capa y por
 * material anatómico declarado en `extras.zmat` (el atlas guarda `zmat` con el
 * nombre del material de Blender: Bone, Cartilage, Teeth, Lung, Tendon…).
 *
 * Paleta adaptada al tema oscuro BODYVISION (la original del atlas está pensada
 * para fondo claro).
 */
interface LayerStyle {
  color: string
  roughness: number
  metalness: number
  clearcoat: number
  clearcoatRoughness: number
  /** Opacidad inicial de la capa al encenderse. */
  initialOpacity: number
  /** Render por ambas caras: las mallas no son cerradas (vísceras, vasos). */
  doubleSide: boolean
}

export const LAYER_STYLE: Record<AnatomyLayerId, LayerStyle> = {
  skin: {
    color: '#d9a483',
    roughness: 0.62,
    metalness: 0,
    clearcoat: 0.18,
    clearcoatRoughness: 0.55,
    initialOpacity: 1,
    doubleSide: true,
  },
  skeleton: {
    color: '#e6dfcb',
    roughness: 0.5,
    metalness: 0,
    clearcoat: 0.25,
    clearcoatRoughness: 0.4,
    initialOpacity: 1,
    doubleSide: true,
  },
  muscles: {
    color: '#b6463f',
    roughness: 0.72,
    metalness: 0,
    clearcoat: 0.12,
    clearcoatRoughness: 0.7,
    initialOpacity: 1,
    doubleSide: true,
  },
  organs: {
    color: '#a55b4e',
    roughness: 0.66,
    metalness: 0,
    clearcoat: 0.1,
    clearcoatRoughness: 0.6,
    initialOpacity: 1,
    doubleSide: true,
  },
  arteries: {
    color: '#d1342c',
    roughness: 0.48,
    metalness: 0,
    clearcoat: 0.2,
    clearcoatRoughness: 0.5,
    initialOpacity: 1,
    doubleSide: true,
  },
  veins: {
    color: '#3f74d6',
    roughness: 0.48,
    metalness: 0,
    clearcoat: 0.2,
    clearcoatRoughness: 0.5,
    initialOpacity: 1,
    doubleSide: true,
  },
  nerves: {
    color: '#e0b13a',
    roughness: 0.55,
    metalness: 0,
    clearcoat: 0.15,
    clearcoatRoughness: 0.6,
    initialOpacity: 1,
    doubleSide: true,
  },
}

/** Color por material anatómico (extras.zmat) cuando queremos más detalle. */
const MATERIAL_OVERRIDES: Partial<Record<AnatomyLayerId, Record<string, string>>> = {
  skeleton: { Tooth: '#f7f2e4', Teeth: '#f7f2e4', Cartilage: '#bcdde3' },
  muscles: { Tendon: '#e6dcc6' },
  organs: {
    Lung: '#e08f92',
    Heart: '#a8303a',
    Intestine: '#dd9581',
    Gland: '#dcae66',
    Mucosa: '#d9848c',
    Bronchi: '#dde4e6',
    Gallbladder: '#5b8a44',
    Eye: '#e6e0d8',
    Cornea: '#cfe8ff',
    Iris: '#4f7aa6',
    Cartilage: '#cfe3e8',
    Lymph: '#8fc97a',
  },
  arteries: { 'Pulmonary artery': '#7f7fd6' },
  veins: { 'Pulmonary vein': '#c76a8e' },
  skin: {
    Black: '#2b1d18',
    Nail: '#efc6b8',
    Garment: '#2c3a5a',
    Eye: '#e6e0d8',
    Iris: '#5b4030',
    Cornea: '#cfe8ff',
  },
}

/** Reglas por nombre de estructura (el atlas solo declara zmat genérico en vísceras). */
const ORGAN_NAME_RULES: [RegExp, string][] = [
  [/liver|caudate lobe|quadrate lobe/i, '#7b2d2a'],
  [/gallbladder/i, '#5b8a44'],
  [/spleen/i, '#6d2a3c'],
  [/heart|ventricle|atrium|auricle|myocard|septum|leaflet|cusp/i, '#a8303a'],
  [/lung/i, '#e08f92'],
  [/stomach|duodenum|jejunum|ileum|intestin|colon|caecum|cecum|appendix|rectum|oesophag|esophag/i, '#dd9581'],
  [/pancrea/i, '#dcae66'],
  [/thyroid|parathyroid|suprarenal|adrenal|hypophysis|pituitary|pineal|thymus/i, '#d9a55e'],
  [/bladder/i, '#d9b38c'],
  [/tongue/i, '#cf6f74'],
  [/brain|frontal lobe|parietal lobe|temporal lobe|occipital lobe|limbic lobe|insula|cerebellum/i, '#d9a9a2'],
]

export interface MeshMaterialInfo {
  layer: AnatomyLayerId
  /** Nombre del material de Blender (`extras.zmat`). */
  materialName: string
  /** Nombre anatómico limpio (`extras.zname`). */
  structureName: string
}

export function colorForMesh({ layer, materialName, structureName }: MeshMaterialInfo): string {
  const override = MATERIAL_OVERRIDES[layer]?.[materialName]
  if (override) return override

  if (layer === 'organs') {
    for (const [rule, color] of ORGAN_NAME_RULES) {
      if (rule.test(structureName)) return color
    }
  }
  if (layer === 'muscles' && /tendon/i.test(materialName)) return '#e6dcc6'
  if (layer === 'skin' && materialName === 'Black') return '#2b1d18'

  return LAYER_STYLE[layer].color
}

/** Material base de una capa. La opacidad se actualiza en caliente desde `LayerPanel`. */
export function createLayerMaterial(layer: AnatomyLayerId, color: string): THREE.MeshPhysicalMaterial {
  const style = LAYER_STYLE[layer]
  return new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(color),
    roughness: style.roughness,
    metalness: style.metalness,
    clearcoat: style.clearcoat,
    clearcoatRoughness: style.clearcoatRoughness,
    side: style.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    transparent: style.initialOpacity < 1,
    opacity: style.initialOpacity,
    depthWrite: style.initialOpacity >= 1,
  })
}

/** Aplica visibilidad/opacidad a un material ya creado. */
export function applyOpacity(material: THREE.Material, opacity: number): void {
  const target = Math.min(1, Math.max(0, opacity))
  const material_ = material as THREE.MeshPhysicalMaterial
  material_.opacity = target
  material_.transparent = target < 1
  material_.depthWrite = target >= 1
  material_.needsUpdate = true
}
