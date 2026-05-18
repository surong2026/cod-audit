r"""检出限与测定范围审核 — R-RANGE-001 ~ R-RANGE-003

HJ 828-2017 §1:
  检出限 4 mg/L, 测定下限 16 mg/L, 测定上限 700 mg/L (未经稀释)
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
import config


class DetectionLimit(BaseRule):
    """R-RANGE-001: 检出限检查 — COD < 4 → 应报"<4"或"4L" """
    code = "R-RANGE-001"
    category = "检出限与范围"
    name = "检出限"
    hj_ref = "HJ 828-2017 §1 — 取样10.0ml时检出限4mg/L"

    def check(self, ctx: BatchContext) -> RuleResult:
        issues = []
        for s in ctx.record.actual_samples:
            # 检查重算值是否<4，但填报值没有正确表示为<4
            if s.cod_calculated is not None and s.cod_calculated < config.DETECTION_LIMIT:
                if not s.is_below_dl:
                    issues.append(
                        f"{s.sample_id}: 重算值{s.cod_calculated:.1f}mg/L < {config.DETECTION_LIMIT}mg/L检出限, "
                        f"填报为{s.cod_display}"
                    )

        if not issues:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "所有样品结果≥检出限或已正确标注低于检出限",
                f"<{config.DETECTION_LIMIT}mg/L → 报告\"<{config.DETECTION_LIMIT}\"", self.hj_ref,
                "检出限检查通过")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.WARNING,
            "; ".join(issues),
            f"<{config.DETECTION_LIMIT}mg/L → 报告\"<{config.DETECTION_LIMIT}\"", self.hj_ref,
            "部分样品计算结果低于检出限但未正确标注",
            "低于检出限的结果应报告为\"<4\"或\"4L\"")


class QuantitationLimit(BaseRule):
    """R-RANGE-002: 测定下限检查 — 4 ≤ COD < 16 报告为低于测定下限"""
    code = "R-RANGE-002"
    category = "检出限与范围"
    name = "测定下限"
    hj_ref = "HJ 828-2017 §1 — 测定下限16mg/L"

    def check(self, ctx: BatchContext) -> RuleResult:
        below_ql = []
        for s in ctx.record.actual_samples:
            val = s.cod_calculated if s.cod_calculated is not None else s.reported_cod
            if val is not None and config.DETECTION_LIMIT <= val < config.QUANTITATION_LIMIT:
                below_ql.append(
                    f"{s.sample_id}: {val} mg/L (检出限{config.DETECTION_LIMIT}-测定下限{config.QUANTITATION_LIMIT})"
                )

        if not below_ql:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "所有样品结果≥测定下限(16mg/L)或低于检出限",
                f"≥{config.QUANTITATION_LIMIT} mg/L", self.hj_ref,
                "测定下限检查通过")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.INFO,
            "; ".join(below_ql),
            f"≥{config.QUANTITATION_LIMIT} mg/L", self.hj_ref,
            f"{len(below_ql)}个样品结果低于测定下限({config.QUANTITATION_LIMIT}mg/L)，不确定度较大",
            "低于测定下限的结果可以报出，但应注意不确定度较大")


class UpperLimit(BaseRule):
    """R-RANGE-003: 测定上限检查 — 未经稀释的COD > 700 mg/L"""
    code = "R-RANGE-003"
    category = "检出限与范围"
    name = "测定上限"
    hj_ref = "HJ 828-2017 §1 — 未经稀释的水样测定上限为700mg/L"

    def check(self, ctx: BatchContext) -> RuleResult:
        over_range = []
        for s in ctx.record.actual_samples:
            val = s.reported_cod or (s.cod_calculated if s.cod_calculated else None)
            if val is None:
                continue
            if val > config.UPPER_LIMIT_UNDILUTED and s.dilution_factor == 1.0:
                over_range.append(
                    f"{s.sample_id}: {val} mg/L > {config.UPPER_LIMIT_UNDILUTED} mg/L (未经稀释)"
                )

        if not over_range:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "所有样品结果≤测定上限或已稀释",
                f"≤ {config.UPPER_LIMIT_UNDILUTED} mg/L (未经稀释)", self.hj_ref,
                "测定上限检查通过")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(over_range),
            f"≤ {config.UPPER_LIMIT_UNDILUTED} mg/L (未经稀释)", self.hj_ref,
            "部分样品超过未经稀释的测定上限，须稀释后重新测定",
            "超过700mg/L的样品须稀释后测定。稀释倍数应使结果落在4-700mg/L范围内。")
