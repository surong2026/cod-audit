# 化学需氧量（COD）分析记录审核系统 — 技术规范

> 版本: 1.0 | 日期: 2026-05-18 | 状态: 待开发

---

## 1. 项目概述

### 1.1 目标

开发一个实验室分析测试原始记录审核 Web 应用，支持用户上传 COD（化学需氧量）原始记录文件（xls/xlsx/pdf/docx/图片/XML），系统自动提取数据，依据 **HJ 828-2017《水质 化学需氧量的测定 重铬酸盐法》** 逐项审核，生成结构化审核报告。

### 1.2 适用范围

- 第一阶段：仅审核 COD（HJ 828-2017，重铬酸盐法/容量法）
- 后续阶段：扩展至其他监测项目（氨氮、总磷、重金属等）

### 1.3 项目定位

- **独立新项目** `cod_audit/`，不与现有 nh3_audit 项目耦合
- 可复用 nh3_audit 的架构思想（models/engine/rules/ui 分层），但代码独立
- 部署模式：兼顾 Streamlit Cloud 公网部署 和 本地单机运行

---

## 2. 核心用户流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 上传记录  │ → │ 数据提取  │ → │ 在线修正  │ → │ 自动审核  │ → │ 审核报告  │
│ (多格式)  │    │ (混合策略) │    │ (人工确认) │    │ (规则引擎) │    │ (Web+JSON) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

1. 用户上传原始记录文件（拖拽或选择文件）
2. 系统解析文件提取结构化数据（混合策略：规则/OCR优先 → AI辅助纠错）
3. 用户在线校验提取结果，修正错误字段（如 OCR 将 "22.60" 识别为 "22.6O"）
4. 系统按 HJ 828-2017 规则引擎执行全面审核
5. 输出交互式审核报告（Web 页面）+ 可下载 JSON/PDF

### 2.1 用户角色（第一版：单一角色）

- 第一版不实现多角色权限系统，所有用户均可上传、审核、查看报告
- 后续版本再引入分析人/复核人/审核人三级权限

---

## 3. 文件解析与数据提取

### 3.1 支持的输入格式

| 格式 | 解析策略 | 工具链 |
|------|---------|--------|
| `.xls` / `.xlsx` | 结构化提取，按行列读取 | xlrd / openpyxl |
| `.pdf` (文本型) | 提取文本+表格定位 | pdfplumber / PyMuPDF |
| `.pdf` (扫描型/图片) | OCR → 文本 → 结构化 | PaddleOCR / Tesseract |
| `.docx` | 提取文本+表格 | python-docx |
| `.png/.jpg/.tiff` | OCR → 文本 → 结构化 | PaddleOCR / Tesseract |
| `.xml` | 解析 XML 树 → 字段映射 | xml.etree |

### 3.2 混合解析策略

```
文件 → [规则引擎: 尝试结构化提取]
           ↓ 提取失败或置信度低
       [AI 辅助: 大模型字段映射/纠错]
           ↓
       [结构化数据 → 用户确认界面]
```

- **第一层（规则/OCR）**: 优先使用确定性方法提取数据
- **第二层（AI 辅助）**: 仅在以下情况调用大模型 API：
  - 表格布局无法识别
  - 关键字段提取置信度低
  - OCR 输出有明显乱码需要纠错
- **成本控制**: 大部分标准格式记录完全走规则层，AI 仅作为 fallback

### 3.3 数据提取目标字段

必须从原始记录中提取以下字段：

#### 表头/元数据

| 字段 | 说明 | 来源示例 |
|------|------|---------|
| `record_id` | 记录编号 | GJW-04-2016-YS-SZ-011 |
| `task_id` | 任务编号 | 202604450900 |
| `org_name` | 监测机构名称 | 广西壮族自治区玉林生态环境监测中心 |
| `sampling_date` | 采样日期 | 2026-04-02 |
| `analysis_date` | 分析日期 | 2026-04-03 |
| `method_ref` | 分析方法依据 | HJ 828-2017 |
| `temperature` | 环境温度(℃) | 24.5 |
| `humidity` | 环境湿度(%) | 55 |

#### 试剂/标定

