"""共享字段提取工具 — 样品分类、日期/浮点解析、文本清理"""

from datetime import date, datetime
from typing import Optional
import re


# ============================================================
# 类型转换
# ============================================================

def safe_float(val) -> Optional[float]:
    """安全转换为 float，无法转换返回 None"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if val != val or val == float('inf') or val == float('-inf'):
            return None
        return float(val)
    s = str(val).strip()
    if not s or s in ('/', '-', '--', 'N/A', ''):
        return None
    s = s.replace(',', '.').replace(' ', '')
    # 处理百分比
    if s.endswith('%'):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def safe_int(val) -> Optional[int]:
    """安全转换为 int"""
    f = safe_float(val)
    if f is None:
        return None
    return int(f) if f == int(f) else None


def safe_date(val) -> Optional[date]:
    """安全转换为 date，支持多种格式"""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()

    s = str(val).strip()
    if not s:
        return None

    # xlrd 日期浮点数
    try:
        f = float(s)
        if 40000 < f < 60000:
            return None  # 可能是 Excel 序列号，但上下文不足
    except ValueError:
        pass

    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # 中文格式: 2026年4月2日
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?', s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


# ============================================================
# 文本清理
# ============================================================

def clean_text(val) -> str:
    """清理文本：去空格、标准化 Unicode"""
    if val is None:
        return ""
    s = str(val).strip()
    s = s.replace('\n', ' ').replace('\r', '')
    # 全角数字转半角
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    return s


def merge_multiline_name(lines: list[str]) -> str:
    """合并跨行拆分的中文样品名"""
    if not lines:
        return ""
    return ''.join(line.strip() for line in lines).strip()


# ============================================================
# COD 填报值解析
# ============================================================

def parse_reported_cod(raw: str) -> tuple[Optional[float], bool]:
    """解析 COD 填报值

    Returns:
        (reported_cod, is_below_dl)
        - 正常值: (15.0, False)
        - 低于检出限: (None, True)  — "4L", "<4", "＜4"
        - 空白: (None, False)        — "/", "-", ""
    """
    s = clean_text(raw)

    if not s or s in ('/', '-', '--', ''):
        return None, False

    # 低于检出限模式
    if re.match(r'^[＜<]\s*(\d+\.?\d*)\s*L?$', s):
        return None, True

    if re.match(r'^(\d+\.?\d*)\s*L$', s):
        return None, True

    # 正常数值
    f = safe_float(s.replace('L', '').replace('<', '').replace('＜', ''))
    if f is not None:
        return f, False

    return None, False


# ============================================================
# 样品分类 (核心逻辑)
# ============================================================

def classify_samples(samples: list) -> list:
    """
    对所有样品行进行类型标记: is_blank, is_qc_standard, is_parallel

    必须在所有样品提取完后调用。

    分类规则:
    - 实验室空白:  sample_id 包含 "实验室空白"
    - 全程序空白:  sample_id 包含 "全程序空白" → NOT is_blank (不走空白均值)
    - 质控标样:    sample_id 包含 "标样" / "质控样" / "有证标样" / YLB / GBW
    - 平行样:      sample_id 包含 "平行" 或有配对编号
    - 平行配对:    剥离平行后缀提取基 ID，同基 ID 配对
    """

    # 第一遍: 标记 is_blank 和 is_qc_standard
    for s in samples:
        sid = clean_text(s.sample_id)

        # 实验室空白检测
        if _is_lab_blank(sid):
            s.is_blank = True
            s.is_qc_standard = False
            continue

        # 全程序空白: 不算入空白均值，但也不是普通样品
        if '全程序空白' in sid:
            s.is_blank = False
            continue

        # 质控标样检测
        if _is_qc_standard(sid):
            s.is_qc_standard = True
            s.is_blank = False
            continue

        # 空白兜底: reported_cod 为 "/" 且 sample_id 包含 "空白"
        if '空白' in sid and s.reported_cod_raw in ('/', '-', ''):
            s.is_blank = True
            continue

    # 第二遍: 标记 is_parallel 和 parallel_pair_id
    for s in samples:
        if s.is_blank or s.is_qc_standard:
            continue

        sid = clean_text(s.sample_id)

        if '平行' in sid:
            s.is_parallel = True
            # 提取基 ID: "12026040115510012752-1-平行" → "12026040115510012752"
            s.parallel_pair_id = _extract_base_id(sid)
        else:
            # 检查是否作为平行对中的原始样 (在 QC 表中有对应的平行样)
            # 注意: 此逻辑在集成 QC 数据后可能需调整
            pass

    # 第三遍: 关联平行对 — 如果同一基 ID 有两个样品，都标记为 is_parallel
    base_ids = {}
    for s in samples:
        if s.is_parallel and s.parallel_pair_id:
            bid = s.parallel_pair_id
            if bid not in base_ids:
                base_ids[bid] = []
            base_ids[bid].append(s)

    for bid, group in base_ids.items():
        if len(group) == 1:
            # 只有一个平行样？可能原始样没标记 is_parallel
            # 找同名基 ID 的原始样
            for s in samples:
                if not s.is_parallel and clean_text(s.sample_id) == bid:
                    s.is_parallel = True
                    s.parallel_pair_id = bid
                    break


def _is_lab_blank(sample_id: str) -> bool:
    """判断是否为实验室空白"""
    return ('实验室空白' in sample_id or
            sample_id.strip().startswith('空白') or
            (sample_id.startswith('实验室') and '空白' in sample_id))


def _is_qc_standard(sample_id: str) -> bool:
    """判断是否为有证标样/质控样"""
    keywords = ['标样', '质控样', '有证标样', '密码标样', '明码标样',
                'YLB', 'GBW', 'BWB', 'GSB']
    for kw in keywords:
        if kw in sample_id:
            return True
    return False


def _extract_base_id(sample_id: str) -> str:
    """从平行样 ID 中提取基 ID

    "12026040115510012752-1-平行" → "12026040115510012752"
    "12026040115510012752-平行"  → "12026040115510012752"
    """
    # 移除 "-平行" 后缀
    s = sample_id.replace('-平行', '').replace('_平行', '').strip()
    # 移除 "-1", "-2" 等序号后缀 (仅当后面没有更多内容时)
    s = re.sub(r'[_-]\d+$', '', s)
    return s


# ============================================================
# QC 保证值范围解析
# ============================================================

def parse_guarantee_range(text: str) -> tuple[Optional[float], Optional[float]]:
    """解析保证值范围文本

    "14.3 ± 1.1(mg/L)" → (14.3, 1.1)
    "14.3±1.1"          → (14.3, 1.1)
    "＜4(mg/L)"         → (4.0, None)  — 单侧上限
    Returns: (center, tolerance) or (None, None)
    """
    s = clean_text(text)
    if not s:
        return None, None

    # 模式: "X ± Y"
    m = re.match(r'(\d+\.?\d*)\s*[±±]\s*(\d+\.?\d*)', s)
    if m:
        return float(m.group(1)), float(m.group(2))

    # 模式: "＜X" 或 "<X"
    m = re.match(r'[＜<]\s*(\d+\.?\d*)', s)
    if m:
        return float(m.group(1)), None

    # 普通数值
    f = safe_float(s)
    if f is not None:
        return f, None

    return None, None
