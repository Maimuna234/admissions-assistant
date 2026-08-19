import { useState } from "react";
import { useAuth } from "../../auth";
import type { User, UserStatus } from "../../auth";

type FilterStatus = "all" | UserStatus;
type FilterRole   = "all" | "admin" | "tutor";

function StatusPill({ status }: { status: UserStatus }) {
  const cfg: Record<UserStatus, { bg: string; color: string; label: string }> = {
    active:   { bg: "rgba(0,48,135,0.08)",   color: "var(--uol-navy)", label: "Active"   },
    inactive: { bg: "var(--muted)",           color: "var(--muted-foreground)", label: "Inactive" },
    pending:  { bg: "#FEF3C7",               color: "#92400E",         label: "Pending"  },
    rejected: { bg: "#FEF2F2",               color: "#B91C1C",         label: "Rejected" },
  };
  const { bg, color, label } = cfg[status];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-sm"
      style={{ background: bg, color }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function RolePill({ role }: { role: User["role"] }) {
  return (
    <span className="text-xs font-medium px-1.5 py-0.5 rounded-sm"
      style={{
        background: role === "admin" ? "rgba(228,0,58,0.08)" : "var(--muted)",
        color: role === "admin" ? "var(--uol-red)" : "var(--muted-foreground)",
      }}>
      {role === "admin" ? "Administrator" : "Tutor"}
    </span>
  );
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/* ── Reject modal ──────────────────────────────────────────────────────────── */
function RejectModal({ user, onConfirm, onCancel }: {
  user: User;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.45)" }}
      onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="w-full max-w-sm rounded-sm border shadow-lg" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
        <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-red)" }} />
        <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <h2 className="font-serif font-semibold text-base" style={{ color: "var(--foreground)" }}>
            Reject registration
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--muted-foreground)" }}>
            {user.name} · {user.email}
          </p>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div>
            <label htmlFor="reject-reason" className="block text-xs font-semibold mb-1.5" style={{ color: "var(--foreground)" }}>
              Rejection reason <span style={{ color: "var(--uol-red)" }}>*</span>
            </label>
            <textarea
              id="reject-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Provide a clear reason that will be shown to the applicant…"
              rows={3}
              className="w-full px-3 py-2 rounded-sm border text-xs resize-none"
              style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }}
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => reason.trim() && onConfirm(reason.trim())}
              disabled={!reason.trim()}
              className="flex-1 py-2 rounded-sm text-xs font-semibold disabled:opacity-50"
              style={{ background: "var(--uol-red)", color: "#fff" }}>
              Confirm rejection
            </button>
            <button onClick={onCancel}
              className="px-4 py-2 rounded-sm border text-xs font-medium"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Add user modal ────────────────────────────────────────────────────────── */