| 字段 | 说明 |
|------|------|
| `k2cr2o7_prep_date` | 重铬酸钾溶液配制日期 |
| `k2cr2o7_conc` | 重铬酸钾溶液浓度(mol/L) |
| `fAS_std_date` | 硫酸亚铁铵标定日期 |
| `fAS_std_k2cr2o7_vol` | 标定时重铬酸钾用量(ml) |
| `fAS_std_k2cr2o7_conc` | 标定时重铬酸钾浓度(mol/L) |
| `fAS_std_volumes` | 标定消耗体积列表 [V1, V2, ...] (平行双样) |
| `fAS_conc` | 硫酸亚铁铵标准溶液浓度(计算值) |

#### 仪器

| 字段 | 说明 |
|------|------|
| `instruments` | 仪器列表，每项含 {名称, 型号, 编号, 溯源有效期, 溯源方式} |

#### 样品数据（每行）

| 字段 | 说明 |
|------|------|
| `seq` | 序号 |
| `sample_id` | 样品编号 |
| `volume` | 取样体积(ml) |
| `dilution_factor` | 稀释倍数 |
| `diluted_volume` | 稀释后取样体积(ml) |
| `k2cr2o7_conc` | 重铬酸钾溶液浓度(mol/L) |
| `end_reading` | 滴定终读(ml) |
| `start_reading` | 滴定始读(ml) |
| `net_volume` | 净用量(ml) |
| `reported_cod` | 记录表填报的COD浓度(mg/L) 或 "<4" 等 |
| `salinity` | 盐度 |
| `cl_estimate` | 氯离子估算量(mg/L) |

#### 质控表（第二Sheet）

| 字段 | 说明 |
|------|------|
| `qc_blanks` | 全程序空白/实验室空白 {样品编号, 保证值, 测定值, 是否合格} |
| `qc_parallels` | 平行样 {样品编号, 浓度1, 浓度2, 均值, 相对偏差%, 是否合格} |
| `qc_standard` | 有证标样 {样品编号, 保证值范围, 测定值, 是否合格} |
| `qc_spike` | 加标回收样 {样品编号, 测定量, 加标量, 加标后测定量, 回收率%, 是否合格} |

### 3.4 在线修正流程

- 提取完成后，展示所有字段的提取值，标注低置信度字段（黄色底）
- 用户可点击任意字段修改
- 修改后点击"确认并审核"触发规则引擎
- **不直接拒绝任何记录** — 只要用户在修正后提交即可

---

## 4. 审核规则引擎

### 4.1 规则架构

```
engine/
  auditor.py          -- 审核编排器（协调所有规则）
  rules/
    base.py           -- 规则基类
    calibration.py    -- 标定审核
    blank.py          -- 空白试验审核
    precision.py      -- 精密度审核（平行样）
    accuracy.py       -- 准确度审核（有证标样/质控样）
    calculation.py    -- 计算审核（重算+校验）
    instrument.py     -- 仪器溯源审核
    method_params.py  -- 方法参数审核（试剂浓度、用量等）
    chloride.py       -- 氯离子干扰审核
    detection_range.py-- 检出限与测定范围审核
    result_format.py  -- 结果表示审核（有效数字/修约）
    dilution.py       -- 稀释合理性审核
```

### 4.2 审核粒度：按批次审核

一个批次 = 一次上传的完整记录（含多个样品+质控数据），审核结论针对整个批次的质量控制水平。每个审核项作用于批次内的相关数据（空白、标样、平行样等是批次级指标，单个样品的COD值也是该样品的结果）。

### 4.3 审核规则清单（共 31 项）

---

#### 规则组 1: 硫酸亚铁铵标定审核 (CAL)

**R-CAL-001: 标定日期与浓度自洽**
- 检查：标定日期 == 分析日期（每日临用前标定，HJ 828 6.12.1）
- 逻辑：`fAS_std_date == analysis_date`
- 判定：不一致 → **FAIL**（除非有合理说明，则 WARNING）
- HJ 引用：HJ 828-2017 §6.12.1 "每日临用前，必须用重铬酸钾标准溶液准确标定"

