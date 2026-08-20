import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const API_AUTH_KEY = import.meta.env.VITE_API_AUTH_KEY ?? "openwebui-local-key";

type MetricKey =
  | "avg_confidence_score"
  | "avg_faithfulness"
  | "avg_answer_relevancy"
  | "avg_context_precision"
  | "avg_context_recall";

interface EvaluationData {
  summaryAvailable: boolean;
  summary: Partial<Record<MetricKey | "total_questions" | "abstain_count", number>>;
  summaryFile: { exists: boolean; updatedAt: string | null; sizeBytes: number };
  goldenDataset: { exists: boolean; updatedAt: string | null; sizeBytes: number; rows: number };
  chartFile: { exists: boolean; updatedAt: string | null; sizeBytes: number };
  resultFiles: { name: string; sizeBytes: number; updatedAt: string }[];
}

interface AuditSummary {
  total_rows: number;
  avg_coverage_pct: number;
  below_60_count: number;
}

interface PrioritySummary {
  priority: string;
  count: number;
  avg_coverage_pct: number;
  below_60: number;
}

interface LowCoverageRow {
  university: string;
  priority: string;
  coverage_pct: number;
  programme_title: string;
  sql_missing_fields: string;
  kb_missing_fields: string;
}

interface AuditData {
  auditAvailable: boolean;
  summary: AuditSummary;
  prioritySummary: PrioritySummary[];
  lowestCoverageRows: LowCoverageRow[];
  auditFile: { exists: boolean; updatedAt: string | null; sizeBytes: number; rows: number };
  auditFiles: { name: string; sizeBytes: number; updatedAt: string }[];
}

type ActivePanel = "evaluation" | "audit";

function authHeaders(contentType = true): HeadersInit {
  return {
    Authorization: `Bearer ${API_AUTH_KEY}`,
    ...(contentType ? { "Content-Type": "application/json" } : {}),
  };
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; error?: string };
    return payload.detail ?? payload.error ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function downloadCsv(url: string, filename: string): Promise<void> {
  const response = await fetch(url, { headers: authHeaders(false) });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(blobUrl);
}

function scorePercent(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0%";
  return `${Math.max(0, Math.min(100, value * 100)).toFixed(1)}%`;
}

function readableBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

