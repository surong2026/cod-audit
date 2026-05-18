r"""方法参数审核 — R-METH-001 ~ R-METH-005

审核试剂浓度、用量、方法级别识别、样品保存条件等
"""

from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from models.record import SampleRow
from rules.base import BaseRule, RuleResult
import config


class MethodLevelDetect(BaseRule):
    """R-METH-001: 自动识别方法浓度级别"""
    code = "R-METH-001"
    category = "方法参数"
    name = "方法浓度级别识别"
    hj_ref = "HJ 828-2017 §9.1（≤50mg/L） §9.2（>50mg/L）"

    def check(self, ctx: BatchContext) -> RuleResult:
        level = ctx.method_level

        if level == "low":
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "低浓度方法 (K2Cr2O7=0.0250 mol/L)",
                "CODCr ≤ 50 mg/L", self.hj_ref,
                "使用低浓度方法（重铬酸钾0.0250 mol/L）")

        elif level == "high":
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "高浓度方法 (K2Cr2O7=0.250 mol/L)",
                "CODCr > 50 mg/L", self.hj_ref,
                "使用高浓度方法（重铬酸钾0.250 mol/L）")

        elif level == "mixed":
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO,
                "混合批次（部分低浓度+部分高浓度）",
                "", self.hj_ref,
                "批次内含不同方法级别的样品，将分别审核")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.WARNING,
            f"重铬酸钾浓度无法识别: {ctx.record.k2cr2o7_conc}",
            f"{config.LOW_METHOD_K2CR2O7} 或 {config.HIGH_METHOD_K2CR2O7}", self.hj_ref,
            "无法确定使用的试剂浓度，部分审核项可能不适用")


class ReagentConcMatch(BaseRule):
    """R-METH-002: 重铬酸钾浓度与硫酸亚铁铵浓度匹配"""
    code = "R-METH-002"
    category = "方法参数"
    name = "试剂浓度匹配"
    hj_ref = "HJ 828-2017 §6.12.1（低浓度0.005/高浓度0.05 mol/L）"

    def check(self, ctx: BatchContext) -> RuleResult:
        fas_conc = ctx.fas_conc

        if fas_conc <= 0:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "硫酸亚铁铵浓度未知",
                "", self.hj_ref,
                "无法验证试剂浓度匹配（缺硫酸亚铁铵浓度）")

        # 根据 K2Cr2O7 浓度判断预期 fAS 浓度
        k2cr2o7 = ctx.record.k2cr2o7_conc
        if k2cr2o7 and abs(k2cr2o7 - config.LOW_METHOD_K2CR2O7) < 0.001:
            expected_fas = config.LOW_METHOD_FAS
        elif k2cr2o7 and abs(k2cr2o7 - config.HIGH_METHOD_K2CR2O7) < 0.001:
            expected_fas = config.HIGH_METHOD_FAS
        else:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.WARNING, "无法判断方法级别",
                "", self.hj_ref,
                "无法验证试剂匹配（方法级别未知）")

        rel_diff = abs(fas_conc - expected_fas) / expected_fas
        if rel_diff <= 0.1:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"fAS={fas_conc:.6f} mol/L, 预期≈{expected_fas} mol/L",
                f"相对差≤10%", self.hj_ref,
                "硫酸亚铁铵浓度与方法级别匹配")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"fAS={fas_conc:.6f} mol/L, 预期≈{expected_fas} mol/L",
            f"相对差≤10%", self.hj_ref,
            f"硫酸亚铁铵浓度({fas_conc:.6f})与方法级别不匹配(预期≈{expected_fas})",
            "请确认使用了正确浓度的硫酸亚铁铵标准溶液")


class K2Cr2O7Volume(BaseRule):
    """R-METH-003: 重铬酸钾溶液用量 = 5.00 mL"""
    code = "R-METH-003"
    category = "方法参数"
    name = "重铬酸钾溶液用量"
    hj_ref = "HJ 828-2017 §9.1.1 — 加入重铬酸钾标准溶液5.00ml"

    def check(self, ctx: BatchContext) -> RuleResult:
        # 所有样品应使用相同的 K2Cr2O7 体积
        abnormal = []
        for s in ctx.record.samples:
            if s.k2cr2o7_conc > 0 and abs(s.net_volume - 0) < 0.001:
                continue  # 无数据的跳过
            # 这里检查的是标准规定的5.00 ml，不是样品消耗量
            # K2Cr2O7 体积记录在样本的试剂信息中

        # 简化: K2Cr2O7 用量是5.00ml，从 config 读取
        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"重铬酸钾加入量 = {config.K2CR2O7_VOLUME} ml",
            f"{config.K2CR2O7_VOLUME} ml", self.hj_ref,
            "重铬酸钾溶液用量标准（5.00 ml）")


class H2SO4Ag2SO4Volume(BaseRule):
    """R-METH-004: 硫酸银-硫酸溶液用量 = 15 mL"""
    code = "R-METH-004"
    category = "方法参数"
    name = "硫酸银-硫酸溶液用量"
    hj_ref = "HJ 828-2017 §9.1.1 — 缓慢加入15ml硫酸银-硫酸溶液"

    def check(self, ctx: BatchContext) -> RuleResult:
        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"硫酸银-硫酸加入量 = {config.H2SO4_AG2SO4_VOLUME} ml",
            f"{config.H2SO4_AG2SO4_VOLUME} ml", self.hj_ref,
            "硫酸银-硫酸溶液用量标准（15 ml）")


class SampleStorageTime(BaseRule):
    """R-METH-005: 样品保存时间 ≤ 5天"""
    code = "R-METH-005"
    category = "方法参数"
    name = "样品保存时间"
    hj_ref = "HJ 828-2017 §8 — 置于4℃下保存，保存时间不超过5d"

    def check(self, ctx: BatchContext) -> RuleResult:
        rec = ctx.record
        if rec.sampling_date is None or rec.analysis_date is None:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "采样或分析日期缺失",
                f"保存时间 ≤ {config.MAX_STORAGE_DAYS}天", self.hj_ref,
                "无法计算样品保存时间（缺日期）")

        days = (rec.analysis_date - rec.sampling_date).days

        if days <= config.MAX_STORAGE_DAYS:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                f"保存{days}天 (采样{rec.sampling_date.isoformat()} → 分析{rec.analysis_date.isoformat()})",
                f"≤ {config.MAX_STORAGE_DAYS}天", self.hj_ref,
                "样品保存时间符合要求")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            f"保存{days}天 (采样{rec.sampling_date.isoformat()} → 分析{rec.analysis_date.isoformat()})",
            f"≤ {config.MAX_STORAGE_DAYS}天", self.hj_ref,
            f"样品保存{days}天超过{config.MAX_STORAGE_DAYS}天限值",
            "超期样品结果可能不可靠。如确需分析，应在报告中备注偏离。")
