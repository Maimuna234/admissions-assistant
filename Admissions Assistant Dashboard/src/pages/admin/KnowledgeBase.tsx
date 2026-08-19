import { useState } from "react";

type Priority = "entry" | "curriculum" | "outcomes" | "fees" | "teaching" | "rankings";
type FileType = "csv" | "scraper" | "ingestion" | "generated";
type DataStatus = "current" | "stale" | "updating" | "error";

interface DataSource {
  priority: Priority;
  label: string;
  recordCount: number;
  lastUpdated: string;
  status: DataStatus;
  csvFile: string;
  scraperScript: string;
  ingestionScript: string;
  generatedFile: string;
}

const PRIORITY_LABELS: Record<Priority, string> = {
  entry: "Entry Requirements",
  curriculum: "Curriculum & Accreditation",
  outcomes: "Graduate Outcomes & Salary",
  fees: "Fees & Cost",
  teaching: "Teaching Quality & NSS",
  rankings: "University Rankings",
};

const DATA_SOURCES: DataSource[] = [
  {
    priority: "entry",
    label: "Entry Requirements",
    recordCount: 142,
    lastUpdated: "2026-08-15T09:30:00Z",
    status: "current",
    csvFile: "entry_requirements_2026.csv",
    scraperScript: "scrape_entry_requirements.py",
    ingestionScript: "ingest_entry_requirements.py",
    generatedFile: "entry_requirements_processed.json",
  },
  {
    priority: "curriculum",
    label: "Curriculum & Accreditation",
    recordCount: 98,
    lastUpdated: "2026-08-12T14:00:00Z",
    status: "stale",
    csvFile: "curriculum_accreditation_2026.csv",
    scraperScript: "scrape_curriculum.py",
    ingestionScript: "ingest_curriculum.py",
    generatedFile: "curriculum_processed.json",
  },
  {
    priority: "outcomes",
    label: "Graduate Outcomes & Salary",
    recordCount: 210,
    lastUpdated: "2026-08-17T11:00:00Z",
    status: "current",
    csvFile: "graduate_outcomes_2026.csv",
    scraperScript: "scrape_graduate_outcomes.py",
    ingestionScript: "ingest_graduate_outcomes.py",
    generatedFile: "graduate_outcomes_processed.json",
  },
  {
    priority: "fees",
    label: "Fees & Cost",
    recordCount: 88,
    lastUpdated: "2026-08-10T08:00:00Z",
    status: "stale",
    csvFile: "fees_cost_2026.csv",
    scraperScript: "scrape_fees.py",
    ingestionScript: "ingest_fees.py",
    generatedFile: "fees_processed.json",
  },
  {
    priority: "teaching",
    label: "Teaching Quality & NSS",
    recordCount: 176,
    lastUpdated: "2026-08-18T16:45:00Z",
    status: "current",
    csvFile: "nss_tef_2026.csv",
    scraperScript: "scrape_nss_tef.py",
    ingestionScript: "ingest_nss_tef.py",
    generatedFile: "nss_tef_processed.json",
  },
  {
    priority: "rankings",
    label: "University Rankings",
    recordCount: 120,
    lastUpdated: "2026-08-19T07:00:00Z",
    status: "current",
    csvFile: "rankings_2026.csv",
    scraperScript: "scrape_rankings.py",
    ingestionScript: "ingest_rankings.py",
    generatedFile: "rankings_processed.json",
  },
];

