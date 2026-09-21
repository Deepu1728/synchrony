import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const { status, retry } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <p className="center muted">Checking your session...</p>;
  }
  if (status === "unavailable") {
    return (
      <div className="center">
        <p>Cannot reach the server.</p>
        <button className="button" onClick={retry}>Retry</button>
      </div>
    );
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}
