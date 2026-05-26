import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { auth } from "../services/api";

export default function Login() {
  const [email, setEmail] = useState("demo@amrsentinel.org");
  const [password, setPassword] = useState("demo_password");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const result = await auth.login(email, password);
      localStorage.setItem("amr_token", result.token);
      localStorage.setItem("amr_user", JSON.stringify(result.user));
      navigate("/", { replace: true });
    } catch {
      setErr("Invalid credentials");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sentinel-700 to-sentinel-500">
      <form
        onSubmit={submit}
        className="bg-white rounded-lg shadow-xl p-10 w-96"
      >
        <h1 className="text-2xl font-semibold text-sentinel-700 mb-1">
          AMR Sentinel
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Antimicrobial resistance surveillance & stewardship
        </p>
        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full mb-4 border rounded px-3 py-2 text-sm focus:ring-2 focus:ring-sentinel-500 outline-none"
          required
        />
        <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-4 border rounded px-3 py-2 text-sm focus:ring-2 focus:ring-sentinel-500 outline-none"
          required
        />
        {err && <div className="text-red-600 text-sm mb-3">{err}</div>}
        <button
          disabled={busy}
          className="w-full bg-sentinel-700 text-white py-2 rounded hover:bg-sentinel-500 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
