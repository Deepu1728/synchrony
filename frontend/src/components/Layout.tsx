import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { HealthBadge } from "./HealthBadge";

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Synchrony Fraud Console</span>
        <nav className="nav">
          <NavLink to="/" end>Live feed</NavLink>
          <NavLink to="/metrics">Metrics</NavLink>
        </nav>
        <HealthBadge />
        {user && (
          <span className="user-chip">
            <span className="user-name">{user.username}</span>
            <span className="user-role">{user.role}</span>
            <button className="button button-secondary" onClick={logout}>Log out</button>
          </span>
        )}
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
