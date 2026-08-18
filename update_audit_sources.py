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
DB_NAME_ALIASES = {"University of Liverpool": "The University of Liverpool"}

FEE_SOURCES = {
    "University of Manchester": ("https://www.manchester.ac.uk/study/undergraduate/courses/2027/00560/bsc-computer-science/", "9790", "Not stated", "2026 home fee £9,790 per year; 2027 fees not yet set and expected to increase slightly. Additional compulsory costs above 1% of the annual home fee should be disclosed.",),
    "Lancaster University": ("https://www.lancaster.ac.uk/study/undergraduate/courses/computer-science-bsc-hons-g400/2027/#fees", "10050", "TBC", "2027/28 annual tuition: Home £10,050; International fee TBC. The supplied source notes fees are set for a 12-month session and 2026-entry scholarships may be used as a guide.",),
    "University of Leeds": ("https://courses.leeds.ac.uk/202627/3260/computer-science-bsc#fees", "9790", "32750", "2026/27 tuition: UK £9,790 per year; International £32,750 per year. The source confirms a 2027/28 UK fee of £10,050 and reduced fees may apply to study-abroad or work-placement years.",),
    "University of Birmingham": ("https://www.birmingham.ac.uk/study/undergraduate/subjects/computer-science-courses/computer-science-bsc", "9790", "Not stated", "September 2026 home tuition fee £9,790 per year. A placement year is charged at 15% of the agreed tuition fee; international fee depends on country and is not stated in the supplied extract.",),
    "University of Nottingham": ("https://www.nottingham.ac.uk/studywithus/ugstudy/courses/UG/2026/Computer-Science-BSc-Hons.html", "Not stated", "33000", "International tuition fee £33,000 per year. The supplied course page also notes possible reduced fees during study abroad or placement; home fee was not stated in the extract.",),
    "University of Sheffield": ("https://sheffield.ac.uk/undergraduate/tuition-fees-2026", "9790", "Not stated", "Standard annual 2026 undergraduate home tuition fee £9,790. Overseas fees vary by fee status and course; reduced fees may apply for study abroad, employment, or industry years.",),
    "Newcastle University": ("https://www.ncl.ac.uk/undergraduate/degrees/g400/", "9790", "31500", "2026/27 Computer Science BSc tuition: Home £9,790 for Year 1; International £31,500 for Year 1. The source lists £10,050 for 2027/28 home fees and notes annual changes may apply.",),
    "Liverpool John Moores University": ("https://www.ljmu.ac.uk/study/courses/undergraduates/2026/35579-computer-science-bsc-hons", "9790", "Not stated", "2026/27 home tuition £9,790 per year, subject to Parliamentary approval. Study abroad year £1,465; placement year £1,955. International fee was not stated in the supplied extract.",),
    "Manchester Metropolitan University": ("https://www.mmu.ac.uk/study/undergraduate/course/bsc-computer-science#fees", "9790", "21500", "UK full-time tuition £9,790 per year; UK foundation fee £9,790. International full-time and foundation fees £21,500 per year.",),
    "Queen Mary University London": ("https://www.qmul.ac.uk/undergraduate/coursefinder/courses/2026/computer-science/", "9790", "32950", "2026 Computer Science BSc fees: Home £9,790; Overseas £32,950. The page lists indicative Clearing requirements and a September 2026 start.",),
    "University of Liverpool": ("https://www.liverpool.ac.uk/courses/redirect/computer-science-bsc-hons/overview#fees-and-funding", "9790", "32000", "2026/27 tuition: UK £9,790 per year; International £32,000 per year. Year in industry £1,955; year abroad £1,465 for the China option, and international year abroad £16,000.",),
}

