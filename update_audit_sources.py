import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "CSV-version.csv"
SQLITE_PATH = ROOT / "admissions_structured.db"
KB_PATH = ROOT / "clearing_knowledge_base.json"


ENTRY_SOURCES = {
    "University of Manchester": ("https://www.manchester.ac.uk/study/undergraduate/courses/2026/00560/bsc-computer-science/", "A-level A*A*A including A* in Mathematics and at least one science subject. Contextual offer AAA. IB 38 overall with 7,7,6 at Higher Level including 7 in Mathematics: Analysis and Approaches. GCSE Mathematics and English Language normally B/6. IELTS 7.0 overall with no component below 6.5; TOEFL iBT 100 overall with no subscore below 22."),
    "University of Birmingham": ("https://www.birmingham.ac.uk/study/undergraduate/subjects/computer-science-courses/computer-science-bsc", "A-level A*AA including A-level Mathematics grade A. IB 7,6,6 at Higher Level including Mathematics, minimum 32 points overall. BTEC only accepted with other qualifications including A-level Mathematics. Contextual offer AAA including A in Mathematics or Further Mathematics; Pathways to Birmingham ABB including A in Maths or Further Maths. IELTS 6.0 overall with no band below 5.5."),
    "University of Leeds": ("https://courses.leeds.ac.uk/3260/computer_science_bsc#entry", "A-level AAA including Mathematics. GCSE English Language grade 4/C or equivalent. EPQ/IPQ may support an AAB offer including Mathematics. Access to Leeds typical offer ABB including A in Mathematics. IB 18 Higher Level points including Mathematics. IELTS 6.0 overall with no component below 5.5."),
    "University of Sheffield": ("https://sheffield.ac.uk/undergraduate/courses/2026/computer-science-bsc#entryreqs", "Standard A-level offer A*AA including Mathematics; Access Sheffield offer AAA including Mathematics and Computer Science. IB standard 38 with 6 in Higher Level Mathematics; Access Sheffield 36 with the stated Mathematics and Computer Science conditions. GCSE English Language 4/C or IELTS 6.5 overall with at least 6.0 in each component."),
    "University of Nottingham": ("https://www.nottingham.ac.uk/studywithus/ugstudy/courses/UG/2026/Computer-Science-BSc-Hons.html", "A-level BBC (or listed equivalent combinations). Computer Science grade C required if taken. IB Diploma 26 points overall or Higher Level Certificates 554/644. IELTS 6.0 overall with no less than 5.5 in each element. No other requirements listed."),
    "Queen Mary University London": ("https://www.qmul.ac.uk/undergraduate/coursefinder/courses/2026/computer-science", "A-level AAA including one of Mathematics, Computer Science, or Physics. IB minimum 36 overall with 6,6,6 at Higher Level including one of those subjects. GCSE minimum five passes including English grade C/4 and Mathematics grade B/5. Standard contextual offer ABB; enhanced contextual offer BBB, including Maths, Physics, or Computer Science."),
    "Newcastle University": ("https://www.ncl.ac.uk/undergraduate/degrees/g400/", "For 2026 entry, A-level AAB excluding General Studies and Critical Thinking, with GCSE Mathematics grade B/6. IB 34 points, with Standard Level Mathematics grade 5 if not offered at Higher Level. BTEC/OCR Extended Diploma D*DD with minimum grade B/6 in at least five GCSEs including Mathematics. Contextual or alternative routes may reduce the offer by up to three grades."),
    "University of Liverpool": ("http://liverpool.ac.uk/courses/course/computer-science-bsc-hons#entry-requirements", "The supplied 2026 source states that subject-specific entry requirements continue to apply during Clearing. English requirements include IELTS 6.0 overall with no component below 5.5, TOEFL iBT 88 for tests taken by 20 January 2026 or 4.5 under the later scale, Duolingo 115, and PTE Academic 59 with no component below 59. Pre-sessional English is available where applicable."),
    "Lancaster University": ("https://www.lancaster.ac.uk/study/undergraduate/courses/computer-science-bsc-hons-g400/2026/#course-entry", "A-level AAB. Applicants with Computing, Computer Science, or Mathematics may be considered for a lower offer. Access to HE: 36 Level 3 credits at Distinction plus 9 at Merit. BTEC Extended Diploma DDD. IB 35 overall with 16 points from the best three Higher Level subjects. GCSE Mathematics 6/B and English Language 4/C. IELTS 6.0 overall with at least 5.5 in each component."),
    "Manchester Metropolitan University": ("https://www.mmu.ac.uk/study/undergraduate/course/bsc-computer-science#entry-requirements", "A-level BBB including grade B in IT, Computer Science, Mathematics, Digital Technology, Software Systems Development, or a science subject. BTEC/OCR Extended Diploma DDD in IT or Computing. Access to HE Pass in Computing, IT, or Science with minimum 122 UCAS Tariff points. IB minimum 30 overall or 120 UCAS points including HL5 in a relevant subject. GCSE English and Mathematics C/4. IELTS 6.0 overall with no component below 5.5."),
    "Liverpool John Moores University": ("https://www.ljmu.ac.uk/study/courses/undergraduates/2026/45579-computer-science-bsc-hons", "The supplied 2026 source lists a minimum of 64 UCAS points and directs applicants to the Clearing application form or hotline for the latest entry requirements."),
}

