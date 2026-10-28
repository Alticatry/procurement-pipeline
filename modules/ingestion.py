import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import pdfplumber

SUPPORTED_EXTENSIONS = (".pdf", ".xlsx", ".csv", ".txt")
SPLIT_BLANK_LINE = "Blank line between messages"
SPLIT_EACH_LINE = "Each line is one message"
SPLIT_MODES = (SPLIT_BLANK_LINE, SPLIT_EACH_LINE)


def clean_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pasted_text(text):
    cleaned = clean_text(text or "")
    if not cleaned:
        raise ValueError("The pasted text is empty.")
    return cleaned


def split_messages(text, mode=SPLIT_BLANK_LINE):
    cleaned = clean_text(text or "")
    if not cleaned:
        return []
    if mode == SPLIT_EACH_LINE:
        parts = cleaned.split("\n")
    else:
        parts = re.split(r"\n\s*\n", cleaned)
    return [part.strip() for part in parts if part.strip()]


def read_pdf(source):
    pages = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text)
    text = clean_text("\n\n".join(pages))
    if not text:
        raise ValueError("No readable text was found in the PDF. Scanned or photo-based PDFs are not supported.")
    return text


def read_excel(source):
    sheets = pd.read_excel(source, sheet_name=None, dtype=str)
    parts = []
    for name, frame in sheets.items():
        frame = frame.dropna(how="all").fillna("")
        if frame.empty:
            continue
        parts.append(f"Sheet: {name}\n{frame.to_csv(index=False)}")
    text = clean_text("\n\n".join(parts))
    if not text:
        raise ValueError("The Excel file contains no data.")
    return text


def read_csv(source):
    frame = pd.read_csv(source, dtype=str).dropna(how="all").fillna("")
    if frame.empty:
        raise ValueError("The CSV file contains no data.")
    return clean_text(frame.to_csv(index=False))


def read_text_file(source):
    raw = source.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return read_pasted_text(raw)


def read_uploaded_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{suffix}'. Use PDF, XLSX, CSV or TXT.")
    data = BytesIO(uploaded_file.getvalue())
    if suffix == ".pdf":
        return read_pdf(data)
    if suffix == ".xlsx":
        return read_excel(data)
    if suffix == ".csv":
        return read_csv(data)
    return read_text_file(data)
