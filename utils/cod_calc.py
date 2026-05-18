"""HJ 828-2017 计算公式实现

COD (mg/L) = C × (V0 - V1) × 8000 / V2 × f

其中:
  C    — 硫酸亚铁铵标定浓度 mol/L
  V0   — 空白消耗体积 ml
  V1   — 样品消耗体积 ml
  8000 — 1/4 O2 摩尔质量换算值 mg/L
  V2   — 取样体积 ml
  f    — 稀释倍数
"""


def calc_fas_concentration(k2cr2o7_conc: float, k2cr2o7_vol: float,
                           fas_vol_avg: float) -> float:
    """计算硫酸亚铁铵标准溶液浓度

    c(fAS) = (c(K2Cr2O7) × V(K2Cr2O7)) / V(fAS)

    Args:
        k2cr2o7_conc: 重铬酸钾浓度 mol/L (0.0250 或 0.250)
        k2cr2o7_vol: 重铬酸钾用量 ml (标准为 5.00)
        fas_vol_avg: 硫酸亚铁铵平均消耗量 ml

    Returns:
        硫酸亚铁铵浓度 mol/L
    """
    if fas_vol_avg <= 0:
        return 0.0
    return (k2cr2o7_conc * k2cr2o7_vol) / fas_vol_avg


def calc_cod(fas_conc: float, blank_vol: float, sample_vol: float,
             aliquot_vol: float = 10.0, dilution_factor: float = 1.0,
             molar_factor: float = 8000.0) -> float:
    """计算 COD 浓度

    COD = C × (V0 - V1) × 8000 / V2 × f

    Args:
        fas_conc: 硫酸亚铁铵浓度 mol/L
        blank_vol: 空白消耗体积 ml (V0)
        sample_vol: 样品消耗体积 ml (V1)
        aliquot_vol: 取样体积 ml (V2)
        dilution_factor: 稀释倍数 (f)
        molar_factor: 摩尔质量换算系数

    Returns:
        COD 浓度 mg/L (未修约的原始值)
    """
    return fas_conc * (blank_vol - sample_vol) * molar_factor / aliquot_vol * dilution_factor


def calc_parallel_rpd(val1: float, val2: float) -> float:
    """计算平行样相对偏差 (%)

    RPD = |x1 - x2| / mean(x1, x2) × 100%
    """
    if val1 == 0 and val2 == 0:
        return 0.0
    mean_val = (val1 + val2) / 2.0
    if mean_val == 0:
        return 0.0
    return abs(val1 - val2) / mean_val * 100.0


def calc_hgso4_required(cl_estimate: float, sample_volume: float = 10.0,
                        hgso4_cl_ratio: float = 20.0,
                        hgso4_solution_conc: float = 100.0) -> float:
    """计算需要加入的硫酸汞溶液体积

    m(Cl) = cl_estimate(mg/L) × sample_volume(ml) / 1000  (mg)
    m(HgSO4)_required = m(Cl) × ratio  (mg)
    V(HgSO4)_required = m(HgSO4)_required / conc  (ml, 100g/L=100mg/ml)

    Args:
        cl_estimate: 氯离子估算量 mg/L
        sample_volume: 取样体积 ml
        hgso4_cl_ratio: 质量比 (默认 20)
        hgso4_solution_conc: 硫酸汞溶液浓度 mg/ml (100g/L=100mg/ml)

    Returns:
        所需硫酸汞溶液体积 ml
    """
    if cl_estimate is None or cl_estimate <= 0:
        return 0.0
    m_cl = cl_estimate * sample_volume / 1000.0  # mg
    m_hgso4 = m_cl * hgso4_cl_ratio
    return m_hgso4 / hgso4_solution_conc
