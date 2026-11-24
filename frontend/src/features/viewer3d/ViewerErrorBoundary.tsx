import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Nombre de la capa, para el log. */
  label: string
  /**
   * El fallback debe ser `null` cuando el boundary vive dentro del `<Canvas>`:
   * react-three-fiber interpreta los elementos JSX como objetos 3D, así que un
   * `<div>` ahí rompería el render. El error se comunica al padre por `onError`,
   * que lo muestra en el panel de capas (fuera del canvas).
   */
  renderFallback?: () => ReactNode
  onError?: (message: string) => void
}

interface State {
  message: string | null
}

/**
 * Aísla fallos de carga/render de una capa 3D. Si un GLB corrupto o un fallo del
 * driver WebGL rompe una capa, el resto del visor sigue funcionando.
 */
export class ViewerErrorBoundary extends Component<Props, State> {
  state: State = { message: null }

  static getDerivedStateFromError(error: unknown): State {
    return { message: error instanceof Error ? error.message : 'Error desconocido' }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[visor 3D] ${this.props.label}:`, error, info.componentStack)
    this.props.onError?.(error.message)
  }

  render() {
    if (this.state.message !== null) {
      return this.props.renderFallback ? this.props.renderFallback() : null
    }
    return this.props.children
  }
}
