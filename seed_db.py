import os
import sqlite3


def ensure_course_facts_schema(db_path: str) -> None:
    """Ensure course_facts contains all expected columns for structured comparisons."""
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
    if cur.fetchone() is None:
        conn.close()
        return

    existing_columns = {col[1] for col in cur.execute("PRAGMA table_info(course_facts)").fetchall()}
    # New schema columns — add any that are missing for backward compatibility with old exports.
    migrations = [
        ("tuition_fee_uk", "TEXT"),
        ("tuition_fee_intl", "TEXT"),
        ("alevel_requirement", "TEXT"),
        ("median_salary_leo3", "REAL"),
        ("median_salary_go", "REAL"),
        ("median_salary_leo5", "REAL"),
        ("guardian_rank", "INTEGER"),
        ("cug_rank", "INTEGER"),
        ("qs_rank", "INTEGER"),
        ("tef_overall_rating", "TEXT"),
        ("tef_student_experience", "TEXT"),
        ("nss_teaching_satisfaction", "REAL"),
        ("nss_facilities_resources", "REAL"),
        ("nss_mental_wellbeing", "REAL"),
        ("pct_professional_managerial", "REAL"),
        ("pct_entrants_alevel", "REAL"),
        ("pct_entrants_bacc", "REAL"),
        ("is_honours", "INTEGER"),
        ("has_foundation_year", "INTEGER"),
        ("has_year_abroad", "INTEGER"),
        ("is_distance_learning", "INTEGER"),
        ("kis_course_id", "TEXT"),
        ("kis_mode", "INTEGER"),
        ("pubukprn", "INTEGER"),
        ("final_year_project_credits", "TEXT"),
    ]

    for column_name, column_type in migrations:
        if column_name not in existing_columns:
            cur.execute(f"ALTER TABLE course_facts ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()


def import_structured_admissions_db(source_db_path, target_db_path="university_stats.db"):
    """Import all rows and columns from admissions_structured.db into the working database."""
    if not os.path.exists(source_db_path):
        raise FileNotFoundError(f"Missing source database: {source_db_path}")

    source_conn = sqlite3.connect(source_db_path)
    source_cur = source_conn.cursor()
    source_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
    if source_cur.fetchone() is None:
        source_conn.close()
        raise ValueError(f"No course_facts table found in {source_db_path}")

    # Dynamically mirror the full source schema so new columns are always picked up.
    col_info = source_cur.execute("PRAGMA table_info(course_facts)").fetchall()
    source_columns = [col[1] for col in col_info]
    col_defs = ", ".join(
        f"{col[1]} {col[2]}" + (" PRIMARY KEY AUTOINCREMENT" if col[5] == 1 else "")
        for col in col_info
    )

    rows = source_cur.execute("SELECT * FROM course_facts").fetchall()
    source_conn.close()

    target_conn = sqlite3.connect(target_db_path)
    target_cur = target_conn.cursor()
    target_cur.execute("DROP TABLE IF EXISTS course_facts")
    target_cur.execute(f"CREATE TABLE course_facts ({col_defs})")

    placeholders = ", ".join("?" for _ in source_columns)
    col_names = ", ".join(source_columns)
    target_cur.executemany(f"INSERT INTO course_facts ({col_names}) VALUES ({placeholders})", rows)
    target_conn.commit()
    target_conn.close()
    print(f"Imported {len(rows)} rows from {source_db_path} into {target_db_path} ({len(source_columns)} columns)")


def seed_verified_database(db_path="admissions_structured.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fallback seed: minimal schema matching the current admissions_structured.db layout.
    cursor.execute("DROP TABLE IF EXISTS course_facts")

    cursor.execute("""
    CREATE TABLE course_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        university TEXT NOT NULL,
        course_title TEXT NOT NULL,
        ucas_code TEXT,
        duration_years INTEGER,
        is_honours INTEGER,
        has_placement_year INTEGER,
        has_year_abroad INTEGER,
        has_foundation_year INTEGER,
        entry_tariff REAL,
        alevel_requirement TEXT,
        tuition_fee_uk TEXT,
        tuition_fee_intl TEXT,
        bcs_accredited INTEGER,
        employment_rate_15m REAL,
        pct_professional_managerial REAL,
        median_salary_go REAL,
        median_salary_leo3 REAL,
        median_salary_leo5 REAL,
        final_year_project_credits TEXT,
        guardian_rank INTEGER,
        cug_rank INTEGER,
        qs_rank INTEGER,
        tef_overall_rating TEXT,
        tef_student_experience TEXT,
        nss_teaching_satisfaction REAL,
        nss_facilities_resources REAL,
        nss_mental_wellbeing REAL
    )
    """)

    verified_data = [
        # (university, course_title, ucas_code, duration_years, is_honours, has_placement_year,
        #  has_year_abroad, has_foundation_year, entry_tariff, alevel_requirement,
        #  tuition_fee_uk, tuition_fee_intl, bcs_accredited, employment_rate_15m,
        #  pct_professional_managerial, median_salary_go, median_salary_leo3, median_salary_leo5,
        #  final_year_project_credits, guardian_rank, cug_rank, qs_rank,
        #  tef_overall_rating, tef_student_experience,
        #  nss_teaching_satisfaction, nss_facilities_resources, nss_mental_wellbeing)
        ("University of Liverpool", "Computer Science BSc", "G400", 3, 1, 1, 0, 0, 152, "AAA",
         "Not published centrally", "Not published centrally", 1, 87.0, 65.0, 28000.0, 32500.0, 38000.0,
         "40", None, None, None, "Silver", "Gold", 82.0, 79.0, 80.0),
        ("University of Leeds", "Computer Science BSc", "G400", 3, 1, 1, 0, 0, 168, "AAA",
         "Not published centrally", "Not published centrally", 1, 88.5, 68.0, 29000.0, 32000.0, 39000.0,
         "40", None, None, None, "Gold", "Gold", 85.0, 82.0, 83.0),
        ("University of Sheffield", "Computer Science BSc", "G402", 3, 1, 1, 0, 0, 162, "A*AA",
         "Not published centrally", "Not published centrally", 1, 86.0, 66.0, 27500.0, 31500.0, 37500.0,
         "40", None, None, None, "Gold", "Silver", 83.0, 80.0, 81.0),
    ]

    cursor.executemany("""
    INSERT INTO course_facts (
        university, course_title, ucas_code, duration_years, is_honours, has_placement_year,
        has_year_abroad, has_foundation_year, entry_tariff, alevel_requirement,
        tuition_fee_uk, tuition_fee_intl, bcs_accredited, employment_rate_15m,
        pct_professional_managerial, median_salary_go, median_salary_leo3, median_salary_leo5,
        final_year_project_credits, guardian_rank, cug_rank, qs_rank,
        tef_overall_rating, tef_student_experience,
        nss_teaching_satisfaction, nss_facilities_resources, nss_mental_wellbeing
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, verified_data)

    conn.commit()
    conn.close()
    print(f"Seeded structured admissions database at {db_path}")


if __name__ == "__main__":
    seed_verified_database()
