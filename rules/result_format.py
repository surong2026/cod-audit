r"""结果表示审核 — R-FMT-001 ~ R-FMT-002

HJ 828-2017 §10.2:
  COD < 100 mg/L → 保留至整数位
  COD ≥ 100 mg/L → 保留三位有效数字
"""

import math
from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
from utils.rounding import round_cod_to_float, to_3_sig_figs
import config


class RoundingRule(BaseRule):
    """R-FMT-001: 有效数字修约规则"""
    code = "R-FMT-001"
    category = "结果表示"
    name = "有效数字修约"
    hj_ref = "HJ 828-2017 §10.2 — <100保留整位, ≥100保留三位有效数字"

    def check(self, ctx: BatchContext) -> RuleResult:
        violations = []

        for s in ctx.record.actual_samples:
            val = s.reported_cod
            if val is None or s.is_below_dl:
                continue

            if val < config.COD_INTEGER_THRESHOLD:
                # 应从记录原始文本提取来验证是否真的是整数
                raw = s.reported_cod_raw.strip() if s.reported_cod_raw else ""
                try:
                    if raw:
                        parsed = float(raw)
                        if parsed != round(parsed):
                            violations.append(
                                f"{s.sample_id}: {raw} (应修约为{round(parsed)})"
                            )
                except ValueError:
                    pass

            elif val >= config.COD_INTEGER_THRESHOLD:
                # ≥100 应保留三位有效数字
                expected_rounded = to_3_sig_figs(val)
                raw = s.reported_cod_raw.strip() if s.reported_cod_raw else ""
                try:
                    if raw:
                        parsed = float(raw)
                        if parsed != expected_rounded:
                            violations.append(
                                f"{s.sample_id}: {raw} (三位有效数字应为{expected_rounded})"
                            )
                except ValueError:
                    pass

        if not violations:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "所有结果修约正确",
                "<100→整数, ≥100→三位有效数字", self.hj_ref,
                "有效数字修约符合HJ 828-2017要求")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(violations),
            "<100→整数, ≥100→三位有效数字", self.hj_ref,
            f"{len(violations)}个样品修约不符合要求",
            "请按HJ 828-2017 §10.2修正结果的有效数字")


class BelowDLFormat(BaseRule):
    """R-FMT-002: 低于检出限的表示应为 "<4" 或 "4L" """
    code = "R-FMT-002"
    category = "结果表示"
    name = "低于检出限表示"
    hj_ref = "HJ 828-2017 §1 — 检出限4mg/L"

    def check(self, ctx: BatchContext) -> RuleResult:
        issues = []

        for s in ctx.record.samples:
            if s.is_below_dl:
                raw = s.reported_cod_raw.strip().upper() if s.reported_cod_raw else ""
                ok_formats = ("<4", "4L", "＜4", "4L", "<4.0")
                if raw not in ok_formats and not raw.startswith("<") and not raw.endswith("L"):
                    issues.append(f"{s.sample_id}: 当前表示='{raw}', 建议'<4'或'4L'")

        if not issues:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "低于检出限的结果表示正确",
                "\"<4\" 或 \"4L\"", self.hj_ref,
                "低于检出限的结果使用了规范表示")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.WARNING,
            "; ".join(issues),
            "\"<4\" 或 \"4L\"", self.hj_ref,
            "部分低于检出限结果的表示不规范",
            "建议统一使用\"<4\"或\"4L\"表示低于检出限")
