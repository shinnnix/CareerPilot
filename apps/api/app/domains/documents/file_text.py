from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.core.errors import UnsupportedDocumentError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
TEXT_EXTENSIONS = {".txt", ".md"}
PDF_EXTENSIONS = {".pdf"}


def extract_text_from_upload(*, file_name: str, content: bytes) -> tuple[str, str]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise UnsupportedDocumentError("文件超过 2 MiB 的第二周导入上限")
    suffix = Path(file_name).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return _decode_text(content), "text/markdown" if suffix == ".md" else "text/plain"
    if suffix in PDF_EXTENSIONS:
        return _extract_pdf_text(content), "application/pdf"
    raise UnsupportedDocumentError("当前仅支持 .txt、.md 和文本型 .pdf 文件")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedDocumentError("无法识别文本文件编码，请转换为 UTF-8 后重试")


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        raise UnsupportedDocumentError("PDF 解析失败，请确认文件未加密且内容完整") from exc
    if len(text) < 20:
        raise UnsupportedDocumentError("PDF 未提取到足够文本；扫描件需要在后续版本使用 OCR")
    return text
