"""氯离子-硫酸汞换算工具函数"""


def estimate_cl_from_titration(drops: int, sample_volume: float = 10.0,
                               drop_volume: float = 0.04,
                               agno3_conc: float = 0.141) -> float:
    """从硝酸银滴定滴数估算氯离子浓度（附录A粗判法）

    每滴0.04ml AgNO3(0.141mol/L) 对应 Cl-量:
    n(Cl-) = 0.141 × 0.04 / 1000 = 5.64×10^-6 mol
    m(Cl-) = 5.64×10^-6 × 35.45 = 0.200 mg
    Cl-(mg/L) = 0.200 × 1000 / V_sample(ml)

    Args:
        drops: 滴数
        sample_volume: 取样体积 ml
        drop_volume: 每滴体积 ml (默认0.04)
        agno3_conc: 硝酸银浓度 mol/L

    Returns:
        氯离子估算浓度 mg/L
    """
    if drops <= 0 or sample_volume <= 0:
        return 0.0
    n_ag = agno3_conc * drop_volume * drops / 1000.0  # mol
    m_cl = n_ag * 35.45 * 1000  # mg
    return m_cl / sample_volume * 1000  # mg/L


def check_hgso4_sufficient(cl_estimate: float, sample_volume: float,
                           hgso4_added: float,
                           hgso4_cl_ratio: float = 20.0,
                           hgso4_solution_conc: float = 100.0) -> tuple[bool, float, float]:
    """检查硫酸汞加入量是否足够

    Args:
        cl_estimate: 氯离子估算量 mg/L
        sample_volume: 取样体积 ml
        hgso4_added: 实际硫酸汞溶液加入量 ml
        hgso4_cl_ratio: 质量比 (默认20)
        hgso4_solution_conc: 硫酸汞溶液浓度 mg/ml (100g/L)

    Returns:
        (是否足够, 所需体积ml, 实际体积ml)
    """
    from utils.cod_calc import calc_hgso4_required
    required = calc_hgso4_required(cl_estimate, sample_volume,
                                   hgso4_cl_ratio, hgso4_solution_conc)
    return hgso4_added >= required, required, hgso4_added


def check_cl_diluted_ok(cl_estimate: float, dilution_factor: float,
                        max_cl: float = 1000.0) -> tuple[bool, float]:
    """检查稀释后氯离子是否超标

    HJ 828-2017 §1: 不适用于含氯化物浓度>1000mg/L(稀释后)的水样

    Args:
        cl_estimate: 氯离子估算量 mg/L
        dilution_factor: 稀释倍数
        max_cl: 稀释后最大允许浓度

    Returns:
        (是否适用, 稀释后浓度)
    """
    if dilution_factor <= 0:
        dilution_factor = 1.0
    diluted_cl = cl_estimate / dilution_factor
    return diluted_cl <= max_cl, diluted_cl