COURSE_SOURCES = {
    "University of Manchester": ("https://www.manchester.ac.uk/study/undergraduate/courses/2026/00560/bsc-computer-science/", "2026 Computer Science course units include First Year Team Project, Mathematical Techniques, Fundamentals of Computation, Computer Engineering, Data Science, Computer Architecture, Operating Systems, and Introduction to Programming. Year 2 includes Software Engineering, Programming Languages, Algorithms and Data Structures, with optional Logic, Microcontrollers, and Database Systems. Year 3 has a mandatory 40-credit project and specialist options including AI, robotics, IoT, agile pipelines, and machine learning."),
    "University of Birmingham": ("https://www.birmingham.ac.uk/study/undergraduate/subjects/computer-science-courses/computer-science-bsc", "The course has 12 core modules across the first two years, each worth 20 credits. 2026/27 examples include Object Oriented Programming, Theories of Computation, Artificial Intelligence 1, Computer Systems and Professional Practice, Data Structures and Algorithms, and Mathematical and Logical Foundations. Year 3 includes a 40-credit Computer Science Project plus 80 credits of optional modules."),
    "University of Leeds": ("https://courses.leeds.ac.uk/3260/computer_science_bsc#content", "Each year consists of 120 credits. Year 1 covers Programming, Computer Systems and Architecture, and Theoretical Foundations. Year 2 covers Software Engineering, Operating Systems, Networks, Security, and Algorithms. Year 3 includes Professional Innovation and Enterprise, a 40-credit Individual Project, specialist options, paid summer internships, and an optional work placement or study-abroad year."),
    "University of Sheffield": ("https://sheffield.ac.uk/undergraduate/courses/2026/computer-science-bsc#modules", "Confirmed first-year modules include Introduction to Software Engineering, Foundations of Computer Science, Java Programming, Systems and Networks, Practical Algorithms and Data Structures, and Introduction to Artificial Intelligence. Year 2 includes programming languages, databases, automata, AI, cybersecurity, and a 20-credit Software Hut. Year 3 includes a dissertation project and advanced options such as deep learning, robotics, cryptography, and NLP."),
    "University of Nottingham": ("https://www.nottingham.ac.uk/studywithus/ugstudy/courses/UG/2026/Computer-Science-BSc-Hons.html", "The course includes a Year 2 group project with industry collaboration. Core modules include Assembly Language, Computer Architecture, Databases and Interfaces, AI, Software Engineering, Mathematics, Networks, Programming and Algorithms, and Programming Paradigms. Later study includes algorithms, formal reasoning, operating systems, security, machine learning, computer vision, and an individual dissertation."),
    "Queen Mary University London": ("https://www.qmul.ac.uk/undergraduate/coursefinder/courses/2026/computer-science", "The three-year BSc includes Year 1 procedural programming, systems and networks, discrete structures, web technology, information systems, and automata. Year 2 covers software engineering, probability, databases, algorithms, operating systems, graphical user interfaces, and internet protocols, with an optional summer internship. Year 3 includes a 60-credit project and specialist options; industrial experience and year-abroad routes are available."),
    "Newcastle University": ("https://www.ncl.ac.uk/undergraduate/degrees/g400/", "Stage 1 covers Fundamentals of Computing, Computer Systems Design and Architectures, Data Science, and two Programming Portfolio modules. Stage 2 covers Security Programming, Algorithm Design, a 30-credit Software Engineering Team Project, contemporary computing, and software systems design. Stage 3 includes a major individual project, practical labs, coursework, presentations, and industry-informed project work."),
    "University of Liverpool": ("https://www.liverpool.ac.uk/courses/course/computer-science-bsc-hons", "Year 1 compulsory study includes Analytic Techniques, Computer Systems, Data Structures and Algorithms, Foundations of Computer Science, AI, Object-Oriented Programming, and Programming. Year 2 includes Complexity of Algorithms, Database Development, Group Software Project, Software Engineering, and specialist options. Year 3 includes a 30-credit honours project and options such as networks, formal methods, robotics, quantum computing, and cloud computing; year-in-industry and year-abroad routes are available."),
    "Lancaster University": ("https://www.lancaster.ac.uk/study/undergraduate/courses/computer-science-bsc-hons-g400/2026/#structure", "Year 1 core study includes Digital Systems, Fundamentals of Computer Science, Software Development, and Designing Software Systems. Year 2 includes a Computer Science Group Project, HCI, Networks and Systems, and Secure Data and Systems. Year 3 includes a Third Year Project and options including machine learning, NLP, quantum computing, secure AI, and distributed systems."),
    "Manchester Metropolitan University": ("https://www.mmu.ac.uk/study/undergraduate/course/bsc-computer-science#course-information", "The course covers programming, mathematics for computing, computer architecture, web development, databases, algorithms, networks, operating systems, AI, scalable architecture, cloud computing, and a final-year project. Core examples include Computing Fundamentals, Introduction to Programming, Team Project, Web Development and Databases, Computer Graphics, Advanced Programming Design, and Networks and Operating Systems. A four-year placement route is available."),
    "Liverpool John Moores University": ("https://www.ljmu.ac.uk/study/courses/undergraduates/2026/45579-computer-science-bsc-hons", "Foundation modules include Mathematics, Programming, Information Systems Development, Creative Computing, Applied Computing, and Algorithms. Year 1 includes Intro to Programming, Professional Practice, Data Modelling, Foundations of Computer Science, Web Development, and Computer Systems Architecture. Year 2 includes Group Project, Databases, Operating Systems, Algorithm Design, and Automata. Year 3 includes Computer Graphics, Contemporary Concepts, and a 40-credit Project, with AI, cryptography, network defence, and embedded-systems options."),
}