**R-CAL-002: 标定平行双样**
- 检查：标定必须做平行双样（至少2次滴定）
- 逻辑：`len(fAS_std_volumes) >= 2`
- 判定：不足2次 → **FAIL**
- HJ 引用：HJ 828-2017 §6.12.1 "标定时应做平行双样"

**R-CAL-003: 标定平行样偏差**
- 检查：平行标定的两次滴定体积偏差
- 逻辑：`|V1 - V2| ≤ 0.05 mL`（默认阈值，可配置）
- 判定：超阈值 → **FAIL**
- HJ 引用：HJ 828-2017 §6.12.1 对标定精度的隐含要求

**R-CAL-004: 标定浓度计算验证**
- 检查：系统独立计算标定浓度，与记录填报值比对
- 公式（低浓度）: `c = (0.0250 × 5.00) / V_avg`
- 公式（高浓度）: `c = (0.250 × 5.00) / V_avg`
- 逻辑：`abs(c_calculated - c_reported) / c_reported ≤ 0.001`（完全一致）
- 判定：不一致 → **FAIL**
- HJ 引用：HJ 828-2017 §6.12.1

---

#### 规则组 2: 空白试验审核 (BLK)

**R-BLK-001: 空白数量**
- 检查：每批至少2个空白试验
- 逻辑：`count(blank_samples) >= 2`
- 判定：不足 → **FAIL**
- HJ 引用：HJ 828-2017 §12.1 "每批样品应至少做两个空白试验"

**R-BLK-002: 空白一致性**
- 检查：两个空白消耗体积的一致性
- 逻辑：`|V_blank1 - V_blank2| ≤ 0.5 mL`
- 判定：超阈值 → **FAIL**
- HJ 引用：HJ 828-2017 §12.1（操作一致性要求）

**R-BLK-003: 空白值合理性**
- 检查：空白消耗体积应在合理范围内（低浓度方法约 22-25 mL）
- 逻辑：`15 ≤ V_blank ≤ 30`（范围可配置）
- 判定：超出 → **WARNING**（提示可能存在试剂问题）

---

#### 规则组 3: 精密度审核 — 平行样 (PREC)

**R-PREC-001: 平行样数量**
- 检查：每批至少做 10% 平行样（<10个样品时至少1个）
- 逻辑：`count(parallel_pairs) >= max(1, ceil(count(samples) * 0.1))`
- 判定：不足 → **FAIL**
- HJ 引用：HJ 828-2017 §12.2

**R-PREC-002: 平行样相对偏差**
- 检查：平行双样相对偏差 ≤ ±10%
- 公式：`RPD = |x1 - x2| / mean(x1, x2) × 100%`
- 逻辑：`RPD ≤ 10.0`
- 判定：超限 → **FAIL**
- HJ 引用：HJ 828-2017 §12.2

**R-PREC-003: 检出限以下豁免**
- 检查：当平行双样中任一结果 < 检出限（4 mg/L）时 → **自动豁免 R-PREC-002**
- 逻辑：短路，不计算也不报错，仅标记 INFO "低于检出限，不做平行偏差审核"
- 判定：**INFO**（不是 FAIL 也不是 PASS）

---

#### 规则组 4: 准确度审核 — 有证标样/质控样 (ACC)

**R-ACC-001: 质控样存在性**
- 检查：每批至少有一个有证标准样品或质控样品
- 逻辑：`count(qc_standards) >= 1`
- 判定：缺失 → **FAIL**
- HJ 引用：HJ 828-2017 §12.3

**R-ACC-002: 质控样结果在保证值范围内**
- 检查：质控样测定值在证书给定的保证值范围内
- 逻辑：`certified_lower ≤ measured_value ≤ certified_upper`
- 判定：超出 → **FAIL**
- HJ 引用：HJ 828-2017 §12.3

---

#### 规则组 5: 计算审核 (CALC)

**R-CALC-001: COD 浓度重算验证**
- 检查：系统独立计算每个样品的 COD 浓度，与填报值比对
- 公式：`COD = C_fAS × (V_blank_avg - V_sample) × 8000 / V2 × f`
- 其中：`V_blank_avg` = 所有空白消耗量的平均值
- 四舍五入规则：<100 mg/L → 整数; ≥100 mg/L → 三位有效数字
- 逻辑：`COD_calculated_rounded == COD_reported`
- 判定：不一致 → **FAIL**（用户要求"完全一致才通过"）
- HJ 引用：HJ 828-2017 §10.1, §10.2

