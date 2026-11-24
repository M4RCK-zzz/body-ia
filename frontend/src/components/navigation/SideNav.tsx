import { NavLink } from 'react-router-dom'

interface NavItem {
  label: string
  to?: string
  phase?: number
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/' },
  { label: 'Expedientes', to: '/expedientes' },
  { label: 'Captura corporal', to: '/capture' },
  { label: 'Análisis de pose', to: '/analyses' },
  { label: 'Visor 3D', to: '/viewer' },
  { label: 'Simulador', to: '/simulations' },
  { label: 'Reportes', to: '/reports' },
  { label: 'Administración', phase: 3 },
]

export function SideNav() {
  return (
    <nav className="sidebar" aria-label="Navegación principal">
      <div className="brand">
        BODY<span>VISION</span> AI
      </div>
      <ul className="nav-list">
        {NAV_ITEMS.map((item) => (
          <li key={item.label}>
            {item.to ? (
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}
              >
                {item.label}
              </NavLink>
            ) : (
              <span className="nav-link nav-link--disabled" aria-disabled="true">
                {item.label}
                <small className="phase-tag">Fase {item.phase}</small>
              </span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  )
}