function AddUserModal({ onClose }: { onClose: () => void }) {
  const { createUser } = useAuth();
  const [form, setForm] = useState<{ name: string; email: string; role: "admin" | "tutor"; department: string; password: string }>({ name: "", email: "", role: "tutor", department: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  const handleAdd = async () => {
    if (!form.name.trim()) { setError("Name is required."); return; }
    if (!form.email.endsWith("@liverpool.ac.uk")) { setError("Must be a @liverpool.ac.uk email."); return; }
    setLoading(true);
    const result = await createUser({ ...form, password: form.password || "Temp1234!" });
    setLoading(false);
    if (!result.ok) setError(result.error ?? "Failed.");
    else onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.45)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-md rounded-sm border shadow-lg" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
        <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-navy)" }} />
        <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: "var(--border)" }}>
          <h2 className="font-serif font-semibold text-base" style={{ color: "var(--foreground)" }}>Add user</h2>
          <button onClick={onClose} className="w-6 h-6 flex items-center justify-center rounded-sm" style={{ color: "var(--muted-foreground)" }} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          {[
            { id: "add-name", label: "Full name", key: "name" as const, type: "text", placeholder: "Dr. Jane Smith" },
            { id: "add-email", label: "University email", key: "email" as const, type: "email", placeholder: "user@liverpool.ac.uk" },
            { id: "add-pw", label: "Temporary password (default: Temp1234!)", key: "password" as const, type: "text", placeholder: "Temp1234!" },
          ].map((f) => (
            <div key={f.id}>
              <label htmlFor={f.id} className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>{f.label}</label>
              <input id={f.id} type={f.type} value={form[f.key]} placeholder={f.placeholder}
                onChange={set(f.key)}
                className="w-full px-2.5 py-1.5 rounded-sm border text-xs"
                style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }} />
            </div>
          ))}
          <div>
            <label htmlFor="add-role" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>Role</label>
            <select id="add-role" value={form.role} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value as "admin" | "tutor" }))}
              className="w-full px-2.5 py-1.5 rounded-sm border text-xs"
              style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }}>
              <option value="tutor">Admission Tutor</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <div>
            <label htmlFor="add-dept" className="block text-xs font-semibold mb-1" style={{ color: "var(--foreground)" }}>Department</label>
            <select id="add-dept" value={form.department} onChange={set("department")}
              className="w-full px-2.5 py-1.5 rounded-sm border text-xs"
              style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }}>
              <option value="">Select department (optional)</option>
              <option>Computer Science</option>
              <option>Electrical Engineering &amp; Electronics</option>
              <option>Mathematical Sciences</option>
              <option>Admissions Office</option>
              <option>Other</option>
            </select>
          </div>
          {error && <p className="text-xs" style={{ color: "#B91C1C" }} role="alert">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button onClick={handleAdd} disabled={loading}
              className="flex-1 py-2 rounded-sm text-xs font-semibold disabled:opacity-60"
              style={{ background: "var(--uol-navy)", color: "#fff" }}>
              {loading ? "Creating…" : "Create account"}
            </button>
            <button onClick={onClose}
              className="px-4 py-2 rounded-sm border text-xs font-medium"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main panel ────────────────────────────────────────────────────────────── */
export default function UsersPanel() {
  const { allUsers, approveUser, rejectUser, deactivateUser, activateUser } = useAuth();
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [filterRole, setFilterRole] = useState<FilterRole>("all");
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<User | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const filtered = allUsers.filter((u) => {
    if (filterStatus !== "all" && u.status !== filterStatus) return false;
    if (filterRole !== "all" && u.role !== filterRole) return false;
    if (search && !u.name.toLowerCase().includes(search.toLowerCase()) && !u.email.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: allUsers.length,
    active: allUsers.filter((u) => u.status === "active").length,
    pending: allUsers.filter((u) => u.status === "pending").length,
    rejected: allUsers.filter((u) => u.status === "rejected").length,
  };

  const pendingUsers = allUsers.filter((u) => u.status === "pending");

  return (
    <div className="space-y-4">
      {/* Pending approvals alert */}
      {pendingUsers.length > 0 && (
        <div className="border rounded-sm overflow-hidden" style={{ borderColor: "#FCD34D" }}>
          <div className="px-4 py-3 flex items-start gap-3" style={{ background: "#FFFBEB" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0" style={{ color: "#92400E" }}>
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <div className="flex-1">
              <p className="text-xs font-semibold" style={{ color: "#92400E" }}>
                {pendingUsers.length} registration{pendingUsers.length > 1 ? "s" : ""} awaiting approval
              </p>
              <div className="mt-2 space-y-1.5">
                {pendingUsers.map((u) => (
                  <div key={u.id} className="flex items-center justify-between gap-4 p-2 rounded-sm"
                    style={{ background: "rgba(255,255,255,0.6)" }}>
                    <div>
                      <span className="text-xs font-medium" style={{ color: "#92400E" }}>{u.name}</span>
                      <span className="text-xs ml-2" style={{ color: "#B45309" }}>{u.email}</span>
                      {u.department && <span className="text-xs ml-2" style={{ color: "#B45309" }}>· {u.department}</span>}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => approveUser(u.id)}
                        className="px-2.5 py-1 rounded-sm text-xs font-semibold"
                        style={{ background: "var(--uol-navy)", color: "#fff" }}>
                        Approve
                      </button>
                      <button
                        onClick={() => setRejectTarget(u)}
                        className="px-2.5 py-1 rounded-sm text-xs font-semibold border"
                        style={{ borderColor: "var(--uol-red)", color: "var(--uol-red)", background: "transparent" }}>
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total users", value: stats.total },
          { label: "Active", value: stats.active, color: "var(--uol-navy)" },
          { label: "Pending approval", value: stats.pending, color: "#92400E" },
          { label: "Rejected", value: stats.rejected, color: "var(--uol-red)" },
        ].map((s) => (
          <div key={s.label} className="border rounded-sm px-3 py-2.5"
            style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>{s.label}</p>
            <p className="font-serif text-2xl font-semibold mt-0.5" style={{ color: s.color ?? "var(--foreground)" }}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--muted-foreground)" }}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search users…"
              className="pl-7 pr-3 py-1.5 rounded-sm border text-xs w-44"
              style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--foreground)" }} />
          </div>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
            className="px-2.5 py-1.5 rounded-sm border text-xs"
            style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--foreground)" }}>
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending</option>
            <option value="rejected">Rejected</option>
          </select>
          <select value={filterRole} onChange={(e) => setFilterRole(e.target.value as FilterRole)}
            className="px-2.5 py-1.5 rounded-sm border text-xs"
            style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--foreground)" }}>
            <option value="all">All roles</option>
            <option value="admin">Admin</option>
            <option value="tutor">Tutor</option>
          </select>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-semibold"
          style={{ background: "var(--uol-navy)", color: "#fff" }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Add user
        </button>
      </div>

      {/* Table */}
      <div className="border rounded-sm overflow-hidden" style={{ borderColor: "var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--uol-navy)", color: "#fff" }}>
                {["Name", "Email", "Role", "Department", "Status", "Last login", "Actions"].map((h) => (
                  <th key={h} className="text-left px-3 py-2.5 font-semibold whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-8 text-center" style={{ color: "var(--muted-foreground)" }}>
                  No users match the current filters.
                </td></tr>
              )}
              {filtered.map((u, i) => (
                <tr key={u.id} style={{
                  background: i % 2 === 0 ? "var(--card)" : "var(--background)",
                  borderBottom: "1px solid var(--border)",
                }}>
                  <td className="px-3 py-2.5 font-medium whitespace-nowrap" style={{ color: "var(--foreground)" }}>{u.name}</td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>{u.email}</td>
                  <td className="px-3 py-2.5"><RolePill role={u.role} /></td>
                  <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>{u.department ?? "—"}</td>
                  <td className="px-3 py-2.5"><StatusPill status={u.status} /></td>
                  <td className="px-3 py-2.5 whitespace-nowrap" style={{ color: "var(--muted-foreground)" }}>
                    {formatDate(u.lastLogin)}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      {/* Pending: approve or reject */}
                      {u.status === "pending" && (
                        <>
                          <button onClick={() => approveUser(u.id)}
                            className="px-2 py-0.5 rounded-sm text-xs font-semibold"
                            style={{ background: "var(--uol-navy)", color: "#fff" }}>
                            Approve
                          </button>
                          <button onClick={() => setRejectTarget(u)}
                            className="px-2 py-0.5 rounded-sm text-xs font-semibold border"
                            style={{ borderColor: "var(--uol-red)", color: "var(--uol-red)" }}>
                            Reject
                          </button>
                        </>
                      )}
                      {/* Rejected: re-approve option */}
                      {u.status === "rejected" && (
                        <button onClick={() => approveUser(u.id)}
                          className="px-2 py-0.5 rounded-sm text-xs font-medium"
                          style={{ background: "rgba(0,48,135,0.08)", color: "var(--uol-navy)" }}>
                          Re-approve
                        </button>
                      )}
                      {/* Active: deactivate */}
                      {u.status === "active" && (
                        <button onClick={() => deactivateUser(u.id)}
                          className="px-2 py-0.5 rounded-sm text-xs font-medium"
                          style={{ background: "#FEF2F2", color: "#B91C1C" }}>
                          Deactivate
                        </button>
                      )}
                      {/* Inactive: activate */}
                      {u.status === "inactive" && (
                        <button onClick={() => activateUser(u.id)}
                          className="px-2 py-0.5 rounded-sm text-xs font-medium"
                          style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
                          Activate
                        </button>
                      )}
                      <button onClick={() => setSelectedUser(u)}
                        className="px-2 py-0.5 rounded-sm text-xs font-medium"
                        style={{ color: "var(--foreground)", background: "var(--muted)" }}>
                        Details
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* User detail modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.45)" }}
          onClick={(e) => e.target === e.currentTarget && setSelectedUser(null)}>
          <div className="w-full max-w-sm rounded-sm border shadow-lg" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
            <div className="h-1 rounded-t-sm" style={{ background: "var(--uol-navy)" }} />
            <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: "var(--border)" }}>
              <h2 className="font-serif font-semibold text-base" style={{ color: "var(--foreground)" }}>User details</h2>
              <button onClick={() => setSelectedUser(null)} aria-label="Close"
                className="w-6 h-6 flex items-center justify-center rounded-sm" style={{ color: "var(--muted-foreground)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <div className="px-5 py-4 space-y-0.5 text-xs">
              {[
                { label: "Name", value: selectedUser.name },
                { label: "Email", value: selectedUser.email },
                { label: "Role", value: selectedUser.role === "admin" ? "Administrator" : "Admission Tutor" },
                { label: "Department", value: selectedUser.department ?? "—" },
                { label: "Status", value: selectedUser.status },
                { label: "Last login", value: formatDate(selectedUser.lastLogin) },
                { label: "Account created", value: formatDate(selectedUser.createdAt) },
                ...(selectedUser.rejectionReason ? [{ label: "Rejection reason", value: selectedUser.rejectionReason }] : []),
              ].map((r) => (
                <div key={r.label} className="flex justify-between py-1.5 border-b" style={{ borderColor: "var(--border)" }}>
                  <span style={{ color: "var(--muted-foreground)" }}>{r.label}</span>
                  <span className="font-medium text-right max-w-[60%]" style={{ color: "var(--foreground)" }}>{r.value}</span>
                </div>
              ))}
              <div className="pt-3 flex gap-2">
                {selectedUser.status === "pending" && (
                  <>
                    <button onClick={() => { approveUser(selectedUser.id); setSelectedUser(null); }}
                      className="flex-1 py-2 rounded-sm text-xs font-semibold"
                      style={{ background: "var(--uol-navy)", color: "#fff" }}>
                      Approve
                    </button>
                    <button onClick={() => { setRejectTarget(selectedUser); setSelectedUser(null); }}
                      className="flex-1 py-2 rounded-sm text-xs font-semibold border"
                      style={{ borderColor: "var(--uol-red)", color: "var(--uol-red)" }}>
                      Reject
                    </button>
                  </>
                )}
                <button onClick={() => setSelectedUser(null)}
                  className="flex-1 py-2 rounded-sm border text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showAdd  && <AddUserModal onClose={() => setShowAdd(false)} />}
      {rejectTarget && (
        <RejectModal
          user={rejectTarget}
          onConfirm={async (reason) => { await rejectUser(rejectTarget.id, reason); setRejectTarget(null); }}
          onCancel={() => setRejectTarget(null)}
        />
      )}
    </div>
  );
}
