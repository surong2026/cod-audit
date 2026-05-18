"""COD 审核数据模型"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Instrument:
    name: str = ""             # 仪器名称, 如 "酸式滴定管(50ml)"
    model: str = ""            # 型号, 如 "CODcr回流消解仪(1200K型)"
    serial_no: str = ""        # 编号, 如 "YL-D50-001"
    calibration_expiry: Optional[date] = None  # 溯源有效期
    calibration_method: str = ""  # 溯源方式, 如 "检定"


@dataclass
class SampleRow:
    seq: int = 0
    sample_id: str = ""                  # 样品编号
    volume: float = 10.00                # 取样体积 ml
    dilution_factor: float = 1.0         # 稀释倍数
    diluted_volume: float = 10.00        # 稀释后取样体积 ml
    k2cr2o7_conc: float = 0.0250         # 重铬酸钾浓度 mol/L
    end_reading: float = 0.0             # 终读 ml
    start_reading: float = 0.0           # 始读 ml
    net_volume: float = 0.0              # 净用量 ml
    reported_cod_raw: str = ""           # 填报值原始文本 ("15", "<4", "4L")
    reported_cod: Optional[float] = None # 解析后的数值, <4时设为None
    is_below_dl: bool = False            # 是否低于检出限
    salinity: Optional[float] = None     # 盐度
    cl_estimate: Optional[float] = None  # 氯离子估算量 mg/L
    hgso4_added: Optional[float] = None  # 硫酸汞溶液加入量 ml

    # 审核引擎写入字段
    method_level: str = ""               # "low" | "high" | "unknown"
    cod_calculated: Optional[float] = None  # 系统重算值
    is_blank: bool = False               # 是否为空白样
    is_qc_standard: bool = False         # 是否为有证标样/质控样
    is_parallel: bool = False            # 是否为平行样
    parallel_pair_id: str = ""           # 平行样配对标识

    @property
    def cod_display(self) -> str:
        if self.is_below_dl:
            return "<4"
        if self.reported_cod is not None:
            return str(self.reported_cod)
        return self.reported_cod_raw


@dataclass
class FASStandardization:
    """硫酸亚铁铵标定数据"""
    date: Optional[date] = None
    k2cr2o7_volume: float = 5.00         # 标定时重铬酸钾用量 ml
    k2cr2o7_conc: float = 0.0250         # 标定时重铬酸钾浓度 mol/L
    volumes: list[float] = field(default_factory=list)  # 平行滴定体积
    reported_conc: Optional[float] = None  # 记录填报的标定浓度

    @property
    def average_volume(self) -> Optional[float]:
        if not self.volumes:
            return None
        return sum(self.volumes) / len(self.volumes)

    @property
    def calculated_conc(self) -> Optional[float]:
        """系统独立计算标定浓度"""
        avg = self.average_volume
        if avg is None or avg == 0:
            return None
        return (self.k2cr2o7_conc * self.k2cr2o7_volume) / avg


@dataclass
class QCData:
    """质控数据（对应质控结果表 Sheet）"""
    # 全程序空白
    field_blank_sample_id: str = ""
    field_blank_guarantee: str = ""       # 保证值文本, 如 "<4(mg/L)"
    field_blank_measured: str = ""        # 测定值文本
    field_blank_qualified: bool = True

    # 实验室空白 (列表)
    lab_blank_sample_ids: list[str] = field(default_factory=list)

    # 平行样
    parallel_sample_id: str = ""
    parallel_value1: Optional[float] = None
    parallel_value2: Optional[float] = None
    parallel_mean: Optional[float] = None
    parallel_rpd: Optional[float] = None  # %
    parallel_qualified: bool = True

    # 有证标样
    std_sample_id: str = ""
    std_guarantee_range: str = ""         # 如 "14.3 ± 1.1(mg/L)"
    std_measured: Optional[float] = None
    std_qualified: bool = True

    # 加标回收
    spike_sample_id: str = ""
    spike_sample_amount: Optional[float] = None  # μg
    spike_added: Optional[float] = None          # μg
    spike_measured: Optional[float] = None       # μg
    spike_recovery: Optional[float] = None       # %
    spike_qualified: bool = True


@dataclass
class CODRecord:
    """COD 分析原始记录 — 一个批次"""
    # 元数据
    record_id: str = ""
    task_id: str = ""
    org_name: str = ""
    task_name: str = ""

    # 日期
    sampling_date: Optional[date] = None
    analysis_date: Optional[date] = None

    # 方法
    method_ref: str = "水质 化学需氧量的测定 重铬酸盐法(HJ 828-2017)"

    # 环境条件
    temperature: Optional[float] = None   # ℃
    humidity: Optional[float] = None      # %

    # 试剂配制
    k2cr2o7_prep_date: Optional[date] = None
    k2cr2o7_conc: Optional[float] = None  # mol/L, 批次统一浓度

    # 标定
    fas_std: FASStandardization = field(default_factory=FASStandardization)

    # 仪器
    instruments: list[Instrument] = field(default_factory=list)

    # 样品列表
    samples: list[SampleRow] = field(default_factory=list)

    # 质控数据
    qc: QCData = field(default_factory=QCData)

    # 其他
    remarks: str = ""
    analyst: str = ""
    reviewer: str = ""
    approver: str = ""

    # --- 派生属性 ---

    @property
    def blanks(self) -> list[SampleRow]:
        return [s for s in self.samples if s.is_blank]

    @property
    def actual_samples(self) -> list[SampleRow]:
        """非空白、非标样的实际样品"""
        return [s for s in self.samples if not s.is_blank and not s.is_qc_standard]

    @property
    def qc_standards(self) -> list[SampleRow]:
        return [s for s in self.samples if s.is_qc_standard]

    @property
    def parallels(self) -> list[SampleRow]:
        return [s for s in self.samples if s.is_parallel]

    @property
    def blank_avg_volume(self) -> Optional[float]:
        """空白消耗体积平均值"""
        vols = [s.net_volume for s in self.blanks if s.net_volume > 0]
        if not vols:
            return None
        return sum(vols) / len(vols)

    @property
    def total_sample_count(self) -> int:
        """实际样品数（不含空白、标样）"""
        return len(self.actual_samples)

    @property
    def overall_method_level(self) -> str:
        """批次的整体方法级别"""
        concs = [s.k2cr2o7_conc for s in self.samples if s.k2cr2o7_conc > 0]
        if not concs:
            return "unknown"
        unique = set(concs)
        if len(unique) == 1:
            c = unique.pop()
            if abs(c - 0.0250) < 0.001:
                return "low"
            elif abs(c - 0.250) < 0.001:
                return "high"
        return "mixed"

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 导出和数据库存储）"""
        import dataclasses
        return dataclasses.asdict(self)
