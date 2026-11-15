import io
import re
import shutil
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

def split_chunks(text: str, size: int = 6000, overlap: int = 400) -> list[str]:
    chunks, start = [], 0
    text = text.strip()
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind("\n", start, end)
            if cut > start + size // 2:
                end = cut
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks

def find_tesseract() -> str | None:
    candidates = []
    hit = shutil.which("tesseract")
    if hit:
        candidates.append(Path(hit))
    candidates.extend([
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path.home() / "AppData/Local/Tesseract-OCR/tesseract.exe",
        Path.home() / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe",
    ])
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            if candidate.is_file():
                return str(candidate)
    return None

def _extract_pdf(raw: bytes) -> tuple[str, int, str, str]:
    reader = PdfReader(io.BytesIO(raw))
    page_text = []
    for index, page in enumerate(reader.pages, start=1):
        content = (page.extract_text() or "").strip()
        if content:
            page_text.append(f"--- Page {index} ---\n{content}")
    title = ""
    if reader.metadata:
        title = reader.metadata.title or ""
    text = "\n\n".join(page_text).strip()
    method = "embedded_pdf_text"
    # Use OCR when embedded text is essentially absent.
    if len(text) < max(80, len(reader.pages) * 20):
        executable = find_tesseract()
        if not executable:
            raise ValueError(
                "This PDF appears to be scanned/image-based. Install Tesseract OCR "
                "and add it to PATH, then restart the backend. Embedded-text PDFs "
                "do not require Tesseract."
            )
        try:
            import fitz
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise ValueError(
                "Scanned PDF OCR dependencies are missing. Install PyMuPDF, "
                "pytesseract and Pillow using the backend requirements."
            ) from exc
        pytesseract.pytesseract.tesseract_cmd = executable
        pdf = fitz.open(stream=raw, filetype="pdf")
        pages = []
        # Resume uploads are capped by MAX_UPLOAD_MB; process up to 40 pages.
        for index in range(min(len(pdf), 40)):
            page = pdf.load_page(index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            value = pytesseract.image_to_string(image, config="--oem 3 --psm 6")
            if value.strip():
                pages.append(f"--- Page {index + 1} (OCR) ---\n{value.strip()}")
        text = "\n\n".join(pages).strip()
        method = "pymupdf_tesseract_ocr"
    return text, len(reader.pages), title, method

def _extract_docx(raw: bytes) -> tuple[str, int, str, str]:
    doc = Document(io.BytesIO(raw))
    parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table_index, table in enumerate(doc.tables, start=1):
        parts.append(f"--- Table {table_index} ---")
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("No readable text found in this Word document.")
    return text, 1, "", "python_docx_paragraphs_and_tables"

def extract_document(raw: bytes, extension: str) -> dict[str, Any]:
    if extension == ".pdf":
        text, page_count, title, method = _extract_pdf(raw)
    elif extension == ".docx":
        text, page_count, title, method = _extract_docx(raw)
    else:
        raise ValueError("Only PDF and DOCX files are supported.")
    if not text.strip():
        raise ValueError("No readable text could be extracted from this document.")
    return {
        "text": text,
        "page_count": page_count,
        "title": title,
        "extraction_method": method,
        "chunks": split_chunks(text),
    }

def retrieve_chunks(chunks: list[str], question: str, top_k: int = 5) -> list[tuple[int, str]]:
    terms = set(re.findall(r"[a-z0-9]{2,}", question.lower()))
    scored = []
    for index, chunk in enumerate(chunks):
        low = chunk.lower()
        score = sum(low.count(term) for term in terms)
        if score:
            scored.append((score, index, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return [(i, chunks[i]) for i in range(min(top_k, len(chunks)))]
    return [(i, chunk) for _, i, chunk in scored[:top_k]]