**R-CALC-002: 空白均值使用验证**
- 检查：系统复核时使用的空白均值是否与填报值一致
- 逻辑：`abs(V0_calculated_avg - V0_recorded) ≤ 0.01`
- 判定：不一致 → **WARNING**

---

#### 规则组 6: 仪器溯源审核 (INST)

**R-INST-001: 酸式滴定管在有效期内**
- 检查：`analysis_date ≤ burette_calibration_expiry`
- 判定：过期 → **FAIL**
- HJ 引用：HJ 828-2017 §7.4（仪器要求）+ 计量法规

**R-INST-002: COD 消解/回流装置在有效期内**
- 检查：`analysis_date ≤ digestion_device_calibration_expiry`
- 判定：过期 → **FAIL**

**R-INST-003: 分析天平在有效期内**（如有）
- 检查：`analysis_date ≤ balance_calibration_expiry`
- 判定：过期 → **FAIL**

---

#### 规则组 7: 方法参数审核 (METH)

**R-METH-001: 方法浓度级别自动识别**
- 检查：根据重铬酸钾浓度自动识别低/高浓度方法
- 逻辑：`k2cr2o7_conc == 0.0250 → LOW (≤50 mg/L 方法)`；`k2cr2o7_conc == 0.250 → HIGH (>50 mg/L 方法)`
- 判定：无法识别 → **WARNING** "未知试剂浓度配置"
- 注：混合批次（含不同方法的样品）每样品独立检查

**R-METH-002: 试剂浓度与硫酸亚铁铵浓度匹配**
- 检查：低浓度方法 → fAS ≈ 0.005 mol/L；高浓度方法 → fAS ≈ 0.05 mol/L
- 逻辑：`abs(fAS_conc - expected) / expected ≤ 0.1`
- 判定：不匹配 → **FAIL**

**R-METH-003: 重铬酸钾溶液用量**
- 检查：`k2cr2o7_volume == 5.00 mL`
- 判定：不一致 → **WARNING**

**R-METH-004: 硫酸银-硫酸溶液用量**
- 检查：`h2so4_ag2so4_volume == 15 mL`
- 判定：不一致 → **WARNING**
- HJ 引用：HJ 828-2017 §9.1.1

**R-METH-005: 样品保存时间**
- 检查：`(analysis_date - sampling_date) ≤ 5 days`
- 检查：样品加 H2SO4 至 pH<2，4℃ 保存
- 判定：超期 → **FAIL**（如果不能确认保存条件则 WARNING）
- HJ 引用：HJ 828-2017 §8

---

#### 规则组 8: 氯离子干扰审核 (CL)

**R-CL-001: 氯离子浓度上限**
- 检查：稀释后 `Cl- ≤ 1000 mg/L`
- 逻辑：`cl_estimate / dilution_factor ≤ 1000`
- 判定：超限 → **FAIL** "本方法不适用于氯离子浓度>1000 mg/L（稀释后）的水样"
- HJ 引用：HJ 828-2017 §1

**R-CL-002: 硫酸汞加入量验证**
- 检查：`m(HgSO4) : m(Cl-) ≥ 20:1`
- 计算步骤：
  1. `m_Cl = cl_estimate × sample_volume / 1000` (mg→g)
  2. `m_HgSO4_required = m_Cl × 20` (g)
  3. `V_HgSO4_required = m_HgSO4_required / 0.1` (mL, 100g/L溶液)
  4. 验证：`V_HgSO4_added ≥ V_HgSO4_required`
- 同时检查：`V_HgSO4_added ≤ 2.0 mL`（最大加入量）
- 判定：不足 → **FAIL**；超过 2 mL → **WARNING**
- HJ 引用：HJ 828-2017 §5, §9.1.1

---

#### 规则组 9: 检出限与测定范围 (RANGE)

