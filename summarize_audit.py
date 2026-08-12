import json

with open('priority_data_audit.json', 'r', encoding='utf-8') as handle:
    data = json.load(handle)

rows = data.get('rows', [])
mismatches = [r for r in rows if r.get('programme_title') and not r.get('programme_matches_keyword')]
unique = []
seen = set()
for row in mismatches:
    key = (row['university'], row['programme_title'])
    if key not in seen:
        seen.add(key)
        unique.append(key)

print(f'programme_mismatch_rows={len(mismatches)}')
print(f'unique_mismatch_unis={len(unique)}')
for university, title in unique[:12]:
    print(f'{university} -> {title}')

print('--- lowest coverage rows ---')
for row in sorted(rows, key=lambda item: item['coverage_pct'])[:15]:
    sql_missing = ','.join(row.get('sql_missing_fields', []))
    kb_missing = ','.join(row.get('kb_missing_fields', []))
    print(f"{row['university']} | {row['priority']} | {row['coverage_pct']}% | SQL miss: {sql_missing} | KB miss: {kb_missing}")
