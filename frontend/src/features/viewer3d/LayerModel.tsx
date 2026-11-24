import { useEffect, useMemo } from 'react'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

import type { AnatomyLayerId, AnatomyLayerManifest } from '@/types/viewer3d'
import { anatomyAssetUrl } from './assets'
import { applyOpacity, colorForMesh, createLayerMaterial } from './materials'

// Decodificador Draco servido desde `public/draco/` (copiado del paquete three.js):
// sin CDN externo, sin peticiones a terceros y funciona offline.
useGLTF.setDecoderPath(`${import.meta.env.BASE_URL}draco/`)

interface LayerModelProps {
  layer: AnatomyLayerManifest
  visible: boolean
  opacity: number
  wireframe: boolean
  onReady: (layer: AnatomyLayerId, meshCount: number) => void
}

/** Etiqueta limpia: los nombres de Blender acaban en `.001`. */
function cleanName(name: string | undefined): string {
  return (name ?? '').replace(/\.\d{3}$/, '')
}

interface MeshExtras {
  zname?: string
  zmat?: string
}

/**
 * Una capa anatómica. Cada capa es su propio GLB: se descarga por separado para
 * que el visor pueda cargar en streaming y el usuario no espere 9 MB de golpe.
 *
 * `useGLTF` cachea el documento; aquí se clona el `scene` para poder tener
 * materiales propios (opacidad y wireframe independientes por capa).
 */
export function LayerModel({ layer, visible, opacity, wireframe, onReady }: LayerModelProps) {
  const url = anatomyAssetUrl(layer.file)
  const { scene } = useGLTF(url) as unknown as { scene: THREE.Group }

  const group = useMemo(() => {
    const clone = scene.clone(true)
    const materials = new Map<string, THREE.MeshPhysicalMaterial>()

    clone.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return
      const extras = (object.userData ?? {}) as MeshExtras
      const structureName = cleanName(extras.zname ?? object.name)
      const materialName = extras.zmat ?? ''

      const color = colorForMesh({ layer: layer.id, materialName, structureName })
      const key = `${color}|${materialName}`
      let material = materials.get(key)
      if (!material) {
        material = createLayerMaterial(layer.id, color)
        materials.set(key, material)
      }

      object.material = material
      object.userData = { layer: layer.id, structureName, materialName }
      object.castShadow = false
      object.receiveShadow = false
      object.frustumCulled = true
    })

    return clone
  }, [scene, layer.id])

  // Visibilidad, opacidad y wireframe se aplican en caliente: no remontan la capa.
  useEffect(() => {
    group.visible = visible
  }, [group, visible])

  useEffect(() => {
    const materials = new Set<THREE.Material>()
    group.traverse((object) => {
      if (object instanceof THREE.Mesh) materials.add(object.material as THREE.Material)
    })
    materials.forEach((material) => {
      applyOpacity(material, opacity)
      ;(material as THREE.MeshPhysicalMaterial).wireframe = wireframe
    })
  }, [group, opacity, wireframe])

  useEffect(() => {
    let count = 0
    group.traverse((object) => {
      if (object instanceof THREE.Mesh) count += 1
    })
    onReady(layer.id, count)
  }, [group, layer.id, onReady])

  // Liberar los materiales propios al desmontar; la geometría sigue en la caché de useGLTF.
  useEffect(() => {
    return () => {
      const disposed = new Set<THREE.Material>()
      group.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          const material = object.material as THREE.Material
          if (!disposed.has(material)) {
            disposed.add(material)
            material.dispose()
          }
        }
      })
    }
  }, [group])

  return <primitive object={group} name={`layer-${layer.id}`} />
}
