import os
import json
import csv
import time
import uuid
import sys
import sqlite3
import threading
import subprocess
from typing import Any, Dict, Iterator, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

import admin_kb
import auth_db


APP_TITLE = "Admissions Assistant API"
APP_VERSION = "1.0.0"
MODEL_ID = "admissions-rag"
UI_TITLE = "Admissions Assistant"
BASELINE_UNIVERSITY = "University of Liverpool"
BASELINE_PROGRAMME = "Computer Science BSc"
ROOT = os.path.dirname(os.path.abspath(__file__))
EVALUATION_SCRIPT = "evaluator.py"
DATA_AUDIT_SCRIPT = "audit_priority_data.py"


def _force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


_force_utf8_stdio()


def _load_summary_metrics() -> Dict[str, Any]:
        summary_path = os.getenv("EVALUATION_SUMMARY_PATH", "evaluation_summary.csv")
        if not os.path.exists(summary_path):
                return {
                        "available": False,
                        "source": summary_path,
                }

        try:
                with open(summary_path, "r", encoding="utf-8") as handle:
                        lines = [line.strip() for line in handle.readlines() if line.strip()]
                if len(lines) < 2:
                        return {"available": False, "source": summary_path}

                headers = lines[0].split(",")
                values = lines[1].split(",")
                metrics = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
                metrics["available"] = True
                metrics["source"] = summary_path
                return metrics
        except Exception as exc:
                return {
                        "available": False,
                        "source": summary_path,
                        "error": str(exc),
                }


def _resolve_workspace_file(filename: str) -> str:
    if os.path.isabs(filename):
        return filename
    return os.path.join(ROOT, filename)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _file_meta(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"exists": False, "path": path, "updatedAt": None, "sizeBytes": 0}
    return {
        "exists": True,
        "path": path,
        "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path))),
        "sizeBytes": os.path.getsize(path),
    }


def _csv_row_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def _read_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _run_workspace_script(script_name: str, timeout: int = 300) -> Dict[str, Any]:
    script_path = _resolve_workspace_file(script_name)
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"{script_name} was not found in the project directory."}

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{script_name} timed out after {timeout} seconds."}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-5000:],
        "stderr": (proc.stderr or "")[-5000:],
    }


def _list_matching_files(prefixes: List[str]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(ROOT)):
        if not os.path.isfile(os.path.join(ROOT, name)):
            continue
        lower = name.lower()
        if any(lower.startswith(prefix.lower()) for prefix in prefixes):
            path = os.path.join(ROOT, name)
            matches.append({
                "name": name,
                "sizeBytes": os.path.getsize(path),
                "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path))),
            })
    return matches


def _evaluation_dashboard_payload() -> Dict[str, Any]:
    summary_path = _resolve_workspace_file("evaluation_summary.csv")
    summary_rows = _read_csv_rows(summary_path)
    summary = dict(summary_rows[0]) if summary_rows else {}
    for key in [
        "avg_confidence_score",
        "avg_faithfulness",
        "avg_answer_relevancy",
        "avg_context_precision",
        "avg_context_recall",
    ]:
        numeric_value = _safe_float(summary.get(key))
        if numeric_value is not None:
            summary[key] = numeric_value
    for key in ["total_questions", "abstain_count"]:
        try:
            summary[key] = int(float(summary.get(key, 0)))
        except (TypeError, ValueError):
            summary[key] = 0

    return {
        "summaryAvailable": bool(summary_rows),
        "summary": summary,
        "summaryFile": _file_meta(summary_path),
        "goldenDataset": {
            **_file_meta(_resolve_workspace_file("golden_dataset.csv")),
            "rows": _csv_row_count(_resolve_workspace_file("golden_dataset.csv")),
        },
        "chartFile": _file_meta(_resolve_workspace_file("evaluation_summary.png")),
        "resultFiles": _list_matching_files(["evaluation_"]),
    }


def _audit_dashboard_payload() -> Dict[str, Any]:
    audit_csv_path = _resolve_workspace_file("priority_data_audit.csv")
    rows = _read_csv_rows(audit_csv_path)
    priority_summary: Dict[str, Dict[str, Any]] = {}
    overall_coverage_values: List[float] = []
    for row in rows:
        priority = str(row.get("priority", "")).strip() or "Unknown"
        coverage = _safe_float(row.get("coverage_pct"))
        if coverage is None:
            continue
        overall_coverage_values.append(coverage)
        bucket = priority_summary.setdefault(priority, {"count": 0, "avg_coverage_pct": 0.0, "below_60": 0, "_sum": 0.0})
        bucket["count"] += 1
        bucket["_sum"] += coverage
        if coverage < 60:
            bucket["below_60"] += 1

    for bucket in priority_summary.values():
        count = bucket["count"]
        bucket["avg_coverage_pct"] = round((bucket["_sum"] / count) if count else 0.0, 1)
        del bucket["_sum"]

    low_coverage_rows = []
    for row in rows:
        coverage = _safe_float(row.get("coverage_pct"))
        if coverage is None:
            continue
        low_coverage_rows.append({
            "university": row.get("university", ""),
            "priority": row.get("priority", ""),
            "coverage_pct": coverage,
            "programme_title": row.get("programme_title", ""),
            "sql_missing_fields": row.get("sql_missing_fields", ""),
            "kb_missing_fields": row.get("kb_missing_fields", ""),
        })
    low_coverage_rows.sort(key=lambda item: item["coverage_pct"])

    return {
        "auditAvailable": bool(rows),
        "summary": {
            "total_rows": len(rows),
            "avg_coverage_pct": round(sum(overall_coverage_values) / len(overall_coverage_values), 1) if overall_coverage_values else 0.0,
            "below_60_count": sum(1 for value in overall_coverage_values if value < 60),
        },
        "prioritySummary": [
            {
                "priority": priority,
                "count": values["count"],
                "avg_coverage_pct": values["avg_coverage_pct"],
                "below_60": values["below_60"],
            }
            for priority, values in sorted(priority_summary.items())
        ],
        "lowestCoverageRows": low_coverage_rows[:12],
        "auditFile": {
            **_file_meta(audit_csv_path),
            "rows": len(rows),
        },
        "auditFiles": _list_matching_files(["priority_data_audit", "audit_"]),
    }


