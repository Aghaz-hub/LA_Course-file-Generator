"""Turn a syllabus PDF (and optionally the program-structure PDF) into text for the AI extractor."""
from __future__ import annotations

import pdfplumber


def pdf_text(file, max_chars: int = 60000) -> str:
    parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            for tbl in page.extract_tables():
                parts.append("\n".join(" | ".join((c or "").strip() for c in row) for row in tbl))
    return "\n".join(parts)[:max_chars]


def find_course_text(full_text: str, course_code: str, window: int = 9000) -> str:
    """A program syllabus PDF holds many courses: return the stretch that starts at the course code."""
    i = full_text.upper().find(course_code.upper())
    return full_text[i:i + window] if i >= 0 else full_text[:window]
