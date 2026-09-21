import { NavLink, Outlet } from "react-router-dom";
import { HealthBadge } from "./HealthBadge";

export function Layout() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Synchrony Fraud Console</span>
        <nav className="nav">
          <NavLink to="/" end>Live feed</NavLink>
          <NavLink to="/metrics">Metrics</NavLink>
        </nav>
        <HealthBadge />
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
