from pathlib import Path
from pypdf import PdfReader
from docx import Document

def extract_resume_text(path: Path, extension: str) -> str:
    if extension == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    elif extension == ".docx":
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        text = "\n".join(parts)
    else:
        raise ValueError("Only PDF and DOCX files are supported.")
    if not text.strip():
        raise ValueError("No readable text found. Scanned-PDF OCR is not included.")
    return text.strip()
