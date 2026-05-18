"""解析器调度层 — 按文件类型分发到对应解析器"""

from dataclasses import dataclass, field
from typing import Optional

from models.record import CODRecord


@dataclass
class ParseResult:
    record: Optional[CODRecord] = None
    warnings: list[str] = field(default_factory=list)
    source_format: str = ""
    used_ai_fallback: bool = False

    @property
    def ok(self) -> bool:
        return self.record is not None


def parse(file_bytes: bytes, filename: str) -> ParseResult:
    """主入口: 根据扩展名分发解析

    Returns:
        ParseResult with extracted CODRecord, warnings, and metadata
    """
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext in ('xls', 'xlsx'):
        return _parse_excel(file_bytes, filename, ext)
    elif ext == 'pdf':
        return _parse_pdf(file_bytes, filename)
    elif ext in ('docx', 'doc'):
        return _parse_docx(file_bytes, filename)
    elif ext in ('png', 'jpg', 'jpeg', 'tiff', 'bmp'):
        return _parse_image(file_bytes, filename)
    else:
        return ParseResult(
            warnings=[f"不支持的文件格式: .{ext}，支持: xls, xlsx, pdf, docx, png, jpg"]
        )


def _parse_excel(file_bytes: bytes, filename: str, ext: str) -> ParseResult:
    from parsers.excel_parser import parse_excel_bytes

    try:
        rec = parse_excel_bytes(file_bytes, filename)
        return ParseResult(record=rec, source_format=ext)
    except Exception as e:
        return ParseResult(warnings=[f"Excel 解析失败: {e}"])


def _parse_pdf(file_bytes: bytes, filename: str) -> ParseResult:
    from parsers.pdf_parser import parse_pdf_bytes

    try:
        rec = parse_pdf_bytes(file_bytes, filename)
        return ParseResult(record=rec, source_format="pdf")
    except Exception as e:
        return ParseResult(warnings=[f"PDF 解析失败: {e}"])


def _parse_docx(file_bytes: bytes, filename: str) -> ParseResult:
    from parsers.docx_parser import parse_docx_bytes
    try:
        rec = parse_docx_bytes(file_bytes, filename)
        return ParseResult(record=rec, source_format="docx")
    except ImportError:
        return ParseResult(warnings=["DOCX 解析器未安装 (需要 python-docx)"])
    except Exception as e:
        return ParseResult(warnings=[f"DOCX 解析失败: {e}"])


def _parse_image(file_bytes: bytes, filename: str) -> ParseResult:
    from parsers.image_parser import parse_image_bytes
    try:
        rec, used_ai = parse_image_bytes(file_bytes, filename)
        return ParseResult(record=rec, source_format="image", used_ai_fallback=used_ai)
    except ImportError:
        return ParseResult(warnings=["图片解析器未安装 (需要 easyocr)"])
    except Exception as e:
        return ParseResult(warnings=[f"图片解析失败: {e}"])
