import argparse
import csv
import json
import sqlite3
from pathlib import Path

PLACEHOLDERS = {
    None,
    "",
    "None",
    "nan",
    "NaN",
    "N/A",
    "Not found",
    "Not published centrally",
    "Needs verification",
    "Information Not Listed",
}

PRIORITY_FIELD_MAP = {
    "Entry Requirements": {
        "sql_fields": ["entry_tariff", "alevel_requirement", "pct_entrants_alevel", "has_foundation_year"],
        "kb_metrics": [],
        "kb_layers": ["entry_requirements"],
    },
    "Curriculum & Accreditation": {
        "sql_fields": ["bcs_accredited", "has_placement_year", "has_year_abroad", "final_year_project_credits"],
        "kb_metrics": [],
        "kb_layers": ["curriculum_year_1", "curriculum_year_2", "curriculum_year_3", "industrial_placements"],
    },
    "Graduate Outcomes & Salary": {
        "sql_fields": ["median_salary_leo3", "median_salary_leo5", "median_salary_go", "employment_rate_15m", "pct_professional_managerial"],
        "kb_metrics": ["leo_median_salary_3_years", "graduate_in_work_15_months_pct"],
        "kb_layers": ["career_outcomes"],
    },
    "Fees & Cost": {
        "sql_fields": ["tuition_fee_uk", "tuition_fee_intl"],
        "kb_metrics": ["annual_tuition_fee_uk"],
        "kb_layers": [],
    },
    "Teaching Quality & NSS": {
        "sql_fields": ["nss_teaching_satisfaction", "nss_mental_wellbeing", "nss_facilities_resources", "tef_overall_rating", "tef_student_experience"],
        "kb_metrics": [],
        "kb_layers": ["student_support", "infrastructure_and_facilities"],
    },
    "University Rankings": {
        "sql_fields": ["guardian_rank", "cug_rank", "qs_rank"],
        "kb_metrics": [],
        "kb_layers": [],
    },
}


def uni_key(name: str) -> str:
    return " ".join(str(name or "").lower().replace("the ", "").split())


def is_present(value) -> bool:
    if isinstance(value, str):
        return value.strip() not in PLACEHOLDERS
    return value not in PLACEHOLDERS


def load_kb_entries(kb_path: Path):
    with kb_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, list) else []


def select_best_row(rows, programme_keyword: str):
    if not rows:
        return None
    keyword = (programme_keyword or "").strip().lower()
    if not keyword:
        return rows[0]

    strict_matches = []
    broad_matches = []
    for row in rows:
        title = str(row.get("course_title", "") or "").lower()
        if keyword in title and "with" not in title and "(" not in title:
            strict_matches.append(row)
        if keyword in title:
            broad_matches.append(row)

    if strict_matches:
        return strict_matches[0]
    if broad_matches:
        return broad_matches[0]
    return rows[0]


