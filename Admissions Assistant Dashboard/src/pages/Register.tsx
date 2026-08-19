import { useState, FormEvent } from "react";
import { useAuth } from "../auth";
import UoLLogo from "../components/UoLLogo";

interface Props { onNavigateLogin: () => void; }

export default function Register({ onNavigateLogin }: Props) {
  const { register } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", department: "", password: "", confirm: "" });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const validate = () => {
    if (!form.name.trim()) return "Please enter your full name.";
    if (!form.email) return "Please enter your email address.";
    if (!form.email.endsWith("@liverpool.ac.uk")) return "You must use a @liverpool.ac.uk email address.";
    if (form.password.length < 8) return "Password must be at least 8 characters.";
    if (!/[A-Z]/.test(form.password)) return "Password must contain at least one uppercase letter.";
    if (!/[0-9]/.test(form.password)) return "Password must contain at least one number.";
    if (form.password !== form.confirm) return "Passwords do not match.";
    return null;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setLoading(true); setError(null);
    const result = await register({ name: form.name, email: form.email, password: form.password, department: form.department || undefined });
    setLoading(false);
    if (!result.ok) setError(result.error ?? "Registration failed.");
    else setSuccess(true);
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "var(--background)" }}>
        <div className="max-w-sm w-full text-center">
          <div className="mb-6"><UoLLogo size="md" /></div>
          <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-red)" }} />
          <div className="border border-t-0 rounded-b-sm px-6 py-8" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: "rgba(0,48,135,0.08)" }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--uol-navy)" }}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2 className="font-serif text-xl font-semibold mb-2" style={{ color: "var(--uol-navy)" }}>Request submitted</h2>
            <p className="text-sm mb-6 leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
              Your account request is awaiting administrator approval. You will be notified once access is confirmed.
            </p>
            <button onClick={onNavigateLogin}
              className="px-4 py-2 rounded-sm text-xs font-semibold"
              style={{ background: "var(--uol-navy)", color: "#fff" }}>
              Return to sign in
            </button>
          </div>
        </div>
      </div>
    );
  }

  const pwChecks = [
    { label: "At least 8 characters", met: form.password.length >= 8 },
    { label: "One uppercase letter", met: /[A-Z]/.test(form.password) },
    { label: "One number", met: /[0-9]/.test(form.password) },
    { label: "Passwords match", met: form.password.length > 0 && form.password === form.confirm },
  ];

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-md">
        <div className="mb-6"><UoLLogo size="md" /></div>

        <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-red)" }} />
        <div className="border border-t-0 rounded-b-sm overflow-hidden" style={{ borderColor: "var(--border)" }}>
          <div className="px-6 py-4 border-b" style={{ borderColor: "var(--border)", background: "var(--uol-navy)" }}>
            <h1 className="font-serif text-lg font-semibold" style={{ color: "#fff" }}>Request access</h1>
            <p className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.65)" }}>
              Admissions tutor accounts require administrator approval before activation.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4" style={{ background: "var(--card)" }} noValidate>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <label htmlFor="reg-name" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  Full name <span style={{ color: "var(--uol-red)" }}>*</span>
                </label>
                <input id="reg-name" type="text" autoComplete="name" value={form.name} onChange={set("name")}
                  placeholder="Dr. Jane Smith"
                  className="w-full px-3 py-2 rounded-sm border text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }} />
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="reg-email" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  University email <span style={{ color: "var(--uol-red)" }}>*</span>
                </label>
                <input id="reg-email" type="email" autoComplete="email" value={form.email} onChange={set("email")}
                  placeholder="you@liverpool.ac.uk"
                  className="w-full px-3 py-2 rounded-sm border text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }} />
                <p className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>Must be a @liverpool.ac.uk address.</p>
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="reg-dept" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>Department</label>
                <select id="reg-dept" value={form.department} onChange={set("department")}
                  className="w-full px-3 py-2 rounded-sm border text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }}>
                  <option value="">Select department (optional)</option>
                  <option>Computer Science</option>
                  <option>Electrical Engineering &amp; Electronics</option>
                  <option>Mathematical Sciences</option>
                  <option>Physics</option>
                  <option>Admissions Office</option>
                  <option>Other</option>
                </select>
              </div>
              <div>
                <label htmlFor="reg-pw" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  Password <span style={{ color: "var(--uol-red)" }}>*</span>
                </label>
                <div className="relative">
                  <input id="reg-pw" type={showPw ? "text" : "password"} autoComplete="new-password"
                    value={form.password} onChange={set("password")} placeholder="Min. 8 chars"
                    className="w-full px-3 py-2 pr-9 rounded-sm border text-sm"
                    style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }} />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--muted-foreground)" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                    </svg>
                  </button>
                </div>
              </div>
              <div>
                <label htmlFor="reg-confirm" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  Confirm password <span style={{ color: "var(--uol-red)" }}>*</span>
                </label>
                <input id="reg-confirm" type={showPw ? "text" : "password"} autoComplete="new-password"
                  value={form.confirm} onChange={set("confirm")} placeholder="Repeat password"
                  className="w-full px-3 py-2 rounded-sm border text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }} />
              </div>
            </div>

            <div className="p-3 rounded-sm text-xs space-y-1.5" style={{ background: "var(--muted)" }}>
              {pwChecks.map((r) => (
                <div key={r.label} className="flex items-center gap-1.5">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                    style={{ color: r.met ? "var(--uol-navy)" : "var(--muted-foreground)" }}>
                    {r.met ? <polyline points="20 6 9 17 4 12"/> : <circle cx="12" cy="12" r="9"/>}
                  </svg>
                  <span style={{ color: r.met ? "var(--uol-navy)" : "var(--muted-foreground)" }}>{r.label}</span>
                </div>
              ))}
            </div>

            {error && (
              <div className="flex items-start gap-2 p-2.5 rounded-sm border text-xs"
                style={{ background: "#FEF2F2", borderColor: "#FECACA", color: "#B91C1C" }} role="alert">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-sm text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
              style={{ background: "var(--uol-navy)", color: "#fff" }}>
              {loading
                ? <><span className="w-3.5 h-3.5 border-2 rounded-full animate-spin" style={{ borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} />Submitting…</>
                : "Submit access request"}
            </button>

            <p className="text-xs text-center" style={{ color: "var(--muted-foreground)" }}>
              Already have an account?{" "}
              <button onClick={onNavigateLogin} className="font-semibold underline underline-offset-2" style={{ color: "var(--uol-red)" }}>
                Sign in
              </button>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