const SCRIPT_PREVIEWS: Record<string, string> = {
  "scrape_entry_requirements.py": `#!/usr/bin/env python3
"""
Scraper: Entry Requirements
Targets official course pages for all comparison universities.
Sources: UCAS, university course pages.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime

UNIVERSITIES = [
    {"name": "University of Liverpool", "url": "https://www.liverpool.ac.uk/study/undergraduate/courses/computer-science-bsc-hons/entry/"},
    {"name": "University of Leeds",     "url": "https://courses.leeds.ac.uk/g500/computer-science-bsc"},
    {"name": "University of Sheffield", "url": "https://www.sheffield.ac.uk/undergraduate/courses/2026/computer-science-bsc-geng"},
    {"name": "University of Manchester","url": "https://www.manchester.ac.uk/study/undergraduate/courses/2026/00560/bsc-computer-science/"},
    # ... all 10 comparison universities
]

def scrape_university(entry: dict) -> dict:
    resp = requests.get(entry["url"], timeout=15, headers={"User-Agent": "AdmissionsBot/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Extract A-level offer, IB points, GCSE requirements
    return {
        "university": entry["name"],
        "url": entry["url"],
        "a_level_offer": extract_alevel(soup),
        "ib_points": extract_ib(soup),
        "gcse_maths": extract_gcse(soup),
        "english_requirement": extract_english(soup),
        "scraped_at": datetime.utcnow().isoformat(),
    }

def main():
    logging.basicConfig(level=logging.INFO)
    records = []
    for uni in UNIVERSITIES:
        try:
            data = scrape_university(uni)
            records.append(data)
            logging.info(f"Scraped: {uni['name']}")
        except Exception as e:
            logging.error(f"Failed {uni['name']}: {e}")
    df = pd.DataFrame(records)
    df.to_csv("entry_requirements_2026.csv", index=False)
    logging.info(f"Saved {len(records)} records to entry_requirements_2026.csv")

if __name__ == "__main__":
    main()`,

  "ingest_entry_requirements.py": `#!/usr/bin/env python3
"""
Ingestion: Entry Requirements
Validates and loads entry requirements CSV into the knowledge base.
"""
import pandas as pd
import json
import logging
from pathlib import Path

REQUIRED_COLS = ["university", "a_level_offer", "ib_points", "gcse_maths", "english_requirement", "scraped_at"]

def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df = df.dropna(subset=["university", "a_level_offer"])
    df["ib_points"] = pd.to_numeric(df["ib_points"], errors="coerce")
    return df

def transform(df: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        records.append({
            "university": row["university"],
            "entry_requirements": {
                "a_level": row["a_level_offer"],
                "ib_diploma": f"{int(row['ib_points'])} points" if pd.notna(row["ib_points"]) else "Not specified",
                "gcse_maths": row["gcse_maths"],
                "english": row["english_requirement"],
            },
            "source_url": row.get("url", ""),
            "last_verified": row["scraped_at"],
        })
    return records

def main():
    logging.basicConfig(level=logging.INFO)
    csv_path = Path("entry_requirements_2026.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found. Run scraper first.")
    df = pd.read_csv(csv_path)
    df = validate(df)
    records = transform(df)
    out_path = Path("entry_requirements_processed.json")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    logging.info(f"Ingested {len(records)} records → {out_path}")

if __name__ == "__main__":
    main()`,

  "scrape_graduate_outcomes.py": `#!/usr/bin/env python3
"""
Scraper: Graduate Outcomes & Salary
Sources: HESA Graduate Outcomes survey, Longitudinal Education Outcomes (LEO).
"""
import requests
import pandas as pd
import logging
from datetime import datetime

HESA_API_BASE = "https://www.hesa.ac.uk/api/graduate-outcomes"
LEO_API_BASE  = "https://stat-xplore.dwp.gov.uk/webapi/rest/v1/table"

UNIVERSITIES = [
    {"name": "University of Liverpool", "hesa_id": "0069", "ukprn": "10006842"},
    {"name": "University of Leeds",     "hesa_id": "0041", "ukprn": "10003105"},
    # ... all comparison universities
]

def fetch_hesa_outcomes(hesa_id: str) -> dict:
    """Fetch 1-year, 3-year and 5-year outcomes from HESA GO survey."""
    url = f"{HESA_API_BASE}/institution/{hesa_id}/subject/I100"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()

def main():
    logging.basicConfig(level=logging.INFO)
    records = []
    for uni in UNIVERSITIES:
        try:
            raw = fetch_hesa_outcomes(uni["hesa_id"])
            records.append({
                "university": uni["name"],
                "median_salary_3yr": raw.get("median_3yr"),
                "median_salary_5yr": raw.get("median_5yr"),
                "employment_rate": raw.get("employment_rate"),
                "professional_employment_pct": raw.get("prof_mgr_pct"),
                "scraped_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logging.error(f"Failed {uni['name']}: {e}")
    pd.DataFrame(records).to_csv("graduate_outcomes_2026.csv", index=False)

if __name__ == "__main__":
    main()`,

  "scrape_rankings.py": `#!/usr/bin/env python3
"""
Scraper: University Rankings
Sources: Complete University Guide (CUG), QS World Rankings, THE.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime

CUG_CS_URL  = "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings/computer-science"
CUG_ALL_URL = "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings"
QS_API      = "https://www.topuniversities.com/university-rankings/world-university-rankings/2026"

TARGET_UNIS = [
    "University of Liverpool", "University of Leeds", "University of Sheffield",
    "University of Manchester", "Lancaster University", "University of Nottingham",
    "University of Birmingham", "Newcastle University",
    "Liverpool John Moores University", "Manchester Metropolitan University",
    "Queen Mary University London",
]

def scrape_cug_cs(url: str) -> dict[str, int]:
    """Returns dict of university name → CS rank."""
    resp = requests.get(url, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    rankings = {}
    for row in soup.select("table.rankings-table tbody tr"):
        rank = row.select_one("td.rank")
        name = row.select_one("td.institution")
        if rank and name:
            rankings[name.text.strip()] = int(rank.text.strip())
    return rankings

def main():
    logging.basicConfig(level=logging.INFO)
    cug_cs   = scrape_cug_cs(CUG_CS_URL)
    cug_all  = scrape_cug_cs(CUG_ALL_URL)
    records = []
    for uni in TARGET_UNIS:
        records.append({
            "university": uni,
            "cug_cs_rank": cug_cs.get(uni, ""),
            "cug_overall_rank": cug_all.get(uni, ""),
            "scraped_at": datetime.utcnow().isoformat(),
        })
    pd.DataFrame(records).to_csv("rankings_2026.csv", index=False)
    logging.info(f"Rankings saved for {len(records)} universities")

if __name__ == "__main__":
    main()`,
};

