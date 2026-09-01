import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { googleLoginUrl, login, register } from "../api";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") await register(email, password, name);
      else await login(email, password);
      nav("/");
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 380, margin: "80px auto", padding: 24 }}>
      <h1 style={{ marginBottom: 20 }}>
        📚 {mode === "register" ? "Create account" : "Sign in"}
      </h1>
      <form onSubmit={submit} style={{ display: "grid", gap: 10 }}>
        {mode === "register" && (
          <input placeholder="Name (optional)" value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle} />
        )}
        <input placeholder="Email" type="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
        <input placeholder={mode === "register" ? "Password (min 8 chars)" : "Password"}
          type="password" required minLength={mode === "register" ? 8 : 1}
          value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
        {error && <div className="error-msg">{error}</div>}
        <button className="btn" disabled={busy}>
          {busy ? "…" : mode === "register" ? "Create account" : "Sign in"}
        </button>
      </form>

      <div style={{ textAlign: "center", margin: "16px 0", color: "var(--muted)", fontSize: 13 }}>
        — or —
      </div>
      <a href={googleLoginUrl} style={{ textDecoration: "none" }}>
        <button className="btn ghost" style={{ width: "100%" }}>
          Continue with Google
        </button>
      </a>

      <p style={{ marginTop: 20, fontSize: 14, color: "var(--muted)" }}>
        {mode === "register" ? (
          <>Already have an account? <Link to="/login" style={{ color: "var(--accent)" }}>Sign in</Link></>
        ) : (
          <>No account? <Link to="/register" style={{ color: "var(--accent)" }}>Create one</Link></>
        )}
      </p>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--ink)",
  borderRadius: 8, padding: "10px 12px", fontSize: 14,
};
