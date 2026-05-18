"""批次上下文 — 提取批次级统计信息供规则使用"""

from dataclasses import dataclass, field
from models.record import CODRecord, SampleRow
from engine.calculator import compute_fas_concentration, compute_blank_average, recompute_all_cod


@dataclass
class BatchContext:
    """批次审核上下文 — 缓存批次级计算结果"""
    record: CODRecord
    fas_conc: float = 0.0
    blank_avg: float = 0.0
    method_level: str = "unknown"
    low_conc_samples: list[SampleRow] = field(default_factory=list)
    high_conc_samples: list[SampleRow] = field(default_factory=list)

    @property
    def blank_count(self) -> int:
        return len(self.record.blanks)

    @property
    def qc_standard_count(self) -> int:
        return len(self.record.qc_standards)

    @property
    def parallel_pair_count(self) -> int:
        return len(self.record.parallels) // 2 if self.record.parallels else 0

    @property
    def actual_sample_count(self) -> int:
        return self.record.total_sample_count


def build_batch_context(record: CODRecord) -> BatchContext:
    """构建批次审核上下文

    1. 重新计算所有 COD
    2. 提取空白均值、标定浓度
    3. 区分高/低浓度样品
    """
    recompute_all_cod(record)
    fas_conc = compute_fas_concentration(record)
    blank_avg = compute_blank_average(record)

    low_samples = []
    high_samples = []
    for s in record.samples:
        if s.is_blank:
            continue
        if abs(s.k2cr2o7_conc - 0.0250) < 0.001:
            s.method_level = "low"
            low_samples.append(s)
        elif abs(s.k2cr2o7_conc - 0.250) < 0.001:
            s.method_level = "high"
            high_samples.append(s)
        else:
            s.method_level = "unknown"

    return BatchContext(
        record=record,
        fas_conc=fas_conc,
        blank_avg=blank_avg,
        method_level=record.overall_method_level,
        low_conc_samples=low_samples,
        high_conc_samples=high_samples,
    )
