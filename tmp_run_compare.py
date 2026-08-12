from rag_orchestrator import AdmissionsRAGOrchestrator

rag = AdmissionsRAGOrchestrator(db_directory='./chroma_db', sql_db_path='./admissions_structured.db')
res = rag.query_pipeline(
    'Compare the target programme against the selected competitor university and return a short decision summary.',
    target_competitor='Lancaster University',
    target_programme='Computer Science BSc - University of Liverpool',
    target_baseline='University of Liverpool',
    priorities=['Fees & Cost','Entry Requirements','Curriculum & Accreditation','Graduate Outcomes & Salary','Teaching Quality & NSS','University Rankings']
)
print('ENGINE=', res.get('engine_used'))
print('ANSWER=', res.get('answer'))
print('CONF=', res.get('confidence_score'))
print('ABSTAIN=', res.get('should_abstain'))
print('CITATIONS=', len(res.get('citations') or []))
