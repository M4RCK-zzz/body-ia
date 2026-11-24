import { useGLTF } from '@react-three/drei'

/**
 * Resolución de rutas de los activos 3D.
 *
 * El manifiesto guarda rutas relativas a `public/` (`models/skin.glb`) para que
 * el paquete funcione igual en la raíz o bajo un subdirectorio (GitHub Pages,
 * despliegue con `BASE_URL`). Nunca se resuelven contra la URL de la página,
 * porque `/viewer/:profileId` rompería la ruta relativa.
 */
export function anatomyAssetUrl(file: string, baseUrl = import.meta.env.BASE_URL): string {
  return `${baseUrl}${file.replace(/^\/+/, '')}`
}

/**
 * Precarga una capa cuando el usuario la enciende (streaming guiado): así el
 * `Suspense` de esa capa encuentra el GLB ya en la caché de three.
 */
export function preloadLayer(file: string): void {
  useGLTF.preload(anatomyAssetUrl(file))
}
