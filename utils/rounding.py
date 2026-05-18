"""结果修约规则 — HJ 828-2017 §10.2

COD < 4 mg/L  → 报告 "<4" 或 "4L"
COD < 100 mg/L → 保留至整数位
COD ≥ 100 mg/L → 保留三位有效数字
"""

import math


def round_cod(value: float, detection_limit: float = 4.0,
              integer_threshold: float = 100.0) -> str:
    """对 COD 结果值按 HJ 828-2017 规则修约

    Args:
        value: COD 原始计算值 mg/L
        detection_limit: 检出限 mg/L
        integer_threshold: 整数修约阈值 mg/L

    Returns:
        修约后的字符串表示
    """
    if value < detection_limit:
        return "<4"

    if value < integer_threshold:
        return str(round(value))
    else:
        return format(value, ".3g")


def round_cod_to_float(value: float, detection_limit: float = 4.0,
                       integer_threshold: float = 100.0) -> float:
    """修约并返回数值（低于检出限返回 nan）

    Args:
        value: COD 原始计算值 mg/L

    Returns:
        修约后的浮点数, <DL 返回 float('nan')
    """
    import math
    if value < detection_limit:
        return float('nan')
    if value < integer_threshold:
        return float(round(value))
    else:
        return float(format(value, ".3g"))


def to_3_sig_figs(value: float) -> float:
    """保留三位有效数字"""
    if value == 0:
        return 0.0
    return float(format(value, ".3g"))


def parse_reported_cod(raw: str) -> tuple:
    """解析记录表填报的 COD 值

    Args:
        raw: 填报值原始文本, 如 "15", "14.4", "<4", "4L", "4L", "/"

    Returns:
        (数值或None, 是否低于检出限)
    """
    raw = raw.strip().upper()
    if raw in ("", "/", "-", "—"):
        return None, False

    # 低于检出限的表达
    if raw in ("<4", "4L", "＜4", "<4.0", "4L"):
        return None, True
    if raw.startswith("<") or raw.endswith("L"):
        try:
            val = float(raw.replace("<", "").replace("L", "").replace("＜", ""))
            return None, val <= 4.0
        except ValueError:
            return None, False

    try:
        return float(raw), False
    except ValueError:
        return None, False
