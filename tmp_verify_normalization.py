import types
import sys

sys.modules['langchain_huggingface'] = types.ModuleType('langchain_huggingface')
sys.modules['langchain_chroma'] = types.ModuleType('langchain_chroma')
sys.modules['langchain_google_genai'] = types.ModuleType('langchain_google_genai')
sys.modules['langchain_ollama'] = types.ModuleType('langchain_ollama')

import rag_orchestrator

class Doc:
    pass

doc = Doc()
doc.page_content = 'Context Area [Curriculum Year 1] for University of Leeds (CS303): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.'
doc.metadata = {'university': 'University of Leeds', 'course_code': 'CS303', 'content_type': 'curriculum'}

orchestrator = rag_orchestrator.AdmissionsRAGOrchestrator.__new__(rag_orchestrator.AdmissionsRAGOrchestrator)
result = orchestrator._normalize_answer_from_context(
    'What are the core modules taught in Year 1?',
    'I can help with that in general terms.',
    [doc],
)
print(result)
