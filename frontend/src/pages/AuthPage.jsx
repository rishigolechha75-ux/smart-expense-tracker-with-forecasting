import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { authenticate } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = isLogin ? { email: form.email, password: form.password } : form;
      await authenticate(mode, data);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-side">
        <span className="brand-mark large">₹</span>
        <h1>Know where your money goes, and where it's heading.</h1>
        <p>Log expenses, set monthly budgets and get a forecast of next month's spending.</p>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <h2>{isLogin ? "Log in" : "Create an account"}</h2>
        {!isLogin && (
          <label>
            Name
            <input value={form.name} onChange={update("name")} required maxLength={100} autoComplete="name" />
          </label>
        )}
        <label>
          Email
          <input type="email" value={form.email} onChange={update("email")} required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={update("password")}
            required
            minLength={isLogin ? 1 : 8}
            autoComplete={isLogin ? "current-password" : "new-password"}
          />
          {!isLogin && <span className="hint">At least 8 characters</span>}
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primary" disabled={busy}>
          {busy ? "Please wait..." : isLogin ? "Log in" : "Sign up"}
        </button>
        <p className="muted switch">
          {isLogin ? "New here? " : "Already have an account? "}
          <Link to={isLogin ? "/register" : "/login"}>{isLogin ? "Create an account" : "Log in"}</Link>
        </p>
      </form>
    </div>
  );
}
