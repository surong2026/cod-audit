"""图片解析器 — EasyOCR 文本识别 + AI mapper 主路径

支持格式: PNG, JPG, JPEG, TIFF, BMP

策略:
  1. EasyOCR 提取所有文本块
  2. 按 y 坐标排序重建行顺序
  3. 拼接为 token 流
  4. 尝试启发式提取 (复用 PDF 解析器函数)
  5. 若样品数为 0，自动调用 AI mapper 从 OCR 文本提取
"""

from io import BytesIO
from typing import Optional


def parse_image_bytes(file_bytes: bytes, filename: str) -> "tuple[CODRecord, bool]":
    """从图片字节流解析 COD 记录。返回 (record, used_ai)."""
    import numpy as np
    from PIL import Image

    img = Image.open(BytesIO(file_bytes))
    return _extract(img)


def parse_image(file_path: str) -> "tuple[CODRecord, bool]":
    """从图片文件路径解析 COD 记录。返回 (record, used_ai)."""
    from PIL import Image
    img = Image.open(file_path)
    return _extract(img)


def _extract(img) -> "tuple[CODRecord, bool]":
    import numpy as np

    try:
        import easyocr
    except ImportError:
        raise ImportError("EasyOCR 未安装。安装: pip install easyocr")

    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    img_array = _pil_to_array(img)

    results = reader.readtext(img_array)

    # 按 y 坐标排序 (行优先)
    results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))

    lines = [text for (_bbox, text, _conf) in results if text.strip()]

    # 拼接为文本流
    text = '\n'.join(lines)

    # 启发式提取 → 若样品缺失则 AI mapper
    rec, used_ai = _parse_text(text)

    return rec, used_ai


def _pil_to_array(img) -> "np.ndarray":
    """PIL Image → numpy array (RGB)"""
    import numpy as np

    if img.mode == 'RGBA':
        img = img.convert('RGB')
    elif img.mode == 'L':
        img = img.convert('RGB')

    return np.array(img)


def _parse_text(text: str) -> "tuple[CODRecord, bool]":
    from parsers.pdf_parser import (
        _extract_metadata, _extract_instruments, _extract_samples,
        _extract_fas, _extract_footer, _extract_qc, _detect_level,
    )
    from parsers.field_extractor import classify_samples

    rec = CODRecord()

    # 分页检测: "质控结果表" 之前 = page1, 之后 = page2
    qc_pos = text.find('质控结果表')
    if qc_pos > 0:
        page1 = text[:qc_pos]
        page2 = text[qc_pos:]
    else:
        page1 = text
        page2 = ""

    _extract_metadata(page1, rec)
    _extract_instruments(page1, rec)
    _extract_samples(page1, rec)
    _extract_fas(page1, rec)
    _extract_footer(page1, rec)
    if page2:
        _extract_qc(page2, rec)

    classify_samples(rec.samples)
    _detect_level(rec)

    # 若启发式未提取到样品，走 AI mapper
    used_ai = False
    if not rec.samples:
        used_ai = _try_ai_mapper(text, rec)

    return rec, used_ai


def _try_ai_mapper(ocr_text: str, rec: "CODRecord") -> bool:
    """尝试用 AI mapper 从 OCR 文本中提取缺失字段"""
    from parsers.ai_mapper import AIFieldMapper

    mapper = AIFieldMapper()
    if not mapper.available:
        return False

    _, changed = mapper.fill_gaps(ocr_text, rec)
    return changed


from models.record import CODRecord
