r"""氯离子干扰审核 — R-CL-001 ~ R-CL-002

HJ 828-2017 §5:
  主要干扰物为氯化物，可加入硫酸汞溶液去除
  m[HgSO4]:m[Cl-] ≥ 20:1 比例加入，最大2ml

HJ 828-2017 §1:
  不适用于含氯化物浓度大于1000mg/L(稀释后)的水样
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
from utils.cod_calc import calc_hgso4_required
import config


class ChlorideLimit(BaseRule):
    """R-CL-001: 稀释后氯离子 ≤ 1000 mg/L"""
    code = "R-CL-001"
    category = "氯离子干扰"
    name = "氯离子浓度上限"
    hj_ref = "HJ 828-2017 §1 — 不适用于氯化物>1000mg/L(稀释后)"

    def check(self, ctx: BatchContext) -> RuleResult:
        violations = []
        for s in ctx.record.actual_samples:
            cl = s.cl_estimate
            if cl is None or cl <= 0:
                continue
            dilution = s.dilution_factor if s.dilution_factor >= 1 else 1.0
            diluted_cl = cl / dilution

            if diluted_cl > config.CL_MAX_DILUTED:
                violations.append(
                    f"{s.sample_id}: Cl-={cl}mg/L, 稀释{dilution}×后={diluted_cl:.0f}mg/L > {config.CL_MAX_DILUTED}mg/L"
                )

        if not violations:
            checked = sum(1 for s in ctx.record.actual_samples
                         if s.cl_estimate is not None and s.cl_estimate > 0)
            if checked == 0:
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.INFO, "无氯离子数据",
                    f"稀释后 ≤ {config.CL_MAX_DILUTED} mg/L", self.hj_ref,
                    "记录中未填写氯离子估算量，跳过此项检查")
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"已检查{checked}个样品, 稀释后Cl-均≤{config.CL_MAX_DILUTED}mg/L",
                f"稀释后 ≤ {config.CL_MAX_DILUTED} mg/L", self.hj_ref,
                "所有样品的氯离子浓度在方法适用范围内")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(violations),
            f"稀释后 ≤ {config.CL_MAX_DILUTED} mg/L", self.hj_ref,
            f"{len(violations)}个样品稀释后氯离子超标，本方法不适用",
            "稀释后氯离子>1000mg/L的水样不适用HJ 828-2017。请改用其他方法或进一步稀释（需验证无基体效应）。")


class HgSO4Sufficient(BaseRule):
    """R-CL-002: 硫酸汞加入量 ≥ 所需量 (m(HgSO4):m(Cl-) ≥ 20:1)"""
    code = "R-CL-002"
    category = "氯离子干扰"
    name = "硫酸汞加入量验证"
    hj_ref = "HJ 828-2017 §5, §9.1.1 — m[HgSO4]:m[Cl-]≥20:1, 最大2ml"

    def check(self, ctx: BatchContext) -> RuleResult:
        checked = 0
        violations = []
        warnings = []

        for s in ctx.record.samples:
            cl = s.cl_estimate
            if cl is None or cl <= 0:
                continue

            required = calc_hgso4_required(cl, s.volume, config.HGSO4_CL_RATIO, config.HGSO4_SOLUTION_CONC)
            added = s.hgso4_added

            if required > config.HGSO4_MAX_VOLUME:
                warnings.append(
                    f"{s.sample_id}: 需要{required:.2f}ml > 最大2ml, 限制加入2ml"
                )
                required = config.HGSO4_MAX_VOLUME

            checked += 1

            if added is None:
                violations.append(
                    f"{s.sample_id}: Cl-={cl}mg/L, 需HgSO4 {required:.3f}ml, 加入量未填写"
                )
            elif added < required:
                violations.append(
                    f"{s.sample_id}: Cl-={cl}mg/L, 加入{added:.3f}ml < 需{required:.3f}ml"
                )

        if checked == 0:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "无氯离子数据",
                f"m(HgSO4):m(Cl-) ≥ {config.HGSO4_CL_RATIO}:1", self.hj_ref,
                "记录中未填写氯离子估算量，跳过硫酸汞验证")

        if not violations:
            msg = f"已检查{checked}个样品, 硫酸汞加入量均满足≥{config.HGSO4_CL_RATIO}:1要求"
            if warnings:
                msg += "; " + "; ".join(warnings)
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.WARNING, msg,
                    f"m(HgSO4):m(Cl-) ≥ {config.HGSO4_CL_RATIO}:1, 最大2ml", self.hj_ref,
                    "部分样品所需HgSO4超过最大加入量2ml",
                    "氯离子较高时建议稀释样品")
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS, msg,
                f"m(HgSO4):m(Cl-) ≥ {config.HGSO4_CL_RATIO}:1", self.hj_ref,
                "硫酸汞加入量足够掩蔽氯离子")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(violations),
            f"m(HgSO4):m(Cl-) ≥ {config.HGSO4_CL_RATIO}:1", self.hj_ref,
            f"{len(violations)}个样品硫酸汞加入量不足",
            "按氯离子估算量补充硫酸汞溶液（m(HgSO4):m(Cl-)≥20:1），最大不超过2ml")
