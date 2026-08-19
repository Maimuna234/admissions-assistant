import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import {
  initDb,
  dbGetUserByEmail,
  dbGetAllUsers,
  dbCreateUser,
  dbUpdateUserStatus,
  dbUpdateLastLogin,
  hashPassword,
  type DbUser,
} from "./db";

// ─── Types ────────────────────────────────────────────────────────────────────

export type UserRole   = "admin" | "tutor";
export type UserStatus = "active" | "inactive" | "pending" | "rejected";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department?: string;
  status: UserStatus;
  rejectionReason?: string;
  lastLogin?: string;
  createdAt: string;
}

export interface RegisterData {
  name: string;
  email: string;
  password: string;
  department?: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  dbReady: boolean;
  login:    (email: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  register: (data: RegisterData)              => Promise<{ ok: boolean; error?: string }>;
  logout:   () => void;
  // Admin ops
  allUsers: User[];
  refreshUsers: () => Promise<void>;
  approveUser:  (id: string)                            => Promise<void>;
  rejectUser:   (id: string, reason: string)            => Promise<void>;
  deactivateUser: (id: string)                          => Promise<void>;
  activateUser:   (id: string)                          => Promise<void>;
  createUser:   (data: RegisterData & { role: UserRole }) => Promise<{ ok: boolean; error?: string }>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function toUser(row: DbUser): User {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    department: row.department ?? undefined,
    status: row.status,
    rejectionReason: row.rejection_reason ?? undefined,
    lastLogin: row.last_login ?? undefined,
    createdAt: row.created_at,
  };
}

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [dbReady, setDbReady] = useState(false);

  useEffect(() => {
    initDb().then(async () => {
      setDbReady(true);
      const rows = await dbGetAllUsers();
      setAllUsers(rows.map(toUser));
    });
  }, []);

  const refreshUsers = async () => {
    const rows = await dbGetAllUsers();
    setAllUsers(rows.map(toUser));
  };

  // ── Login ─────────────────────────────────────────────────────────────────

  const login = async (email: string, password: string) => {
    const row = await dbGetUserByEmail(email.trim().toLowerCase());
    if (!row) return { ok: false, error: "No account found with this email address." };

    const hash = await hashPassword(password);
    if (hash !== row.password_hash) return { ok: false, error: "Incorrect password." };

    if (row.status === "rejected") {
      return {
        ok: false,
        error: `Your registration was not approved${row.rejection_reason ? `: ${row.rejection_reason}` : "."} Contact the administrator.`,
      };
    }
    if (row.status === "pending") {
      return { ok: false, error: "Your account is awaiting administrator approval. You will be notified by email." };
    }
    if (row.status === "inactive") {
      return { ok: false, error: "This account has been deactivated. Contact your administrator." };
    }

    await dbUpdateLastLogin(row.id);
    setUser(toUser({ ...row, last_login: new Date().toISOString() }));
    return { ok: true };
  };

  // ── Register ──────────────────────────────────────────────────────────────

  const register = async (data: RegisterData) => {
    const emailLower = data.email.trim().toLowerCase();
    if (!emailLower.endsWith("@liverpool.ac.uk"))
      return { ok: false, error: "Registration requires a @liverpool.ac.uk email address." };

    const exists = await dbGetUserByEmail(emailLower);
    if (exists) return { ok: false, error: "An account with this email already exists." };

    const id = `u${Date.now()}`;
    const passwordHash = await hashPassword(data.password);
    await dbCreateUser({
      id,
      name: data.name,
      email: emailLower,
      passwordHash,
      role: "tutor",
      department: data.department,
    });
    await refreshUsers();
    return { ok: true };
  };

  // ── Admin: create user directly ───────────────────────────────────────────

  const createUser = async (data: RegisterData & { role: UserRole }) => {
    const emailLower = data.email.trim().toLowerCase();
    if (!emailLower.endsWith("@liverpool.ac.uk"))
      return { ok: false, error: "Must be a @liverpool.ac.uk email." };
    const exists = await dbGetUserByEmail(emailLower);
    if (exists) return { ok: false, error: "Email already exists." };

    const id = `u${Date.now()}`;
    const passwordHash = await hashPassword(data.password || "Temp1234!");
    await dbCreateUser({ id, name: data.name, email: emailLower, passwordHash, role: data.role, department: data.department });
    // Admin-created accounts go straight to active
    await dbUpdateUserStatus(id, "active");
    await refreshUsers();
    return { ok: true };
  };

  // ── Admin: status ops ─────────────────────────────────────────────────────

  const approveUser = async (id: string) => {
    await dbUpdateUserStatus(id, "active");
    await refreshUsers();
  };

  const rejectUser = async (id: string, reason: string) => {
    await dbUpdateUserStatus(id, "rejected", reason);
    await refreshUsers();
  };

  const deactivateUser = async (id: string) => {
    await dbUpdateUserStatus(id, "inactive");
    await refreshUsers();
  };

  const activateUser = async (id: string) => {
    await dbUpdateUserStatus(id, "active");
    await refreshUsers();
  };

  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{
      user, isAuthenticated: !!user, dbReady,
      login, register, logout,
      allUsers, refreshUsers,
      approveUser, rejectUser, deactivateUser, activateUser, createUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
