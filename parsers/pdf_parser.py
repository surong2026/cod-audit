"""PDF 解析器 — pymupdf token 流解析

PDF 全文提取将表格线性化为逐行 token 序列:
  - 每个单元格内容占一行 (多行文本拆分到多行)
  - 样品行: seq, name_lines..., volume, dilution, diluted_vol,
              k2cr2o7_conc, end_read, start_read, net_vol, COD, Cl
  - FAS:   "硫酸亚铁铵溶液的标定", 标定日期, k2cr2o7_vol, k2cr2o7_conc,
            第一体积..., 第二体积..., "/" "/" "/"
"""

import re
from datetime import date, datetime
from typing import Optional

from models.record import (
    CODRecord, SampleRow, Instrument, FASStandardization, QCData,
)
from parsers.field_extractor import (
    safe_float, safe_date, clean_text,
    parse_reported_cod, classify_samples,
)


# ============================================================
# 公共入口
# ============================================================

def parse_pdf_bytes(file_bytes: bytes, filename: str) -> CODRecord:
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        return _extract(doc)
    finally:
        doc.close()


def parse_pdf(file_path: str) -> CODRecord:
    import fitz
    doc = fitz.open(file_path)
    try:
        return _extract(doc)
    finally:
        doc.close()


def _extract(doc) -> CODRecord:
    rec = CODRecord()

    # 收集所有页文本
    page_texts = [doc[i].get_text("text") for i in range(doc.page_count)]

    # 分页
    p1 = []
    p2 = []
    for i, t in enumerate(page_texts):
        if '质控结果表' in t:
            p2.append(t)
        else:
            p1.append(t)

    page1 = '\n'.join(p1)
    page2 = '\n'.join(p2) if p2 else ''

    # 提取
    _extract_metadata(page1, rec)
    _extract_instruments(page1, rec)
    _extract_samples(page1, rec)
    _extract_fas(page1, rec)
    _extract_footer(page1, rec)
    _extract_qc(page2, rec)

    classify_samples(rec.samples)
    _detect_level(rec)

    return rec


# ============================================================
# 元数据
# ============================================================

def _extract_metadata(text: str, rec: CODRecord):
    m = re.search(r'记录编号[：:]\s*([A-Z]{2,4}[-\w]+)', text)
    if m: rec.record_id = m.group(1)
    m = re.search(r'任务编号[：:]\s*(\d{10,})', text)
    if m: rec.task_id = m.group(1)
    m = re.search(r'监测机构名称[：:\s]+([^\n]{4,40})', text)
    if m: rec.org_name = m.group(1).strip()
    m = re.search(r'监测任务名称[：:\s]+([^\n]{2,30})', text)
    if m and m.group(1).strip(): rec.task_name = m.group(1).strip()
    m = re.search(r'采样日期\s*\n\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', text)
    if not m:
        m = re.search(r'采样日期\s*\n(.+?)\n分析日期', text)
        if m:
            d = safe_date(m.group(1).strip())
            if d: rec.sampling_date = d
    if m:
        d_group = m.group(1) if m.lastindex else None
        if d_group:
            d = safe_date(d_group)
            if d: rec.sampling_date = d
    m = re.search(r'分析日期\s*\n\s*(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', text)
    if m:
        rec.analysis_date = safe_date(m.group(1))
    m = re.search(r'分析日期\s*\n(.+?)\n分析方法', text)
    if m and rec.analysis_date is None:
        d = safe_date(m.group(1).strip())
        if d: rec.analysis_date = d
    m = re.search(r'温度[^0-9]*(\d+\.?\d*)', text)
    if m: rec.temperature = safe_float(m.group(1))
    m = re.search(r'湿度[^0-9]*(\d+\.?\d*)', text)
    if m: rec.humidity = safe_float(m.group(1))
    m = re.search(r'重铬酸钾[^\n]*浓度[^0-9]*(\d+\.\d{4})', text)
    if m: rec.k2cr2o7_conc = safe_float(m.group(1))
    m = re.search(r'方法[^\n]*\n(.+?)\n', text)
    if m: rec.method_ref = m.group(1).strip()


# ============================================================
# 仪器
# ============================================================

