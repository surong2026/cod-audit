r"""准确度审核 — 有证标样/质控样 — R-ACC-001 ~ R-ACC-002

HJ 828-2017 §12.3:
  每批样品测定时，应分析一个有证标准样品或质控样品，
  其测定值应在保证值范围内或达到规定的质量控制要求。
"""

import re
from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult


def _parse_certified_range(text: str) -> tuple:
    """解析保证值范围文本

    "14.3 ± 1.1(mg/L)" → (13.2, 15.4)
    "＜4(mg/L)" → (None, None) 下限值
    """
    if not text:
        return None, None
    text = text.replace(" ", "").replace("（", "(").replace("）", ")")
    m = re.match(r'([\d.]+)\s*[±±]\s*([\d.]+)', text)
    if m:
        center = float(m.group(1))
        half = float(m.group(2))
        return center - half, center + half
    # "<4(mg/L)" 类型
    if text.startswith("＜") or text.startswith("<"):
        return None, None
    try:
        val = float(text)
        return val, val
    except ValueError:
        return None, None


class QCStandardExists(BaseRule):
    """R-ACC-001: 每批至少有1个有证标样/质控样"""
    code = "R-ACC-001"
    category = "准确度审核"
    name = "质控样存在性"
    hj_ref = "HJ 828-2017 §12.3 — 每批应分析一个有证标准样品或质控样品"

    def check(self, ctx: BatchContext) -> RuleResult:
        n = ctx.qc_standard_count
        has_qc = bool(ctx.record.qc.std_sample_id)

        if n >= 1 or has_qc:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"质控样数量={n}, 编号={ctx.record.qc.std_sample_id}",
                "≥ 1", self.hj_ref,
                "已测定质控样")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL, "质控样数量=0",
            "≥ 1", self.hj_ref,
            "本批次未测定质控样",
            "每批样品必须分析一个有证标准样品或质控样品")


class QCStandardInRange(BaseRule):
    """R-ACC-002: 质控样测定值在保证值范围内"""
    code = "R-ACC-002"
    category = "准确度审核"
    name = "质控样结果在保证值范围内"
    hj_ref = "HJ 828-2017 §12.3 — 测定值应在保证值范围内"

    def check(self, ctx: BatchContext) -> RuleResult:
        qc = ctx.record.qc
        measured = qc.std_measured
        guarantee = qc.std_guarantee_range

        if measured is None:
            # 尝试从样品列表找标样的填报值
            for s in ctx.record.qc_standards:
                if s.reported_cod is not None:
                    measured = s.reported_cod
                    break

        if measured is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, "质控样测定值缺失",
                guarantee or "需保证值范围", self.hj_ref,
                "无法提取质控样测定值")

        if not guarantee:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.WARNING,
                f"测定值={measured} mg/L",
                "保证值范围未填写", self.hj_ref,
                "质控样有测定值但保证值范围未填写，无法判断是否合格",
                "请补充质控样证书上的保证值范围")

        lo, hi = _parse_certified_range(guarantee)

        if lo is None and hi is None:
            # 可能是 "<4" 型保证值
            if guarantee.startswith("＜") or guarantee.startswith("<"):
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.PASS,
                    f"测定值={measured} mg/L, 保证值={guarantee}",
                    guarantee, self.hj_ref,
                    "质控样测定值符合保证范围（低于限值）")

            return RuleResult(self.code, self.category, self.name,
                AuditStatus.WARNING,
                f"测定值={measured} mg/L, 保证值={guarantee}",
                "无法解析保证范围", self.hj_ref,
                "质控样保证值范围格式无法解析",
                "请用\"14.3 ± 1.1\"格式填写保证值范围")

        if lo <= measured <= hi:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"测定值={measured} mg/L",
                f"{lo} - {hi} mg/L", self.hj_ref,
                "质控样测定值在保证值范围内")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"测定值={measured} mg/L",
            f"{lo} - {hi} mg/L", self.hj_ref,
            f"质控样测定值{measured}超出保证值范围{lo}-{hi}",
            "检查标准溶液、操作过程，必要时重做")
