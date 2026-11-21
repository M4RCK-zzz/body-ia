import { Outlet } from "react-router-dom";
import { SideNav } from "@/components/navigation/SideNav";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { UserMenu } from "@/features/auth/UserMenu";

export function AppShell() {
  return (
    <div className="app-shell">
      <SideNav />
      <div className="app-main">
        <header className="topbar">
          <span className="topbar__context">Panel de trabajo</span>
          <span className="topbar__tag">Entorno de desarrollo · sin datos reales</span>
          <UserMenu />
        </header>
        <main className="content">
          <Outlet />
        </main>
        <Disclaimer />
      </div>
    </div>
  );
}