def _extract_instruments(text: str, rec: CODRecord):
    m = re.search(r'(酸式滴定管[^\n]*)', text)
    if m:
        inst = Instrument(name=m.group(1).strip())
        m2 = re.search(r'YL\s*[-]?\s*D\s*\d+\s*[-]?\s*\d+', text)
        if m2: inst.serial_no = re.sub(r'\s+', '', m2.group(0))
        pos = text.find('滴定管')
        if pos > 0:
            m3 = re.search(r'(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', text[pos:])
            if m3: inst.calibration_expiry = safe_date(m3.group(1))
        m4 = re.search(r'检定', text[pos:] if pos > 0 else text)
        if m4: inst.calibration_method = '检定'
        rec.instruments.append(inst)

    m = re.search(r'(CODcr[^\n]{0,30})', text)
    if m:
        name = m.group(1).strip()
        if '型' not in name and len(name) < 20:
            inst = Instrument(name=name)
            m2 = re.search(r'CODcr[\s\S]{0,100}?(\d{5})', text)
            if m2: inst.serial_no = m2.group(1)
            dates = re.findall(r'(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', text)
            if len(dates) >= 2: inst.calibration_expiry = safe_date(dates[1])
            rec.instruments.append(inst)


# ============================================================
# 样品 — token 流解析
# ============================================================

def _extract_samples(text: str, rec: CODRecord):
    """Token 流解析样品数据

    表格被线性化为逐行 token:
      seq_num, name_line1, name_line2..., volume, dilution, diluted_vol,
      k2cr2o7_conc, end_read, start_read, net_vol, reported_cod, cl_estimate

    每个样品行以一位或两位数字开头 (序号),
    接着可能是多行中文/数字混合的样品名称,
    然后 10 个固定值.
    """
    lines = text.split('\n')

    # 定位样品数据起始: 找到 "估算量" 或 "(mg/L)" 之后第一个纯数字行 "1"
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '1' and i > 20:
            # 验证: 下一行应该是样品名的一部分
            if i + 1 < len(lines) and len(lines[i + 1].strip()) > 1:
                start_idx = i
                break

    if start_idx is None:
        # 尝试从 "净用量" 关键字之后找
        for i, line in enumerate(lines):
            if '净用量' in line and '(' not in line:
                # 跳过这个 token 后的几行 (可能还有空行或子表头)
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() == '1':
                        start_idx = j
                        break
                break

    if start_idx is None:
        return

    # 从 start_idx 开始解析
    idx = start_idx
    while idx < len(lines):
        token = lines[idx].strip()
        if not token:
            idx += 1
            continue

        # 停止条件
        if '硫酸亚铁铵' in token and '标准溶液消耗量' not in token:
            break
        if token in ('说明', '备注'):
            break

        # 尝试解析序号
        seq_val = safe_float(token)
        if seq_val is None or seq_val != int(seq_val):
            idx += 1
            continue

        seq = int(seq_val)
        idx += 1

        # 收集样品名称 (多行合并, 直到遇到纯数值)
        name_parts = []
        while idx < len(lines):
            t = lines[idx].strip()
            if not t:
                idx += 1
                continue
            # 如果是纯数值且看起来不像样品 ID 的一部分 (如 "2029")
            f = safe_float(t)
            if f is not None and not re.match(r'^\d{3,}$', t):
                # 纯数值 → 样品名结束
                break
            name_parts.append(t)
            idx += 1

        sample_id = ''.join(name_parts).replace(' ', '')

        # 读取 9 个固定列值
        # volume, dilution, diluted_vol, k2cr2o7_conc,
        # end_read, start_read, net_vol, reported_cod_raw, cl_estimate
        values = []
        cod_raw = ""
        cl_val = None

        remaining = []
        while idx < len(lines) and len(remaining) < 10:
            t = lines[idx].strip()
            if not t:
                idx += 1
                continue
            # 遇到新序号或 FAS 标记 → 停止
            if re.match(r'^\d+$', t) and safe_float(t) is not None:
                # 检查是否是下一个样品行
                if t == str(seq + 1) or (len(t) <= 2 and safe_float(t) == seq + 1):
                    break
            if '硫酸亚铁铵' in t:
                break
            remaining.append(t)
            idx += 1

        # 解析 remaining tokens
        nums = []
        cod_raw = ""
        text_tokens = []

        for t in remaining:
            f = safe_float(t)
            if f is not None:
                nums.append(f)
            else:
                text_tokens.append(t)

            # 检测 COD 值文本 (仅非分隔符)
            if t.endswith('L') and t[:-1].replace('.','').isdigit():
                cod_raw = t
            elif t == '4L' or re.match(r'^[＜<]\s*\d+', t):
                cod_raw = t

        # 计算 conc_idx: nums[3] 是 k2cr2o7_conc (≈0.025 or ≈0.250)
        conc_idx = 3
        if len(nums) > 3 and (abs(nums[3] - 0.025) < 0.01 or abs(nums[3] - 0.250) < 0.01):
            conc_idx = 4

        # 数值型 COD: remaining 的第4个值 (index conc_idx+3) 是 COD
        numeric_cod = None
        if len(nums) > conc_idx + 3:
            cod_candidate = nums[conc_idx + 3]
            if cod_candidate < 5000 and 4 <= cod_candidate <= 700:
                numeric_cod = str(int(cod_candidate) if cod_candidate == int(cod_candidate) else cod_candidate)
                cod_raw = numeric_cod

        # 分隔符 COD: 仅当没有数值型 COD 且没有文本 COD 时才用
        if not cod_raw:
            for t in text_tokens:
                if t in ('/', '-', '--'):
                    cod_raw = t
                    break

        # 赋值
        if len(nums) >= 7:
            sample = SampleRow(seq=seq, sample_id=sample_id)
            sample.volume = nums[0] if nums[0] > 1 else 10.00
            sample.dilution_factor = nums[1] if nums[1] >= 1 else 1.0
            sample.diluted_volume = nums[2] if nums[2] >= 1 else 10.00
            if conc_idx == 4:
                sample.k2cr2o7_conc = nums[3]

            remaining_vals = nums[conc_idx:]
            if len(remaining_vals) >= 3:
                sample.end_reading = remaining_vals[0]
                sample.start_reading = remaining_vals[1]
                sample.net_volume = remaining_vals[2]

            # COD 填报值
            if cod_raw:
                sample.reported_cod_raw = cod_raw
                cod_val, is_below = parse_reported_cod(cod_raw)
                sample.reported_cod = cod_val
                sample.is_below_dl = is_below

            # Cl 估算量: remaining_vals 的最后一个值
            if len(remaining_vals) >= 4:
                cl_candidate = remaining_vals[-1]
                if cl_candidate >= 0 and cl_candidate < 5000:
                    sample.cl_estimate = cl_candidate

            rec.samples.append(sample)

        # 如果 seq 已经到 8 了, 可能后面就是 "/" 和 FAS 了
        if seq >= 8:
            break