SOURCE_NAME_ALIASES = {"Queen Mary University of London": "Queen Mary University London"}


def update_database(rows):
    connection = sqlite3.connect(SQLITE_PATH)
    cursor = connection.cursor()
    existing = {item[1] for item in cursor.execute("PRAGMA table_info(course_facts)")}
    for column in ("cug_subject_rank_2026", "cug_overall_rank_2026", "qs_rank_2026", "ranking_source_url_2026", "entry_source_url_2026"):
        if column not in existing:
            cursor.execute(f"ALTER TABLE course_facts ADD COLUMN {column} TEXT")
    for row in rows:
        university = row["University"]
        source_key = SOURCE_NAME_ALIASES.get(university, university)
        entry_url, _ = ENTRY_SOURCES[source_key]
        values = (row["CUG 2026 - Computer Science (Main Comparison)"], row["CUG 2026 - Overall (UK)"], row["QS World Ranking 2026"], row["Ranking Source URL (Verification)"], entry_url)
        cursor.execute("UPDATE course_facts SET cug_subject_rank_2026=?, cug_overall_rank_2026=?, qs_rank_2026=?, ranking_source_url_2026=?, entry_source_url_2026=? WHERE university=?", (*values, university))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO course_facts (university, course_title, ucas_code, cug_subject_rank_2026, cug_overall_rank_2026, qs_rank_2026, ranking_source_url_2026, entry_source_url_2026) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (university, "Computer Science", "G400", *values))
        cursor.execute("UPDATE course_facts SET cug_rank=?, qs_rank=? WHERE university=?", (values[0], values[2], university))
    connection.commit()
    connection.close()


def update_knowledge_base(rows):
    entries = json.loads(KB_PATH.read_text(encoding="utf-8"))
    by_name = {entry["university_name"]: entry for entry in entries}
    for row in rows:
        university = row["University"]
        source_key = SOURCE_NAME_ALIASES.get(university, university)
        entry_url, entry_text = ENTRY_SOURCES[source_key]
        entry = by_name.setdefault(source_key, {"university_name": source_key, "course_code": "G400", "metrics": {}, "knowledge_layers": {}})
        entry.setdefault("knowledge_layers", {})["entry_requirements"] = entry_text
        entry["knowledge_layers"]["entry_requirements_2026"] = entry_text
        entry["knowledge_layers"]["rankings_2026"] = f"2026 rankings: CUG Computer Science main comparison {row['CUG 2026 - Computer Science (Main Comparison)']}; CUG Overall UK {row['CUG 2026 - Overall (UK)']}; QS World Ranking {row['QS World Ranking 2026']}."
        references = entry.setdefault("metadata_reference", {})
        references["source_url"] = entry_url
        references["verification_layer"] = "2026 institutional course page and supplied ranking verification URL"
        references["layer_sources"] = {**references.get("layer_sources", {}), "entry_requirements": entry_url, "entry_requirements_2026": entry_url, "rankings_2026": row["Ranking Source URL (Verification)"]}
    KB_PATH.write_text(json.dumps(list(by_name.values()), indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        ranking_rows = list(csv.DictReader(handle))
    update_database(ranking_rows)
    update_knowledge_base(ranking_rows)
    print(f"Updated {len(ranking_rows)} ranking records, SQLite source fields, and KB source chunks.")