import os
import sqlite3


def ensure_course_facts_schema(db_path: str) -> None:
    """Ensure course_facts contains columns needed for structured comparisons."""
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
    if cur.fetchone() is None:
        conn.close()
        return

    existing_columns = {col[1] for col in cur.execute("PRAGMA table_info(course_facts)").fetchall()}
    migrations = [
        ("uk_tuition_fee", "INTEGER"),
        ("international_tuition_fee", "INTEGER"),
        ("final_year_project_credits", "INTEGER"),
        ("a_level_requirement", "TEXT"),
    ]

    for column_name, column_type in migrations:
        if column_name not in existing_columns:
            cur.execute(f"ALTER TABLE course_facts ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()


def import_structured_admissions_db(source_db_path, target_db_path="university_stats.db"):
    """Import rows from an external admissions SQLite DB into the project database."""
    if not os.path.exists(source_db_path):
        raise FileNotFoundError(f"Missing source database: {source_db_path}")

    source_conn = sqlite3.connect(source_db_path)
    source_cur = source_conn.cursor()
    source_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
    if source_cur.fetchone() is None:
        source_conn.close()
        raise ValueError(f"No course_facts table found in {source_db_path}")

    source_columns = [col[1] for col in source_cur.execute("PRAGMA table_info(course_facts)").fetchall()]
    source_conn.close()

    target_conn = sqlite3.connect(target_db_path)
    target_cur = target_conn.cursor()
    target_cur.execute("DROP TABLE IF EXISTS course_facts")
    target_cur.execute("""
    CREATE TABLE course_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        university TEXT NOT NULL,
        course_title TEXT NOT NULL,
        ucas_code TEXT NOT NULL,
        duration_years INTEGER,
        has_placement_year INTEGER,
        uk_tuition_fee INTEGER,
        international_tuition_fee INTEGER,
        employment_rate_15m REAL,
        median_salary_3yr REAL,
        final_year_project_credits INTEGER,
        a_level_requirement TEXT,
        entry_tariff REAL,
        bcs_accredited INTEGER
    )
    """)

    target_columns = [
        "university",
        "course_title",
        "ucas_code",
        "duration_years",
        "has_placement_year",
        "uk_tuition_fee",
        "international_tuition_fee",
        "employment_rate_15m",
        "median_salary_3yr",
        "final_year_project_credits",
        "a_level_requirement",
        "entry_tariff",
        "bcs_accredited",
    ]

    available_source_columns = [col for col in target_columns if col in source_columns]
    select_list = ", ".join(available_source_columns)
    insert_sql = f"""
    INSERT INTO course_facts ({', '.join(target_columns)})
    VALUES ({', '.join('?' for _ in target_columns)})
    """

    source_conn = sqlite3.connect(source_db_path)
    source_cur = source_conn.cursor()
    rows = source_cur.execute(f"SELECT {select_list} FROM course_facts").fetchall()
    source_conn.close()

    normalized_rows = []
    for row in rows:
        normalized = []
        for target_col in target_columns:
            if target_col in available_source_columns:
                value = row[available_source_columns.index(target_col)]
            elif target_col in {"duration_years", "has_placement_year", "bcs_accredited", "uk_tuition_fee", "international_tuition_fee", "final_year_project_credits"}:
                value = None
            elif target_col in {"employment_rate_15m", "median_salary_3yr", "entry_tariff"}:
                value = None
            else:
                value = None
            normalized.append(value)
        normalized_rows.append(tuple(normalized))

    target_cur.executemany(insert_sql, normalized_rows)
    target_conn.commit()
    target_conn.close()
    ensure_course_facts_schema(target_db_path)
    print(f"Imported structured admissions data from {source_db_path} into {target_db_path}")


def seed_verified_database(db_path="admissions_structured.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS course_facts")

    cursor.execute("""
    CREATE TABLE course_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        university TEXT NOT NULL,
        course_title TEXT NOT NULL,
        ucas_code TEXT NOT NULL,
        duration_years INTEGER NOT NULL,
        has_placement_year BOOLEAN NOT NULL,
        uk_tuition_fee INTEGER NOT NULL,
        international_tuition_fee INTEGER NOT NULL,
        median_salary_3yr INTEGER NOT NULL,
        employment_rate_15m REAL NOT NULL,
        final_year_project_credits INTEGER NOT NULL,
        a_level_requirement TEXT NOT NULL,
        bcs_accredited BOOLEAN NOT NULL
    )
    """)

    verified_data = [
        ("University of Liverpool", "Computer Science BSc", "G400", 3, 1, 9250, 27750, 32500, 87.0, 40, "AAA", 1),
        ("University of Leeds", "Computer Science BSc", "G400", 3, 1, 9250, 30250, 32000, 88.5, 40, "AAA", 1),
        ("University of Sheffield", "Computer Science BSc", "G402", 3, 1, 9250, 29110, 31500, 86.0, 40, "A*AA", 1),
        ("University of Nottingham", "Computer Science BSc", "G400", 3, 1, 9250, 28500, 33000, 89.0, 30, "A*AA", 1),
        ("Lancaster University", "Computer Science BSc", "G400", 3, 1, 9250, 26500, 31000, 82.0, 30, "AAB", 1),
        ("Manchester Metropolitan University", "Computer Science BSc", "G401", 3, 1, 9250, 19000, 27500, 78.5, 30, "BCC", 1),
        ("Newcastle University", "Computer Science BSc", "G400", 3, 1, 9250, 29400, 31000, 82.0, 40, "AAB", 1),
        ("University of Manchester", "Computer Science BSc", "G400", 3, 1, 9250, 34500, 36000, 91.0, 40, "A*A*A", 1),
        ("University of Edinburgh", "Computer Science BSc (Hons)", "G400", 4, 1, 9250, 34800, 35000, 90.0, 40, "A*A*A", 1),
    ]

    cursor.executemany("""
    INSERT INTO course_facts (
        university, course_title, ucas_code, duration_years, has_placement_year,
        uk_tuition_fee, international_tuition_fee, median_salary_3yr,
        employment_rate_15m, final_year_project_credits, a_level_requirement, bcs_accredited
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, verified_data)

    conn.commit()
    conn.close()
    print(f"Seeded structured admissions database at {db_path}")


if __name__ == "__main__":
    seed_verified_database()