export default function ModelEvaluation() {
  const [activePanel, setActivePanel] = useState<ActivePanel>("evaluation");
  const [evaluationData, setEvaluationData] = useState<EvaluationData | null>(null);
  const [auditData, setAuditData] = useState<AuditData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [commandOutput, setCommandOutput] = useState<string | null>(null);
  const [goldenFile, setGoldenFile] = useState<File | null>(null);
  const [auditFile, setAuditFile] = useState<File | null>(null);

  const loadAll = async () => {
    const [evaluationResponse, auditResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/api/admin/evaluation`, { headers: authHeaders(false) }),
      fetch(`${API_BASE_URL}/api/admin/audit`, { headers: authHeaders(false) }),
    ]);

    if (!evaluationResponse.ok) throw new Error(await parseError(evaluationResponse));
    if (!auditResponse.ok) throw new Error(await parseError(auditResponse));

    setEvaluationData((await evaluationResponse.json()) as EvaluationData);
    setAuditData((await auditResponse.json()) as AuditData);
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        await loadAll();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load model evaluation dashboard.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const metricCards = useMemo(() => {
    const summary = evaluationData?.summary ?? {};
    return [
      { key: "avg_confidence_score", label: "Confidence", value: summary.avg_confidence_score },
      { key: "avg_faithfulness", label: "Faithfulness", value: summary.avg_faithfulness },
      { key: "avg_answer_relevancy", label: "Answer relevancy", value: summary.avg_answer_relevancy },
      { key: "avg_context_precision", label: "Context precision", value: summary.avg_context_precision },
      { key: "avg_context_recall", label: "Context recall", value: summary.avg_context_recall },
    ];
  }, [evaluationData]);

  const runEvaluation = async () => {
    setActionLoading(true);
    setError(null);
    setInfo(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/evaluation/run`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response));
      const payload = (await response.json()) as {
        ok: boolean;
        error?: string;
        stdout?: string;
        stderr?: string;
        dashboard: EvaluationData;
      };
      if (!payload.ok) throw new Error(payload.error ?? "Evaluation script failed.");
      setEvaluationData(payload.dashboard);
      setCommandOutput(payload.stdout?.trim() || null);
      setInfo("Evaluation run completed successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run evaluation.");
    } finally {
      setActionLoading(false);
    }
  };

  const runAudit = async () => {
    setActionLoading(true);
    setError(null);
    setInfo(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/audit/run`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response));
      const payload = (await response.json()) as {
        ok: boolean;
        error?: string;
        stdout?: string;
        stderr?: string;
        dashboard: AuditData;
      };
      if (!payload.ok) throw new Error(payload.error ?? "Data audit script failed.");
      setAuditData(payload.dashboard);
      setCommandOutput(payload.stdout?.trim() || null);
      setInfo("Data audit run completed successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run data audit.");
    } finally {
      setActionLoading(false);
    }
  };

  const uploadGoldenDataset = async () => {
    if (!goldenFile) {
      setError("Select a CSV file before uploading.");
      return;
    }
    setActionLoading(true);
    setError(null);
    setInfo(null);
    try {
      const formData = new FormData();
      formData.append("file", goldenFile);
      const response = await fetch(`${API_BASE_URL}/api/admin/evaluation/upload-golden`, {
        method: "POST",
        headers: { Authorization: `Bearer ${API_AUTH_KEY}` },
        body: formData,
      });
      if (!response.ok) throw new Error(await parseError(response));
      const payload = (await response.json()) as { ok: boolean; error?: string; dashboard: EvaluationData };
      if (!payload.ok) throw new Error(payload.error ?? "Golden dataset upload failed.");
      setEvaluationData(payload.dashboard);
      setGoldenFile(null);
      setInfo("Golden dataset uploaded and replaced.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload golden dataset.");
    } finally {
      setActionLoading(false);
    }
  };

  const uploadAuditDataset = async () => {
    if (!auditFile) {
      setError("Select a CSV file before uploading.");
      return;
    }
    setActionLoading(true);
    setError(null);
    setInfo(null);
    try {
      const formData = new FormData();
      formData.append("file", auditFile);
      const response = await fetch(`${API_BASE_URL}/api/admin/audit/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${API_AUTH_KEY}` },
        body: formData,
      });
      if (!response.ok) throw new Error(await parseError(response));
      const payload = (await response.json()) as { ok: boolean; error?: string; dashboard: AuditData };
      if (!payload.ok) throw new Error(payload.error ?? "Audit file upload failed.");
      setAuditData(payload.dashboard);
      setAuditFile(null);
      setInfo("Audit CSV uploaded and replaced.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload audit CSV.");
    } finally {
      setActionLoading(false);
    }
  };

  const refreshData = async () => {
    setLoading(true);
    setError(null);
    try {
      await loadAll();
      setInfo("Dashboard data refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh dashboard.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 rounded-sm border text-sm" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
        Loading evaluation dashboard...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActivePanel("evaluation")}
          className="px-3 py-1.5 text-xs rounded-sm border"
          style={{
            borderColor: "var(--border)",
            background: activePanel === "evaluation" ? "rgba(45,80,22,0.08)" : "var(--card)",
            color: activePanel === "evaluation" ? "var(--forest)" : "var(--foreground)",
          }}
        >
          Model Evaluation
        </button>
        <button
          onClick={() => setActivePanel("audit")}
          className="px-3 py-1.5 text-xs rounded-sm border"
          style={{
            borderColor: "var(--border)",
            background: activePanel === "audit" ? "rgba(45,80,22,0.08)" : "var(--card)",
            color: activePanel === "audit" ? "var(--forest)" : "var(--foreground)",
          }}
        >
          Data Audit
        </button>
        <button
          onClick={refreshData}
          className="ml-auto px-3 py-1.5 text-xs rounded-sm border"
          style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
          disabled={actionLoading}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-sm border text-xs" style={{ borderColor: "#fca5a5", background: "#fef2f2", color: "#991b1b" }}>
          {error}
        </div>
      )}
      {info && (
        <div className="p-3 rounded-sm border text-xs" style={{ borderColor: "#86efac", background: "#f0fdf4", color: "#166534" }}>
          {info}
        </div>
      )}
      {commandOutput && (
        <pre className="p-3 rounded-sm border text-xs overflow-x-auto whitespace-pre-wrap" style={{ borderColor: "var(--border)", background: "var(--background)", color: "var(--foreground)" }}>
          {commandOutput}
        </pre>
      )}

      {activePanel === "evaluation" && evaluationData && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Run Evaluation</h3>
              <p className="text-xs mb-3" style={{ color: "var(--muted-foreground)" }}>
                Uses [golden_dataset.csv](/C:/Users/ANAS/admissions-assistant-run/golden_dataset.csv) and runs [evaluator.py](/C:/Users/ANAS/admissions-assistant-run/evaluator.py).
              </p>
              <button
                onClick={runEvaluation}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs rounded-sm"
                style={{ background: "var(--forest)", color: "#fff" }}
              >
                {actionLoading ? "Running..." : "Run Evaluation Script"}
              </button>
            </div>

            <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Golden Dataset Override</h3>
              <p className="text-xs mb-2" style={{ color: "var(--muted-foreground)" }}>
                Upload a CSV to replace [golden_dataset.csv](/C:/Users/ANAS/admissions-assistant-run/golden_dataset.csv) for real-time evaluation.
              </p>
              <input
                type="file"
                accept=".csv"
                onChange={(event) => setGoldenFile(event.target.files?.[0] ?? null)}
                className="block w-full text-xs mb-2"
              />
              <button
                onClick={uploadGoldenDataset}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs rounded-sm border"
                style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
              >
                Upload & Replace Dataset
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total questions" value={String(evaluationData.summary.total_questions ?? 0)} />
            <StatCard label="Abstain count" value={String(evaluationData.summary.abstain_count ?? 0)} />
            <StatCard label="Golden rows" value={String(evaluationData.goldenDataset.rows)} />
            <StatCard label="Summary updated" value={evaluationData.summaryFile.updatedAt ?? "—"} />
          </div>

          <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>Evaluation Metrics</h3>
              <button
                onClick={() => downloadCsv(`${API_BASE_URL}/api/admin/evaluation/download-summary`, "evaluation_summary.csv")}
                className="px-2.5 py-1 text-xs rounded-sm border"
                style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
              >
                Download Summary CSV
              </button>
            </div>

            {!evaluationData.summaryAvailable ? (
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>No summary generated yet. Run the evaluation script first.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {metricCards.map((metric) => {
                  const score = typeof metric.value === "number" ? Math.max(0, Math.min(1, metric.value)) : 0;
                  return (
                    <div key={metric.key} className="rounded-sm border p-2" style={{ borderColor: "var(--border)" }}>
                      <div className="flex items-center justify-between text-xs mb-1" style={{ color: "var(--foreground)" }}>
                        <span>{metric.label}</span>
                        <span>{scorePercent(metric.value)}</span>
                      </div>
                      <div className="h-2 rounded-sm" style={{ background: "var(--muted)" }}>
                        <div className="h-2 rounded-sm" style={{ width: `${score * 100}%`, background: "var(--forest)" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Evaluation Files</h3>
            <ul className="space-y-1 text-xs" style={{ color: "var(--muted-foreground)" }}>
              {evaluationData.resultFiles.length === 0 && <li>No evaluation output files found.</li>}
              {evaluationData.resultFiles.map((file) => (
                <li key={file.name} className="flex items-center justify-between gap-2">
                  <span>{file.name}</span>
                  <span>{readableBytes(file.sizeBytes)} · {file.updatedAt}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {activePanel === "audit" && auditData && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Run Data Audit</h3>
              <p className="text-xs mb-3" style={{ color: "var(--muted-foreground)" }}>
                Runs [audit_priority_data.py](/C:/Users/ANAS/admissions-assistant-run/audit_priority_data.py) and refreshes [priority_data_audit.csv](/C:/Users/ANAS/admissions-assistant-run/priority_data_audit.csv).
              </p>
              <button
                onClick={runAudit}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs rounded-sm"
                style={{ background: "var(--forest)", color: "#fff" }}
              >
                {actionLoading ? "Running..." : "Run Audit Script"}
              </button>
            </div>

            <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Audit CSV Override</h3>
              <p className="text-xs mb-2" style={{ color: "var(--muted-foreground)" }}>
                Upload a replacement CSV for [priority_data_audit.csv](/C:/Users/ANAS/admissions-assistant-run/priority_data_audit.csv).
              </p>
              <input
                type="file"
                accept=".csv"
                onChange={(event) => setAuditFile(event.target.files?.[0] ?? null)}
                className="block w-full text-xs mb-2"
              />
              <button
                onClick={uploadAuditDataset}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs rounded-sm border"
                style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
              >
                Upload & Replace Audit CSV
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <StatCard label="Audit rows" value={String(auditData.summary.total_rows)} />
            <StatCard label="Average coverage" value={`${auditData.summary.avg_coverage_pct}%`} />
            <StatCard label="Below 60%" value={String(auditData.summary.below_60_count)} />
            <StatCard label="Audit updated" value={auditData.auditFile.updatedAt ?? "—"} />
          </div>

          <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>Priority Coverage Summary</h3>
              <button
                onClick={() => downloadCsv(`${API_BASE_URL}/api/admin/audit/download`, "priority_data_audit.csv")}
                className="px-2.5 py-1 text-xs rounded-sm border"
                style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
              >
                Download Audit CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ color: "var(--muted-foreground)" }}>
                    <th className="text-left py-1">Priority</th>
                    <th className="text-left py-1">Universities</th>
                    <th className="text-left py-1">Avg coverage</th>
                    <th className="text-left py-1">Below 60%</th>
                  </tr>
                </thead>
                <tbody>
                  {auditData.prioritySummary.map((row) => (
                    <tr key={row.priority} style={{ color: "var(--foreground)" }}>
                      <td className="py-1 pr-2">{row.priority}</td>
                      <td className="py-1 pr-2">{row.count}</td>
                      <td className="py-1 pr-2">{row.avg_coverage_pct}%</td>
                      <td className="py-1 pr-2">{row.below_60}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Lowest Coverage Rows</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ color: "var(--muted-foreground)" }}>
                    <th className="text-left py-1">University</th>
                    <th className="text-left py-1">Priority</th>
                    <th className="text-left py-1">Coverage</th>
                    <th className="text-left py-1">Programme</th>
                  </tr>
                </thead>
                <tbody>
                  {auditData.lowestCoverageRows.map((row, index) => (
                    <tr key={`${row.university}-${row.priority}-${index}`} style={{ color: "var(--foreground)" }}>
                      <td className="py-1 pr-2">{row.university || "—"}</td>
                      <td className="py-1 pr-2">{row.priority || "—"}</td>
                      <td className="py-1 pr-2">{row.coverage_pct}%</td>
                      <td className="py-1 pr-2">{row.programme_title || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>Audit Files in Directory</h3>
            <ul className="space-y-1 text-xs" style={{ color: "var(--muted-foreground)" }}>
              {auditData.auditFiles.length === 0 && <li>No audit files found.</li>}
              {auditData.auditFiles.map((file) => (
                <li key={file.name} className="flex items-center justify-between gap-2">
                  <span>{file.name}</span>
                  <span>{readableBytes(file.sizeBytes)} · {file.updatedAt}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border p-3" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
      <p className="text-xs mb-1" style={{ color: "var(--muted-foreground)" }}>{label}</p>
      <p className="text-sm font-semibold break-all" style={{ color: "var(--foreground)" }}>{value}</p>
    </div>
  );
}
