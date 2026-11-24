import { useEffect, useState } from 'react'

/**
 * Manifiesto de activos del visor 3D (`public/models/manifest.json`).
 *
 * Se carga en tiempo de ejecución (no en el bundle) para que el visor conozca
 * tamaño real, checksum y licencia de cada capa. Los archivos viven en `public/`,
 * de modo que se sirven como estáticos y nunca pasan por la API ni por el storage
 * privado del expediente.
 */
const MANIFEST_URL = `${import.meta.env.BASE_URL}models/manifest.json`

interface ManifestState<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export function useAnatomyManifest<T>(): ManifestState<T> {
  const [state, setState] = useState<ManifestState<T>>({ data: null, error: null, loading: true })

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    fetch(MANIFEST_URL, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`No se pudo cargar el manifiesto 3D (HTTP ${response.status}).`)
        }
        return (await response.json()) as T
      })
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false })
      })
      .catch((error: unknown) => {
        if (cancelled || (error instanceof DOMException && error.name === 'AbortError')) return
        setState({
          data: null,
          error: error instanceof Error ? error.message : 'Error desconocido al cargar el manifiesto 3D.',
          loading: false,
        })
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [])

  return state
}
