"""审核结果模型"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class AuditStatus(Enum):
    PASS = "通过"
    INFO = "信息"
    WARNING = "警告"
    FAIL = "不通过"


@dataclass
class AuditItem:
    code: str                 # 规则编码, 如 "R-CAL-001"
    category: str             # 规则组, 如 "标定审核"
    name: str                 # 规则名称
    status: AuditStatus
    actual_value: str = ""    # 实测值描述
    limit_value: str = ""     # 限值/预期值描述
    hj_ref: str = ""          # HJ 828-2017 条款引用
    detail: str = ""          # 详细说明
    suggestion: str = ""      # 整改建议


@dataclass
class AuditReport:
    record_id: str = ""
    audit_time: str = field(default_factory=lambda: datetime.now().isoformat())
    items: list[AuditItem] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for i in self.items if i.status == AuditStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for i in self.items if i.status == AuditStatus.FAIL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.items if i.status == AuditStatus.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.items if i.status == AuditStatus.INFO)

    @property
    def overall_pass(self) -> bool:
        """有任何 FAIL 则整体不通过"""
        return self.fail_count == 0

    @property
    def overall_verdict(self) -> str:
        if self.fail_count > 0:
            return "不通过"
        if self.warning_count > 0:
            return "有条件通过"
        return "通过"

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "audit_time": self.audit_time,
            "overall_verdict": self.overall_verdict,
            "overall_pass": self.overall_pass,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "items": [{
                "code": i.code,
                "category": i.category,
                "name": i.name,
                "status": i.status.value,
                "actual_value": i.actual_value,
                "limit_value": i.limit_value,
                "hj_ref": i.hj_ref,
                "detail": i.detail,
                "suggestion": i.suggestion,
            } for i in self.items],
        }
