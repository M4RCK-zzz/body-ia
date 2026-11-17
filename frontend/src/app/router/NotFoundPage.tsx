import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section>
      <h1>Página no encontrada</h1>
      <p className="muted">La ruta solicitada no existe o aún no está disponible.</p>
      <Link to="/">Volver al dashboard</Link>
    </section>
  )
}