# ============================================================
# FAS 标定
# ============================================================

def _extract_fas(text: str, rec: CODRecord):
    """从全文提取 FAS 标定 — 定位末尾的标定区域"""
    fas = rec.fas_std

    # 定位: 找到 "说明" 作为右边界, "硫酸亚铁铵" 或 "标定" 作为左边界
    shuoming_pos = text.rfind('说明')
    if shuoming_pos < 0:
        shuoming_pos = len(text) - 200

    # 在 "说明" 之前找 "硫酸亚铁铵" 最后出现的位置作为 FAS 区域起点
    fas_marker = '硫酸亚铁铵'
    fas_start = text.rfind(fas_marker, 0, shuoming_pos)
    if fas_start < 0:
        fas_start = text.rfind('标定', 0, shuoming_pos)
    if fas_start < 0:
        fas_start = max(0, shuoming_pos - 300)

    fas_text = text[fas_start:shuoming_pos]

    if not fas_text:
        return

    # 日期: 找 "2026-04-" 并拼接下一行的 "03"
    m = re.search(r'(\d{4}[-\/]\d{1,2})[-\/]\s*\n?\s*(\d{1,2})', fas_text)
    if m:
        date_str = f"{m.group(1)}-{m.group(2)}"
        fas.date = safe_date(date_str)
    if fas.date is None:
        m = re.search(r'(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', fas_text)
        if m:
            fas.date = safe_date(m.group(1))

    # 提取所有数值 token
    nums = re.findall(r'(\d+\.?\d*)', fas_text)
    floats = []
    for n in nums:
        f = safe_float(n)
        if f is not None:
            floats.append(f)

    # 5.00 → K2Cr2O7 volume
    for f in floats:
        if 4.5 < f < 5.5:
            fas.k2cr2o7_volume = f
            break
    # 0.0250 → K2Cr2O7 conc
    for f in floats:
        if 0.024 < f < 0.026:
            fas.k2cr2o7_conc = f
            break

    # 标定体积: 23-26 之间的值, 取净用量 (每个平行样终读和净用量相同, 只取一个)
    # 使用精确值去重 (24.00 和 24.04 不同)
    fas_vols = []
    seen_exact = set()
    for f in floats:
        if 23 < f < 27:
            key = f"{f:.2f}"
            if key not in seen_exact:
                fas_vols.append(f)
                seen_exact.add(key)
    fas.volumes = fas_vols[:3]

    # 标定浓度: 0.005xxx
    for f in floats:
        if 0.005 < f < 0.006:
            fas.reported_conc = f
            break


