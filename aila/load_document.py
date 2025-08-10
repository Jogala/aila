import logging
from pathlib import Path

import PyPDF2
from docx import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_document(file_path: str | Path) -> str:
    """Load and extract text from various document formats."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    extension = file_path.suffix.lower()

    if extension == ".txt":
        return _load_text(file_path)
    elif extension == ".pdf":
        return _load_pdf(file_path)
    elif extension == ".docx":
        return _load_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {extension}")


def _load_text(file_path: Path) -> str:
    """Load plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except UnicodeDecodeError:
        # Try with different encoding
        with open(file_path, "r", encoding="latin-1") as file:
            return file.read()


def _load_pdf(file_path: Path) -> str:
    """Extract text from PDF file."""
    text = ""
    try:
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        raise


def _load_docx(file_path: Path) -> str:
    """Extract text from DOCX file."""
    try:
        doc = Document(str(file_path))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error reading DOCX {file_path}: {e}")
        raise