def update_database(rows):
    connection = sqlite3.connect(SQLITE_PATH)
    cursor = connection.cursor()
    existing = {item[1] for item in cursor.execute("PRAGMA table_info(course_facts)")}
    for column in ("cug_subject_rank_2026", "cug_overall_rank_2026", "qs_rank_2026", "ranking_source_url_2026", "entry_source_url_2026", "home_fee_2026", "international_fee_2026", "fee_source_url_2026", "course_source_url_2026"):
        if column not in existing:
            cursor.execute(f"ALTER TABLE course_facts ADD COLUMN {column} TEXT")
    for row in rows:
        university = row["University"]
        source_key = SOURCE_NAME_ALIASES.get(university, university)
        db_university = DB_NAME_ALIASES.get(university, university)
        entry_url, _ = ENTRY_SOURCES[source_key]
        fee_url, home_fee, international_fee, _ = FEE_SOURCES[source_key]
        course_url, _ = COURSE_SOURCES[source_key]
        values = (row["CUG 2026 - Computer Science (Main Comparison)"], row["CUG 2026 - Overall (UK)"], row["QS World Ranking 2026"], row["Ranking Source URL (Verification)"], entry_url)
        cursor.execute("UPDATE course_facts SET cug_subject_rank_2026=?, cug_overall_rank_2026=?, qs_rank_2026=?, ranking_source_url_2026=?, entry_source_url_2026=? WHERE university=?", (*values, db_university))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO course_facts (university, course_title, ucas_code, cug_subject_rank_2026, cug_overall_rank_2026, qs_rank_2026, ranking_source_url_2026, entry_source_url_2026, home_fee_2026, international_fee_2026, fee_source_url_2026, course_source_url_2026) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (db_university, "Computer Science", "G400", *values, home_fee, international_fee, fee_url, course_url))
        cursor.execute("UPDATE course_facts SET cug_rank=?, qs_rank=? WHERE university=?", (values[0], values[2], db_university))
        cursor.execute("UPDATE course_facts SET tuition_fee_uk=?, tuition_fee_intl=?, home_fee_2026=?, international_fee_2026=?, fee_source_url_2026=?, course_source_url_2026=? WHERE university=? AND lower(course_title) LIKE '%computer science%'", (home_fee, international_fee, home_fee, international_fee, fee_url, course_url, db_university))
    cursor.execute("DELETE FROM course_facts WHERE university='University of Liverpool' AND course_title='Computer Science' AND ucas_code='G400'")
    connection.commit()
    connection.close()


def update_knowledge_base(rows):
    entries = json.loads(KB_PATH.read_text(encoding="utf-8"))
    by_name = {entry["university_name"]: entry for entry in entries}
    for row in rows:
        university = row["University"]
        source_key = SOURCE_NAME_ALIASES.get(university, university)
        entry_url, entry_text = ENTRY_SOURCES[source_key]
        fee_url, home_fee, international_fee, fee_text = FEE_SOURCES[source_key]
        course_url, course_text = COURSE_SOURCES[source_key]
        entry = by_name.setdefault(source_key, {"university_name": source_key, "course_code": "G400", "metrics": {}, "knowledge_layers": {}})
        entry.setdefault("knowledge_layers", {})["entry_requirements"] = entry_text
        entry["knowledge_layers"]["entry_requirements_2026"] = entry_text
        entry["knowledge_layers"]["rankings_2026"] = f"2026 rankings: CUG Computer Science main comparison {row['CUG 2026 - Computer Science (Main Comparison)']}; CUG Overall UK {row['CUG 2026 - Overall (UK)']}; QS World Ranking {row['QS World Ranking 2026']}."
        entry["knowledge_layers"]["fees_2026"] = fee_text
        entry["knowledge_layers"]["course_data_2026"] = course_text
        if home_fee.isdigit():
            entry["metrics"]["annual_tuition_fee_uk"] = int(home_fee)
        entry["metrics"]["annual_tuition_fee_uk_2026"] = home_fee
        entry["metrics"]["annual_tuition_fee_intl_2026"] = international_fee
        references = entry.setdefault("metadata_reference", {})
        references["source_url"] = entry_url
        references["metric_source_url"] = fee_url
        references["verification_layer"] = "2026 institutional course page and supplied ranking verification URL"
        references["layer_sources"] = {**references.get("layer_sources", {}), "entry_requirements": entry_url, "entry_requirements_2026": entry_url, "rankings_2026": row["Ranking Source URL (Verification)"], "fees_2026": fee_url, "course_data_2026": course_url}
    KB_PATH.write_text(json.dumps(list(by_name.values()), indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        ranking_rows = list(csv.DictReader(handle))
    update_database(ranking_rows)
    update_knowledge_base(ranking_rows)
    print(f"Updated {len(ranking_rows)} ranking records, SQLite source fields, and KB source chunks.")