import json
import sqlite3
from collections import defaultdict

kb_path = 'clearing_knowledge_base.json'
struct_db = 'admissions_structured.db'

with open(kb_path, 'r', encoding='utf-8') as f:
    kb = json.load(f)

print('KB entries:', len(kb))
print('KB universities:', sorted({e['university_name'] for e in kb}))

# Knowledge base layer gaps
kb_summary = []
for entry in kb:
    layers = entry.get('knowledge_layers', {})
    missing = [k for k, v in layers.items() if not v or str(v).strip() == 'Information Not Listed']
    kb_summary.append((entry['university_name'], len(missing), missing))

print('\nKnowledge-base gaps by university:')
for university, missing_count, missing in sorted(kb_summary, key=lambda x: (x[1], x[0])):
    if missing_count:
        print(f' - {university}: {missing_count} missing layer(s) -> {", ".join(missing)}')

# Structured DB null counts by university
conn = sqlite3.connect(struct_db)
cur = conn.cursor()
cur.execute('SELECT university, course_title, ucas_code, duration_years, has_placement_year, uk_tuition_fee, international_tuition_fee, median_salary_3yr, employment_rate_15m, final_year_project_credits, a_level_requirement, bcs_accredited FROM course_facts')
rows = cur.fetchall()
conn.close()

field_names = ['course_title', 'ucas_code', 'duration_years', 'has_placement_year', 'uk_tuition_fee', 'international_tuition_fee', 'median_salary_3yr', 'employment_rate_15m', 'final_year_project_credits', 'a_level_requirement', 'bcs_accredited']
summary = defaultdict(lambda: defaultdict(int))
for row in rows:
    university = row[0]
    for idx, value in enumerate(row[1:], start=1):
        if value is None or value == '' or value == 'nan' or value == 'None':
            summary[university][field_names[idx-1]] += 1

print('\nStructured DB missing values by university (count of missing fields across rows):')
for university in sorted(summary):
    missing_fields = {k: v for k, v in summary[university].items() if v}
    if missing_fields:
        print(f' - {university}: {missing_fields}')
