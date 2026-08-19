import { useState, FormEvent } from "react";
import { useAuth } from "../auth";
import UoLLogo from "../components/UoLLogo";

interface Props {
  onNavigateRegister: () => void;
}

export default function Login({ onNavigateRegister }: Props) {
  const { login, dbReady } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError("Please enter your email address and password."); return; }
    setLoading(true);
    setError(null);
    const result = await login(email, password);
    setLoading(false);
    if (!result.ok) setError(result.error ?? "Login failed.");
  };

  if (!dbReady) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--uol-navy)" }}>
        <div className="flex flex-col items-center gap-4">
          <UoLLogo size="lg" inverse />
          <div className="flex items-center gap-2 text-sm" style={{ color: "rgba(255,255,255,0.7)" }}>
            <span className="w-4 h-4 border-2 rounded-full animate-spin"
              style={{ borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} />
            Initialising database…
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex" style={{ background: "var(--background)" }}>

      {/* Left panel — UoL navy */}
      <div className="hidden lg:flex flex-col justify-between w-80 xl:w-96 flex-shrink-0 px-10 py-10 uol-stripe"
        style={{ background: "var(--uol-navy)" }}>
        <div>
          <div className="mb-10">
            <UoLLogo size="lg" inverse />
          </div>

          <h2 className="font-serif text-xl font-semibold leading-snug mb-3" style={{ color: "#FFFFFF" }}>
            AI-powered competitive intelligence for Clearing.
          </h2>
          <p className="text-sm leading-relaxed mb-8" style={{ color: "rgba(255,255,255,0.65)" }}>
            Built for University of Liverpool Admissions Tutors to deliver
            real-time, evidence-based programme comparisons during live Clearing
            calls — faster, sharper, more confident.
          </p>

          <div className="space-y-4">
            {[
              { label: "Course comparisons", detail: "BCS accreditation, modules, placements" },
              { label: "Graduate outcomes", detail: "Salary data, employment rates, LEO" },
              { label: "Live rankings", detail: "CUG, QS, TEF, NSS verified sources" },
              { label: "Fees & entry", detail: "Accurate home and international fees" },
            ].map((item) => (
              <div key={item.label} className="flex items-start gap-3">
                <div className="mt-0.5 w-4 h-4 rounded-sm flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(255,255,255,0.12)" }}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                    style={{ color: "rgba(255,255,255,0.85)" }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>{item.label}</p>
                  <p className="text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Red accent footer bar */}
        <div className="rounded-sm px-4 py-3" style={{ background: "var(--uol-red)" }}>
          <p className="text-xs font-semibold" style={{ color: "#fff" }}>Clearing 2026 · Mid-August</p>
          <p className="text-xs" style={{ color: "rgba(255,255,255,0.75)" }}>
            University of Liverpool · Computer Science
          </p>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="mb-8 lg:hidden">
            <UoLLogo size="md" />
          </div>

          {/* Red top stripe on card */}
          <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-red)" }} />
          <div className="border border-t-0 rounded-b-sm p-6" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <h1 className="font-serif text-xl font-semibold mb-0.5" style={{ color: "var(--uol-navy)" }}>
              Sign in
            </h1>
            <p className="text-xs mb-5" style={{ color: "var(--muted-foreground)" }}>
              Use your University of Liverpool staff credentials.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="email" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  Email address
                </label>
                <input
                  id="email" type="email" autoComplete="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(null); }}
                  placeholder="you@liverpool.ac.uk"
                  className="w-full px-3 py-2 rounded-sm border text-sm"
                  style={{ borderColor: error ? "var(--uol-red)" : "var(--border)", background: "var(--background)", color: "var(--foreground)" }}
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password" type={showPassword ? "text" : "password"} autoComplete="current-password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError(null); }}
                    placeholder="••••••••"
                    className="w-full px-3 py-2 pr-9 rounded-sm border text-sm"
                    style={{ borderColor: error ? "var(--uol-red)" : "var(--border)", background: "var(--background)", color: "var(--foreground)" }}
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--muted-foreground)" }}
                    aria-label={showPassword ? "Hide password" : "Show password"}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      {showPassword
                        ? <><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></>
                        : <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>}
                    </svg>
                  </button>
                </div>
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
                  ? <><span className="w-3.5 h-3.5 border-2 rounded-full animate-spin" style={{ borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} />Signing in…</>
                  : "Sign in"}
              </button>
            </form>

            <div className="mt-5 pt-4 border-t" style={{ borderColor: "var(--border)" }}>
              <p className="text-xs text-center" style={{ color: "var(--muted-foreground)" }}>
                New to Admissions Assistant?{" "}
                <button onClick={onNavigateRegister} className="font-semibold underline underline-offset-2"
                  style={{ color: "var(--uol-red)" }}>
                  Request access
                </button>
              </p>
            </div>
          </div>

          {/* Demo hint */}
          <div className="mt-4 p-3 rounded-sm border" style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
            <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--foreground)" }}>Demo credentials</p>
            <div className="space-y-0.5 text-xs" style={{ color: "var(--muted-foreground)" }}>
              <p><span className="font-semibold">Admin:</span> admin@liverpool.ac.uk / Admin1234!</p>
              <p><span className="font-semibold">Tutor:</span> j.okafor@liverpool.ac.uk / Tutor1234!</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
