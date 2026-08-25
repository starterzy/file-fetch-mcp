import mimetypes
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from .models import ParseResult
from .wps import WPSParserError, is_wps_filename, parse_with_local_package


class UnsupportedFormat(RuntimeError):
    pass


def _format_from_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".pdf": "pdf", ".doc": "doc", ".docx": "docx", ".xls": "xls", ".xlsx": "xlsx",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".xml": "xml", ".txt": "txt", ".zip": "zip",
    }.get(suffix, "text")


def parse_local(path: str | Path, *, filename: str | None = None, media_type: str | None = None) -> ParseResult:
    path = Path(path)
    name = filename or path.name
    file_format = _format_from_name(name)
    if file_format == "pdf":
        return _parse_pdf(path)
    if file_format == "docx":
        return _parse_docx(path)
    if file_format == "doc":
        return _parse_doc(path)
    if file_format == "xls":
        return _parse_xls(path)
    if file_format == "xlsx":
        return _parse_xlsx(path)
    if file_format == "image":
        return _parse_image(path)
    if file_format in {"xml", "txt"}:
        return _parse_plain_text(path, file_format, media_type)
    if file_format == "zip":
        return _parse_zip(path)
    if is_wps_filename(name):
        try:
            return parse_with_local_package(path)
        except WPSParserError as exc:
            raise UnsupportedFormat(str(exc)) from exc
    data = path.read_text(encoding="utf-8", errors="replace")
    return ParseResult(markdown=data, format="text", metadata={"media_type": media_type or mimetypes.guess_type(name)[0]})


def parse_local_bytes(data: bytes, filename: str, media_type: str | None = None) -> ParseResult:
    suffix = Path(filename).suffix.lower()
    # Keep the byte parser deterministic without exposing temporary paths to callers.
    import tempfile
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        handle.write(data)
        handle.close()
        return parse_local(handle.name, filename=filename, media_type=media_type)
    finally:
        Path(handle.name).unlink(missing_ok=True)


def _parse_pdf(path: Path) -> ParseResult:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, 1):
        pages.append(f"## Page {index}\n\n{(page.extract_text() or '').strip()}")
    return ParseResult(markdown="# PDF Document\n\n" + "\n\n".join(pages), format="pdf", metadata={"pages": len(reader.pages)})


def _parse_docx(path: Path) -> ParseResult:
    from docx import Document
    document = Document(str(path))
    blocks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        rows = [[cell.text.replace("\n", " ").strip() for cell in row.cells] for row in table.rows]
        if rows:
            blocks.append(_markdown_table(rows))
    return ParseResult(markdown="# DOCX Document\n\n" + "\n\n".join(blocks), format="docx")


def _parse_doc(path: Path) -> ParseResult:
    """Extract legacy binary .doc through an explicitly installed converter."""
    configured = os.getenv("LEGACY_DOC_PARSER")
    executable = configured or shutil.which("antiword") or shutil.which("catdoc")
    if not executable:
        raise UnsupportedFormat("legacy .doc requires antiword, catdoc, or LEGACY_DOC_PARSER")
    completed = subprocess.run(
        [executable, str(path)],
        check=False,
        capture_output=True,
        timeout=float(os.getenv("LEGACY_DOC_TIMEOUT_SECONDS", "30")),
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip() or "legacy .doc parser failed"
        raise UnsupportedFormat(message)
    text = completed.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        raise UnsupportedFormat("legacy .doc parser returned no text")
    return ParseResult(markdown="# DOC Document\n\n" + text, format="doc")


def _parse_xlsx(path: Path) -> ParseResult:
    from openpyxl import load_workbook
    workbook = load_workbook(str(path), read_only=True, data_only=False)
    blocks = []
    for sheet in workbook.worksheets:
        rows = [["" if value is None else str(value) for value in row] for row in sheet.iter_rows(values_only=True)]
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if rows:
            blocks.append(f"## {sheet.title}\n\n{_markdown_table(rows)}")
    return ParseResult(markdown="# XLSX Workbook\n\n" + "\n\n".join(blocks), format="xlsx", metadata={"sheets": workbook.sheetnames})


def _parse_xls(path: Path) -> ParseResult:
    import xlrd
    workbook = xlrd.open_workbook(str(path), on_demand=True)
    blocks = []
    for sheet in workbook.sheets():
        rows = [["" if value is None else str(value) for value in sheet.row_values(index)] for index in range(sheet.nrows)]
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if rows:
            blocks.append(f"## {sheet.name}\n\n{_markdown_table(rows)}")
    return ParseResult(markdown="# XLS Workbook\n\n" + "\n\n".join(blocks), format="xls", metadata={"sheets": workbook.sheet_names()})


def _parse_image(path: Path) -> ParseResult:
    from PIL import Image
    with Image.open(path) as image:
        metadata = {"width": image.width, "height": image.height, "mode": image.mode, "format": image.format}
    try:
        from rapidocr_onnxruntime import RapidOCR

        output, _ = RapidOCR()(str(path))
        text = "\n".join(item[1] for item in (output or []) if len(item) > 1 and item[1])
        if text.strip():
            return ParseResult(markdown="# Image OCR\n\n" + text.strip(), format="image", metadata=metadata)
    except ImportError:
        pass
    return ParseResult(
        markdown="# Image OCR\n\n[OCR text unavailable]",
        format="image",
        metadata=metadata,
        warnings=["OCR fallback requires the optional rapidocr-onnxruntime dependency"],
    )


def _parse_plain_text(path: Path, file_format: str, media_type: str | None) -> ParseResult:
    """Return XML/TXT as-is; these formats do not need MinerU or conversion."""
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    return ParseResult(
        markdown=text,
        format=file_format,
        metadata={"media_type": media_type or mimetypes.guess_type(path.name)[0]},
    )


def _parse_zip(path: Path) -> ParseResult:
    """Parse every non-directory ZIP entry and separate entries by filename."""
    blocks = []
    file_names = []
    max_files = int(os.getenv("ZIP_MAX_FILES", "1000"))
    max_uncompressed_bytes = int(os.getenv("ZIP_MAX_UNCOMPRESSED_BYTES", str(200 * 1024 * 1024)))
    max_compression_ratio = float(os.getenv("ZIP_MAX_COMPRESSION_RATIO", "1000"))
    total_uncompressed_bytes = 0
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            if len(file_names) >= max_files:
                raise UnsupportedFormat("ZIP contains too many files")
            total_uncompressed_bytes += entry.file_size
            if total_uncompressed_bytes > max_uncompressed_bytes:
                raise UnsupportedFormat("ZIP uncompressed content exceeds configured limit")
            if entry.compress_size and entry.file_size / entry.compress_size > max_compression_ratio:
                raise UnsupportedFormat("ZIP compression ratio exceeds configured limit")
            file_names.append(entry.filename)
            content = parse_local_bytes(
                archive.read(entry),
                entry.filename,
                mimetypes.guess_type(entry.filename)[0],
            )
            blocks.append(f"# {entry.filename}\n\n{content.markdown}")

    return ParseResult(
        markdown="\n\n".join(blocks),
        format="zip",
        metadata={"files": file_names},
    )


def _markdown_table(rows: list[list[str]]) -> str:
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)
