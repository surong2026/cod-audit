"""Excel 布局常量 — 基于真实样本文件 (化学需氧量(容量法)测定原始记录表.xls)

该文件结构稳定，直接用行列索引提取，不依赖通用表格检测。
所有行列号均为 0-indexed。
"""

# ============================================================
# Sheet 识别关键词
# ============================================================
SHEET1_KEYWORDS = ['原始记录', '测定原始记录', '化学需氧量']
SHEET2_KEYWORDS = ['质控', 'QC', '质量控制']

# ============================================================
# Sheet 1 — 化学需氧量(容量法)测定原始记录表
# ============================================================

# 元数据区 (rows 0-6)
METADATA_KEYWORDS = {
    '记录编号': 'record_id',
    '任务编号': 'task_id',
    '监测机构名称': 'org_name',
    '监测任务名称': 'task_name',
    '采样日期': 'sampling_date',
    '分析日期': 'analysis_date',
    '分析方法名称及依据': 'method_ref',
    '环境温度': 'temperature',
    '环境湿度': 'humidity',
    '重铬酸钾溶液配制日期': 'k2cr2o7_prep_date',
    '重铬酸钾溶液浓度': 'k2cr2o7_conc',
}

# 仪器区 (rows 7-8)
INSTRUMENT_ROW_START = 7
INSTRUMENT_ROW_END = 8     # inclusive

# 样品表头行
SAMPLE_HEADER_ROW = 9       # row 9-10 是两行表头
SAMPLE_HEADER_ROW2 = 10

# 样品列映射 (column index -> field name)
SAMPLE_COL_MAP = {
    0: 'seq',
    1: 'sample_id',
    2: 'volume',
    3: 'dilution_factor',
    4: 'diluted_volume',
    5: 'k2cr2o7_conc',
    6: 'end_reading',
    7: 'start_reading',
    8: 'net_volume',
    9: 'reported_cod_raw',
    10: 'salinity',
    11: 'cl_estimate',
}

# FAS 标定区 (rows 19-23)
FAS_SECTION_START = 19      # "硫酸亚铁铵溶液的标定" 标题行
FAS_DATE_ROW = 21           # 标定日期 + K2Cr2O7 用量 + 浓度
FAS_VOL_ROW1 = 21           # 第一组平行体积
FAS_VOL_ROW2 = 22           # 第二组平行体积
FAS_VOL_ROW3 = 23           # 可能为 "/" 的占位行

# 页脚 (rows 24-27)
FOOTER_KEYWORDS = {
    '分析人': 'analyst',
    '复核人': 'reviewer',
    '审核人': 'approver',
}

# ============================================================
# Sheet 2 — 质控结果表
# ============================================================

# 全程序空白
QC_FIELD_BLANK_ROW = 4      # 数据行 (row 3 是表头)
QC_FIELD_BLANK_COL_ID = 0
QC_FIELD_BLANK_COL_GUARANTEE = 2
QC_FIELD_BLANK_COL_MEASURED = 4
QC_FIELD_BLANK_COL_QUALIFIED = 6

# 实验室空白列表
QC_LAB_BLANK_START = 6       # 第一行实验室空白数据
QC_LAB_BLANK_END = 7         # 最后一行 (通常 2 行)

# 平行样
QC_PARALLEL_ROW = 9          # 平行样数据行 (row 8 是表头)
QC_PARALLEL_COL_ID = 0
QC_PARALLEL_COL_VAL1 = 2
QC_PARALLEL_COL_VAL2 = 3
QC_PARALLEL_COL_MEAN = 4
QC_PARALLEL_COL_RPD = 5
QC_PARALLEL_COL_QUALIFIED = 6

# 有证标样
QC_STANDARD_ROW = 11         # 标样数据行 (row 10 是表头)
QC_STANDARD_COL_ID = 0
QC_STANDARD_COL_GUARANTEE = 2
QC_STANDARD_COL_MEASURED = 4
QC_STANDARD_COL_QUALIFIED = 6

# 加标回收
QC_SPIKE_ROW = 12            # 加标数据行 (通常为空)
