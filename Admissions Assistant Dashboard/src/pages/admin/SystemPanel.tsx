import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const API_AUTH_KEY = import.meta.env.VITE_API_AUTH_KEY ?? "openwebui-local-key";

interface SystemPayload {
  system: {
    geminiConfigured: boolean;
    apiAuthConfigured: boolean;
    usersTotal: number;
    usersActive: number;
    usersPending: number;
    serverTime: string;
  };
}

export default function SystemPanel() {
  const [data, setData] = useState<SystemPayload["system"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/api/admin/overview`, {
          headers: { Authorization: `Bearer ${API_AUTH_KEY}` },
        });
        if (!response.ok) {
          throw new Error(`Failed to load system data (${response.status})`);
        }
        const payload = (await response.json()) as SystemPayload;
        setData(payload.system);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load system overview.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="p-4 rounded-sm border text-sm" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
        Loading system status...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 rounded-sm border text-sm" style={{ borderColor: "#fca5a5", background: "#fef2f2", color: "#991b1b" }}>
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 rounded-sm border text-sm" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
        No system data available.
      </div>
    );
  }

  const items = [
    { label: "Gemini configured", value: data.geminiConfigured ? "Yes" : "No" },
    { label: "API auth configured", value: data.apiAuthConfigured ? "Yes" : "No" },
    { label: "Total users", value: String(data.usersTotal) },
    { label: "Active users", value: String(data.usersActive) },
    { label: "Pending approvals", value: String(data.usersPending) },
    { label: "Server time", value: data.serverTime },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
          <p className="text-xs mb-1" style={{ color: "var(--muted-foreground)" }}>{item.label}</p>
          <p className="text-sm font-semibold break-all" style={{ color: "var(--foreground)" }}>{item.value}</p>
        </div>
      ))}
    </div>
  );
}
