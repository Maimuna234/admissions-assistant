// sql.js is loaded via CDN script tag in index.html — window.initSqlJs is available at runtime.
// This avoids Vite WASM bundling issues entirely.

/* eslint-disable @typescript-eslint/no-explicit-any */
type SqlJsStatic = any;
type Database = any;

const DB_KEY = "uol_admissions_db_v2";

let db: Database | null = null;

async function getSqlJs(): Promise<SqlJsStatic> {
  const w = window as any;
  if (!w.initSqlJs) {
    throw new Error("sql.js not loaded — check CDN script in index.html");
  }
  return w.initSqlJs({
    locateFile: () =>
      "/sql-wasm.wasm",
  });
}

function saveToStorage(database: Database) {
  try {
    const data: Uint8Array = database.export();
    localStorage.setItem(DB_KEY, JSON.stringify(Array.from(data)));
  } catch {
    // Storage quota — non-fatal for prototype
  }
}

function loadFromStorage(SQL: SqlJsStatic): Database | null {
  const raw = localStorage.getItem(DB_KEY);
  if (!raw) return null;
  try {
    const arr = new Uint8Array(JSON.parse(raw));
    return new SQL.Database(arr);
  } catch {
    return null;
  }
}

// ─── Public init ─────────────────────────────────────────────────────────────

export async function initDb(): Promise<Database> {
  if (db) return db;
  const SQL = await getSqlJs();
  db = loadFromStorage(SQL) ?? new SQL.Database();
  createSchema(db);
  await seedDefaults(db);
  saveToStorage(db);
  return db;
}

function createSchema(database: Database) {
  database.run(`
    CREATE TABLE IF NOT EXISTS users (
      id               TEXT PRIMARY KEY,
      name             TEXT NOT NULL,
      email            TEXT UNIQUE NOT NULL,
      password_hash    TEXT NOT NULL,
      role             TEXT NOT NULL DEFAULT 'tutor'
                         CHECK(role IN ('admin','tutor')),
      department       TEXT,
      status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('active','inactive','pending','rejected')),
      rejection_reason TEXT,
      last_login       TEXT,
      created_at       TEXT NOT NULL
    );
  `);
}

// ─── SHA-256 via Web Crypto ───────────────────────────────────────────────────

export async function hashPassword(plain: string): Promise<string> {
  const enc = new TextEncoder().encode(plain);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ─── Seed ─────────────────────────────────────────────────────────────────────

async function seedDefaults(database: Database) {
  const rows = queryAll(database, "SELECT id FROM users WHERE email = ?", ["admin@liverpool.ac.uk"]);
  if (rows.length > 0) return;

  const adminHash = await hashPassword("Admin1234!");
  const tutorHash = await hashPassword("Tutor1234!");
  const now = new Date().toISOString();

  const seed = [
    { id: "u1", name: "Dr. Sarah Mitchell",  email: "admin@liverpool.ac.uk",       hash: adminHash, role: "admin", dept: "Computer Science",              status: "active"   },
    { id: "u2", name: "James Okafor",        email: "j.okafor@liverpool.ac.uk",    hash: tutorHash, role: "tutor", dept: "Computer Science",              status: "active"   },
    { id: "u3", name: "Priya Nair",          email: "p.nair@liverpool.ac.uk",      hash: tutorHash, role: "tutor", dept: "Computer Science",              status: "active"   },
    { id: "u4", name: "Thomas Greenwood",    email: "t.greenwood@liverpool.ac.uk", hash: tutorHash, role: "tutor", dept: "Electrical Engineering",        status: "inactive" },
    { id: "u5", name: "Amara Diallo",        email: "a.diallo@liverpool.ac.uk",    hash: tutorHash, role: "tutor", dept: "Computer Science",              status: "pending"  },
  ];

  for (const u of seed) {
    database.run(
      `INSERT OR IGNORE INTO users
         (id, name, email, password_hash, role, department, status, created_at)
       VALUES (?,?,?,?,?,?,?,?)`,
      [u.id, u.name, u.email, u.hash, u.role, u.dept, u.status, now]
    );
  }
  saveToStorage(database);
}

// ─── Internal query helpers ───────────────────────────────────────────────────

function queryAll<T = Record<string, unknown>>(
  database: Database,
  sql: string,
  params: (string | number | null)[] = []
): T[] {
  const stmt = database.prepare(sql);
  stmt.bind(params);
  const rows: T[] = [];
  while (stmt.step()) rows.push(stmt.getAsObject() as T);
  stmt.free();
  return rows;
}

function queryOne<T = Record<string, unknown>>(
  database: Database,
  sql: string,
  params: (string | number | null)[] = []
): T | null {
  return queryAll<T>(database, sql, params)[0] ?? null;
}

// ─── Public DB API ────────────────────────────────────────────────────────────

export interface DbUser {
  id: string;
  name: string;
  email: string;
  password_hash: string;
  role: "admin" | "tutor";
  department: string | null;
  status: "active" | "inactive" | "pending" | "rejected";
  rejection_reason: string | null;
  last_login: string | null;
  created_at: string;
}

export async function dbGetUserByEmail(email: string): Promise<DbUser | null> {
  const database = await initDb();
  return queryOne<DbUser>(database, "SELECT * FROM users WHERE email = ?", [email]);
}

export async function dbGetAllUsers(): Promise<DbUser[]> {
  const database = await initDb();
  return queryAll<DbUser>(database, "SELECT * FROM users ORDER BY created_at DESC");
}

export async function dbCreateUser(u: {
  id: string;
  name: string;
  email: string;
  passwordHash: string;
  role: string;
  department?: string;
}): Promise<void> {
  const database = await initDb();
  database.run(
    `INSERT INTO users (id, name, email, password_hash, role, department, status, created_at)
     VALUES (?,?,?,?,?,?,?,?)`,
    [u.id, u.name, u.email, u.passwordHash, u.role, u.department ?? null, "pending", new Date().toISOString()]
  );
  saveToStorage(database);
}

export async function dbUpdateUserStatus(
  id: string,
  status: DbUser["status"],
  rejectionReason?: string
): Promise<void> {
  const database = await initDb();
  database.run(
    "UPDATE users SET status = ?, rejection_reason = ? WHERE id = ?",
    [status, rejectionReason ?? null, id]
  );
  saveToStorage(database);
}

export async function dbUpdateLastLogin(id: string): Promise<void> {
  const database = await initDb();
  database.run("UPDATE users SET last_login = ? WHERE id = ?", [new Date().toISOString(), id]);
  saveToStorage(database);
}
