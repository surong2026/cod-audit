r"""硫酸亚铁铵标定审核 — R-CAL-001 ~ R-CAL-004

HJ 828-2017 §6.12.1:
  每日临用前，必须用重铬酸钾标准溶液准确标定硫酸亚铁铵溶液浓度
  标定时应做平行双样
  c = (0.0250 / 0.250) × 5.00 / V
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
import config


class CalDateMatch(BaseRule):
    """R-CAL-001: 标定日期 == 分析日期"""
    code = "R-CAL-001"
    category = "标定审核"
    name = "标定日期与浓度自洽"
    hj_ref = "HJ 828-2017 §6.12.1 — 每日临用前必须标定"

    def check(self, ctx: BatchContext) -> RuleResult:
        rec = ctx.record
        std = rec.fas_std

        if std.date is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, "标定日期缺失",
                f"必须记录标定日期", self.hj_ref,
                "记录中缺少硫酸亚铁铵标定日期",
                "请在分析前标定并记录标定日期")

        if rec.analysis_date is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, "分析日期缺失",
                f"标定日期={std.date.isoformat()}", self.hj_ref,
                "缺少分析日期，无法比较标定日期",
                "请填写分析日期")

        if std.date == rec.analysis_date:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"标定日期={std.date.isoformat()}, 分析日期={rec.analysis_date.isoformat()}",
                "标定日期==分析日期", self.hj_ref,
                "当日标定，符合要求")

        days_diff = abs((std.date - rec.analysis_date).days)
        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"标定日期={std.date.isoformat()}, 分析日期={rec.analysis_date.isoformat()}, 相差{days_diff}天",
            "标定日期==分析日期", self.hj_ref,
            f"标定日期与分析日期不一致，相差{days_diff}天",
            "HJ 828-2017要求每日临用前标定硫酸亚铁铵。若沿用前日标定需有SOP说明，否则应重新标定。")


class CalParallelCount(BaseRule):
    """R-CAL-002: 标定必须做平行双样"""
    code = "R-CAL-002"
    category = "标定审核"
    name = "标定平行双样"
    hj_ref = "HJ 828-2017 §6.12.1 — 标定时应做平行双样"

    def check(self, ctx: BatchContext) -> RuleResult:
        vols = ctx.record.fas_std.volumes
        n = len(vols)

        if n < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, f"标定次数={n}",
                "≥2次（平行双样）", self.hj_ref,
                f"仅有{n}次标定数据，不足平行双样要求",
                "请补充平行标定数据")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"标定次数={n}, 体积={vols}",
            "≥2次（平行双样）", self.hj_ref,
            "已做平行双样标定")


class CalParallelDeviation(BaseRule):
    """R-CAL-003: 平行标定偏差 ≤ 0.05 mL"""
    code = "R-CAL-003"
    category = "标定审核"
    name = "标定平行样偏差"
    hj_ref = "HJ 828-2017 §6.12.1 — 标定精密度"

    def check(self, ctx: BatchContext) -> RuleResult:
        vols = ctx.record.fas_std.volumes
        if len(vols) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "标定数据不足",
                f"|V1-V2| ≤ {config.STANDARDIZATION_PARALLEL_MAX_DIFF} ml", self.hj_ref,
                "平行标定数据不足，跳过偏差检查")

        diff = abs(vols[0] - vols[1])
        limit = config.STANDARDIZATION_PARALLEL_MAX_DIFF

        if diff <= limit:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"|{vols[0]} - {vols[1]}| = {diff:.2f} ml",
                f"≤ {limit} ml", self.hj_ref,
                "平行标定偏差在允差范围内")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"|{vols[0]} - {vols[1]}| = {diff:.2f} ml",
            f"≤ {limit} ml", self.hj_ref,
            f"平行标定偏差{diff:.2f} ml超过允差{limit} ml",
            "重新标定硫酸亚铁铵，确保两份滴定偏差在允许范围内")


class CalConcVerify(BaseRule):
    """R-CAL-004: 系统重算标定浓度 vs 填报值"""
    code = "R-CAL-004"
    category = "标定审核"
    name = "标定浓度计算验证"
    hj_ref = "HJ 828-2017 §6.12.1 — 浓度计算公式"

    def check(self, ctx: BatchContext) -> RuleResult:
        std = ctx.record.fas_std
        calc = std.calculated_conc
        reported = std.reported_conc

        if calc is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, "无法计算标定浓度",
                "需要完整的标定数据", self.hj_ref,
                "缺少标定体积或重铬酸钾浓度数据")

        if reported is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL, "记录中未填写标定浓度",
                f"系统计算值={calc:.6f} mol/L", self.hj_ref,
                "记录表缺少硫酸亚铁铵标定浓度",
                "请在记录表中填写标定浓度")

        # 完全一致: 相对差异 ≤ 0.001 (0.1%)
        rel_diff = abs(calc - reported) / reported if reported != 0 else abs(calc - reported)
        if rel_diff <= 0.001:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"系统计算={calc:.6f}, 填报={reported:.6f} mol/L",
                "两者一致（相对差≤0.1%）", self.hj_ref,
                "标定浓度计算与填报值一致")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"系统计算={calc:.6f}, 填报={reported:.6f} mol/L",
            "两者一致（相对差≤0.1%）", self.hj_ref,
            f"标定浓度不一致: 系统算{calc:.6f} vs 填报{reported:.6f}",
            "请检查标定体积记录是否准确，或重新标定")
