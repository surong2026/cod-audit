r"""空白试验审核 — R-BLK-001 ~ R-BLK-003

HJ 828-2017 §12.1: 每批样品应至少做两个空白试验
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
import config


class BlankCount(BaseRule):
    """R-BLK-001: 每批至少2个空白"""
    code = "R-BLK-001"
    category = "空白试验"
    name = "空白数量"
    hj_ref = "HJ 828-2017 §12.1 — 每批样品应至少做两个空白试验"

    def check(self, ctx: BatchContext) -> RuleResult:
        n = ctx.blank_count

        if n < config.MIN_BLANK_COUNT:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, f"空白数量={n}",
                f"≥ {config.MIN_BLANK_COUNT}", self.hj_ref,
                f"仅{n}个空白试验，不满足最低要求",
                "每批至少做两个空白试验")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"空白数量={n}", f"≥ {config.MIN_BLANK_COUNT}", self.hj_ref,
            f"已做{n}个空白试验，满足要求")


class BlankConsistency(BaseRule):
    """R-BLK-002: 两个空白消耗体积的一致性"""
    code = "R-BLK-002"
    category = "空白试验"
    name = "空白一致性"
    hj_ref = "HJ 828-2017 §12.1 — 空白操作一致性"

    def check(self, ctx: BatchContext) -> RuleResult:
        blanks = ctx.record.blanks
        if len(blanks) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "空白数量不足",
                f"|V0_1 - V0_2| ≤ {config.BLANK_CONSISTENCY_MAX_DIFF} ml", self.hj_ref,
                "不足两个空白，跳过一致性检查")

        vols = [b.net_volume for b in blanks[:2] if b.net_volume > 0]
        if len(vols) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.WARNING, "空白体积数据不完整",
                f"|V0_1 - V0_2| ≤ {config.BLANK_CONSISTENCY_MAX_DIFF} ml", self.hj_ref,
                "无法提取两个空白体积进行一致性检查")

        diff = abs(vols[0] - vols[1])
        limit = config.BLANK_CONSISTENCY_MAX_DIFF

        if diff <= limit:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"|{vols[0]:.2f} - {vols[1]:.2f}| = {diff:.2f} ml",
                f"≤ {limit} ml", self.hj_ref,
                "空白试验体积一致")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"|{vols[0]:.2f} - {vols[1]:.2f}| = {diff:.2f} ml",
            f"≤ {limit} ml", self.hj_ref,
            f"两个空白体积相差{diff:.2f} ml，超过{limit} ml允差",
            "可能存在操作问题，建议重做空白试验")


class BlankReasonableness(BaseRule):
    """R-BLK-003: 空白消耗量在合理范围"""
    code = "R-BLK-003"
    category = "空白试验"
    name = "空白值合理性"
    hj_ref = "HJ 828-2017 §9.1.2（空白操作参照样品测定）"

    def check(self, ctx: BatchContext) -> RuleResult:
        blanks = ctx.record.blanks
        if not blanks:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "无空白数据", "", self.hj_ref)

        for b in blanks:
            v = b.net_volume
            if v <= 0:
                continue
            if v < config.BLANK_VOLUME_MIN or v > config.BLANK_VOLUME_MAX:
                return RuleResult(self.code, self.category, self.name,
                    AuditStatus.WARNING,
                    f"空白体积={v:.2f} ml",
                    f"{config.BLANK_VOLUME_MIN}-{config.BLANK_VOLUME_MAX} ml", self.hj_ref,
                    f"空白消耗量{v:.2f} ml超出合理范围",
                    "请检查试剂（重铬酸钾或硫酸亚铁铵浓度）、操作过程是否有误")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"空白体积均在{config.BLANK_VOLUME_MIN}-{config.BLANK_VOLUME_MAX} ml内",
            f"{config.BLANK_VOLUME_MIN}-{config.BLANK_VOLUME_MAX} ml", self.hj_ref,
            "空白消耗体积在合理范围")