**R-RANGE-001: 检出限**
- 检查：方法检出限 = 4 mg/L (取样 10.0 mL 时)
- 逻辑：如果 COD < 4 → 应报告为 "<4" 或 "4L"
- 判定：填报值 ≥4 但实测可能 <4 → **WARNING** "建议报告为低于检出限"

**R-RANGE-002: 测定下限**
- 检查：测定下限 = 16 mg/L
- 逻辑：4 ≤ COD < 16 → 结果可报出但不确定性较大
- 判定：**INFO** "结果低于测定下限（16 mg/L），不确定度较大"

**R-RANGE-003: 测定上限**
- 检查：未经稀释的水样测定上限 = 700 mg/L
- 逻辑：`COD > 700 且 dilution_factor == 1` → 需要稀释后测定
- 判定：**FAIL** "超过测定上限，须稀释后测定"
- HJ 引用：HJ 828-2017 §1

---

#### 规则组 10: 稀释合理性审核 (DIL)

**R-DIL-001: 稀释后结果在有效范围**
- 检查：稀释后的 COD 值应落在 4-700 mg/L 范围内
- 逻辑：`4 ≤ COD_diluted ≤ 700`
- 判定：稀释后仍超上限 → **FAIL** "稀释倍数不足，需进一步稀释"
- 判定：稀释后低于检出限 → **WARNING** "稀释过度"

**R-DIL-002: 稀释倍数与取样体积一致性**
- 检查：`sample_volume × dilution_factor` 关系合理
- 判定：不一致 → **WARNING**

---

#### 规则组 11: 结果表示审核 (FMT)

**R-FMT-001: 有效数字/修约规则**
- 检查：COD < 100 mg/L → 保留至整数位
- 检查：COD ≥ 100 mg/L → 保留三位有效数字
- 判定：违反修约规则 → **FAIL**
- HJ 引用：HJ 828-2017 §10.2

**R-FMT-002: 低于检出限的表示**
- 检查：COD < 4 mg/L → 应表示为 "<4" 或 "4L"
- 判定：表示不当 → **WARNING**

---

### 4.4 审核结果分级

| 级别 | 含义 | 对总体结论的影响 |
|------|------|----------------|
| **PASS** | 该项审核通过 | 无 |
| **INFO** | 提示信息，无需处理 | 无 |
| **WARNING** | 存在风险/不确定性 | 降低总体置信度 |
| **FAIL** | 明确不符合标准要求 | 整体审核不通过 |

### 4.5 总体审核结论

- 存在任何 **FAIL** → 整体结论：**不通过**
- 无 FAIL 但有 WARNING → 整体结论：**有条件通过**（需复核人判断）
- 全部 PASS（可有 INFO） → 整体结论：**通过**

---

## 5. 技术架构

### 5.1 项目结构

```
cod_audit/
  app.py                    -- Streamlit 应用入口
  config.py                 -- HJ 828-2017 参数配置（阈值、常数、范围）
  requirements.txt          -- Python 依赖

  models/
    record.py               -- CODRecord 数据模型（含批次、样品、质控数据）
    audit_result.py         -- AuditResult, AuditItem, AuditReport 模型

  engine/
    auditor.py              -- 审核编排器（按批次执行全部规则）
    calculator.py           -- COD 浓度独立计算器
    batch_context.py        -- 批次上下文（提取空白均值、方法级别等）

  rules/
    base.py                 -- 审核规则基类
    calibration.py          -- R-CAL-001 ~ R-CAL-004
    blank.py                -- R-BLK-001 ~ R-BLK-003
    precision.py            -- R-PREC-001 ~ R-PREC-003
    accuracy.py             -- R-ACC-001 ~ R-ACC-002
    calculation.py          -- R-CALC-001 ~ R-CALC-002
    instrument.py           -- R-INST-001 ~ R-INST-003
    method_params.py        -- R-METH-001 ~ R-METH-005
    chloride.py             -- R-CL-001 ~ R-CL-002
    detection_range.py      -- R-RANGE-001 ~ R-RANGE-003
    dilution.py             -- R-DIL-001 ~ R-DIL-002
    result_format.py        -- R-FMT-001 ~ R-FMT-002
    __init__.py

  parsers/
    base.py                 -- 解析器基类接口
    excel_parser.py         -- xls/xlsx 解析器
    pdf_parser.py           -- PDF 解析器（文本型+扫描型）
    docx_parser.py          -- docx 解析器
    image_parser.py         -- 图片 OCR 解析器
    xml_parser.py           -- XML 解析器
    ai_mapper.py            -- AI 辅助字段映射（LLM fallback）
    __init__.py

  ui/
    components.py           -- 通用 UI 组件
    page_upload.py          -- 上传与解析页
    page_review.py          -- 数据在线修正确认页
    page_audit.py           -- 审核结果展示页
    page_report.py          -- 综合审核报告页
    page_history.py         -- 历史审核记录查询页
    __init__.py

  db/
    schema.sql              -- SQLite 数据库建表语句
    repository.py           -- 数据库读写封装

  utils/
    pdf_debug.py            -- PDF 调试工具（复用自 nh3_audit）
    cod_calc.py             -- COD 计算工具函数
    rounding.py             -- 有效数字修约函数
    chloride_calc.py        -- 氯离子/硫酸汞换算函数

  data/
    records/                -- 上传的原始记录文件存档
    reports/                -- 生成的审核报告 JSON/PDF

  tests/
    test_calculation.py     -- 独立计算验证测试
    test_rules.py           -- 规则逻辑测试
    test_parsers.py         -- 解析器测试（使用样本记录）
    fixtures/               -- 测试用例固定数据
```