def fetch_course_rows(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    available_columns = [r[1] for r in cursor.execute("PRAGMA table_info(course_facts)").fetchall()]
    required = [
        "university", "course_title", "entry_tariff", "alevel_requirement", "pct_entrants_alevel", "has_foundation_year",
        "bcs_accredited", "has_placement_year", "has_year_abroad", "final_year_project_credits", "median_salary_go",
        "median_salary_leo3", "median_salary_leo5", "employment_rate_15m", "pct_professional_managerial", "tuition_fee_uk",
        "tuition_fee_intl", "nss_teaching_satisfaction", "nss_mental_wellbeing", "nss_facilities_resources", "tef_overall_rating",
        "tef_student_experience", "guardian_rank", "cug_rank", "qs_rank",
    ]
    selected = [c for c in required if c in available_columns]
    rows = [dict(row) for row in cursor.execute(f"SELECT {', '.join(selected)} FROM course_facts").fetchall()]
    return rows


def build_report(db_rows, kb_entries, priorities, programme_keyword):
    grouped_sql = {}
    for row in db_rows:
        grouped_sql.setdefault(uni_key(row.get("university")), []).append(row)
    grouped_kb = {uni_key(e.get("university_name")): e for e in kb_entries}
    university_keys = sorted(set(grouped_sql.keys()) | set(grouped_kb.keys()))

    report_rows = []
    for ukey in university_keys:
        best_sql = select_best_row(grouped_sql.get(ukey, []), programme_keyword)
        kb_entry = grouped_kb.get(ukey, {})
        display_name = (best_sql or {}).get("university") or kb_entry.get("university_name") or ukey
        title = str((best_sql or {}).get("course_title", "") or "")
        title_match = programme_keyword.lower() in title.lower() if programme_keyword else True

        for priority in priorities:
            mapping = PRIORITY_FIELD_MAP[priority]
            sql_present, kb_present = 0, 0
            sql_missing, kb_missing = [], []

            for field in mapping["sql_fields"]:
                value = (best_sql or {}).get(field)
                if is_present(value):
                    sql_present += 1
                else:
                    sql_missing.append(field)

            metrics = (kb_entry or {}).get("metrics", {}) or {}
            layers = (kb_entry or {}).get("knowledge_layers", {}) or {}

            for field in mapping["kb_metrics"]:
                value = metrics.get(field)
                if is_present(value):
                    kb_present += 1
                else:
                    kb_missing.append(field)

            for field in mapping["kb_layers"]:
                value = layers.get(field)
                if is_present(value):
                    kb_present += 1
                else:
                    kb_missing.append(field)

            required_total = len(mapping["sql_fields"]) + len(mapping["kb_metrics"]) + len(mapping["kb_layers"])
            coverage_pct = round(((sql_present + kb_present) / required_total) * 100, 1) if required_total else 100.0

            report_rows.append({
                "university": display_name,
                "programme_title": title,
                "programme_matches_keyword": title_match,
                "priority": priority,
                "coverage_pct": coverage_pct,
                "available_fields": sql_present + kb_present,
                "required_fields": required_total,
                "sql_fields_present": sql_present,
                "kb_fields_present": kb_present,
                "sql_missing_fields": sql_missing,
                "kb_missing_fields": kb_missing,
            })
    return report_rows


def summarize(rows):
    out = {}
    for row in rows:
        bucket = out.setdefault(row["priority"], {"count": 0, "coverage_sum": 0.0, "below_60": 0})
        bucket["count"] += 1
        bucket["coverage_sum"] += row["coverage_pct"]
        if row["coverage_pct"] < 60.0:
            bucket["below_60"] += 1
    for v in out.values():
        v["avg_coverage_pct"] = round(v["coverage_sum"] / v["count"], 1) if v["count"] else 0.0
        del v["coverage_sum"]
    return out


def write_csv(rows, path: Path):
    keys = [
        "university", "programme_title", "programme_matches_keyword", "priority", "coverage_pct", "available_fields", "required_fields",
        "sql_fields_present", "kb_fields_present", "sql_missing_fields", "kb_missing_fields",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            r = dict(row)
            r["sql_missing_fields"] = ";".join(r["sql_missing_fields"])
            r["kb_missing_fields"] = ";".join(r["kb_missing_fields"])
            w.writerow(r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="admissions_structured.db")
    parser.add_argument("--kb", default="clearing_knowledge_base.json")
    parser.add_argument("--programme-keyword", default="computer science")
    parser.add_argument("--output-prefix", default="priority_data_audit")
    args = parser.parse_args()

    kb_entries = load_kb_entries(Path(args.kb))
    with sqlite3.connect(args.db) as conn:
        db_rows = fetch_course_rows(conn)

    priorities = list(PRIORITY_FIELD_MAP.keys())
    report_rows = build_report(db_rows, kb_entries, priorities, args.programme_keyword)
    summary = summarize(report_rows)

    json_path = Path(f"{args.output_prefix}.json")
    csv_path = Path(f"{args.output_prefix}.csv")

    payload = {
        "priorities_checked": priorities,
        "programme_keyword": args.programme_keyword,
        "priority_summary": summary,
        "rows": report_rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(report_rows, csv_path)

    print("Priority coverage audit complete")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    for p, v in summary.items():
        print(f"{p}: avg={v['avg_coverage_pct']}%, universities={v['count']}, below_60={v['below_60']}")


if __name__ == "__main__":
    main()
