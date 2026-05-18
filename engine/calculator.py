"""COD 独立计算引擎 — 对批次内所有样品重算 COD 浓度"""

from models.record import CODRecord, SampleRow
from utils.cod_calc import calc_cod, calc_fas_concentration
from utils.rounding import round_cod_to_float


def compute_fas_concentration(record: CODRecord) -> float:
    """从标定数据计算硫酸亚铁铵浓度

    Returns:
        标定浓度 mol/L, 无法计算返回 0.0
    """
    std = record.fas_std
    conc = std.calculated_conc
    return conc if conc is not None else 0.0


def compute_blank_average(record: CODRecord) -> float:
    """计算空白消耗体积均值

    Returns:
        空白均值 ml, 无空白数据返回 0.0
    """
    avg = record.blank_avg_volume
    return avg if avg is not None else 0.0


def recompute_all_cod(record: CODRecord) -> None:
    """对批次内所有样品重新计算 COD 浓度

    遍历 record.samples, 使用标定浓度和空白均值独立计算 COD,
    将算得的值写回 sample.cod_calculated.
    空白样本身不计算（跳过）.
    标样也参与计算（验证其测定值）.
    """
    fas_conc = compute_fas_concentration(record)
    blank_avg = compute_blank_average(record)

    for sample in record.samples:
        if sample.is_blank:
            sample.cod_calculated = None
            continue

        if fas_conc <= 0 or blank_avg <= 0 or sample.net_volume <= 0:
            sample.cod_calculated = None
            continue

        sample.cod_calculated = calc_cod(
            fas_conc=fas_conc,
            blank_vol=blank_avg,
            sample_vol=sample.net_volume,
            aliquot_vol=sample.diluted_volume if sample.diluted_volume > 0 else 10.0,
            dilution_factor=sample.dilution_factor,
        )


def verify_reported_cod(record: CODRecord) -> list[SampleRow]:
    """交叉校验：重算值 vs 填报值

    Returns:
        校验不一致的样品列表
    """
    recompute_all_cod(record)
    mismatches = []

    for sample in record.samples:
        if sample.is_blank or sample.cod_calculated is None:
            continue

        reported = sample.reported_cod
        if reported is None:
            continue  # 低于检出限, 不比较

        calculated = round_cod_to_float(sample.cod_calculated)

        # 完全一致才通过（修约后比较）
        import math
        if math.isnan(calculated):
            continue  # 系统计算也低于检出限

        if reported != calculated:
            mismatches.append(sample)

    return mismatches
