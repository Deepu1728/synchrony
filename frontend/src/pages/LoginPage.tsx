import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { HealthBadge } from "../components/HealthBadge";
import { useAuth } from "../auth/AuthContext";
import { loginErrorMessage } from "../auth/messages";

export function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to={from} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter your username and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(loginErrorMessage(err));
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit} noValidate>
        <h1>Synchrony Fraud Console</h1>
        <p className="muted">Sign in to review alerts.</p>

        <label className="field">
          <span>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            disabled={busy}
            aria-invalid={error !== null}
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={busy}
            aria-invalid={error !== null}
          />
        </label>

        {error && <p className="form-error" role="alert">{error}</p>}

        <button className="button" type="submit" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
        <div className="login-health"><HealthBadge /></div>
      </form>
    </div>
  );
}