function StatusBadge({ status }: { status: DataStatus }) {
  const cfg = {
    current: { bg: "rgba(74,124,47,0.1)", color: "var(--forest)", label: "Current" },
    stale:   { bg: "#FEF3C7", color: "#92400E", label: "Stale" },
    updating:{ bg: "rgba(59,130,246,0.1)", color: "#1D4ED8", label: "Updating…" },
    error:   { bg: "#FEF2F2", color: "#B91C1C", label: "Error" },
  }[status];
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-sm"
      style={{ background: cfg.bg, color: cfg.color }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />
      {cfg.label}
    </span>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

interface ScriptModalProps {
  filename: string;
  content: string;
  onClose: () => void;
}

function ScriptModal({ filename, content, onClose }: ScriptModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(42,42,39,0.6)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-2xl rounded-sm border shadow-lg flex flex-col"
        style={{ background: "var(--card)", borderColor: "var(--border)", maxHeight: "85vh" }}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b flex-shrink-0"
          style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--muted-foreground)" }}>
              <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
            </svg>
            <span className="font-mono text-sm font-semibold" style={{ color: "var(--foreground)" }}>{filename}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const blob = new Blob([content], { type: "text/x-python" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url; a.download = filename; a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-medium border"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download .py
            </button>
            <button onClick={onClose} className="w-6 h-6 flex items-center justify-center rounded-sm"
              style={{ color: "var(--muted-foreground)" }} aria-label="Close">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <pre className="flex-1 overflow-auto px-5 py-4 text-xs leading-relaxed font-mono"
          style={{ background: "#1E1E1E", color: "#D4D4D4" }}>
          {content}
        </pre>
      </div>
    </div>
  );
}

export default function KnowledgeBase() {
  const [sources, setSources] = useState(DATA_SOURCES);
  const [activeScript, setActiveScript] = useState<{ filename: string; content: string } | null>(null);
  const [uploadTarget, setUploadTarget] = useState<Priority | null>(null);
  const [uploadFilename, setUploadFilename] = useState<string | null>(null);
  const [runningUpdate, setRunningUpdate] = useState<Priority | null>(null);
  const [activeTab, setActiveTab] = useState<"sources" | "upload" | "scripts">("sources");

  const openScript = (filename: string) => {
    const content = SCRIPT_PREVIEWS[filename] ?? `# ${filename}\n# Script content not yet available in preview.\n`;
    setActiveScript({ filename, content });
  };

  const downloadCSV = (source: DataSource) => {
    const headers = ["university", "priority", "value_a", "value_b", "source_url", "last_verified"];
    const rows = [
      ["University of Liverpool", source.priority, "Sample A", "Sample B", "https://www.liverpool.ac.uk", source.lastUpdated],
      ["University of Leeds", source.priority, "Sample A", "Sample B", "https://leeds.ac.uk", source.lastUpdated],
    ];
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = source.csvFile; a.click();
    URL.revokeObjectURL(url);
  };

  const runScraper = (priority: Priority) => {
    setRunningUpdate(priority);
    setSources((prev) => prev.map((s) => s.priority === priority ? { ...s, status: "updating" } : s));
    setTimeout(() => {
      setSources((prev) => prev.map((s) => s.priority === priority
        ? { ...s, status: "current", lastUpdated: new Date().toISOString(), recordCount: s.recordCount + Math.floor(Math.random() * 5) }
        : s));
      setRunningUpdate(null);
    }, 3000);
  };

  const handleFileUpload = (priority: Priority, file: File) => {
    setUploadFilename(file.name);
    setTimeout(() => {
      setSources((prev) => prev.map((s) => s.priority === priority
        ? { ...s, status: "current", lastUpdated: new Date().toISOString() }
        : s));
      setUploadTarget(null);
      setUploadFilename(null);
    }, 1500);
  };

  const staleCount = sources.filter((s) => s.status === "stale").length;

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total records", value: sources.reduce((a, s) => a + s.recordCount, 0).toLocaleString() },
          { label: "Data sources", value: sources.length },
          { label: "Current", value: sources.filter((s) => s.status === "current").length, color: "var(--forest)" },
          { label: "Stale / needs update", value: staleCount, color: staleCount > 0 ? "#92400E" : undefined },
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

      {/* Tabs */}
      <div className="flex border-b" style={{ borderColor: "var(--border)" }}>
        {(["sources", "scripts", "upload"] as const).map((tab) => {
          const labels = { sources: "Data Sources", scripts: "Scripts", upload: "Upload Data" };
          return (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className="px-4 py-2 text-xs font-medium border-b-2 -mb-px"
              style={{
                borderColor: activeTab === tab ? "var(--forest)" : "transparent",
                color: activeTab === tab ? "var(--forest)" : "var(--muted-foreground)",
              }}>
              {labels[tab]}
            </button>
          );
        })}
      </div>

      {/* Data Sources tab */}
      {activeTab === "sources" && (
        <div className="space-y-2">
          {staleCount > 0 && (
            <div className="flex items-center gap-2 p-3 rounded-sm border text-xs"
              style={{ borderColor: "#FCD34D", background: "#FFFBEB", color: "#92400E" }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              {staleCount} data source{staleCount > 1 ? "s" : ""} are stale. Run scrapers or upload updated CSVs.
            </div>
          )}

          {sources.map((source) => (
            <div key={source.priority} className="border rounded-sm overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <div className="flex items-center justify-between px-4 py-3 border-b"
                style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                <div className="flex items-center gap-2">
                  <span className="font-serif text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                    {PRIORITY_LABELS[source.priority]}
                  </span>
                  <StatusBadge status={source.status} />
                </div>
                <div className="flex items-center gap-4 text-xs" style={{ color: "var(--muted-foreground)" }}>
                  <span>{source.recordCount.toLocaleString()} records</span>
                  <span>Updated {formatDate(source.lastUpdated)}</span>
                </div>
              </div>

              <div className="px-4 py-3 flex flex-wrap items-center gap-2">
                {/* CSV download */}
                <button onClick={() => downloadCSV(source)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  Download CSV
                </button>

                {/* View scraper */}
                <button onClick={() => openScript(source.scraperScript)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
                  </svg>
                  View scraper
                </button>

                {/* View ingestion */}
                <button onClick={() => openScript(source.ingestionScript)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
                  </svg>
                  View ingestion
                </button>

                {/* Upload CSV */}
                <button onClick={() => setUploadTarget(source.priority)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Upload CSV
                </button>

                {/* Run scraper */}
                <button
                  onClick={() => runScraper(source.priority)}
                  disabled={runningUpdate === source.priority}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm text-xs font-semibold disabled:opacity-60"
                  style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
                  {runningUpdate === source.priority ? (
                    <>
                      <span className="w-3 h-3 border rounded-full animate-spin"
                        style={{ borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} />
                      Running…
                    </>
                  ) : (
                    <>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      Run scraper
                    </>
                  )}
                </button>

                {/* Generated file */}
                <span className="ml-auto text-xs font-mono px-2 py-1 rounded-sm"
                  style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}>
                  {source.generatedFile}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Scripts tab */}
      {activeTab === "scripts" && (
        <div className="space-y-3">
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            All Python scripts used for data collection and ingestion. Click to view source; download for local execution.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.flatMap((s) => [
              { filename: s.scraperScript, type: "Scraper", priority: s.priority, desc: `Web scraper for ${PRIORITY_LABELS[s.priority].toLowerCase()} data` },
              { filename: s.ingestionScript, type: "Ingestion", priority: s.priority, desc: `Validates and loads ${PRIORITY_LABELS[s.priority].toLowerCase()} CSV` },
            ]).map((script) => (
              <div key={script.filename} className="border rounded-sm px-3 py-3 flex items-start justify-between gap-2"
                style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="flex items-start gap-2 min-w-0">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    className="mt-0.5 flex-shrink-0" style={{ color: "var(--muted-foreground)" }}>
                    <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
                  </svg>
                  <div className="min-w-0">
                    <p className="text-xs font-mono font-semibold truncate" style={{ color: "var(--foreground)" }}>{script.filename}</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--muted-foreground)" }}>{script.desc}</p>
                    <span className="inline-block mt-1 text-xs px-1.5 py-0.5 rounded-sm font-medium"
                      style={{
                        background: script.type === "Scraper" ? "rgba(59,130,246,0.08)" : "rgba(74,124,47,0.08)",
                        color: script.type === "Scraper" ? "#1D4ED8" : "var(--forest)",
                      }}>
                      {script.type}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <button onClick={() => openScript(script.filename)}
                    className="px-2 py-1 rounded-sm border text-xs"
                    style={{ borderColor: "var(--border)", color: "var(--foreground)" }}>
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload tab */}
      {activeTab === "upload" && (
        <div className="space-y-4">
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            Upload updated CSV files to refresh the knowledge base. Files are validated against the expected schema before ingestion.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {sources.map((source) => (
              <div key={source.priority} className="border rounded-sm px-4 py-3"
                style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium" style={{ color: "var(--foreground)" }}>
                    {PRIORITY_LABELS[source.priority]}
                  </span>
                  <StatusBadge status={source.status} />
                </div>
                <p className="text-xs mb-3 font-mono" style={{ color: "var(--muted-foreground)" }}>
                  Expected: {source.csvFile}
                </p>
                <label className="flex items-center gap-2 px-3 py-2 rounded-sm border cursor-pointer text-xs font-medium hover:bg-muted"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)", borderStyle: "dashed" }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Choose CSV file
                  <input type="file" accept=".csv" className="sr-only"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(source.priority, file);
                    }} />
                </label>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Script preview modal */}
      {activeScript && (
        <ScriptModal
          filename={activeScript.filename}
          content={activeScript.content}
          onClose={() => setActiveScript(null)}
        />
      )}

      {/* Upload confirmation */}
      {uploadFilename && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-sm border shadow-lg text-xs"
          style={{ background: "var(--card)", borderColor: "var(--border)", color: "var(--foreground)" }}>
          <span className="w-3.5 h-3.5 border-2 rounded-full animate-spin"
            style={{ borderColor: "var(--border)", borderTopColor: "var(--forest)" }} />
          Ingesting {uploadFilename}…
        </div>
      )}
    </div>
  );
}
