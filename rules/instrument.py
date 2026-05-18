r"""仪器溯源审核 — R-INST-001 ~ R-INST-003

HJ 828-2017 §7 仪器和设备 + 计量法规要求仪器在检定/校准有效期内
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult


def _check_instrument(ctx: BatchContext, keyword: str, code: str,
                      name: str, hj_ref: str) -> RuleResult:
    """通用仪器溯源检查"""
    analysis_date = ctx.record.analysis_date
    if analysis_date is None:
        return RuleResult(code, "仪器溯源", name,
            AuditStatus.INFO, "分析日期缺失",
            "分析日期应在仪器溯源有效期内", hj_ref,
            "缺少分析日期，跳过仪器溯源检查")

    for inst in ctx.record.instruments:
        if keyword.lower() in inst.name.lower() or keyword.lower() in inst.model.lower():
            if inst.calibration_expiry is None:
                return RuleResult(code, "仪器溯源", name,
                    AuditStatus.WARNING,
                    f"{inst.name}({inst.serial_no}): 溯源有效期未填写",
                    "分析日期 ≤ 溯源有效期", hj_ref,
                    f"仪器 {inst.name} 缺少溯源有效期信息",
                    "请补充仪器溯源有效期")

            if analysis_date > inst.calibration_expiry:
                return RuleResult(code, "仪器溯源", name,
                    AuditStatus.FAIL,
                    f"{inst.name}({inst.serial_no}): 溯源有效期至{inst.calibration_expiry.isoformat()}, "
                    f"分析日期{analysis_date.isoformat()}已过期",
                    "分析日期 ≤ 溯源有效期", hj_ref,
                    f"仪器 {inst.name} 溯源已过期",
                    "请将仪器送检/校准后再使用")

            return RuleResult(code, "仪器溯源", name,
                AuditStatus.PASS,
                f"{inst.name}({inst.serial_no}): 有效期至{inst.calibration_expiry.isoformat()}, 分析日期在有效期内",
                "分析日期 ≤ 溯源有效期", hj_ref,
                "仪器在溯源有效期内")

    # 未找到对应仪器
    return RuleResult(code, "仪器溯源", name,
        AuditStatus.INFO, f"未找到'{keyword}'类型仪器",
        "", hj_ref,
        f"记录中未检测到{keyword}信息")


class BuretteCalibration(BaseRule):
    """R-INST-001: 酸式滴定管在有效期内"""
    code = "R-INST-001"
    category = "仪器溯源"
    name = "酸式滴定管溯源"
    hj_ref = "HJ 828-2017 §7.4（酸式滴定管）"

    def check(self, ctx: BatchContext) -> RuleResult:
        return _check_instrument(
            ctx, "滴定管", self.code, self.name, self.hj_ref)


class DigestionDeviceCalibration(BaseRule):
    """R-INST-002: COD消解装置在有效期内"""
    code = "R-INST-002"
    category = "仪器溯源"
    name = "COD消解/回流装置溯源"
    hj_ref = "HJ 828-2017 §7.1, §7.2（回流装置、加热装置）"

    def check(self, ctx: BatchContext) -> RuleResult:
        return _check_instrument(
            ctx, "消解", self.code, self.name, self.hj_ref)


class BalanceCalibration(BaseRule):
    """R-INST-003: 分析天平在有效期内"""
    code = "R-INST-003"
    category = "仪器溯源"
    name = "分析天平溯源"
    hj_ref = "HJ 828-2017 §7.3（分析天平：感量为0.0001 g）"

    def check(self, ctx: BatchContext) -> RuleResult:
        return _check_instrument(
            ctx, "天平", self.code, self.name, self.hj_ref)
