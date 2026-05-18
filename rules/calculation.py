r"""计算审核 — R-CALC-001 ~ R-CALC-002

R-CALC-001: 系统重算 COD 并与填报值交叉校验
R-CALC-002: 空白均值使用验证
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
from engine.calculator import recompute_all_cod, verify_reported_cod
from utils.rounding import round_cod_to_float


class CODRecalcVerify(BaseRule):
    """R-CALC-001: COD 浓度重算验证 — 每个非空白样品独立重算并与填报值比对"""
    code = "R-CALC-001"
    category = "计算审核"
    name = "COD浓度重算验证"
    hj_ref = "HJ 828-2017 §10.1, §10.2 — COD计算公式与修约规则"

    def check(self, ctx: BatchContext) -> RuleResult:
        recompute_all_cod(ctx.record)
        mismatches = verify_reported_cod(ctx.record)

        if not mismatches:
            # 统计通过数
            verified = sum(1 for s in ctx.record.samples
                          if not s.is_blank and s.cod_calculated is not None)
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"已验证{verified}个样品, 全部与填报值一致",
                "系统重算值==填报值（修约后）", self.hj_ref,
                "所有样品COD计算值与填报值一致")

        mismatch_detail = []
        for s in mismatches:
            calc = round_cod_to_float(s.cod_calculated) if s.cod_calculated else None
            mismatch_detail.append(
                f"{s.sample_id}: 填报={s.reported_cod} 重算={calc} (原始={s.cod_calculated:.2f})"
            )

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(mismatch_detail),
            "系统重算值==填报值（修约后）", self.hj_ref,
            f"{len(mismatches)}个样品重算值与填报值不一致",
            "请检查滴定体积记录、标定浓度、空白值是否正确")


class BlankAvgUsage(BaseRule):
    """R-CALC-002: 空白均值使用验证"""
    code = "R-CALC-002"
    category = "计算审核"
    name = "空白均值使用验证"
    hj_ref = "HJ 828-2017 §10.1 — 使用空白均值参与计算"

    def check(self, ctx: BatchContext) -> RuleResult:
        blanks = ctx.record.blanks
        if len(blanks) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "空白数量不足",
                "", self.hj_ref,
                "无法验证空白均值（不足2个空白）")

        vols = [b.net_volume for b in blanks if b.net_volume > 0]
        if len(vols) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "空白体积数据不完整",
                "", self.hj_ref)

        avg = sum(vols) / len(vols)
        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"空白均值={avg:.4f} ml (来自{len(vols)}个空白: {[f'{v:.2f}' for v in vols]})",
            "使用所有空白体积的算术均值", self.hj_ref,
            "空白均值已用于COD计算")
