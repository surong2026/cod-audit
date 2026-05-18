r"""精密度审核 — 平行样 — R-PREC-001 ~ R-PREC-003

HJ 828-2017 §12.2:
  每批样品应做10%的平行样。若样品数少于10个，应至少做一个平行样。
  平行样的相对偏差不超过±10%。
"""

import math
from engine.batch_context import BatchContext
from models.audit_result import AuditStatus
from rules.base import BaseRule, RuleResult
from utils.cod_calc import calc_parallel_rpd
import config


class ParallelCount(BaseRule):
    """R-PREC-001: 平行样数量 ≥ max(1, 10%×样品数)"""
    code = "R-PREC-001"
    category = "精密度审核"
    name = "平行样数量"
    hj_ref = "HJ 828-2017 §12.2 — 每批样品应做10%的平行样"

    def check(self, ctx: BatchContext) -> RuleResult:
        n_samples = ctx.actual_sample_count
        n_parallel_pairs = ctx.parallel_pair_count

        required = max(1, math.ceil(n_samples * config.PARALLEL_RATIO)) if n_samples > 0 else 0

        if n_parallel_pairs < required:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.FAIL,
                f"平行样对数={n_parallel_pairs}, 样品数={n_samples}",
                f"≥ {required}对 (10%或至少1对)", self.hj_ref,
                f"平行样数量不足: 需要{required}对, 实际{n_parallel_pairs}对",
                "补充平行样测定")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            f"平行样对数={n_parallel_pairs}, 样品数={n_samples}",
            f"≥ {required}对", self.hj_ref,
            "平行样数量满足要求")


class ParallelRPD(BaseRule):
    """R-PREC-002: 平行样相对偏差 ≤ ±10%"""
    code = "R-PREC-002"
    category = "精密度审核"
    name = "平行样相对偏差"
    hj_ref = "HJ 828-2017 §12.2 — 平行样的相对偏差不超过±10%"

    def check(self, ctx: BatchContext) -> RuleResult:
        parallels = ctx.record.parallels
        if len(parallels) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "平行样数据不足",
                f"RPD ≤ {config.PARALLEL_RPD_MAX}%", self.hj_ref,
                "无平行样数据或只有单个平行样")

        # 配对: 按 parallel_pair_id 分组
        pairs = {}
        for p in parallels:
            pid = p.parallel_pair_id or p.sample_id
            pairs.setdefault(pid, []).append(p)

        # 也处理仅有一对(两个)平行样的情况
        if len(pairs) == 0 and len(parallels) >= 2:
            # 取前两个作为一对
            pairs["_default"] = parallels[:2]

        all_pass = True
        details = []

        for pid, pair in pairs.items():
            if len(pair) < 2:
                continue
            v1, v2 = pair[0].reported_cod, pair[1].reported_cod

            # R-PREC-003 豁免: 任一低于检出限 → 跳过
            if v1 is None or v2 is None:
                details.append(f"{pid}: 低于检出限, 豁免")
                continue
            if pair[0].is_below_dl or pair[1].is_below_dl:
                details.append(f"{pid}: 低于检出限, 豁免")
                continue

            rpd = calc_parallel_rpd(v1, v2)
            if rpd > config.PARALLEL_RPD_MAX:
                all_pass = False
                details.append(f"{pid}: RPD={rpd:.1f}% > {config.PARALLEL_RPD_MAX}% (值={v1}, {v2})")
            else:
                details.append(f"{pid}: RPD={rpd:.1f}% (值={v1}, {v2})")

        if not details:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "无有效平行样数据",
                f"RPD ≤ {config.PARALLEL_RPD_MAX}%", self.hj_ref,
                "无法计算平行样相对偏差")

        if all_pass:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.PASS,
                "; ".join(details),
                f"RPD ≤ {config.PARALLEL_RPD_MAX}%", self.hj_ref,
                "所有平行样相对偏差在允许范围内")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.FAIL,
            "; ".join(details),
            f"RPD ≤ {config.PARALLEL_RPD_MAX}%", self.hj_ref,
            "部分平行样相对偏差超标",
            "检查操作一致性，必要时重做")


class ParallelBelowDLExempt(BaseRule):
    """R-PREC-003: 检出限以下豁免 — 当平行样任一<DL时不计算RPD"""
    code = "R-PREC-003"
    category = "精密度审核"
    name = "检出限以下豁免"
    hj_ref = "HJ 828-2017 §12.2 — 低于检出限时平行偏差不适用"

    def check(self, ctx: BatchContext) -> RuleResult:
        parallels = ctx.record.parallels
        if len(parallels) < 2:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO, "无平行样数据",
                "若任一结果<4mg/L则豁免RPD检查", self.hj_ref)

        exempted = []
        for p in parallels:
            if p.is_below_dl or (p.reported_cod is None and p.is_below_dl):
                exempted.append(p.sample_id)

        if exempted:
            return RuleResult(self.code, self.category, self.name,
                AuditStatus.INFO,
                f"豁免样品: {', '.join(exempted)}",
                "低于检出限(4mg/L)的平行样不计算相对偏差", self.hj_ref,
                f"以下样品低于检出限，豁免平行偏差审核: {', '.join(exempted)}")

        return RuleResult(self.code, self.category, self.name,
            AuditStatus.PASS,
            "所有平行样结果均≥检出限",
            "", self.hj_ref,
            "无需豁免，平行样均高于检出限")
