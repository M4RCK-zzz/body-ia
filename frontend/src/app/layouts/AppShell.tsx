import { Outlet } from 'react-router-dom'
import { Disclaimer } from '@/components/ui/Disclaimer'
import { SideNav } from '@/components/navigation/SideNav'

export function AppShell() {
  return (
    <div className="app-shell">
      <SideNav />
      <div className="app-main">
        <header className="topbar">
          <span className="topbar__context">Panel de trabajo</span>
          <span className="topbar__tag">Entorno de desarrollo · sin datos reales</span>
        </header>
        <main className="content">
          <Outlet />
        </main>
        <Disclaimer />
      </div>
    </div>
  )
}