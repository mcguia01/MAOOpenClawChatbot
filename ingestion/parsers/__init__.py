"""Document parsers — one module per supported file type."""

from ingestion.parsers.docx_parser import parse as parse_docx
from ingestion.parsers.pptx_parser import parse as parse_pptx
from ingestion.parsers.xlsx_parser import parse as parse_xlsx

__all__ = ["parse_docx", "parse_pptx", "parse_xlsx"]
