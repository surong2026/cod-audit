"""审核规则基类"""

from dataclasses import dataclass
from models.audit_result import AuditItem, AuditStatus
from engine.batch_context import BatchContext


@dataclass
class RuleResult:
    """单条规则的审核结果"""
    code: str
    category: str
    name: str
    status: AuditStatus
    actual_value: str = ""
    limit_value: str = ""
    hj_ref: str = ""
    detail: str = ""
    suggestion: str = ""

    def to_audit_item(self) -> AuditItem:
        return AuditItem(
            code=self.code,
            category=self.category,
            name=self.name,
            status=self.status,
            actual_value=self.actual_value,
            limit_value=self.limit_value,
            hj_ref=self.hj_ref,
            detail=self.detail,
            suggestion=self.suggestion,
        )


class BaseRule:
    """规则基类 — 所有审核规则继承此类"""

    code: str = ""
    category: str = ""
    name: str = ""
    hj_ref: str = ""

    def check(self, ctx: BatchContext) -> RuleResult:
        raise NotImplementedError

    def run(self, ctx: BatchContext) -> AuditItem:
        return self.check(ctx).to_audit_item()
