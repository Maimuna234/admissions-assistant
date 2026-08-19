"""Real Knowledge Base admin operations: script metadata, execution, and CSV uploads.

Wires the admin dashboard's Knowledge Base tab to the project's actual scraper,
ranking, curriculum, and ingestion scripts instead of mock data.
"""
import csv
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable

SOURCES: List[Dict[str, Any]] = [
    {
        "id": "rankings_fees_entry",
        "label": "Rankings, Fees & Entry (CSV Import)",
        "script": "update_audit_sources.py",
        "csv": "CSV-version.csv",
        "runnable": True,
        "description": "Applies CSV-version.csv plus verified fee/entry/course evidence into admissions_structured.db and clearing_knowledge_base.json.",
    },
    {
        "id": "rankings_scraper",
        "label": "CUG / QS Rankings Scraper",
        "script": "ranking_scraper.py",
        "csv": None,
        "runnable": True,
        "description": "Fetches the live CUG league table and updates ranking columns in admissions_structured.db.",
    },
    {
        "id": "ucas_scraper",
        "label": "UCAS Entry Requirements Scraper",
        "script": "ucas_scraper.py",
        "csv": None,
        "runnable": True,
        "description": "Scrapes A-level tariff and fee data into admissions_structured.db.",
    },
    {
        "id": "curriculum_scraper",
        "label": "Curriculum & Project Credits Scraper",
        "script": "curriculum_scraper.py",
        "csv": None,
        "runnable": True,
        "description": "Scrapes final-year project credit information into admissions_structured.db.",
    },
    {
        "id": "competitor_scraper",
        "label": "Competitor Qualitative Scraper",
        "script": "competitor_scraper.py",
        "csv": None,
        "runnable": False,
        "description": "Module used by the knowledge base builder to scrape qualitative course content (curriculum, placements, facilities).",
    },
    {
        "id": "knowledge_base_builder",
        "label": "Knowledge Base Builder",
        "script": "build_knowledge_base.py",
        "csv": None,
        "runnable": True,
        "description": "Merges quantitative and qualitative sources into clearing_knowledge_base.json.",
    },
    {
        "id": "vector_indexer",
        "label": "Vector Index Rebuild",
        "script": "vector_indexer.py",
        "csv": None,
        "runnable": True,
        "description": "Rebuilds the chroma_db vector store from clearing_knowledge_base.json.",
    },
    {
        "id": "ingest",
        "label": "Raw Document Ingestion",
        "script": "ingest.py",
        "csv": None,
        "runnable": True,
        "description": "Chunks and embeds sample admissions text records directly into chroma_db.",
    },
]

RUNNABLE_SCRIPTS = {s["script"] for s in SOURCES if s["runnable"]}
KNOWN_SCRIPTS = {s["script"] for s in SOURCES}
UPLOAD_TARGETS = {"CSV-version.csv", "golden_dataset.csv", "priority_data_audit.csv"}


def _path(name: str) -> str:
    return os.path.join(ROOT, name)


def _file_meta(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"exists": False, "updatedAt": None, "sizeBytes": 0}
    return {
        "exists": True,
        "updatedAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path))),
        "sizeBytes": os.path.getsize(path),
    }


def _csv_row_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def list_sources() -> List[Dict[str, Any]]:
    result = []
    for src in SOURCES:
        entry = dict(src)
        script_meta = _file_meta(_path(src["script"]))
        entry["scriptExists"] = script_meta["exists"]
        entry["scriptUpdatedAt"] = script_meta["updatedAt"]
        if src["csv"]:
            csv_meta = _file_meta(_path(src["csv"]))
            entry["csvExists"] = csv_meta["exists"]
            entry["csvUpdatedAt"] = csv_meta["updatedAt"]
            entry["csvRows"] = _csv_row_count(_path(src["csv"]))
        result.append(entry)
    return result


def read_script(script_name: str) -> str:
    if script_name not in KNOWN_SCRIPTS:
        raise ValueError(f"Unknown script: {script_name}")
    path = _path(script_name)
    if not os.path.exists(path):
        return f"# {script_name}\n# File not found on disk.\n"
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def run_script(script_name: str, timeout: int = 180) -> Dict[str, Any]:
    if script_name not in RUNNABLE_SCRIPTS:
        return {"ok": False, "error": f"{script_name} is not a runnable pipeline script."}
    path = _path(script_name)
    if not os.path.exists(path):
        return {"ok": False, "error": f"{script_name} was not found in the project directory."}
    try:
        proc = subprocess.run(
            [PYTHON_EXE, path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{script_name} timed out after {timeout} seconds."}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": str(exc)}


def save_uploaded_csv(target_filename: str, content: bytes) -> Dict[str, Any]:
    if target_filename not in UPLOAD_TARGETS:
        return {"ok": False, "error": f"Uploads are only permitted for: {', '.join(sorted(UPLOAD_TARGETS))}"}
    path = _path(target_filename)
    if os.path.exists(path):
        os.replace(path, f"{path}.bak-{int(time.time())}")
    with open(path, "wb") as handle:
        handle.write(content)
    return {"ok": True, "file": target_filename, "rows": _csv_row_count(path)}