def _render_ui_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{UI_TITLE}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Lora:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
        :root {{
            --paper: #F9F8F4;
            --paper-deep: #EAE8E0;
            --ink: #2A2A27;
            --soft: #F2F0E8;
            --rule: #DDD9CE;
            --muted: #7A7A72;
            --shadow: rgba(42, 42, 39, 0.10);
            --accent: #00205B;
            --accent-strong: #00205B;
            --accent-soft: rgba(0, 32, 91, 0.10);
            --uol-red: #E31C3D;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: 'Source Sans 3', system-ui, sans-serif;
            background: var(--paper);
            color: var(--ink);
            min-height: 100vh;
            line-height: 1.45;
            font-size: 14px;
        }}
        .frame {{
            max-width: 1340px;
            margin: 0 auto;
            padding: 0;
        }}
        .board {{
            position: relative;
            background: transparent;
            padding: 0;
        }}
        .board-stripe {{ height: 4px; background: var(--uol-red); }}
        .board::before, .board::after {{ content: none; }}
        .title-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            margin: 0;
            padding: 14px 20px;
            background: var(--accent-strong);
        }}
        .title {{
            text-align: left;
            font-family: 'Lora', Georgia, serif;
            font-size: 15px;
            letter-spacing: 0.02em;
            font-weight: 700;
            margin: 0;
            color: #FFFFFF;
            text-transform: uppercase;
            line-height: 1.25;
        }}
        .subtitle {{
            margin: 2px 0 0;
            color: var(--muted);
            font-size: 12px;
        }}
        .title-brand {{ display: flex; align-items: center; gap: 10px; }}
        .brand-mark {{ color: #FFFFFF; flex-shrink: 0; }}
        .header-actions {{ display: flex; align-items: center; gap: 8px; }}
        .icon-button {{
            width: 28px; height: 28px; border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            border: 0; background: transparent; color: rgba(255,255,255,0.85);
            cursor: pointer; padding: 0;
        }}
        .icon-button:hover {{ background: rgba(255,255,255,0.12); }}
        .user-chip {{
            display: inline-flex; align-items: center; gap: 6px;
            font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.9);
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: #FFFFFF;
            background: rgba(255,255,255,0.15);
            border-radius: 999px;
            padding: 4px 10px;
        }}
        .status-badge .dot {{ width: 6px; height: 6px; border-radius: 50%; background: #FFFFFF; }}
        .layout {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
            min-height: 72vh;
            padding: 16px 20px 20px;
        }}
        .citations-col {{ grid-column: 1 / -1; }}
        @media (min-width: 760px) {{
            .layout {{ grid-template-columns: 1fr 1fr; }}
        }}
        @media (min-width: 1100px) {{
            .layout {{ grid-template-columns: 0.95fr 1.65fr 0.8fr; }}
            .citations-col {{ grid-column: auto; }}
        }}
        .pane {{
            position: relative;
            border: 1px solid var(--rule);
            border-radius: 6px;
            background: #FFFFFF;
            padding: 16px;
            overflow: hidden;
        }}
        .pane::after {{ content: none; }}
        .section-title {{
            margin: 0 0 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--rule);
            font-family: 'Lora', Georgia, serif;
            font-size: 15px;
            font-weight: 600;
            color: var(--ink);
            letter-spacing: 0;
            text-transform: none;
        }}
        .label {{
            display: block;
            font-size: 12px;
            margin-bottom: 9px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }}
        .field, .textarea, .select {{
            width: 100%;
            border: 1px solid var(--rule);
            border-radius: 4px;
            background: #FFFFFF;
            color: var(--ink);
            padding: 8px 10px;
            font: inherit;
            font-size: 13px;
            outline: none;
        }}
        .field:focus, .textarea:focus, .select:focus {{ border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }}
        .field, .select {{ height: 36px; }}
        .field[readonly] {{ background: var(--soft); color: var(--muted); }}
        .textarea {{ min-height: 110px; resize: vertical; line-height: 1.55; }}
        .stack {{ display: grid; gap: 14px; }}
        .control-group {{ margin-bottom: 16px; }}
        .checkboxes {{ display: grid; gap: 8px; margin-top: 6px; }}
        .checkboxes label {{ display: flex; align-items: center; gap: 8px; font-size: 13px; line-height: 1.4; cursor: pointer; }}
        .checkboxes input {{ width: 15px; height: 15px; accent-color: var(--accent); }}
        .dropdown-arrow {{
            position: relative;
        }}
        .dropdown-arrow::after {{
            content: "▼";
            position: absolute;
            right: 12px;
            top: 32px;
            font-size: 9px;
            color: var(--muted);
            pointer-events: none;
        }}
        .button-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }}
        .button {{
            border: 1px solid var(--rule);
            border-radius: 4px;
            background: #FFFFFF;
            color: var(--ink);
            padding: 9px 16px;
            font-weight: 600;
            letter-spacing: 0;
            text-transform: none;
            font-size: 13px;
            cursor: pointer;
        }}
        .button.primary {{ background: var(--accent-strong); color: #F9F8F4; border-color: var(--accent-strong); }}
        .button:hover {{ filter: brightness(0.97); }}
        .button:disabled {{ opacity: 0.55; cursor: not-allowed; }}
        .conversation {{
            min-height: 260px;
            padding: 0;
            background: transparent;
            border: 0;
        }}
        .answer-card {{
            border: 0;
            border-radius: 0;
            background: transparent;
            padding: 0;
            min-height: 160px;
            white-space: pre-wrap;
            line-height: 1.5;
            font-size: 13px;
        }}
        .summary-box {{ padding: 0; background: transparent; border: 0; }}
        .answer-card .muted {{ color: var(--muted); }}
        .empty-state {{ display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 48px 12px; color: var(--muted); }}
        .empty-state strong {{ display: block; color: var(--ink); font-weight: 600; margin-bottom: 4px; font-size: 13px; }}
        .loading-state {{ display: grid; gap: 10px; }}
        .loading-row {{ display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); font-weight: 600; }}
        .spinner {{ width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--rule); border-top-color: var(--accent); animation: spin 0.8s linear infinite; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .skeleton-row {{ height: 42px; border-radius: 4px; background: linear-gradient(90deg, var(--soft) 25%, var(--paper-deep) 50%, var(--soft) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; }}
        @keyframes shimmer {{ 0% {{ background-position: -200% 0; }} 100% {{ background-position: 200% 0; }} }}
        .error-banner {{
            display: flex; gap: 8px; align-items: flex-start;
            border: 1px solid #FCA5A5; background: #FEF2F2; color: #B91C1C;
            border-radius: 4px; padding: 10px 12px; font-size: 13px; margin-bottom: 10px;
        }}
        .limited-banner {{
            display: flex; gap: 8px; align-items: flex-start;
            border: 1px solid #FCD34D; background: #FFFBEB; color: #92400E;
            border-radius: 4px; padding: 10px 12px; font-size: 12px; margin-bottom: 10px;
        }}
        .summary-content {{ display: grid; gap: 8px; }}
        .priority-section {{
            border: 1px solid var(--rule);
            border-left: 3px solid var(--accent);
            border-radius: 4px;
            background: var(--paper);
            padding: 8px 10px;
        }}
        .priority-heading-row {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 0 0 4px; }}
        .priority-heading {{ margin: 0; font-family: 'Lora', Georgia, serif; font-size: 14px; font-weight: 600; color: var(--ink); }}
        .priority-detail {{ margin: 0; white-space: normal; font-size: 13px; }}
        .priority-winner {{ margin: 5px 0 0; font-weight: 600; color: var(--ink); font-size: 12px; }}
        .winner-badge {{
            display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 700;
            padding: 2px 8px; border-radius: 999px; background: var(--accent-soft); color: var(--accent-strong);
            white-space: nowrap; flex-shrink: 0;
        }}
        .winner-badge.draw {{ background: var(--soft); color: var(--muted); }}
        .priority-reason {{ margin: 3px 0 0; color: var(--muted); font-size: 12px; }}
        .recommendation {{
            border: 1px solid var(--accent);
            border-radius: 4px;
            background: var(--accent-soft);
            padding: 10px 12px;
        }}
        .recommendation-heading {{ margin: 0 0 3px; font-family: 'Lora', Georgia, serif; font-size: 14px; font-weight: 600; color: var(--accent-strong); }}
        .citations {{ display: grid; gap: 8px; margin-top: 6px; }}
        .citation {{
            padding: 10px 0;
            border-bottom: 1px solid var(--rule);
            font-size: 13px;
        }}
        .citation a {{ color: var(--accent-strong); font-weight: 600; text-decoration: underline; }}
        .citation button {{
            border: 0;
            background: transparent;
            color: var(--accent-strong);
            font: inherit;
            font-weight: 600;
            text-decoration: underline;
            padding: 0;
            cursor: pointer;
        }}
        .summary-link {{ color: var(--accent-strong); font-weight: 600; text-decoration: underline; }}
        .citation strong {{ display: inline-block; min-width: 30px; color: var(--muted); font-weight: 600; }}
        .modal-backdrop {{
            position: fixed;
            inset: 0;
            background: rgba(16, 24, 28, 0.62);
            display: none;
            align-items: center;
            justify-content: center;
            padding: 24px;
            z-index: 40;
        }}
        .modal-backdrop.open {{ display: flex; }}
        .modal-card {{
            width: min(860px, 100%);
            max-height: 80vh;
            overflow: auto;
            border: 2px solid var(--rule);
            border-radius: 18px;
            background: linear-gradient(180deg, #fffefb 0%, #eef4f1 100%);
            padding: 20px;
            box-shadow: 0 20px 50px var(--shadow);
        }}
        .modal-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
        .modal-title {{ margin: 0; font-size: 18px; font-weight: 700; }}
        .modal-close {{
            border: 2px solid var(--rule);
            border-radius: 999px;
            background: linear-gradient(180deg, #fffefb 0%, #eef5f2 100%);
            color: var(--ink);
            padding: 6px 12px;
            cursor: pointer;
            font-weight: 700;
        }}
        .modal-meta {{ font-size: 12px; color: var(--muted); margin-bottom: 12px; }}
        .modal-content {{
            border: 1px solid var(--rule);
            border-radius: 4px;
            background: var(--paper);
            padding: 14px;
            white-space: pre-wrap;
            line-height: 1.6;
            font-size: 13px;
        }}
        .verify {{
            margin-top: 14px;
            font-size: 12px;
            color: var(--muted);
        }}
        .status-line {{ margin-top: 12px; font-size: 12px; color: var(--muted); }}
        .board-footer {{ text-align: center; margin-top: 10px; font-size: 12px; color: var(--muted); }}
        .auth-screen {{ min-height: 100vh; display: flex; }}
        .auth-side {{
            display: none;
            flex-direction: column;
            justify-content: space-between;
            width: 340px;
            flex-shrink: 0;
            padding: 40px 32px;
            background: var(--accent-strong);
            color: #FFFFFF;
        }}
        @media (min-width: 900px) {{ .auth-side {{ display: flex; }} }}
        .auth-side h2 {{ font-family: 'Lora', Georgia, serif; font-size: 20px; font-weight: 600; line-height: 1.4; margin: 24px 0 10px; }}
        .auth-side p {{ font-size: 13px; color: rgba(255,255,255,0.7); line-height: 1.6; }}
        .auth-logo {{ display: flex; align-items: center; gap: 10px; }}
        .auth-logo .brand-mark {{ flex-shrink: 0; }}
        .auth-logo-text {{ font-family: 'Lora', Georgia, serif; font-weight: 700; font-size: 15px; line-height: 1.3; text-transform: uppercase; letter-spacing: 0.02em; }}
        .auth-mobile-logo {{ display: flex; justify-content: center; margin-bottom: 20px; color: var(--accent-strong); }}
        @media (min-width: 900px) {{ .auth-mobile-logo {{ display: none; }} }}
        .auth-feature {{ display: flex; gap: 10px; align-items: flex-start; margin-top: 16px; }}
        .auth-feature .tick {{
            width: 16px; height: 16px; border-radius: 4px; background: rgba(255,255,255,0.14);
            display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px;
        }}
        .auth-feature strong {{ display: block; font-size: 12px; color: rgba(255,255,255,0.92); }}
        .auth-feature span {{ font-size: 12px; color: rgba(255,255,255,0.55); }}
        .auth-stripe {{ border-radius: 4px; padding: 10px 12px; background: var(--uol-red); }}
        .auth-stripe strong {{ display: block; font-size: 12px; }}
        .auth-stripe span {{ font-size: 11px; color: rgba(255,255,255,0.8); }}
        .auth-main {{ flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; background: var(--paper); }}
        .auth-card {{ width: 100%; max-width: 340px; }}
        .auth-card-stripe {{ height: 4px; border-radius: 4px 4px 0 0; background: var(--uol-red); }}
        .auth-card-body {{ border: 1px solid var(--rule); border-top: 0; border-radius: 0 0 6px 6px; background: #FFFFFF; padding: 24px; }}
        .auth-title {{ font-family: 'Lora', Georgia, serif; font-size: 19px; font-weight: 600; color: var(--accent-strong); margin: 0 0 3px; }}
        .auth-subtitle {{ font-size: 12px; color: var(--muted); margin: 0 0 18px; }}
        .auth-field {{ margin-bottom: 14px; }}
        .auth-field label {{ display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: var(--ink); }}
        .auth-field input, .auth-field select {{
            width: 100%; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 4px;
            font: inherit; font-size: 13px; background: var(--paper); color: var(--ink);
        }}
        .auth-field input:focus, .auth-field select:focus {{ outline: none; border-color: var(--accent); }}
        .auth-error {{ display: none; background: #FEF2F2; border: 1px solid #FECACA; color: #B91C1C; border-radius: 4px; padding: 8px 10px; font-size: 12px; margin-bottom: 12px; }}
        .auth-error.show {{ display: block; }}
        .auth-success {{ text-align: center; padding: 8px 0; }}
        .auth-success .check-circle {{
            width: 44px; height: 44px; border-radius: 50%; margin: 0 auto 12px; background: rgba(0,32,91,0.08);
            display: flex; align-items: center; justify-content: center; color: var(--accent-strong);
        }}
        .auth-submit {{
            width: 100%; padding: 10px; border: 0; border-radius: 4px; background: var(--accent-strong);
            color: #FFFFFF; font-weight: 600; font-size: 13px; cursor: pointer; margin-top: 4px;
        }}
        .auth-submit:hover {{ filter: brightness(1.08); }}
        .auth-footer {{ margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--rule); text-align: center; font-size: 12px; color: var(--muted); }}
        .auth-link {{ color: var(--uol-red); font-weight: 600; text-decoration: underline; background: none; border: 0; cursor: pointer; font: inherit; }}
        .admin-shell {{ display: flex; min-height: calc(100vh - 54px); }}
        .admin-sidebar {{ width: 210px; flex-shrink: 0; background: #FFFFFF; border-right: 1px solid var(--rule); padding: 16px 10px; }}
        .admin-nav-item {{
            display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
            padding: 8px 10px; border-radius: 4px; border: 0; background: transparent;
            font-size: 13px; font-weight: 600; color: var(--muted); cursor: pointer; margin-bottom: 2px;
        }}
        .admin-nav-item.active {{ background: rgba(0,32,91,0.08); color: var(--accent-strong); }}
        .admin-main {{ flex: 1; padding: 20px 24px; min-width: 0; }}
        .admin-page-title {{ font-family: 'Lora', Georgia, serif; font-size: 18px; font-weight: 600; margin: 0 0 16px; color: var(--ink); }}
        .admin-tab {{ display: none; }}
        .admin-tab.active {{ display: block; }}
        .admin-stat-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 18px; }}
        .admin-stat-card {{ border: 1px solid var(--rule); border-radius: 6px; background: #FFFFFF; padding: 12px 14px; }}
        .admin-stat-card .value {{ font-size: 20px; font-weight: 700; color: var(--accent-strong); }}
        .admin-stat-card .label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
        .admin-panel {{ border: 1px solid var(--rule); border-radius: 6px; background: #FFFFFF; overflow: hidden; margin-bottom: 16px; }}
        .admin-panel-head {{ padding: 10px 14px; border-bottom: 1px solid var(--rule); background: var(--soft); font-weight: 600; font-size: 13px; }}
        .admin-panel-body {{ padding: 14px; }}
        .admin-form-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 10px; }}
        .admin-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        .admin-table th {{ text-align: left; padding: 8px; border-bottom: 1px solid var(--rule); color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        .admin-table td {{ padding: 8px; border-bottom: 1px solid var(--rule); vertical-align: middle; }}
        .admin-badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
        .admin-badge.active {{ background: rgba(0,32,91,0.1); color: var(--accent-strong); }}
        .admin-badge.pending {{ background: #FFFBEB; color: #92400E; }}
        .admin-badge.inactive {{ background: var(--soft); color: var(--muted); }}
        .admin-badge.rejected {{ background: #FEF2F2; color: #B91C1C; }}
        .admin-row-actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .admin-mini-btn {{ border: 1px solid var(--rule); background: #FFFFFF; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600; cursor: pointer; }}
        .admin-mini-btn.approve {{ color: var(--accent-strong); border-color: var(--accent-strong); }}
        .admin-mini-btn.reject, .admin-mini-btn.deactivate {{ color: #B91C1C; border-color: #FECACA; }}
        .kb-subtabs {{ display: flex; gap: 4px; border-bottom: 1px solid var(--rule); margin: 4px 0 14px; }}
        .kb-subtab {{
            border: 0; background: transparent; padding: 8px 12px; font-size: 12px; font-weight: 600;
            color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px;
        }}
        .kb-subtab.active {{ color: var(--accent-strong); border-bottom-color: var(--accent-strong); }}
        .kb-subtab-panel {{ display: none; }}
        .kb-subtab-panel.active {{ display: block; }}
        .kb-status-pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
        .kb-status-pill.ok {{ background: rgba(0,32,91,0.1); color: var(--accent-strong); }}
        .kb-status-pill.missing {{ background: #FEF2F2; color: #B91C1C; }}
        .kb-status-pill.na {{ background: var(--soft); color: var(--muted); }}
        .kb-run-result {{ border: 1px solid var(--rule); border-radius: 6px; background: #FFFFFF; padding: 10px 12px; margin-top: 10px; font-size: 12px; }}
        .kb-run-result pre {{ white-space: pre-wrap; word-break: break-word; background: #1E1E1E; color: #D4D4D4; padding: 8px; border-radius: 4px; max-height: 220px; overflow: auto; margin-top: 6px; }}
    </style>
</head>
<body>
    <div id="loginScreen" class="auth-screen">
        <div class="auth-side">
            <div>
                <div class="auth-logo">
                    <svg width="32" height="32" viewBox="0 0 40 40" fill="none" class="brand-mark">
                        <path d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z" stroke="currentColor" stroke-width="1.6" />
                        <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                    </svg>
                    <span class="auth-logo-text">University of<br />Liverpool</span>
                </div>
                <h2>AI-powered competitive intelligence for Clearing.</h2>
                <p>Deliver real-time, evidence-based programme comparisons during live Clearing calls.</p>
                <div class="auth-feature">
                    <span class="tick">&#10003;</span>
                    <div><strong>Course comparisons</strong><span>BCS accreditation, modules, placements</span></div>
                </div>
                <div class="auth-feature">
                    <span class="tick">&#10003;</span>
                    <div><strong>Graduate outcomes</strong><span>Salary data, employment rates, LEO</span></div>
                </div>
                <div class="auth-feature">
                    <span class="tick">&#10003;</span>
                    <div><strong>Live rankings</strong><span>CUG, QS, TEF, NSS verified sources</span></div>
                </div>
            </div>
            <div class="auth-stripe">
                <strong>Clearing 2026 &middot; Mid-August</strong>
                <span>University of Liverpool &middot; Computer Science</span>
            </div>
        </div>
        <div class="auth-main">
            <div class="auth-card">
                <div class="auth-mobile-logo">
                    <svg width="26" height="26" viewBox="0 0 40 40" fill="none" style="margin-right:8px;">
                        <path d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z" stroke="currentColor" stroke-width="1.6" />
                        <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                    </svg>
                    <span class="auth-logo-text">University of Liverpool</span>
                </div>
                <div class="auth-card-stripe"></div>
                <div class="auth-card-body">
                    <h1 class="auth-title">Sign in</h1>
                    <p class="auth-subtitle">Use your University of Liverpool staff credentials.</p>
                    <div class="auth-error" id="loginError"></div>
                    <div class="auth-field">
                        <label for="loginEmail">Email address</label>
                        <input id="loginEmail" type="email" placeholder="you@liverpool.ac.uk" />
                    </div>
                    <div class="auth-field">
                        <label for="loginPassword">Password</label>
                        <input id="loginPassword" type="password" placeholder="********" />
                    </div>
                    <button class="auth-submit" onclick="handleLogin()">Sign in</button>
                    <div class="auth-footer">
                        New to Admissions Assistant? <button class="auth-link" onclick="showAuthScreen('register')">Request access</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="registerScreen" class="auth-screen" style="display:none">
        <div class="auth-main" style="width:100%">
            <div class="auth-card">
                <div class="auth-mobile-logo" style="display:flex">
                    <svg width="26" height="26" viewBox="0 0 40 40" fill="none" style="margin-right:8px;">
                        <path d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z" stroke="currentColor" stroke-width="1.6" />
                        <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                    </svg>
                    <span class="auth-logo-text">University of Liverpool</span>
                </div>
                <div class="auth-card-stripe"></div>
                <div class="auth-card-body" id="registerCardBody">
                    <h1 class="auth-title">Request access</h1>
                    <p class="auth-subtitle">Registration requires a @liverpool.ac.uk email address.</p>
                    <div class="auth-error" id="registerError"></div>
                    <div class="auth-field">
                        <label for="registerName">Full name</label>
                        <input id="registerName" type="text" placeholder="Jane Okafor" />
                    </div>
                    <div class="auth-field">
                        <label for="registerEmail">Email address</label>
                        <input id="registerEmail" type="email" placeholder="you@liverpool.ac.uk" />
                    </div>
                    <div class="auth-field">
                        <label for="registerPassword">Password</label>
                        <input id="registerPassword" type="password" placeholder="At least 8 characters" />
                    </div>
                    <button class="auth-submit" onclick="handleRegister()">Request access</button>
                    <div class="auth-footer">
                        Already have an account? <button class="auth-link" onclick="showAuthScreen('login')">Sign in</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="dashboardScreen" style="display:none">
    <div class="frame">
        <div class="board">
            <div class="board-stripe"></div>
            <div class="title-row">
                <div class="title-brand">
                    <svg width="26" height="26" viewBox="0 0 40 40" fill="none" class="brand-mark">
                        <path d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z" stroke="currentColor" stroke-width="1.6" />
                        <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                    </svg>
                    <h1 class="title">University of<br />Liverpool</h1>
                </div>
                <div class="header-actions">
                    <span class="status-badge"><span class="dot"></span>Verified data</span>
                    <button class="icon-button" onclick="location.reload()" title="Reload dashboard" aria-label="Reload dashboard">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
                    </button>
                    <span class="user-chip">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                        <span id="currentUserLabel">Tutor</span>
                    </span>
                    <button class="icon-button" onclick="signOut()" title="Sign out" aria-label="Sign out">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                    </button>
                </div>
            </div>

            <div class="layout">
                <section class="pane">
                    <h2 class="section-title">Admissions Tutor Input</h2>
                    <div class="control-group">
                        <label class="label" for="targetProgramme">Target Programme:</label>
                        <input id="targetProgramme" class="field" type="text" value="Computer Science BSc - University of Liverpool" readonly />
                    </div>

                    <div class="control-group dropdown-arrow">
                        <label class="label" for="competitorUniversity">Competitor University:</label>
                        <select id="competitorUniversity" class="select">
                            <option>University of Leeds</option>
                            <option>University of Sheffield</option>
                            <option>University of Manchester</option>
                            <option>Lancaster University</option>
                            <option>University of Nottingham</option>
                            <option>University of Birmingham</option>
                            <option>Newcastle University</option>
                            <option>Liverpool John Moores University</option>
                            <option>Manchester Metropolitan University</option>
                            <option>Queen Mary University London</option>
                        </select>
                    </div>

                    <div class="control-group">
                        <label class="label">Student Priorities:</label>
                        <div class="checkboxes">
                            <label><input id="priorityEntryRequirements" type="checkbox" checked /> Entry Requirements</label>
                            <label><input id="priorityCurriculumAccreditation" type="checkbox" checked /> Curriculum &amp; Accreditation</label>
                            <label><input id="priorityGraduateOutcomes" type="checkbox" checked /> Graduate Outcomes &amp; Salary</label>
                            <label><input id="priorityFeesAndCost" type="checkbox" /> Fees &amp; Cost</label>
                            <label><input id="priorityTeachingQuality" type="checkbox" /> Teaching Quality &amp; NSS</label>
                            <label><input id="priorityRankings" type="checkbox" /> University Rankings</label>
                        </div>
                    </div>

                    <div class="control-group">
                        <label class="label" for="question">Tutor prompt:</label>
                        <textarea id="question" class="textarea">Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary.</textarea>
                    </div>

                    <div class="button-row">
                        <button class="button primary" onclick="submitQuery()">Compare</button>
                        <button class="button" onclick="loadDefaults()">Reset</button>
                    </div>
                </section>

                <section class="pane">
                    <h2 class="section-title">Comparison Summary</h2>
                    <div class="summary-box">
                        <div class="answer-card conversation" id="response">
                            <div class="empty-state">
                                <strong>Your verified comparison will appear here.</strong>
                                Select a competitor, choose priorities, and click Compare.
                            </div>
                        </div>
                    </div>
                </section>

                <section class="pane citations-col">
                    <h2 class="section-title">Citations</h2>
                    <div class="citations" id="sources">
                        <div class="citation"><strong>[1]</strong> Prospectus 2024</div>
                        <div class="citation"><strong>[2]</strong> UCAS Data</div>
                        <div class="citation"><strong>[3]</strong> Vector DB Doc #42</div>
                    </div>
                    <div class="verify">Click to verify →</div>
                </section>
            </div>
        </div>
    </div>
    </div>

    <div id="adminScreen" style="display:none">
        <div class="board-stripe"></div>
        <div class="title-row">
            <div class="title-brand">
                <svg width="26" height="26" viewBox="0 0 40 40" fill="none" class="brand-mark">
                    <path d="M20 2L4 8v10c0 10 7 17 16 20 9-3 16-10 16-20V8L20 2z" stroke="currentColor" stroke-width="1.6" />
                    <path d="M13 14h14M13 20h14M13 26h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                </svg>
                <h1 class="title">University of<br />Liverpool</h1>
            </div>
            <div class="header-actions">
                <span class="status-badge"><span class="dot"></span>Administrator</span>
                <span class="user-chip">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    <span id="adminUserLabel">Administrator</span>
                </span>
                <button class="icon-button" onclick="signOut()" title="Sign out" aria-label="Sign out">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                </button>
            </div>
        </div>

        <div class="admin-shell">
            <nav class="admin-sidebar">
                <button class="admin-nav-item active" data-tab="users" onclick="showAdminTab('users')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                    User Management
                </button>
                <button class="admin-nav-item" data-tab="knowledge" onclick="showAdminTab('knowledge')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                    Knowledge Base
                </button>
                <button class="admin-nav-item" data-tab="evaluation" onclick="showAdminTab('evaluation')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                    Model Evaluation
                </button>
                <button class="admin-nav-item" data-tab="system" onclick="showAdminTab('system')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93l-1.41 1.41M12 2v2M4.93 4.93l1.41 1.41M2 12h2M4.93 19.07l1.41-1.41M12 20v2M19.07 19.07l-1.41-1.41M20 12h2"/></svg>
                    System
                </button>
            </nav>

            <main class="admin-main">
                <div id="adminTab-users" class="admin-tab active">
                    <h2 class="admin-page-title">User Management</h2>
                    <div class="admin-stat-row" id="adminUserStats"></div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Add user</div>
                        <div class="admin-panel-body">
                            <div class="admin-form-row">
                                <div class="auth-field" style="margin-bottom:0"><label>Full name</label><input id="adminNewName" type="text" placeholder="Jane Okafor" /></div>
                                <div class="auth-field" style="margin-bottom:0"><label>Email</label><input id="adminNewEmail" type="email" placeholder="you@liverpool.ac.uk" /></div>
                                <div class="auth-field" style="margin-bottom:0"><label>Department</label><input id="adminNewDepartment" type="text" placeholder="Computer Science" /></div>
                                <div class="auth-field" style="margin-bottom:0">
                                    <label>Role</label>
                                    <select id="adminNewRole"><option value="tutor">Tutor</option><option value="admin">Admin</option></select>
                                </div>
                                <div class="auth-field" style="margin-bottom:0"><label>Temporary password</label><input id="adminNewPassword" type="text" placeholder="Temp1234!" /></div>
                            </div>
                            <div class="auth-error" id="adminCreateError"></div>
                            <button class="auth-submit" style="width:auto;padding:8px 16px" onclick="adminCreateUser()">Create user</button>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">All users</div>
                        <div class="admin-panel-body" style="overflow-x:auto">
                            <table class="admin-table">
                                <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Department</th><th>Status</th><th>Last login</th><th>Actions</th></tr></thead>
                                <tbody id="adminUsersTableBody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="adminTab-knowledge" class="admin-tab">
                    <h2 class="admin-page-title">Knowledge Base</h2>
                    <div class="admin-stat-row" id="adminKnowledgeStats"></div>

                    <div class="kb-subtabs">
                        <button class="kb-subtab active" data-kbtab="sources" onclick="showKbSubtab('sources')">Data Sources</button>
                        <button class="kb-subtab" data-kbtab="scripts" onclick="showKbSubtab('scripts')">Scripts</button>
                        <button class="kb-subtab" data-kbtab="upload" onclick="showKbSubtab('upload')">Upload Data</button>
                    </div>

                    <div id="kbSubtab-sources" class="kb-subtab-panel active">
                        <div class="admin-panel">
                            <div class="admin-panel-body" style="overflow-x:auto">
                                <table class="admin-table">
                                    <thead><tr><th>Source</th><th>Script</th><th>CSV</th><th>Last updated</th><th>Actions</th></tr></thead>
                                    <tbody id="kbSourcesTableBody"></tbody>
                                </table>
                            </div>
                        </div>
                        <div id="kbRunOutput"></div>
                    </div>

                    <div id="kbSubtab-scripts" class="kb-subtab-panel">
                        <div class="admin-panel">
                            <div class="admin-panel-head">Pipeline scripts</div>
                            <div class="admin-panel-body">
                                <div class="admin-row-actions" id="kbScriptButtons" style="flex-wrap:wrap"></div>
                            </div>
                        </div>
                    </div>

                    <div id="kbSubtab-upload" class="kb-subtab-panel">
                        <div class="admin-panel">
                            <div class="admin-panel-head">Upload CSV</div>
                            <div class="admin-panel-body">
                                <div class="admin-form-row">
                                    <div class="auth-field" style="margin-bottom:0">
                                        <label>Target file</label>
                                        <select id="kbUploadTarget"></select>
                                    </div>
                                    <div class="auth-field" style="margin-bottom:0">
                                        <label>CSV file</label>
                                        <input id="kbUploadFile" type="file" accept=".csv" />
                                    </div>
                                </div>
                                <div class="auth-error" id="kbUploadError"></div>
                                <div id="kbUploadSuccess" style="display:none;font-size:12px;color:var(--accent-strong);margin-bottom:10px;"></div>
                                <button class="auth-submit" style="width:auto;padding:8px 16px" onclick="kbUploadCsv()">Upload</button>
                                <p style="font-size:11px;color:var(--muted);margin-top:10px;">Uploading CSV-version.csv replaces the file used by the Rankings, Fees &amp; Entry import script. The previous file is kept as a timestamped backup.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="adminTab-evaluation" class="admin-tab">
                    <h2 class="admin-page-title">Model Evaluation</h2>
                    <div class="admin-stat-row" id="adminEvaluationQuickStats"></div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Evaluation controls</div>
                        <div class="admin-panel-body">
                            <div class="admin-row-actions" style="margin-bottom:10px;">
                                <button class="admin-mini-btn approve" onclick="adminRunEvaluation()">Run evaluation script</button>
                                <button class="admin-mini-btn" onclick="adminDownloadEvaluationSummary()">Download summary CSV</button>
                            </div>
                            <div class="admin-form-row">
                                <div class="auth-field" style="margin-bottom:0;">
                                    <label>Upload golden dataset (CSV)</label>
                                    <input id="evalGoldenFile" type="file" accept=".csv" />
                                </div>
                            </div>
                            <div class="admin-row-actions" style="margin-bottom:10px;">
                                <button class="admin-mini-btn" onclick="adminUploadGoldenDataset()">Upload & replace golden_dataset.csv</button>
                            </div>
                            <div class="auth-error" id="evalActionError"></div>
                            <div id="evalActionSuccess" style="display:none;font-size:12px;color:var(--accent-strong);margin-top:8px;"></div>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Evaluation metrics</div>
                        <div class="admin-panel-body">
                            <div id="adminEvaluationStats"></div>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Evaluation output files</div>
                        <div class="admin-panel-body" id="adminEvaluationFiles" style="font-size:12px;color:var(--muted);"></div>
                    </div>

                    <h2 class="admin-page-title" style="margin-top:24px;">Data Audit</h2>
                    <div class="admin-stat-row" id="adminAuditStats"></div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Audit controls</div>
                        <div class="admin-panel-body">
                            <div class="admin-row-actions" style="margin-bottom:10px;">
                                <button class="admin-mini-btn approve" onclick="adminRunAudit()">Run audit script</button>
                                <button class="admin-mini-btn" onclick="adminDownloadAuditCsv()">Download audit CSV</button>
                            </div>
                            <div class="admin-form-row">
                                <div class="auth-field" style="margin-bottom:0;">
                                    <label>Upload audit CSV override</label>
                                    <input id="auditUploadFile" type="file" accept=".csv" />
                                </div>
                            </div>
                            <div class="admin-row-actions" style="margin-bottom:10px;">
                                <button class="admin-mini-btn" onclick="adminUploadAuditCsv()">Upload & replace priority_data_audit.csv</button>
                            </div>
                            <div class="auth-error" id="auditActionError"></div>
                            <div id="auditActionSuccess" style="display:none;font-size:12px;color:var(--accent-strong);margin-top:8px;"></div>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Priority coverage summary</div>
                        <div class="admin-panel-body" style="overflow-x:auto">
                            <table class="admin-table">
                                <thead><tr><th>Priority</th><th>Universities</th><th>Avg coverage</th><th>Below 60%</th></tr></thead>
                                <tbody id="adminAuditPriorityBody"></tbody>
                            </table>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Lowest coverage rows</div>
                        <div class="admin-panel-body" style="overflow-x:auto">
                            <table class="admin-table">
                                <thead><tr><th>University</th><th>Priority</th><th>Coverage</th><th>Programme</th></tr></thead>
                                <tbody id="adminAuditLowestBody"></tbody>
                            </table>
                        </div>
                    </div>
                    <div class="admin-panel">
                        <div class="admin-panel-head">Audit files in directory</div>
                        <div class="admin-panel-body" id="adminAuditFiles" style="font-size:12px;color:var(--muted);"></div>
                    </div>
                </div>

                <div id="adminTab-system" class="admin-tab">
                    <h2 class="admin-page-title">System</h2>
                    <div class="admin-stat-row" id="adminSystemStats"></div>
                </div>
            </main>
        </div>
    </div>

    <div class="modal-backdrop" id="scriptModal" onclick="closeScriptModal(event)">
        <div class="modal-card" onclick="event.stopPropagation()" style="max-width:720px;">
            <div class="modal-head">
                <div>
                    <h3 class="modal-title" id="scriptModalTitle">script.py</h3>
                    <div class="modal-meta" id="scriptModalMeta"></div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button class="modal-close" onclick="downloadScript()">Download</button>
                    <button class="modal-close" onclick="closeScriptModal()">Close</button>
                </div>
            </div>
            <pre class="modal-content" id="scriptModalContent" style="background:#1E1E1E;color:#D4D4D4;max-height:60vh;overflow:auto;"></pre>
        </div>
    </div>

    <div class="modal-backdrop" id="citationModal" onclick="closeCitationModal(event)">
        <div class="modal-card" onclick="event.stopPropagation()">
            <div class="modal-head">
                <div>
                    <h3 class="modal-title" id="citationModalTitle">Citation evidence</h3>
                    <div class="modal-meta" id="citationModalMeta"></div>
                </div>
                <button class="modal-close" onclick="closeCitationModal()">Close</button>
            </div>
            <div class="modal-content" id="citationModalContent"></div>
        </div>
    </div>

    <script>
        const defaultApiKey = 'openwebui-local-key';
        const state = {{ summary: null, citations: [] }};
        const SESSION_KEY = 'admissionsAssistantSession';

        function showAuthScreen(name) {{
            document.getElementById('loginScreen').style.display = name === 'login' ? 'flex' : 'none';
            document.getElementById('registerScreen').style.display = name === 'register' ? 'flex' : 'none';
            document.getElementById('dashboardScreen').style.display = 'none';
            document.getElementById('adminScreen').style.display = 'none';
        }}

        function showDashboard(displayName) {{
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('registerScreen').style.display = 'none';
            document.getElementById('dashboardScreen').style.display = 'block';
            document.getElementById('adminScreen').style.display = 'none';
            document.getElementById('currentUserLabel').textContent = displayName;
        }}

        function showAdminScreen(displayName) {{
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('registerScreen').style.display = 'none';
            document.getElementById('dashboardScreen').style.display = 'none';
            document.getElementById('adminScreen').style.display = 'block';
            document.getElementById('adminUserLabel').textContent = displayName;
            loadAdminOverview();
            loadKbSources();
            loadEvaluationDashboard();
        }}

        function enterApp(user) {{
            if (user.role === 'admin') {{
                showAdminScreen(user.name);
            }} else {{
                showDashboard(user.name);
            }}
        }}

        function showAdminTab(tab) {{
            document.querySelectorAll('.admin-tab').forEach((el) => el.classList.toggle('active', el.id === `adminTab-${{tab}}`));
            document.querySelectorAll('.admin-nav-item').forEach((el) => el.classList.toggle('active', el.dataset.tab === tab));
            if (tab === 'evaluation') {{
                loadEvaluationDashboard();
            }}
        }}

        function statCard(label, value) {{
            return `<div class="admin-stat-card"><div class="value">${{escapeHtml(String(value))}}</div><div class="label">${{escapeHtml(label)}}</div></div>`;
        }}

        function adminUserActions(user) {{
            const buttons = [];
            if (user.status === 'pending') {{
                buttons.push(`<button class="admin-mini-btn approve" onclick="adminSetStatus('${{user.id}}','active')">Approve</button>`);
                buttons.push(`<button class="admin-mini-btn reject" onclick="adminRejectUser('${{user.id}}')">Reject</button>`);
            }} else if (user.status === 'active') {{
                buttons.push(`<button class="admin-mini-btn deactivate" onclick="adminSetStatus('${{user.id}}','inactive')">Deactivate</button>`);
            }} else {{
                buttons.push(`<button class="admin-mini-btn approve" onclick="adminSetStatus('${{user.id}}','active')">Activate</button>`);
            }}
            return buttons.join(' ');
        }}

        function renderAdminUsers(users) {{
            const counts = {{ active: 0, pending: 0, inactive: 0, rejected: 0 }};
            users.forEach((u) => {{ counts[u.status] = (counts[u.status] || 0) + 1; }});
            document.getElementById('adminUserStats').innerHTML = [
                statCard('Total users', users.length),
                statCard('Active', counts.active || 0),
                statCard('Pending', counts.pending || 0),
                statCard('Inactive', counts.inactive || 0),
                statCard('Rejected', counts.rejected || 0),
            ].join('');

            document.getElementById('adminUsersTableBody').innerHTML = users.map((u) => `
                <tr>
                    <td>${{escapeHtml(u.name)}}</td>
                    <td>${{escapeHtml(u.email)}}</td>
                    <td>${{escapeHtml(u.role)}}</td>
                    <td>${{escapeHtml(u.department || '—')}}</td>
                    <td><span class="admin-badge ${{u.status}}">${{escapeHtml(u.status)}}</span></td>
                    <td>${{u.lastLogin ? escapeHtml(u.lastLogin) : 'Never'}}</td>
                    <td><div class="admin-row-actions">${{adminUserActions(u)}}</div></td>
                </tr>`).join('');
        }}

        async function loadAdminOverview() {{
            try {{
                const response = await fetch('/api/admin/overview', {{ headers: authHeaders() }});
                const data = await response.json();
                state.admin = data;
                renderAdminUsers(data.users || []);

                const k = data.knowledge || {{}};
                document.getElementById('adminKnowledgeStats').innerHTML = [
                    statCard('Knowledge base entries', k.kbEntries ?? 0),
                    statCard('Last updated', k.kbUpdated || 'Unknown'),
                    statCard('Course records (SQL)', k.courseFactsRows ?? 0),
                    statCard('Structured DB', k.sqlDbPresent ? 'Connected' : 'Missing'),
                    statCard('Vector store', k.chromaDbPresent ? 'Connected' : 'Missing'),
                ].join('');

                const e = data.evaluation || {{}};
                const quickStatsEl = document.getElementById('adminEvaluationQuickStats');
                if (quickStatsEl) {{
                    quickStatsEl.innerHTML = e.available === false
                    ? '<p style="font-size:12px;color:var(--muted)">No evaluation summary has been generated yet.</p>'
                    : [
                        statCard('Total questions', e.total_questions ?? 'N/A'),
                        statCard('Avg confidence', e.avg_confidence_score ?? 'N/A'),
                        statCard('Abstain count', e.abstain_count ?? 'N/A'),
                        statCard('Avg faithfulness', e.avg_faithfulness ?? 'N/A'),
                        statCard('Avg relevancy', e.avg_answer_relevancy ?? 'N/A'),
                        statCard('Avg precision', e.avg_context_precision ?? 'N/A'),
                        statCard('Avg recall', e.avg_context_recall ?? 'N/A'),
                    ].join('');
                }}

                const s = data.system || {{}};
                document.getElementById('adminSystemStats').innerHTML = [
                    statCard('Gemini configured', s.geminiConfigured ? 'Yes' : 'No'),
                    statCard('API auth configured', s.apiAuthConfigured ? 'Yes' : 'No'),
                    statCard('Total users', s.usersTotal ?? 0),
                    statCard('Active users', s.usersActive ?? 0),
                    statCard('Pending approvals', s.usersPending ?? 0),
                    statCard('Server time', s.serverTime || ''),
                ].join('');
            }} catch (error) {{
                document.getElementById('adminUsersTableBody').innerHTML = `<tr><td colspan="7">Unable to load users: ${{escapeHtml(error.message)}}</td></tr>`;
            }}
        }}

        async function adminSetStatus(id, status, reason) {{
            await fetch(`/api/auth/users/${{id}}/status`, {{
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({{ status, rejection_reason: reason || null }}),
            }});
            loadAdminOverview();
        }}

        function adminRejectUser(id) {{
            const reason = window.prompt('Reason for rejection (shown to the applicant):', '');
            if (reason === null) return;
            adminSetStatus(id, 'rejected', reason);
        }}

        async function adminCreateUser() {{
            const name = document.getElementById('adminNewName').value.trim();
            const email = document.getElementById('adminNewEmail').value.trim();
            const department = document.getElementById('adminNewDepartment').value.trim();
            const role = document.getElementById('adminNewRole').value;
            const password = document.getElementById('adminNewPassword').value || 'Temp1234!';
            setAuthError('adminCreateError', '');
            if (!name || !email) {{
                setAuthError('adminCreateError', 'Name and email are required.');
                return;
            }}
            try {{
                const response = await fetch('/api/auth/users', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{ name, email, password, role, department: department || null }}),
                }});
                const result = await response.json();
                if (!result.ok) {{
                    setAuthError('adminCreateError', result.error || 'Unable to create user.');
                    return;
                }}
                document.getElementById('adminNewName').value = '';
                document.getElementById('adminNewEmail').value = '';
                document.getElementById('adminNewDepartment').value = '';
                document.getElementById('adminNewPassword').value = '';
                loadAdminOverview();
            }} catch (error) {{
                setAuthError('adminCreateError', `Unable to reach the admissions service: ${{error.message}}`);
            }}
        }}

        function showKbSubtab(tab) {{
            document.querySelectorAll('.kb-subtab-panel').forEach((el) => el.classList.toggle('active', el.id === `kbSubtab-${{tab}}`));
            document.querySelectorAll('.kb-subtab').forEach((el) => el.classList.toggle('active', el.dataset.kbtab === tab));
        }}

        function kbStatusPill(exists) {{
            if (exists === null || exists === undefined) return '<span class="kb-status-pill na">N/A</span>';
            return exists ? '<span class="kb-status-pill ok">Found</span>' : '<span class="kb-status-pill missing">Missing</span>';
        }}

        function renderKbSources(sources) {{
            document.getElementById('kbSourcesTableBody').innerHTML = sources.map((s) => {{
                const csvCell = s.csv
                    ? `${{escapeHtml(s.csv)}} (${{s.csvRows ?? 0}} rows) ${{kbStatusPill(s.csvExists)}}`
                    : '<span class="kb-status-pill na">N/A</span>';
                const runBtn = s.runnable
                    ? `<button class="admin-mini-btn approve" onclick="kbRunScript('${{s.script}}','${{s.id}}')">Run now</button>`
                    : '<span class="kb-status-pill na">Module only</span>';
                return `<tr id="kbRow-${{s.id}}">
                    <td><strong>${{escapeHtml(s.label)}}</strong><br /><span style="color:var(--muted);font-size:11px;">${{escapeHtml(s.description)}}</span></td>
                    <td>${{escapeHtml(s.script)}} ${{kbStatusPill(s.scriptExists)}}<br /><button class="admin-mini-btn" onclick="openScriptModal('${{s.script}}')">View script</button></td>
                    <td>${{csvCell}}</td>
                    <td>${{s.csvUpdatedAt ? escapeHtml(s.csvUpdatedAt) : (s.scriptUpdatedAt ? escapeHtml(s.scriptUpdatedAt) : '—')}}</td>
                    <td><div class="admin-row-actions">${{runBtn}}</div></td>
                </tr>`;
            }}).join('');

            document.getElementById('kbScriptButtons').innerHTML = sources.map((s) =>
                `<button class="admin-mini-btn" onclick="openScriptModal('${{s.script}}')">${{escapeHtml(s.script)}}</button>`
            ).join('');
        }}

        async function loadKbSources() {{
            try {{
                const response = await fetch('/api/admin/kb/sources', {{ headers: authHeaders() }});
                const data = await response.json();
                state.kbSources = data.sources || [];
                renderKbSources(state.kbSources);

                const select = document.getElementById('kbUploadTarget');
                select.innerHTML = (data.uploadTargets || []).map((t) => `<option value="${{escapeHtml(t)}}">${{escapeHtml(t)}}</option>`).join('');
            }} catch (error) {{
                document.getElementById('kbSourcesTableBody').innerHTML = `<tr><td colspan="5">Unable to load sources: ${{escapeHtml(error.message)}}</td></tr>`;
            }}
        }}

        async function kbRunScript(script, sourceId) {{
            const row = document.getElementById(`kbRow-${{sourceId}}`);
            const output = document.getElementById('kbRunOutput');
            output.innerHTML = `<div class="kb-run-result"><span class="spinner"></span> Running ${{escapeHtml(script)}}…</div>`;
            if (row) row.style.opacity = '0.6';
            try {{
                const response = await fetch('/api/admin/kb/run', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{ script }}),
                }});
                const result = await response.json();
                const status = result.ok ? 'kb-status-pill ok' : 'kb-status-pill missing';
                output.innerHTML = `
                    <div class="kb-run-result">
                        <span class="${{status}}">${{result.ok ? 'Completed' : 'Failed'}}</span>
                        <strong> ${{escapeHtml(script)}}</strong>
                        ${{result.error ? `<div style="color:#B91C1C;margin-top:6px;">${{escapeHtml(result.error)}}</div>` : ''}}
                        ${{result.stdout ? `<div>stdout:</div><pre>${{escapeHtml(result.stdout)}}</pre>` : ''}}
                        ${{result.stderr ? `<div>stderr:</div><pre>${{escapeHtml(result.stderr)}}</pre>` : ''}}
                    </div>`;
            }} catch (error) {{
                output.innerHTML = `<div class="kb-run-result" style="color:#B91C1C;">Unable to run ${{escapeHtml(script)}}: ${{escapeHtml(error.message)}}</div>`;
            }} finally {{
                if (row) row.style.opacity = '1';
                loadKbSources();
                loadAdminOverview();
            }}
        }}

        async function openScriptModal(scriptName) {{
            document.getElementById('scriptModalTitle').textContent = scriptName;
            document.getElementById('scriptModalMeta').textContent = 'Loading…';
            document.getElementById('scriptModalContent').textContent = '';
            document.getElementById('scriptModal').classList.add('open');
            try {{
                const response = await fetch(`/api/admin/kb/script/${{encodeURIComponent(scriptName)}}`, {{ headers: authHeaders() }});
                const data = await response.json();
                state.activeScript = data;
                document.getElementById('scriptModalMeta').textContent = `${{(data.content || '').split('\\n').length}} lines`;
                document.getElementById('scriptModalContent').textContent = data.content || '';
            }} catch (error) {{
                document.getElementById('scriptModalMeta').textContent = 'Failed to load script.';
            }}
        }}

        function closeScriptModal(event) {{
            if (event && event.target && event.target.id !== 'scriptModal') return;
            document.getElementById('scriptModal').classList.remove('open');
        }}

        function downloadScript() {{
            const script = state.activeScript;
            if (!script) return;
            const blob = new Blob([script.content || ''], {{ type: 'text/x-python' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = script.filename; a.click();
            URL.revokeObjectURL(url);
        }}

        async function kbUploadCsv() {{
            const target = document.getElementById('kbUploadTarget').value;
            const fileInput = document.getElementById('kbUploadFile');
            const file = fileInput.files[0];
            setAuthError('kbUploadError', '');
            document.getElementById('kbUploadSuccess').style.display = 'none';
            if (!file) {{
                setAuthError('kbUploadError', 'Choose a CSV file to upload.');
                return;
            }}
            const formData = new FormData();
            formData.append('target', target);
            formData.append('file', file);
            try {{
                const response = await fetch('/api/admin/kb/upload', {{
                    method: 'POST',
                    headers: {{ 'Authorization': `Bearer ${{defaultApiKey}}` }},
                    body: formData,
                }});
                const result = await response.json();
                if (!result.ok) {{
                    setAuthError('kbUploadError', result.error || 'Upload failed.');
                    return;
                }}
                const successEl = document.getElementById('kbUploadSuccess');
                successEl.style.display = 'block';
                successEl.textContent = `Uploaded ${{result.file}} (${{result.rows}} rows).`;
                fileInput.value = '';
                loadKbSources();
            }} catch (error) {{
                setAuthError('kbUploadError', `Unable to reach the admissions service: ${{error.message}}`);
            }}
        }}

        function formatPercent(value) {{
            const num = Number(value);
            if (Number.isNaN(num)) return '0.0%';
            return `${{(num * 100).toFixed(1)}}%`;
        }}

        function formatSize(bytes) {{
            const value = Number(bytes) || 0;
            if (value < 1024) return `${{value}} B`;
            if (value < 1024 * 1024) return `${{(value / 1024).toFixed(1)}} KB`;
            return `${{(value / (1024 * 1024)).toFixed(2)}} MB`;
        }}

        function renderEvaluationDetails(payload) {{
            const summary = payload.summary || {{}};
            const summaryAvailable = Boolean(payload.summaryAvailable);
            const metricsEl = document.getElementById('adminEvaluationStats');
            if (metricsEl) {{
                if (!summaryAvailable) {{
                    metricsEl.innerHTML = '<p style="font-size:12px;color:var(--muted)">No evaluation summary generated yet. Run the evaluation script first.</p>';
                }} else {{
                    const metricRows = [
                        ['Confidence', summary.avg_confidence_score],
                        ['Faithfulness', summary.avg_faithfulness],
                        ['Answer relevancy', summary.avg_answer_relevancy],
                        ['Context precision', summary.avg_context_precision],
                        ['Context recall', summary.avg_context_recall],
                    ];
                    metricsEl.innerHTML = metricRows.map(([label, value]) => {{
                        const safe = Math.max(0, Math.min(1, Number(value || 0)));
                        return `
                            <div style="margin-bottom:10px;">
                                <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
                                    <strong>${{escapeHtml(label)}}</strong>
                                    <span>${{escapeHtml(formatPercent(safe))}}</span>
                                </div>
                                <div style="height:8px;border-radius:4px;background:var(--soft);overflow:hidden;">
                                    <div style="height:100%;width:${{(safe * 100).toFixed(1)}}%;background:var(--accent-strong);"></div>
                                </div>
                            </div>
                        `;
                    }}).join('');
                }}
            }}

            const filesEl = document.getElementById('adminEvaluationFiles');
            if (filesEl) {{
                const resultFiles = payload.resultFiles || [];
                const summaryMeta = payload.summaryFile || {{}};
                const goldenMeta = payload.goldenDataset || {{}};
                filesEl.innerHTML = `
                    <div style="margin-bottom:8px;">
                        <strong>Summary:</strong>
                        ${{summaryMeta.exists ? `evaluation_summary.csv · ${{formatSize(summaryMeta.sizeBytes)}} · ${{escapeHtml(summaryMeta.updatedAt || 'unknown')}}` : 'Missing'}}
                    </div>
                    <div style="margin-bottom:8px;">
                        <strong>Golden dataset:</strong>
                        ${{goldenMeta.exists ? `golden_dataset.csv · ${{goldenMeta.rows || 0}} rows · ${{escapeHtml(goldenMeta.updatedAt || 'unknown')}}` : 'Missing'}}
                    </div>
                    <div><strong>Detected evaluation files:</strong></div>
                    <ul style="margin:6px 0 0 16px;padding:0;">
                        ${{resultFiles.length ? resultFiles.map((f) => `<li>${{escapeHtml(f.name)}} · ${{formatSize(f.sizeBytes)}} · ${{escapeHtml(f.updatedAt)}}</li>`).join('') : '<li>No evaluation files found.</li>'}}
                    </ul>
                `;
            }}
        }}

        function renderAuditDetails(payload) {{
            const summary = payload.summary || {{}};
            const auditStatsEl = document.getElementById('adminAuditStats');
            if (auditStatsEl) {{
                auditStatsEl.innerHTML = [
                    statCard('Audit rows', summary.total_rows ?? 0),
                    statCard('Avg coverage', `${{summary.avg_coverage_pct ?? 0}}%`),
                    statCard('Below 60%', summary.below_60_count ?? 0),
                    statCard('Audit ready', payload.auditAvailable ? 'Yes' : 'No'),
                ].join('');
            }}

            const priorityBody = document.getElementById('adminAuditPriorityBody');
            if (priorityBody) {{
                const priorities = payload.prioritySummary || [];
                priorityBody.innerHTML = priorities.length
                    ? priorities.map((row) => `
                        <tr>
                            <td>${{escapeHtml(row.priority)}}</td>
                            <td>${{escapeHtml(row.count)}}</td>
                            <td>${{escapeHtml(String(row.avg_coverage_pct))}}%</td>
                            <td>${{escapeHtml(row.below_60)}}</td>
                        </tr>
                    `).join('')
                    : '<tr><td colspan="4">No audit priority summary available.</td></tr>';
            }}

            const lowestBody = document.getElementById('adminAuditLowestBody');
            if (lowestBody) {{
                const rows = payload.lowestCoverageRows || [];
                lowestBody.innerHTML = rows.length
                    ? rows.map((row) => `
                        <tr>
                            <td>${{escapeHtml(row.university || '—')}}</td>
                            <td>${{escapeHtml(row.priority || '—')}}</td>
                            <td>${{escapeHtml(String(row.coverage_pct))}}%</td>
                            <td>${{escapeHtml(row.programme_title || '—')}}</td>
                        </tr>
                    `).join('')
                    : '<tr><td colspan="4">No low-coverage rows available.</td></tr>';
            }}

            const filesEl = document.getElementById('adminAuditFiles');
            if (filesEl) {{
                const auditFiles = payload.auditFiles || [];
                const auditMeta = payload.auditFile || {{}};
                filesEl.innerHTML = `
                    <div style="margin-bottom:8px;">
                        <strong>Primary audit file:</strong>
                        ${{auditMeta.exists ? `priority_data_audit.csv · ${{auditMeta.rows || 0}} rows · ${{escapeHtml(auditMeta.updatedAt || 'unknown')}}` : 'Missing'}}
                    </div>
                    <div><strong>Detected audit files:</strong></div>
                    <ul style="margin:6px 0 0 16px;padding:0;">
                        ${{auditFiles.length ? auditFiles.map((f) => `<li>${{escapeHtml(f.name)}} · ${{formatSize(f.sizeBytes)}} · ${{escapeHtml(f.updatedAt)}}</li>`).join('') : '<li>No audit files found.</li>'}}
                    </ul>
                `;
            }}
        }}

        async function loadEvaluationDashboard() {{
            try {{
                const [evalResponse, auditResponse] = await Promise.all([
                    fetch('/api/admin/evaluation', {{ headers: authHeaders() }}),
                    fetch('/api/admin/audit', {{ headers: authHeaders() }}),
                ]);
                const evalPayload = await evalResponse.json();
                const auditPayload = await auditResponse.json();
                if (!evalResponse.ok) throw new Error(evalPayload.detail || evalPayload.error || 'Unable to load evaluation data.');
                if (!auditResponse.ok) throw new Error(auditPayload.detail || auditPayload.error || 'Unable to load audit data.');
                renderEvaluationDetails(evalPayload);
                renderAuditDetails(auditPayload);
            }} catch (error) {{
                const metricsEl = document.getElementById('adminEvaluationStats');
                if (metricsEl) metricsEl.innerHTML = `<p style="font-size:12px;color:#B91C1C;">${{escapeHtml(error.message)}}</p>`;
            }}
        }}

        async function adminRunEvaluation() {{
            setAuthError('evalActionError', '');
            document.getElementById('evalActionSuccess').style.display = 'none';
            try {{
                const response = await fetch('/api/admin/evaluation/run', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{}}),
                }});
                const result = await response.json();
                if (!response.ok || !result.ok) {{
                    setAuthError('evalActionError', result.detail || result.error || 'Failed to run evaluation script.');
                    return;
                }}
                if (result.dashboard) renderEvaluationDetails(result.dashboard);
                const successEl = document.getElementById('evalActionSuccess');
                successEl.style.display = 'block';
                successEl.textContent = 'Evaluation script completed successfully.';
                loadAdminOverview();
            }} catch (error) {{
                setAuthError('evalActionError', `Unable to run evaluation: ${{error.message}}`);
            }}
        }}

        async function adminUploadGoldenDataset() {{
            const fileInput = document.getElementById('evalGoldenFile');
            const file = fileInput.files[0];
            setAuthError('evalActionError', '');
            document.getElementById('evalActionSuccess').style.display = 'none';
            if (!file) {{
                setAuthError('evalActionError', 'Choose a golden dataset CSV to upload.');
                return;
            }}
            const formData = new FormData();
            formData.append('file', file);
            try {{
                const response = await fetch('/api/admin/evaluation/upload-golden', {{
                    method: 'POST',
                    headers: {{ 'Authorization': authHeaders().Authorization }},
                    body: formData,
                }});
                const result = await response.json();
                if (!response.ok || !result.ok) {{
                    setAuthError('evalActionError', result.detail || result.error || 'Golden dataset upload failed.');
                    return;
                }}
                fileInput.value = '';
                if (result.dashboard) renderEvaluationDetails(result.dashboard);
                const successEl = document.getElementById('evalActionSuccess');
                successEl.style.display = 'block';
                successEl.textContent = `Uploaded golden_dataset.csv (${{result.rows || 0}} rows).`;
            }} catch (error) {{
                setAuthError('evalActionError', `Unable to upload golden dataset: ${{error.message}}`);
            }}
        }}

        async function adminDownloadEvaluationSummary() {{
            try {{
                const response = await fetch('/api/admin/evaluation/download-summary', {{ headers: authHeaders() }});
                if (!response.ok) {{
                    const payload = await response.json();
                    throw new Error(payload.detail || 'Unable to download evaluation summary.');
                }}
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'evaluation_summary.csv';
                link.click();
                URL.revokeObjectURL(url);
            }} catch (error) {{
                setAuthError('evalActionError', error.message);
            }}
        }}

        async function adminRunAudit() {{
            setAuthError('auditActionError', '');
            document.getElementById('auditActionSuccess').style.display = 'none';
            try {{
                const response = await fetch('/api/admin/audit/run', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{}}),
                }});
                const result = await response.json();
                if (!response.ok || !result.ok) {{
                    setAuthError('auditActionError', result.detail || result.error || 'Failed to run audit script.');
                    return;
                }}
                if (result.dashboard) renderAuditDetails(result.dashboard);
                const successEl = document.getElementById('auditActionSuccess');
                successEl.style.display = 'block';
                successEl.textContent = 'Audit script completed successfully.';
            }} catch (error) {{
                setAuthError('auditActionError', `Unable to run audit: ${{error.message}}`);
            }}
        }}

        async function adminUploadAuditCsv() {{
            const fileInput = document.getElementById('auditUploadFile');
            const file = fileInput.files[0];
            setAuthError('auditActionError', '');
            document.getElementById('auditActionSuccess').style.display = 'none';
            if (!file) {{
                setAuthError('auditActionError', 'Choose an audit CSV file to upload.');
                return;
            }}
            const formData = new FormData();
            formData.append('file', file);
            try {{
                const response = await fetch('/api/admin/audit/upload', {{
                    method: 'POST',
                    headers: {{ 'Authorization': authHeaders().Authorization }},
                    body: formData,
                }});
                const result = await response.json();
                if (!response.ok || !result.ok) {{
                    setAuthError('auditActionError', result.detail || result.error || 'Audit CSV upload failed.');
                    return;
                }}
                fileInput.value = '';
                if (result.dashboard) renderAuditDetails(result.dashboard);
                const successEl = document.getElementById('auditActionSuccess');
                successEl.style.display = 'block';
                successEl.textContent = `Uploaded priority_data_audit.csv (${{result.rows || 0}} rows).`;
            }} catch (error) {{
                setAuthError('auditActionError', `Unable to upload audit CSV: ${{error.message}}`);
            }}
        }}

        async function adminDownloadAuditCsv() {{
            try {{
                const response = await fetch('/api/admin/audit/download', {{ headers: authHeaders() }});
                if (!response.ok) {{
                    const payload = await response.json();
                    throw new Error(payload.detail || 'Unable to download audit CSV.');
                }}
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'priority_data_audit.csv';
                link.click();
                URL.revokeObjectURL(url);
            }} catch (error) {{
                setAuthError('auditActionError', error.message);
            }}
        }}

        function setAuthError(elementId, message) {{
            const el = document.getElementById(elementId);
            el.textContent = message;
            el.classList.toggle('show', Boolean(message));
        }}

        async function handleLogin() {{
            const email = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            if (!email || !password) {{
                setAuthError('loginError', 'Please enter your email address and password.');
                return;
            }}
            setAuthError('loginError', '');
            try {{
                const response = await fetch('/api/auth/login', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ email, password }}),
                }});
                const result = await response.json();
                if (!result.ok) {{
                    setAuthError('loginError', result.error || 'Sign in failed.');
                    return;
                }}
                sessionStorage.setItem(SESSION_KEY, JSON.stringify(result.user));
                enterApp(result.user);
            }} catch (error) {{
                setAuthError('loginError', `Unable to reach the admissions service: ${{error.message}}`);
            }}
        }}

        async function handleRegister() {{
            const name = document.getElementById('registerName').value.trim();
            const email = document.getElementById('registerEmail').value.trim();
            const password = document.getElementById('registerPassword').value;
            if (!name || !email || !password) {{
                setAuthError('registerError', 'Please complete every field.');
                return;
            }}
            setAuthError('registerError', '');
            let result;
            try {{
                const response = await fetch('/api/auth/register', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ name, email, password }}),
                }});
                result = await response.json();
            }} catch (error) {{
                setAuthError('registerError', `Unable to reach the admissions service: ${{error.message}}`);
                return;
            }}
            if (!result.ok) {{
                setAuthError('registerError', result.error || 'Registration failed.');
                return;
            }}
            document.getElementById('registerCardBody').innerHTML = `
                <div class="auth-success">
                    <div class="check-circle">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    </div>
                    <h1 class="auth-title">Request submitted</h1>
                    <p class="auth-subtitle">An administrator will review your access request for ${{escapeHtml(name)}}.</p>
                    <button class="auth-submit" onclick="showAuthScreen('login')">Back to sign in</button>
                </div>`;
        }}

        function signOut() {{
            sessionStorage.removeItem(SESSION_KEY);
            showAuthScreen('login');
        }}

        function restoreSession() {{
            const raw = sessionStorage.getItem(SESSION_KEY);
            if (!raw) {{ showAuthScreen('login'); return; }}
            try {{
                const session = JSON.parse(raw);
                enterApp({{ name: session.name || 'Tutor', role: session.role || 'tutor' }});
            }} catch (error) {{
                showAuthScreen('login');
            }}
        }}

        function authHeaders() {{
            const key = defaultApiKey;
            return {{ 'Authorization': `Bearer ${{key}}`, 'Content-Type': 'application/json' }};
        }}

        function loadDefaults() {{
            document.getElementById('targetProgramme').value = 'Computer Science BSc - University of Liverpool';
            document.getElementById('competitorUniversity').value = 'University of Leeds';
            document.getElementById('priorityEntryRequirements').checked = true;
            document.getElementById('priorityCurriculumAccreditation').checked = true;
            document.getElementById('priorityGraduateOutcomes').checked = true;
            document.getElementById('priorityFeesAndCost').checked = false;
            document.getElementById('priorityTeachingQuality').checked = false;
            document.getElementById('priorityRankings').checked = false;
            document.getElementById('question').value = 'Compare the target programme against the selected competitor university using the selected priorities and return a short decision summary.';
        }}

        function escapeHtml(text) {{
            return String(text || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }}

        function citationLabel(source, index, providedLabel) {{
            const fallback = `Source ${{index + 1}}`;
            if (providedLabel) return providedLabel;
            if (!source) return fallback;
            if (source.startsWith('SQLite:')) return 'Structured admissions database';
            if (source.includes('knowledge_base')) return 'Vector DB Doc #42';
            return source.replace(/^https?:\/\//, '').replace(/\/.*$/, '') || fallback;
        }}

        function linkSummaryCitations(answer) {{
            const escaped = escapeHtml(answer || '');
            return escaped.replace(/\[(\d+)\]/g, (_, n) => `<a class="summary-link" href="#" onclick="openCitationByNumber(${{Number(n)}}); return false;">[${{n}}]</a>`);
        }}

        function formatComparisonSummary(answer) {{
            const raw = String(answer || '').replace(/\\r?\\n/g, ' ').trim();
            if (!raw) return '<div class="empty-state">No answer returned.</div>';

            const isLimited = /too limited|limited data|limited evidence|could not be fully verified/i.test(raw);
            const limitedBanner = isLimited
                ? '<div class="limited-banner"><strong>Limited evidence:</strong>&nbsp;Some selected priorities have partial or unverified data. Treat those figures with caution.</div>'
                : '';

            let body = raw.replace(/^Decision summary:\s*/i, '');
            let recommendation = '';
            const recommendationMatch = body.match(/Overall recommendation:\s*(.*?)(?=\s*\[\d+\]|$)/i);
            if (recommendationMatch) {{
                recommendation = recommendationMatch[1].trim().replace(/[.]+$/, '');
                body = body.slice(0, recommendationMatch.index).replace(/[|\s]+$/, '').trim();
            }}

            const sections = body.split(/\s*\|\s*/).filter(Boolean);
            const rendered = sections.map((section) => {{
                const match = section.match(/^([^:]+):\s*(.*)$/);
                if (!match) return `<p class="priority-detail">${{linkSummaryCitations(section)}}</p>`;

                const heading = match[1].trim();
                let detail = match[2].trim();
                let winner = '';
                let reason = '';
                const winnerMatch = detail.match(/\s*Winner:\s*(.*?)(?=\.\s*(?:Higher|Lower|Both|A-level|The current|$))/i);
                if (winnerMatch) {{
                    winner = winnerMatch[1].trim();
                    detail = detail.slice(0, winnerMatch.index).trim();
                    const remainder = match[2].slice(winnerMatch.index + winnerMatch[0].length).trim();
                    reason = remainder.replace(/^\.\s*/, '').trim();
                }}

                const isDraw = /unavailable|draw|closely matched/i.test(winner) || !winner;
                const badge = winner
                    ? `<span class="winner-badge${{isDraw ? ' draw' : ''}}">${{isDraw ? 'No clear winner' : escapeHtml(winner)}}</span>`
                    : '';

                return `<section class="priority-section">
                    <div class="priority-heading-row">
                        <h4 class="priority-heading">${{escapeHtml(heading)}}</h4>
                        ${{badge}}
                    </div>
                    <p class="priority-detail">${{linkSummaryCitations(detail)}}</p>
                    ${{reason ? `<p class="priority-reason">${{linkSummaryCitations(reason)}}</p>` : ''}}
                </section>`;
            }}).join('');

            const recommendationHtml = recommendation
                ? `<section class="recommendation"><h4 class="recommendation-heading">Overall Recommendation</h4><div>${{linkSummaryCitations(recommendation)}}</div></section>`
                : '';
            return `${{limitedBanner}}<div class="summary-content">${{rendered}}${{recommendationHtml}}</div>`;
        }}

        function openCitationByNumber(number) {{
            const item = (state.citations || [])[number - 1];
            if (!item) return;
            document.getElementById('citationModalTitle').textContent = `[${{number}}] ${{item.label || `Source ${{number}}`}}`;
            const metaParts = [];
            if (item.source) metaParts.push(item.source);
            if (item.url) metaParts.push(item.url);
            document.getElementById('citationModalMeta').textContent = metaParts.join(' | ');
            document.getElementById('citationModalContent').textContent = item.content || item.snippet || 'No evidence text available.';
            document.getElementById('citationModal').classList.add('open');
        }}

        function closeCitationModal(event) {{
            if (event && event.target && event.target.id !== 'citationModal') return;
            document.getElementById('citationModal').classList.remove('open');
        }}

        function renderCitations(result) {{
            const container = document.getElementById('sources');
            const citations = (result.citations || []).filter(Boolean);
            state.citations = citations;

            if (!citations.length) {{
                container.innerHTML = '<div class="citation"><strong>[1]</strong> No citations returned.</div>';
                return;
            }}

            container.innerHTML = citations.map((item, index) => {{
                const source = item.source || '';
                const label = escapeHtml(citationLabel(source, index, item.label || ''));
                const snippet = item.snippet ? escapeHtml(item.snippet.length > 180 ? `${{item.snippet.slice(0, 180)}}...` : item.snippet) : '';
                const external = item.url ? `<div style="margin-top:6px;"><a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">Open source page</a></div>` : '';
                return `<div class="citation" id="citation-${{index + 1}}"><strong>[${{index + 1}}]</strong> <button onclick="openCitationByNumber(${{index + 1}})">${{label}}</button>${{snippet ? `<div style="margin-top:6px;color:var(--muted);font-size:13px;">${{snippet}}</div>` : ''}}${{external}}</div>`;
            }}).join('');
        }}

        function setSummaryText(result) {{
            const response = document.getElementById('response');
            const answer = result.answer || 'No answer returned.';
            response.innerHTML = formatComparisonSummary(answer);
            renderCitations(result);
        }}

        async function refreshStatus() {{
            return;
        }}

        async function submitQuery() {{
            const targetProgramme = 'Computer Science BSc';
            const baselineUniversity = 'University of Liverpool';
            const competitorUniversity = document.getElementById('competitorUniversity').value.trim();
            const priorities = [
                document.getElementById('priorityEntryRequirements').checked ? 'Entry Requirements (A-level requirement, entry tariff UCAS points, % entrants via A-level, foundation year availability)' : null,
                document.getElementById('priorityCurriculumAccreditation').checked ? 'Curriculum & Accreditation (BCS accreditation, final year project credits, placement year, year abroad)' : null,
                document.getElementById('priorityGraduateOutcomes').checked ? 'Graduate Outcomes & Salary (median salary LEO 3-year, LEO 5-year, graduate outcomes salary, employment rate 15 months, % professional/managerial jobs)' : null,
                document.getElementById('priorityFeesAndCost').checked ? 'Fees & Cost (UK tuition fee, international tuition fee)' : null,
                document.getElementById('priorityTeachingQuality').checked ? 'Teaching Quality & NSS (NSS teaching satisfaction, NSS mental wellbeing, NSS facilities, TEF overall rating, TEF student experience)' : null,
                document.getElementById('priorityRankings').checked ? 'University Rankings (Guardian rank, CUG rank, QS world rank)' : null,
            ].filter(Boolean);
            const additionalInstruction = document.getElementById('question').value.trim();

            if (priorities.length === 0) {{
                document.getElementById('response').innerHTML = '<div class="error-banner">Please select at least one priority before comparing.</div>';
                return;
            }}

            const promptParts = [
                `Compare the target programme "${{targetProgramme}}" from "${{baselineUniversity}}" against the selected competitor university "${{competitorUniversity || 'N/A'}}" using the selected priorities (${{priorities.join(', ') || 'none'}}) and return a short decision summary.`
            ];
            if (additionalInstruction) {{
                promptParts.push(`Additional tutor instruction: ${{additionalInstruction}}`);
            }}
            const tutorPrompt = promptParts.join('\\n');

            document.getElementById('response').innerHTML = `
                <div class="loading-state">
                    <div class="loading-row"><span class="spinner"></span>Generating comparison summary…</div>
                    <div class="skeleton-row"></div>
                    <div class="skeleton-row"></div>
                    <div class="skeleton-row"></div>
                </div>`;

            try {{
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({{
                        question: tutorPrompt,
                        target_programme: targetProgramme,
                        baseline_university: baselineUniversity,
                        competitor_university: competitorUniversity,
                        priorities: priorities,
                        additional_instruction: additionalInstruction,
                    }}),
                }});
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Request failed');
                setSummaryText(result);
            }} catch (error) {{
                document.getElementById('response').innerHTML = `<div class="error-banner">Comparison unavailable: ${{escapeHtml(error.message)}}</div>`;
            }}
        }}

        refreshStatus();
        setInterval(refreshStatus, 12000);
        restoreSession();
    </script>
</body>
</html>""".format(UI_TITLE=UI_TITLE)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                if isinstance(text_val, str):
                    chunks.append(text_val)
        return "\n".join(chunks).strip()

    return ""


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                if isinstance(text_val, str):
                    chunks.append(text_val)
        return "\n".join(chunks).strip()

    return ""


def _get_latest_user_message(messages: List["ChatMessage"]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            text = _extract_text_content(msg.content)
            if text:
                return text
    return ""


def _sanitize_tutor_prompt(text: str) -> str:
    if not text:
        return ""

    sanitized = text
    blocked_phrases = [
        "Compare only these two universities.",
        "Compare only University of Liverpool Computer Science BSc with the selected competitor university.",
    ]
    for phrase in blocked_phrases:
        sanitized = sanitized.replace(phrase, "")

    sanitized = " ".join(sanitized.split())
    return sanitized.strip()


def _check_api_key(auth_header: Optional[str]) -> None:
    expected = os.getenv("API_AUTH_KEY", "openwebui-local-key")

    # Keep auth optional if explicitly disabled for trusted internal networks.
    if os.getenv("DISABLE_API_AUTH", "false").lower() == "true":
        return

    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    provided = auth_header.split(" ", 1)[1].strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_ID
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.0
    stream: Optional[bool] = False
    user: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: Dict[str, str]
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]


def _to_chat_completion(
    completion_id: str,
    created: int,
    answer: str,
    query: str,
) -> ChatCompletionResponse:
    prompt_tokens = max(1, len(query.split()))
    completion_tokens = max(1, len(answer.split()))

    return ChatCompletionResponse(
        id=completion_id,
        object="chat.completion",
        created=created,
        model=MODEL_ID,
        choices=[
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": answer},
                finish_reason="stop",
            )
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


def _stream_completion_chunks(completion_id: str, created: int, answer: str) -> Iterator[str]:
    words = answer.split()
    if not words:
        words = [""]

    for i, word in enumerate(words):
        token = f"{word} " if i < len(words) - 1 else word
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload)}\n\n"

    final_payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_payload)}\n\n"
    yield "data: [DONE]\n\n"


app = FastAPI(title=APP_TITLE, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rag_instance: Any = None
_rag_lock = threading.Lock()
_rag_prewarm_started = False


def _get_rag() -> Any:
    global _rag_instance
    if _rag_instance is None:
        with _rag_lock:
            if _rag_instance is None:
                from rag_orchestrator import AdmissionsRAGOrchestrator

                _rag_instance = AdmissionsRAGOrchestrator(
                    db_directory=os.getenv("CHROMA_DB_PATH", "./chroma_db"),
                    sql_db_path=os.getenv("SQL_DB_PATH", "./admissions_structured.db"),
                )
    return _rag_instance


def _prewarm_rag() -> None:
    global _rag_prewarm_started
    if _rag_prewarm_started:
        return
    _rag_prewarm_started = True

    def _worker() -> None:
        try:
            _get_rag()
        except Exception:
            pass

    threading.Thread(target=_worker, name="rag-prewarm", daemon=True).start()


@app.get("/")
def root() -> HTMLResponse:
    return HTMLResponse(_render_ui_html())


@app.on_event("startup")
def startup_event() -> None:
    auth_db.init_auth_db()
    _prewarm_rag()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    department: Optional[str] = None


class UserStatusRequest(BaseModel):
    status: str
    rejection_reason: Optional[str] = None


class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "tutor"
    department: Optional[str] = None


def _user_public_fields(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "department": row["department"],
        "status": row["status"],
        "lastLogin": row["last_login"],
        "createdAt": row["created_at"],
    }


@app.post("/api/auth/login")
def api_auth_login(payload: LoginRequest) -> Dict[str, Any]:
    row = auth_db.get_user_by_email(payload.email)
    if row is None:
        return {"ok": False, "error": "No account found with this email address."}

    if auth_db.hash_password(payload.password) != row["password_hash"]:
        return {"ok": False, "error": "Incorrect password."}

    if row["status"] == "rejected":
        reason = f": {row['rejection_reason']}" if row["rejection_reason"] else "."
        return {"ok": False, "error": f"Your registration was not approved{reason} Contact the administrator."}
    if row["status"] == "pending":
        return {"ok": False, "error": "Your account is awaiting administrator approval. You will be notified by email."}
    if row["status"] == "inactive":
        return {"ok": False, "error": "This account has been deactivated. Contact your administrator."}

    auth_db.update_last_login(row["id"])
    return {"ok": True, "user": _user_public_fields(row)}


@app.post("/api/auth/register")
def api_auth_register(payload: RegisterRequest) -> Dict[str, Any]:
    email = payload.email.strip().lower()
    if not email.endswith("@liverpool.ac.uk"):
        return {"ok": False, "error": "Registration requires a @liverpool.ac.uk email address."}
    if len(payload.password) < 8:
        return {"ok": False, "error": "Password must be at least 8 characters."}
    if auth_db.get_user_by_email(email) is not None:
        return {"ok": False, "error": "An account with this email already exists."}

    user = auth_db.create_user(payload.name.strip(), email, payload.password, "tutor", payload.department)
    return {"ok": True, "user": user}


@app.get("/api/auth/users")
def api_auth_list_users(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    rows = auth_db.list_users()
    return {"users": [
        {
            "id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
            "department": r["department"], "status": r["status"],
            "lastLogin": r["last_login"], "createdAt": r["created_at"],
        }
        for r in rows
    ]}


@app.post("/api/auth/users/{user_id}/status")
def api_auth_update_status(
    user_id: str,
    payload: UserStatusRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)
    try:
        auth_db.update_user_status(user_id, payload.status, payload.rejection_reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.post("/api/auth/users")
def api_auth_create_user(
    payload: CreateUserRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)
    email = payload.email.strip().lower()
    if not email.endswith("@liverpool.ac.uk"):
        return {"ok": False, "error": "Must be a @liverpool.ac.uk email."}
    if auth_db.get_user_by_email(email) is not None:
        return {"ok": False, "error": "Email already exists."}
    if payload.role not in auth_db.VALID_ROLES:
        return {"ok": False, "error": "Invalid role."}

    user = auth_db.create_user(payload.name.strip(), email, payload.password or "Temp1234!", payload.role, payload.department)
    auth_db.update_user_status(user["id"], "active")
    return {"ok": True, "user": {**user, "status": "active"}}


def _knowledge_base_summary() -> Dict[str, Any]:
    root = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(root, "clearing_knowledge_base.json")
    kb_entries = 0
    kb_updated: Optional[str] = None
    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r", encoding="utf-8") as handle:
                kb_entries = len(json.load(handle))
        except Exception:
            kb_entries = 0
        kb_updated = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(kb_path)))

    sql_db_path = os.getenv("SQL_DB_PATH", os.path.join(root, "admissions_structured.db"))
    course_rows = 0
    if os.path.exists(sql_db_path):
        try:
            conn = sqlite3.connect(sql_db_path)
            course_rows = conn.execute("SELECT COUNT(*) FROM course_facts").fetchone()[0]
            conn.close()
        except Exception:
            course_rows = 0

    chroma_dir = os.getenv("CHROMA_DB_PATH", os.path.join(root, "chroma_db"))
    return {
        "kbEntries": kb_entries,
        "kbUpdated": kb_updated,
        "courseFactsRows": course_rows,
        "sqlDbPresent": os.path.exists(sql_db_path),
        "chromaDbPresent": os.path.isdir(chroma_dir),
    }


def _system_summary(users: List[Dict[str, Any]]) -> Dict[str, Any]:
    gemini_configured = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GIMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return {
        "geminiConfigured": gemini_configured,
        "apiAuthConfigured": bool(os.getenv("API_AUTH_KEY", "openwebui-local-key")),
        "usersTotal": len(users),
        "usersActive": sum(1 for u in users if u["status"] == "active"),
        "usersPending": sum(1 for u in users if u["status"] == "pending"),
        "serverTime": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/admin/overview")
def api_admin_overview(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    rows = auth_db.list_users()
    users = [
        {
            "id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
            "department": r["department"], "status": r["status"],
            "lastLogin": r["last_login"], "createdAt": r["created_at"],
        }
        for r in rows
    ]
    return {
        "users": users,
        "knowledge": _knowledge_base_summary(),
        "evaluation": _load_summary_metrics(),
        "system": _system_summary(users),
    }


class RunScriptRequest(BaseModel):
    script: str


@app.get("/api/admin/kb/sources")
def api_admin_kb_sources(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    return {"sources": admin_kb.list_sources(), "uploadTargets": sorted(admin_kb.UPLOAD_TARGETS)}


@app.get("/api/admin/kb/script/{script_name}")
def api_admin_kb_script(script_name: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    try:
        content = admin_kb.read_script(script_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"filename": script_name, "content": content}


@app.post("/api/admin/kb/run")
def api_admin_kb_run(payload: RunScriptRequest, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    return admin_kb.run_script(payload.script)


@app.post("/api/admin/kb/upload")
async def api_admin_kb_upload(
    target: str = Form(...),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)
    content = await file.read()
    return admin_kb.save_uploaded_csv(target, content)


@app.get("/api/admin/evaluation")
def api_admin_evaluation(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    return _evaluation_dashboard_payload()


@app.post("/api/admin/evaluation/run")
def api_admin_run_evaluation(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    result = _run_workspace_script(EVALUATION_SCRIPT, timeout=420)
    result["dashboard"] = _evaluation_dashboard_payload()
    return result


@app.post("/api/admin/evaluation/upload-golden")
async def api_admin_upload_golden_dataset(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)
    content = await file.read()
    upload = admin_kb.save_uploaded_csv("golden_dataset.csv", content)
    upload["dashboard"] = _evaluation_dashboard_payload()
    return upload


@app.get("/api/admin/evaluation/download-summary")
def api_admin_download_evaluation_summary(authorization: Optional[str] = Header(default=None)) -> FileResponse:
    _check_api_key(authorization)
    summary_path = _resolve_workspace_file("evaluation_summary.csv")
    if not os.path.exists(summary_path):
        raise HTTPException(status_code=404, detail="evaluation_summary.csv was not found.")
    return FileResponse(path=summary_path, media_type="text/csv", filename="evaluation_summary.csv")


@app.get("/api/admin/audit")
def api_admin_audit(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    return _audit_dashboard_payload()


@app.post("/api/admin/audit/run")
def api_admin_run_audit(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    result = _run_workspace_script(DATA_AUDIT_SCRIPT, timeout=420)
    result["dashboard"] = _audit_dashboard_payload()
    return result


@app.post("/api/admin/audit/upload")
async def api_admin_upload_audit_file(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)
    content = await file.read()
    upload = admin_kb.save_uploaded_csv("priority_data_audit.csv", content)
    upload["dashboard"] = _audit_dashboard_payload()
    return upload


@app.get("/api/admin/audit/download")
def api_admin_download_audit_csv(authorization: Optional[str] = Header(default=None)) -> FileResponse:
    _check_api_key(authorization)
    csv_path = _resolve_workspace_file("priority_data_audit.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="priority_data_audit.csv was not found.")
    return FileResponse(path=csv_path, media_type="text/csv", filename="priority_data_audit.csv")


@app.get("/api/summary")
def api_summary() -> Dict[str, Any]:
    return _load_summary_metrics()


@app.post("/api/chat")
def api_chat(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _check_api_key(authorization)

    question = _sanitize_tutor_prompt(str(payload.get("question", "")).strip())
    target_programme = BASELINE_PROGRAMME
    baseline_university = BASELINE_UNIVERSITY
    competitor_university = str(payload.get("competitor_university", "")).strip()
    additional_instruction = _sanitize_tutor_prompt(str(payload.get("additional_instruction", "")).strip())
    priorities = payload.get("priorities", [])
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")

    # Map priority labels to the DB column groups they cover, so the SQL router fires correctly.
    _PRIORITY_COLUMN_HINTS = {
        "Entry Requirements": "entry tariff alevel_requirement UCAS points a-level requirement foundation year",
        "Curriculum & Accreditation": "bcs accredited final year project credits placement year year abroad",
        "Graduate Outcomes & Salary": "median salary employment rate professional managerial LEO 3-year 5-year",
        "Fees & Cost": "tuition fee uk international tuition fee",
        "Teaching Quality & NSS": "nss teaching satisfaction mental wellbeing facilities tef rating",
        "University Rankings": "guardian rank cug rank qs rank league table ranking",
    }

    priority_column_terms = []
    for p in priorities:
        for label, terms in _PRIORITY_COLUMN_HINTS.items():
            if label.lower() in str(p).lower():
                priority_column_terms.append(terms)
                break

    focused_question = question
    if target_programme or competitor_university or priorities:
        priority_text = ", ".join(str(item) for item in priorities) if priorities else "none"
        parts = [
            f'Compare the target programme "{target_programme}" from "{baseline_university}" against the selected competitor university "{competitor_university or "N/A"}" using the selected priorities ({priority_text}) and return a short decision summary.'
        ]
        if priority_column_terms:
            parts.append(f"Focus on: {' | '.join(priority_column_terms)}")
        if question:
            parts.append(f"Provided tutor prompt: {question}")
        if additional_instruction:
            parts.append(f"Additional tutor instruction: {additional_instruction}")
        if target_programme:
            parts.append(f"Target programme: {target_programme}")
        if baseline_university:
            parts.append(f"Baseline university: {baseline_university}")
        if competitor_university:
            parts.append(f"Competitor university: {competitor_university}")
        if priorities:
            parts.append(f"Student priorities: {', '.join(str(item) for item in priorities)}")
        focused_question = "\n".join(parts)

    result = _get_rag().query_pipeline(
        focused_question,
        target_competitor=competitor_university or None,
        target_programme=target_programme or None,
        target_baseline=baseline_university or None,
        priorities=priorities or None,
    )
    return {
        "question": question,
        "answer": result.get("answer", "Insufficient information in the provided context."),
        "engine_used": result.get("engine_used"),
        "routing_layer": result.get("routing_layer"),
        "latency_seconds": result.get("latency_seconds"),
        "confidence_score": result.get("confidence_score"),
        "should_abstain": result.get("should_abstain"),
        "sources": result.get("sources", []),
        "citations": result.get("citations", []),
        "contexts": result.get("contexts", []),
    }


@app.get("/v1/models")
def list_models(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _check_api_key(authorization)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": now,
                "owned_by": "admissions-assistant",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(
    payload: ChatCompletionRequest,
    authorization: Optional[str] = Header(default=None),
) -> Any:
    _check_api_key(authorization)

    query = _get_latest_user_message(payload.messages)
    if not query:
        raise HTTPException(status_code=400, detail="No user message found in request")

    result = _get_rag().query_pipeline(query)
    answer = result.get("answer", "Insufficient information in the provided context.")

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    now = int(time.time())

    if payload.stream:
        return StreamingResponse(
            _stream_completion_chunks(completion_id, now, answer),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return _to_chat_completion(completion_id, now, answer, query)
