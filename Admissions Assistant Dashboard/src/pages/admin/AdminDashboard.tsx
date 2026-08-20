import { useState, type ReactNode } from "react";
import { useAuth } from "../../auth";
import UsersPanel from "./UsersPanel";
import KnowledgeBase from "./KnowledgeBase";
import ModelEvaluation from "./ModelEvaluation";
import SystemPanel from "./SystemPanel";

type AdminTab = "users" | "knowledge" | "evaluation" | "system";

const NAV: { id: AdminTab; label: string; icon: ReactNode; desc: string }[] = [
  {
    id: "users",
    label: "User Management",
    desc: "Accounts & access",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
  },
  {
    id: "knowledge",
    label: "Knowledge Base",
    desc: "Data & scrapers",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
  },
  {
    id: "evaluation",
    label: "Model Evaluation",
    desc: "Performance metrics",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    id: "system",
    label: "System",
    desc: "Operational settings",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.07 4.93l-1.41 1.41M12 2v2M4.93 4.93l1.41 1.41M2 12h2M4.93 19.07l1.41-1.41M12 20v2M19.07 19.07l-1.41-1.41M20 12h2" />
      </svg>
    ),
  },
];

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeNav = NAV.find((n) => n.id === activeTab)!;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--background)" }}>

      {/* Top header */}
      <header className="border-b flex-shrink-0" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        <div className="px-4 sm:px-6 h-11 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden w-7 h-7 flex items-center justify-center rounded-sm"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle menu"
              style={{ color: "var(--muted-foreground)" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: "var(--forest)" }}>
                <path d="M12 14l9-5-9-5-9 5 9 5z" />
                <path d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
              </svg>
              <span className="font-serif font-semibold text-sm" style={{ color: "var(--foreground)" }}>
                Admissions Assistant
              </span>
            </div>
            <span className="hidden sm:inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-sm font-medium"
              style={{ background: "rgba(45,80,22,0.1)", color: "var(--forest)" }}>
              Administrator
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-1.5 text-xs" style={{ color: "var(--muted-foreground)" }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
              </svg>
              {user?.name}
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm border text-xs hover:bg-muted"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
              aria-label="Sign out"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Sidebar overlay on mobile */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-30 lg:hidden" style={{ background: "rgba(0,0,0,0.3)" }}
            onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <nav
          className={`
            fixed lg:static inset-y-0 left-0 z-40 w-56 flex-shrink-0 flex flex-col border-r
            transform transition-transform duration-200
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
          `}
          style={{ borderColor: "var(--border)", background: "var(--card)", top: "44px", bottom: 0 }}
        >
          <div className="px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--muted-foreground)" }}>
              Administration
            </p>
            <div className="space-y-0.5">
              {NAV.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => { setActiveTab(item.id); setSidebarOpen(false); }}
                    className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-sm text-left"
                    style={{
                      background: active ? "rgba(45,80,22,0.08)" : "transparent",
                      color: active ? "var(--forest)" : "var(--foreground)",
                    }}
                    aria-current={active ? "page" : undefined}
                  >
                    <span style={{ color: active ? "var(--forest)" : "var(--muted-foreground)" }}>
                      {item.icon}
                    </span>
                    <div>
                      <p className="text-xs font-medium leading-none mb-0.5">{item.label}</p>
                      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{item.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-auto px-4 py-4 border-t" style={{ borderColor: "var(--border)" }}>
            <p className="text-xs font-medium mb-0.5" style={{ color: "var(--foreground)" }}>Clearing 2026</p>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>University of Liverpool · CS</p>
            <div className="mt-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--forest)" }} />
              <span className="text-xs" style={{ color: "var(--forest)" }}>System operational</span>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="px-4 sm:px-6 py-4">
            {/* Page heading */}
            <div className="flex items-center gap-2 mb-5 pb-4 border-b" style={{ borderColor: "var(--border)" }}>
              <span style={{ color: "var(--muted-foreground)" }}>{activeNav.icon}</span>
              <div>
                <h1 className="font-serif font-semibold text-base" style={{ color: "var(--foreground)" }}>
                  {activeNav.label}
                </h1>
                <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{activeNav.desc}</p>
              </div>
            </div>

            {activeTab === "users" && <UsersPanel />}
            {activeTab === "knowledge" && <KnowledgeBase />}
            {activeTab === "evaluation" && <ModelEvaluation />}
            {activeTab === "system" && <SystemPanel />}
          </div>
        </main>
      </div>
    </div>
  );
}