### 5.2 技术栈

| 层级 | 技术选择 |
|------|---------|
| Web 框架 | Streamlit |
| 数据模型 | Python dataclasses |
| Excel 解析 | xlrd (xls) + openpyxl (xlsx) |
| PDF 解析 | pdfplumber / PyMuPDF (fitz) |
| OCR | PaddleOCR (离线) |
| AI 映射 | Claude API / OpenAI API (按需调用) |
| 数据库 | SQLite3 (本地) |
| 测试 | pytest |
| 部署 | Streamlit Cloud + 本地 `streamlit run` |

### 5.3 数据库设计（SQLite）

```sql
-- 审核记录表
CREATE TABLE audit_records (
    id TEXT PRIMARY KEY,              -- 记录编号
    task_id TEXT,
    org_name TEXT,
    analysis_date TEXT,
    method_ref TEXT,
    original_filename TEXT,
    original_file_path TEXT,           -- 原始文件存储路径
    extracted_data TEXT,               -- JSON: 提取的结构化数据
    audit_report TEXT,                 -- JSON: 审核报告
    overall_verdict TEXT,              -- "通过" | "有条件通过" | "不通过"
    fail_count INT,
    warning_count INT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 审核项明细表（便于统计分析）
CREATE TABLE audit_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT REFERENCES audit_records(id),
    item_code TEXT,                    -- 如 "R-CAL-001"
    category TEXT,                     -- 如 "标定审核"
    name TEXT,
    status TEXT,                       -- PASS / INFO / WARNING / FAIL
    actual_value TEXT,
    limit_value TEXT,
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 6. 计算引擎核心逻辑

### 6.1 硫酸亚铁铵浓度标定

```
低浓度方法: c(fAS) = (0.0250 × 5.00) / V_avg
高浓度方法: c(fAS) = (0.250 × 5.00) / V_avg

其中 V_avg = mean(平行滴定体积)

示例（来自样本记录）:
  V1=24.00, V2=24.04 → V_avg=24.02
  c = (0.0250 × 5.00) / 24.02 = 0.125 / 24.02 = 0.005204 mol/L
```

### 6.2 COD 浓度计算

```
COD (mg/L) = c(fAS) × (V0_avg - V1) × 8000 / V2 × f

其中:
  c(fAS)  = 硫酸亚铁铵标定浓度 (mol/L)
  V0_avg  = 空白消耗体积均值 (ml)
  V1      = 样品消耗体积 (ml)
  8000    = 1/4 O2 的摩尔质量换算值 (mg/L)
  V2      = 取样体积 (ml)
  f       = 稀释倍数

示例（来自样本记录）:
  实验室标样-YLB20260289:
    c=0.005204, V0_avg=22.625, V1=19.16, V2=10.00, f=1
    COD = 0.005204 × (22.625-19.16) × 8000 / 10.00 × 1
        = 0.005204 × 3.465 × 800
        = 14.42 → 14.4 (与填报值一致)
