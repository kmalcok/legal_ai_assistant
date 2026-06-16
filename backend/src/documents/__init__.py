"""
Document upload + parsing + page-based access (no vector RAG).

Core concepts:
- A Document is a user-owned uploaded file.
- Each document is processed into "pages" for consistent citations.
  - PDF pages map to real pages.
  - DOCX/UDF are split into pseudo-pages deterministically.
"""