# ============================================================
# 页脚
# ============================================================

def _extract_footer(text: str, rec: CODRecord):
    for label, attr in [('分析人', 'analyst'), ('复核人', 'reviewer'), ('审核人', 'approver')]:
        m = re.search(rf'{label}[：:]\s*(\S+)', text)
        if m:
            setattr(rec, attr, m.group(1))


# ============================================================
# QC 数据 (Page 2)
# ============================================================

def _extract_qc(text: str, rec: CODRecord):
    if not text:
        return
    qc = rec.qc

    # 全程序空白
    m = re.search(r'(120\d{15,18}[^)\n]*(?:空白\S*))', text)
    if m: qc.field_blank_sample_id = m.group(1).strip()
    m = re.search(r'[＜<]\s*\d+\s*\(mg/L\)', text)
    if m: qc.field_blank_guarantee = m.group(0).strip()
    m = re.search(r'\b(\d+\s*L)\b', text)
    if m: qc.field_blank_measured = m.group(1).strip()
    qc.field_blank_qualified = '不合格' not in text

    # 实验室空白
    blank_ids = re.findall(r'(实验室空白[-\w\d]+)', text)
    qc.lab_blank_sample_ids = [b for b in blank_ids if '样品编号' not in b]

    # 平行样
    m = re.search(r'(120\d{15,18})\s*\n?\s*(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)', text)
    if m:
        qc.parallel_sample_id = m.group(1)
        qc.parallel_value1 = safe_float(m.group(2))
        qc.parallel_value2 = safe_float(m.group(3))
        qc.parallel_mean = safe_float(m.group(4))
        qc.parallel_rpd = safe_float(m.group(5))
    qc.parallel_qualified = '不合格' not in text

    # 有证标样
    m = re.search(r'(实验室标样[-\w]+)', text)
    if m: qc.std_sample_id = m.group(1).strip()
    m = re.search(r'(\d+\.\d+\s*[±±]\s*\d+\.\d+)', text)
    if m: qc.std_guarantee_range = m.group(1).strip()
    # 测定量: 找所有 (mg/L) 值，排除 ± 前面的，取最后一个
    all_mgl = re.findall(r'(\d+\.?\d*)\s*\(mg/L\)', text)
    # 过滤掉属于保证值范围的 (前面有 ± 符号)
    candidates = []
    for val in all_mgl:
        # 在原文中找到这个值，检查前面是否有 ±
        idx = text.find(val + '(mg/L)')
        if idx == -1:
            idx = text.find(val + ' (mg/L)')
        if idx > 0:
            before = text[max(0, idx - 8):idx]
            if '±' not in before:
                candidates.append(safe_float(val))
    if candidates:
        qc.std_measured = candidates[-1]
    qc.std_qualified = '不合格' not in text


def _detect_level(rec: CODRecord):
    conc = rec.k2cr2o7_conc or 0.0250
    level = "low" if abs(conc - 0.0250) < 0.001 else "high" if abs(conc - 0.250) < 0.001 else "unknown"
    for s in rec.samples:
        s.method_level = level