```

### 6.3 结果修约

```
def round_cod(value):
    if value < 4:
        return "<4"          # 低于检出限
    elif value < 100:
        return round(value)   # 整数
    else:
        return to_3_sig_figs(value)  # 三位有效数字
```

### 6.4 氯离子-硫酸汞换算

```
m_Cl = cl_estimate(mg/L) × sample_volume(ml) / 1000  # mg
m_HgSO4_required = m_Cl × 20                          # mg (质量比≥20:1)
V_HgSO4_required = m_HgSO4_required / 100              # mL (100 g/L = 100 mg/mL)
```

---

## 7. 配置参数（config.py）

所有阈值、常数、范围集中配置，便于调整和复用于其他方法：

```python
# HJ 828-2017 审核参数配置

# 方法检出限与范围
DETECTION_LIMIT = 4          # mg/L
QUANTITATION_LIMIT = 16      # mg/L
UPPER_LIMIT_UNDILUTED = 700  # mg/L

# 试剂浓度
LOW_METHOD_K2CR2O7 = 0.0250   # mol/L
HIGH_METHOD_K2CR2O7 = 0.250   # mol/L
LOW_METHOD_FAS = 0.005         # mol/L (approx)
HIGH_METHOD_FAS = 0.05         # mol/L (approx)
K2CR2O7_VOLUME = 5.00          # mL
H2SO4_AG2SO4_VOLUME = 15       # mL

# 标定
STANDARDIZATION_PARALLEL_MAX_DIFF = 0.05  # mL（平行标定最大允差）
STANDARDIZATION_DAILY_REQUIRED = True

# 空白
MIN_BLANK_COUNT = 2
BLANK_CONSISTENCY_MAX_DIFF = 0.5  # mL

# 精密度
PARALLEL_RATIO = 0.10             # 10%
PARALLEL_RPD_MAX = 10.0           # %

# 样品保存
MAX_STORAGE_DAYS = 5

# 氯离子
CL_MAX_DILUTED = 1000             # mg/L
HGSO4_CL_RATIO = 20               # 质量比
HGSO4_SOLUTION_CONC = 100         # g/L
HGSO4_MAX_VOLUME = 2.0            # mL

# 计算
COD_MOLAR_MASS_FACTOR = 8000      # 1/4 O2 mg/L

