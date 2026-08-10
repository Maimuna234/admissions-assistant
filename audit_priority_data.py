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
        "sql_fields": [
            "entry_tariff",
            "alevel_requirement",
            "pct_entrants_alevel",
            "has_foundation_year",
        ],
        "kb_metrics": [],
        "kb_layers": ["entry_requirements"],
    },
    "Curriculum & Accreditation": {
        "sql_fields": [
            "bcs_accredited",
            "has_placement_year",
            "has_year_abroad",
            "final_year_project_credits",
        ],
        "kb_metrics": [],
        "kb_layers": [
            "curriculum_year_1",
            "curriculum_year_2",
            "curriculum_year_3",
            "industrial_placements",
        ],
    },
    "Graduate Outcomes & Salary": {
        "sql_fields": [
            "median_salary_leo3",
            "median_salary_leo5",
            "median_salary_go",
            "employment_rate_15m",
            "pct_professional_managerial",
        ],
        "kb_metrics": [
            "leo_median_salary_3_years",
            "graduate_in_work_15_months_pct",
        ],
        "kb_layers": ["career_outcomes"],
    },
    "Fees & Cost": {
        "sql_fields": ["tuition_fee_uk", "tuition_fee_intl"],
        "kb_metrics": ["annual_tuition_fee_uk"],
        "kb_layers": [],
    },
    "Teaching Quality & NSS": {
        "sql_fields": [
            "nss_teaching_satisfaction",
            "nss_mental_wellbeing",
            "nss_facilities_resources",
            "tef_overall_rating",
            "tef_student_experience",
        ],
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
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base file not found: {kb_path}")
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


def fetch_course_rows(conn, universities=None):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    table_exists = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'"
    ).fetchone()
    if not table_exists:
        raise RuntimeError("Table 'course_facts' was not found in the structured DB.")

    available_columns = [r[1] for r in cursor.execute("PRAGMA table_info(course_facts)").fetchall()]
    required = [
        "university",
        "course_title",
        "ucas_code",
        "entry_tariff",
        "alevel_requirement",
        "pct_entrants_alevel",
        "has_foundation_year",
        "bcs_accredited",
        "has_placement_year",
        "has_year_abroad",
        "final_year_project_credits",
        "median_salary_go",
        "median_salary_leo3",
        "median_salary_leo5",
        "employment_rate_15m",
        "pct_professional_managerial",
        "tuition_fee_uk",
        "tuition_fee_intl",
        "nss_teaching_satisfaction",
        "nss_mental_wellbeing",
        "nss_facilities_resources",
        "tef_overall_rating",
        "tef_student_experience",
        "guardian_rank",
        "cug_rank",
        "qs_rank",
    ]
    selected = [c for c in required if c in available_columns]
    if not selected:
        raise RuntimeError("No expected course_facts columns are available in the DB.")

    sql = f"SELECT {', '.join(selected)} FROM course_facts"
    params = []
    if universities:
        placeholders = ", ".join(["?" for _ in universities])
        sql += f" WHERE university IN ({placeholders})"
        params.extend(universities)

    rows = [dict(row) for row in cursor.execute(sql, params).fetchall()]
    return rows, selected


def build_report(db_rows, kb_entries, priorities, programme_keyword):
    grouped_sql = {}
    for row in db_rows:
        grouped_sql.setdefault(uni_key(row.get("university")), []).append(row)

    grouped_kb = {}
    for entry in kb_entries:
        grouped_kb[uni_key(entry.get("university_name"))] = entry

    university_keys = sorted(set(grouped_sql.keys()) | set(grouped_kb.keys()))

    report_rows = []
    for ukey in university_keys:
        sql_candidates = grouped_sql.get(ukey, [])
        best_sql = select_best_row(sql_candidates, programme_keyword)
        kb_entry = grouped_kb.get(ukey, {})

        display_name = ""
        if best_sql and best_sql.get("university"):
            display_name = best_sql["university"]
        elif kb_entry.get("university_name"):
            display_name = kb_entry["university_name"]
        else:
            display_name = ukey

        title = str((best_sql or {}).get("course_title", "") or "")
        title_match = programme_keyword.lower() in title.lower() if programme_keyword else True

        for priority in priorities:
            mapping = PRIORITY_FIELD_MAP[priority]
            sql_present = 0
            sql_missing = []
            for field in mapping["sql_fields"]:
                value = (best_sql or {}).get(field)
                if is_present(value):
                    sql_present += 1
                else:
                    sql_missing.append(field)

            kb_metrics = (kb_entry or {}).get("metrics", {}) or {}
            kb_layers = (kb_entry or {}).get("knowledge_layers", {}) or {}

            kb_present = 0
            kb_missing = []
            for metric in mapping["kb_metrics"]:
                value = kb_metrics.get(metric)
                if is_present(value):
                    kb_present += 1
                else:
                    kb_missing.append(metric)

            for layer in mapping["kb_layers"]:
                value = kb_layers.get(layer)
                if is_present(value):
                    kb_present += 1
                else:
                    kb_missing.append(layer)

            required_total = len(mapping["sql_fields"]) + len(mapping["kb_metrics"]) + len(mapping["kb_layers"])
            available_total = sql_present + kb_present
            coverage_pct = round((available_total / required_total) * 100, 1) if required_total else 100.0

            report_rows.append({
                "university": display_name,
                "programme_title": title,
                "programme_matches_keyword": title_match,
                "priority": priority,
                "coverage_pct": coverage_pct,
                "available_fields": available_total,
                "required_fields": required_total,
                "sql_fields_present": sql_present,
                "kb_fields_present": kb_present,
                "sql_missing_fields": sql_missing,
                "kb_missing_fields": kb_missing,
            })

    return report_rows


