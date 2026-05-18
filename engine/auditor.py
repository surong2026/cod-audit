"""审核编排器 — 协调所有规则, 按批次执行完整审核"""

from models.record import CODRecord
from models.audit_result import AuditReport, AuditItem
from engine.batch_context import build_batch_context, BatchContext

from rules.calibration import (
    CalDateMatch, CalParallelCount, CalParallelDeviation, CalConcVerify,
)
from rules.blank import BlankCount, BlankConsistency, BlankReasonableness
from rules.precision import ParallelCount, ParallelRPD, ParallelBelowDLExempt
from rules.accuracy import QCStandardExists, QCStandardInRange
from rules.calculation import CODRecalcVerify, BlankAvgUsage
from rules.instrument import (
    BuretteCalibration, DigestionDeviceCalibration, BalanceCalibration,
)
from rules.method_params import (
    MethodLevelDetect, ReagentConcMatch, K2Cr2O7Volume,
    H2SO4Ag2SO4Volume, SampleStorageTime,
)
from rules.chloride import ChlorideLimit, HgSO4Sufficient
from rules.detection_range import DetectionLimit, QuantitationLimit, UpperLimit
from rules.dilution import DilutionInRange, DilutionVolumeConsistency
from rules.result_format import RoundingRule, BelowDLFormat
from rules.base import BaseRule


ALL_RULES: list[BaseRule] = [
    # 标定
    CalDateMatch(), CalParallelCount(), CalParallelDeviation(), CalConcVerify(),
    # 空白
    BlankCount(), BlankConsistency(), BlankReasonableness(),
    # 精密度
    ParallelCount(), ParallelRPD(), ParallelBelowDLExempt(),
    # 准确度
    QCStandardExists(), QCStandardInRange(),
    # 计算
    CODRecalcVerify(), BlankAvgUsage(),
    # 仪器溯源
    BuretteCalibration(), DigestionDeviceCalibration(), BalanceCalibration(),
    # 方法参数
    MethodLevelDetect(), ReagentConcMatch(), K2Cr2O7Volume(),
    H2SO4Ag2SO4Volume(), SampleStorageTime(),
    # 氯离子
    ChlorideLimit(), HgSO4Sufficient(),
    # 检出限与范围
    DetectionLimit(), QuantitationLimit(), UpperLimit(),
    # 稀释
    DilutionInRange(), DilutionVolumeConsistency(),
    # 结果表示
    RoundingRule(), BelowDLFormat(),
]


class Auditor:
    """审核编排器"""

    def __init__(self, rules: list[BaseRule] | None = None):
        self.rules = rules or ALL_RULES

    def audit(self, record: CODRecord) -> AuditReport:
        """执行完整批次审核

        Args:
            record: COD 分析记录

        Returns:
            审核报告
        """
        ctx = build_batch_context(record)
        report = AuditReport(record_id=record.record_id)

        for rule in self.rules:
            try:
                item = rule.run(ctx)
                report.items.append(item)
            except Exception as e:
                report.items.append(AuditItem(
                    code=rule.code,
                    category=rule.category,
                    name=rule.name,
                    status="ERROR",
                    actual_value="",
                    limit_value="",
                    hj_ref=rule.hj_ref,
                    detail=f"规则执行异常: {e}",
                    suggestion="请检查输入数据完整性",
                ))

        return report

    def audit_category(self, record: CODRecord, category: str) -> list[AuditItem]:
        """按类别审核

        Args:
            record: COD 分析记录
            category: 类别名称 (如 "标定审核")

        Returns:
            该类别下的审核项列表
        """
        ctx = build_batch_context(record)
        items = []
        for rule in self.rules:
            if rule.category == category:
                try:
                    items.append(rule.run(ctx))
                except Exception as e:
                    items.append(AuditItem(
                        code=rule.code, category=rule.category, name=rule.name,
                        status="ERROR", detail=f"规则执行异常: {e}",
                        hj_ref=rule.hj_ref,
                    ))
        return items