# 结果修约
COD_INTEGER_THRESHOLD = 100       # 低于此值修约到整数
```

---

## 8. AI 辅助字段映射接口

### 8.1 调用时机

仅当规则解析器提取的关键字段缺失率 > 30% 或用户手动触发时调用。

### 8.2 接口设计

```
输入: 原始文本/OCR结果 + 目标字段schema
输出: {field_name: {"value": ..., "confidence": 0.0-1.0}}
```

### 8.3 Prompt 策略

- 提供 HJ 828-2017 标准的关键术语词典（提高映射准确率）
- 提供一张标准的字段名变体列表（如 "终读"="终读(ml)"="滴定终点"="终点读数"）
- 返回结果附带 confidence，低置信度字段在修正界面高亮显示

---

## 9. 审核报告输出

### 9.1 Web 交互式报告

- 按规则组分类展示，每项显示：状态图标、规则编码、实际值 vs 限值、HJ 引用、建议
- 顶部汇总：通过 X / 警告 X / 不通过 X → 总体结论
- 颜色编码：绿(PASS) / 蓝(INFO) / 橙(WARNING) / 红(FAIL)

### 9.2 JSON 导出

```json
{
  "record_id": "GJW-04-2016-YS-SZ-011",
  "audit_time": "2026-05-18T10:30:00",
  "overall_verdict": "通过",
  "pass_count": 20,
  "warning_count": 2,
  "fail_count": 0,
  "info_count": 4,
  "items": [
    {
      "code": "R-CAL-001",
      "category": "标定审核",
      "name": "标定日期与浓度自洽",
      "status": "PASS",
      "actual_value": "标定日期=2026-04-03, 分析日期=2026-04-03",
      "limit_value": "标定日期==分析日期",
      "hj_ref": "HJ 828-2017 §6.12.1",
      "detail": "...",
      "suggestion": null
    }
  ],
  "extracted_data": { "...": "..." }
}
```

### 9.3 PDF 导出（后续版本）

- 使用 reportlab 或 weasyprint 生成正式审核报告 PDF
- 包含表头信息、审核结果汇总表、逐项详情、电子签名区

---

## 10. 部署方案

### 10.1 Streamlit Cloud 部署

- 配置文件: `.streamlit/config.toml`
- 环境变量: API keys（如需 AI 辅助映射）
- 数据持久化: SQLite 文件存储在 Streamlit Cloud 持久化存储中
- 优势: 免运维，公网可访问

### 10.2 本地单机部署

```bash
cd cod_audit
pip install -r requirements.txt
streamlit run app.py
```

- SQLite 数据库文件存储在本地 `data/` 目录
- 不需要网络连接（除非使用 AI fallback 功能）
- 数据完全本地化

---

## 11. 开发计划

### 第一阶段: 核心引擎 (预计 3-5 天)

- [ ] 数据模型 (models/)
- [ ] COD 计算引擎 (engine/calculator.py)
- [ ] 全部 31 条审核规则 (rules/)
- [ ] 审核编排器 (engine/auditor.py)
- [ ] 配置参数 (config.py)
- [ ] SQLite 数据库 (db/)
- [ ] 单元测试（使用样本记录数据）

### 第二阶段: 文件解析 (预计 2-3 天)

- [ ] Excel 解析器（xls/xlsx）
- [ ] PDF 解析器（文本型+扫描型）
- [ ] 图片 OCR 解析器
- [ ] AI 字段映射 fallback
- [ ] 在线修正界面

### 第三阶段: UI 与集成 (预计 2-3 天)

- [ ] Streamlit 应用主框架
- [ ] 上传与解析页面
- [ ] 数据修正确认页面
- [ ] 审核报告展示页面
- [ ] 历史记录查询页面
- [ ] JSON/PDF 报告导出

### 第四阶段: 测试与部署 (预计 1-2 天)

- [ ] 使用真实样本记录全流程测试
- [ ] 边界情况测试（混合浓度批次、检出限以下结果、仪器过期等）
- [ ] Streamlit Cloud 部署
- [ ] 编写使用文档

---

## 12. 与现有 nh3_audit 项目的关系

| 方面 | nh3_audit | cod_audit |
|------|-----------|-----------|
| 分析方法 | HJ 535-2009 (纳氏试剂分光光度法) | HJ 828-2017 (重铬酸盐法) |
| 核心计算 | 吸光度→标准曲线回归→浓度 | 滴定体积→标定浓度→COD |
| 规则数量 | 18 条 | 26 条 |
| 数据存储 | JSON 文件 | SQLite 数据库 |
| 文件解析 | PDF 专用解析 | 多格式通用解析（xls/pdf/docx/图片/XML） |
| UI 模式 | 表单手动填写 + PDF 上传 | 文件上传→自动提取→修正→审核 |

**复用内容**: utils/pdf_debug.py, models 设计思想, engine/auditor 架构, ui 组件模式
**不耦合**: 各自独立项目，独立部署

---

## 13. 风险与注意事项

1. **OCR 准确率**: 数字识别（如 0/O, 1/l, 8/6）是主要错误来源 → 在线修正界面是安全网
2. **表格布局多样性**: 不同实验室表格差异大 → 混合策略（规则优先 + AI fallback）
3. **科学计算精度**: Python float 与手工计算可能有微小差异 → 四舍五入后再比较，而非原始浮点比较
4. **氯离子数据缺失**: 很多记录可能不填氯离子估算量 → 不能强制检查 R-CL-002，需判断字段是否存在
5. **混合方法批次的边界**: 虽然实际中少见，但代码架构需支持每样品独立方法级别
6. **硫酸亚铁铵浓度的有效期**: 标准要求"每日临用前标定"但有些实验室可能沿用前一天标定 → 标定日期检查触发 FAIL 需明确提示
7. **稀释倍数 >1 时取样体积**: 稀释后的取样体积和原始取样体积的关系需要在数据模型中明确区分