def summarize(report_rows):
    priority_summary = {}
    for row in report_rows:
        bucket = priority_summary.setdefault(row["priority"], {"count": 0, "coverage_sum": 0.0, "below_60": 0})
        bucket["count"] += 1
        bucket["coverage_sum"] += row["coverage_pct"]
        if row["coverage_pct"] < 60.0:
            bucket["below_60"] += 1

    for value in priority_summary.values():
        if value["count"]:
            value["avg_coverage_pct"] = round(value["coverage_sum"] / value["count"], 1)
        else:
            value["avg_coverage_pct"] = 0.0
        del value["coverage_sum"]

    return priority_summary


def write_csv(report_rows, csv_path: Path):
    fieldnames = [
        "university",
        "programme_title",
        "programme_matches_keyword",
        "priority",
        "coverage_pct",
        "available_fields",
        "required_fields",
        "sql_fields_present",
        "kb_fields_present",
        "sql_missing_fields",
        "kb_missing_fields",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report_rows:
            csv_row = dict(row)
            csv_row["sql_missing_fields"] = ";".join(row["sql_missing_fields"])
            csv_row["kb_missing_fields"] = ";".join(row["kb_missing_fields"])
            writer.writerow(csv_row)


def parse_priorities(raw_priorities: str):
    if not raw_priorities.strip():
        return list(PRIORITY_FIELD_MAP.keys())
    parsed = [p.strip() for p in raw_priorities.split(",") if p.strip()]
    unknown = [p for p in parsed if p not in PRIORITY_FIELD_MAP]
    if unknown:
        valid = ", ".join(PRIORITY_FIELD_MAP.keys())
        raise ValueError(f"Unknown priorities: {unknown}. Valid options: {valid}")
    return parsed


def main():
    parser = argparse.ArgumentParser(
        description="Audit university evidence coverage by student priorities across SQL + knowledge base."
    )
    parser.add_argument("--db", default="admissions_structured.db", help="Path to admissions SQLite DB")
    parser.add_argument("--kb", default="clearing_knowledge_base.json", help="Path to knowledge base JSON")
    parser.add_argument(
        "--priorities",
        default="",
        help="Comma-separated priorities. Leave empty to audit all priorities.",
    )
    parser.add_argument(
        "--programme-keyword",
        default="computer science",
        help="Keyword used to validate course_title relevance per university.",
    )
    parser.add_argument(
        "--output-prefix",
        default="priority_data_audit",
        help="Output prefix for generated JSON/CSV files.",
    )
    args = parser.parse_args()

    priorities = parse_priorities(args.priorities)
    db_path = Path(args.db)
    kb_path = Path(args.kb)

    if not db_path.exists():
        raise FileNotFoundError(f"Structured DB not found: {db_path}")

    kb_entries = load_kb_entries(kb_path)
    with sqlite3.connect(db_path) as conn:
        db_rows, _ = fetch_course_rows(conn)

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
    print(f"- JSON report: {json_path}")
    print(f"- CSV report:  {csv_path}")
    print("- Priority averages:")
    for priority, values in summary.items():
        print(
            f"  * {priority}: avg={values['avg_coverage_pct']}% "
            f"(universities={values['count']}, below_60={values['below_60']})"
        )

    mismatches = [
        r for r in report_rows
        if not r["programme_matches_keyword"] and r["programme_title"]
    ]
    if mismatches:
        print("- Programme title mismatches detected (top 10):")
        shown = set()
        for row in mismatches:
            key = (row["university"], row["programme_title"])
            if key in shown:
                continue
            shown.add(key)
            print(f"  * {row['university']}: {row['programme_title']}")
            if len(shown) >= 10:
                break


if __name__ == "__main__":
    main()
