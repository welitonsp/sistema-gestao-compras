"""Core PDF text extraction logic."""

from __future__ import annotations
import io

class PDFTextExtractor:
    """Encapsulates PDF text extraction using pdfminer."""
    
    @staticmethod
    def extract_text(pdf_bytes: bytes) -> str:
        """Extracts plain text from PDF bytes."""
        try:
            from pdfminer.high_level import extract_text
        except ImportError:
            raise RuntimeError("pdfminer.six is not installed in the environment.")

        try:
            return extract_text(io.BytesIO(pdf_bytes)) or ""
        except Exception as exc:
            raise RuntimeError(f"Failed to extract text from PDF: {exc}")
