r"""稀释合理性审核 — R-DIL-001 ~ R-DIL-002

HJ 828-2017 §9.2.1 注: 对于浓度较高的水样可稀释后测定
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
import config


class DilutionInRange(BaseRule):
    """R-DIL-001: 稀释后COD在有效范围 4-700 mg/L"""
    code = "R-DIL-001"
    category = "稀释合理性"
    name = "稀释后结果在有效范围"
    hj_ref = "HJ 828-2017 §1, §9.2.1 — 超出测定上限须稀释"

    def check(self, ctx: BatchContext) -> RuleResult:
        issues = []
        over_diluted = []

        for s in ctx.record.actual_samples:
            if s.dilution_factor <= 1.0:
                continue

            val = s.reported_cod or (s.cod_calculated if s.cod_calculated else None)
            if val is None:
                continue

            # 稀释后原始液浓度 = 报告值 / 稀释倍数... 不，这里的逻辑是:
            # 报告值已经是稀释后的最终结果(乘以了稀释倍数)
            # 所以我们检查报告值本身是否在有效范围
            if val > config.UPPER_LIMIT_UNDILUTED:
                issues.append(
                    f"{s.sample_id}: 稀释{s.dilution_factor}×后报告值{val}mg/L仍超{config.UPPER_LIMIT_UNDILUTED}mg/L"
                )
            elif val < config.DETECTION_LIMIT and s.dilution_factor > 1:
                over_diluted.append(
                    f"{s.sample_id}: 稀释{s.dilution_factor}×后报告值{val}mg/L低于检出限, 可能稀释过度"
                )

        if not issues and not over_diluted:
            # 检查有没有稀释样品
            diluted = sum(1 for s in ctx.record.actual_samples if s.dilution_factor > 1.0)
            if diluted == 0:
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.INFO, "无稀释样品",
                    "", self.hj_ref)

            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"已检查{diluted}个稀释样品, 均在有效范围内",
                f"4-{config.UPPER_LIMIT_UNDILUTED} mg/L", self.hj_ref,
                "稀释后结果在有效范围内")

        result_str = []
        if issues:
            result_str.append(f"FAIL: {'; '.join(issues)}")
        if over_diluted:
            result_str.append(f"WARN: {'; '.join(over_diluted)}")

        status = AuditStatus.FAIL if issues else AuditStatus.WARNING
        return RuleResult(self.code, self.category, self.name,
            status,
            "; ".join(result_str),
            f"4-{config.UPPER_LIMIT_UNDILUTED} mg/L", self.hj_ref,
            "稀释合理性检查发现问题",
            "稀释不足需增加稀释倍数；稀释过度需减少稀释倍数")


class DilutionVolumeConsistency(BaseRule):
    """R-DIL-002: 稀释倍数与取样体积一致性"""
    code = "R-DIL-002"
    category = "稀释合理性"
    name = "稀释倍数与取样体积一致性"
    hj_ref = "HJ 828-2017 §9.2.1"

    def check(self, ctx: BatchContext) -> RuleResult:
        issues = []
        for s in ctx.record.actual_samples:
            if s.dilution_factor <= 1.0:
                continue
            if s.diluted_volume <= 0:
                issues.append(f"{s.sample_id}: 稀释后取样体积未填写")
            # 原始体积 / 稀释倍数 应该与稀释后体积接近
            expected_diluted = s.volume / s.dilution_factor
            if s.diluted_volume > 0 and abs(s.diluted_volume - expected_diluted) > 1.0:
                issues.append(
                    f"{s.sample_id}: 稀释{s.dilution_factor}×, 取样{s.volume}ml, "
                    f"稀释后理论{expected_diluted:.1f}ml vs 实际{s.diluted_volume}ml"
                )

        if not issues:
            diluted = sum(1 for s in ctx.record.actual_samples if s.dilution_factor > 1.0)
            if diluted == 0:
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.INFO, "无稀释样品",
                    "", self.hj_ref)
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"已检查{diluted}个稀释样品",
                "稀释体积关系合理", self.hj_ref,
                "稀释倍数与取样体积一致")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.WARNING,
            "; ".join(issues),
            "", self.hj_ref,
            "部分稀释样品的体积关系不一致",
            "请核实稀释操作记录")
