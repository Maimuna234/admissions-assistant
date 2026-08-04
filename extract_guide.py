from pypdf import PdfReader
reader = PdfReader('Guide1.pdf')
print('PAGES', len(reader.pages))
for i, page in enumerate(reader.pages[:12], 1):
    text = page.extract_text() or ''
    print(f'--- PAGE {i} ---')
    print(text[:5000])
    print()
