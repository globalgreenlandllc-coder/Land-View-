import { useState } from "react";
import { api } from "../api.js";
import Logo from "./Logo.jsx";

// Sign-in / sign-up screen. On success, calls onAuthed(user).
export default function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isRegister = mode === "register";

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (isRegister && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const user = isRegister
        ? await api.register(email.trim(), password)
        : await api.login(email.trim(), password);
      onAuthed(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand"><Logo size={30} /> Land-View</div>
        <h2>{isRegister ? "Create your account" : "Sign in"}</h2>
        <p className="muted small">
          {isRegister
            ? "Design landscapes on real properties. The first account becomes the admin."
            : "Welcome back — sign in to your designs."}
        </p>

        <label className="lbl">Email</label>
        <input type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />

        <label className="lbl">Password</label>
        <input type="password" required minLength={isRegister ? 8 : undefined}
          autoComplete={isRegister ? "new-password" : "current-password"}
          value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder={isRegister ? "At least 8 characters" : "Your password"} />

        {error && <div className="err">{error}</div>}

        <button className="primary block big" disabled={busy} type="submit">
          {busy ? "…" : isRegister ? "Create account" : "Sign in"}
        </button>

        <div className="auth-switch">
          {isRegister ? "Already have an account?" : "New here?"}{" "}
          <button type="button" className="linkish"
            onClick={() => { setMode(isRegister ? "login" : "register"); setError(""); }}>
            {isRegister ? "Sign in" : "Create one"}
          </button>
        </div>
      </form>
    </div>
  );
}
