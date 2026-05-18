"""Excel 解析器 — 解析 .xls/.xlsx COD 原始记录表"""

import os
from datetime import date, datetime
from pathlib import Path

from models.record import (
    CODRecord, SampleRow, Instrument, FASStandardization, QCData,
)


def parse_excel(file_path: str) -> CODRecord:
    """解析 Excel 文件为 CODRecord

    支持 .xls (xlrd) 和 .xlsx (openpyxl)
    """
    ext = Path(file_path).suffix.lower()
    if ext == '.xls':
        return _parse_xls(file_path)
    elif ext in ('.xlsx', '.xlsm'):
        return _parse_xlsx(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def _parse_xls(file_path: str) -> CODRecord:
    """解析 .xls 格式"""
    import xlrd
    wb = xlrd.open_workbook(file_path)
    return _parse_sheets(wb, file_path)


def _parse_xlsx(file_path: str) -> CODRecord:
    """解析 .xlsx 格式"""
    import openpyxl
    wb = openpyxl.load_workbook(file_path, data_only=True)
    return _parse_sheets(wb, file_path)


def _parse_sheets(wb, file_path: str) -> CODRecord:
    """从工作簿解析 CODRecord"""
    import xlrd
    import openpyxl
    is_xlrd = isinstance(wb, xlrd.Book)

    # 尝试找到主数据 sheet
    sheet = _find_sheet(wb, is_xlrd, ['原始记录', '测定记录', 'Sheet1', '记录表'])

    rec = CODRecord()
    rec.record_id = f"record_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if is_xlrd:
        _parse_xlrd_sheet(sheet, rec)
    else:
        _parse_openpyxl_sheet(sheet, rec)

    return rec


def _find_sheet(wb, is_xlrd: bool, candidates: list[str]):
    """查找匹配的 sheet"""
    if is_xlrd:
        for name in candidates:
            if name in wb.sheet_names():
                return wb.sheet_by_name(name)
        return wb.sheet_by_index(0)
    else:
        for name in candidates:
            if name in wb.sheetnames:
                return wb[name]
        return wb.worksheets[0]


def _safe_float(val) -> float | None:
    """安全转换为 float"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s in ('/', '-', '--', 'N/A', ''):
        return None
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


def _safe_date(val) -> date | None:
    """安全转换为 date"""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    import xlrd
    if isinstance(val, xlrd.sheet.xldate):
        # xlrd date handling
        return None  # simplified
    s = str(val).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_xlrd_sheet(sheet, rec: CODRecord) -> None:
    """从 xlrd Sheet 提取数据 — 使用行列扫描匹配关键字段"""
    data = {}
    for row_idx in range(sheet.nrows):
        for col_idx in range(sheet.ncols):
            val = str(sheet.cell_value(row_idx, col_idx)).strip()
            if val:
                data[(row_idx, col_idx)] = val

    _extract_fields(data, rec)


def _parse_openpyxl_sheet(sheet, rec: CODRecord) -> None:
    """从 openpyxl Sheet 提取数据"""
    data = {}
    for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row):
        for cell in row:
            val = str(cell.value).strip() if cell.value is not None else ""
            if val:
                data[(cell.row - 1, cell.column - 1)] = val

    _extract_fields(data, rec)


def _extract_fields(data: dict, rec: CODRecord) -> None:
    """从单元格字典提取字段 — 关键词匹配"""
    field_map = {
        '记录编号': 'record_id',
        '任务编号': 'task_id',
        '任务名称': 'task_name',
        '采样日期': 'sampling_date',
        '分析日期': 'analysis_date',
        '温度': 'temperature',
        '湿度': 'humidity',
        '方法': 'method_ref',
        '分析人': 'analyst',
        '复核人': 'reviewer',
        '审核人': 'approver',
        '单位': 'org_name',
        '机构': 'org_name',
        '监测中心': 'org_name',
    }

    # 扫描所有单元格，匹配关键词
    for (r, c), val in data.items():
        for keyword, attr in field_map.items():
            if keyword in val:
                # 尝试取同行下一列的值
                next_val = data.get((r, c + 1), '')
                if next_val and keyword not in str(next_val):
                    if attr == 'record_id':
                        rec.record_id = str(next_val)
                    elif attr == 'task_id':
                        rec.task_id = str(next_val)
                    elif attr == 'task_name':
                        rec.task_name = str(next_val)
                    elif attr == 'analysis_date':
                        d = _safe_date(next_val)
                        if d:
                            rec.analysis_date = d
                    elif attr == 'sampling_date':
                        d = _safe_date(next_val)
                        if d:
                            rec.sampling_date = d
                    elif attr == 'temperature':
                        rec.temperature = _safe_float(next_val)
                    elif attr == 'humidity':
                        rec.humidity = _safe_float(next_val)
                    elif attr == 'analyst':
                        rec.analyst = str(next_val)
                    elif attr == 'reviewer':
                        rec.reviewer = str(next_val)
                    elif attr == 'approver':
                        rec.approver = str(next_val)
                    elif attr == 'org_name':
                        rec.org_name = str(next_val)


def build_demo_record() -> CODRecord:
    """构建示例 CODRecord（真实样本数据）"""
    rec = CODRecord(
        record_id="GJW-04-2016-YS-SZ-011",
        task_id="202604450900",
        org_name="广西壮族自治区玉林生态环境监测中心",
        task_name="202604分析任务",
        sampling_date=date(2026, 4, 2),
        analysis_date=date(2026, 4, 3),
        method_ref="水质 化学需氧量的测定 重铬酸盐法(HJ 828-2017)",
        temperature=24.5,
        humidity=55.0,
        k2cr2o7_prep_date=date(2026, 4, 3),
        k2cr2o7_conc=0.0250,
        analyst="苏毅",
        reviewer="陈昶",
        approver="吴雄平",
    )

    rec.instruments = [
        Instrument(name="酸式滴定管(50ml)", model="", serial_no="YL-D50-001",
                   calibration_expiry=date(2026, 7, 4), calibration_method="检定"),
        Instrument(name="CODcr回流消解仪(1200K型)", model="1200K型", serial_no="07905",
                   calibration_expiry=date(2026, 5, 19), calibration_method=""),
    ]

    rec.fas_std = FASStandardization(
        date=date(2026, 4, 3),
        k2cr2o7_volume=5.00,
        k2cr2o7_conc=0.0250,
        volumes=[24.00, 24.04],
        reported_conc=0.005204,
    )

    rec.samples = [
        SampleRow(seq=1, sample_id="实验室空白-202604-000012",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=22.60, start_reading=0.00, net_volume=22.60,
                  reported_cod_raw="/", reported_cod=None,
                  is_blank=True, cl_estimate=0.0, method_level="low"),
        SampleRow(seq=2, sample_id="实验室空白-202604-000013",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=22.65, start_reading=0.00, net_volume=22.65,
                  reported_cod_raw="/", reported_cod=None,
                  is_blank=True, cl_estimate=0.0, method_level="low"),
        SampleRow(seq=3, sample_id="实验室标样-YLB20260289",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=19.16, start_reading=0.00, net_volume=19.16,
                  reported_cod_raw="14", reported_cod=14.0,
                  is_qc_standard=True, cl_estimate=0.0, method_level="low"),
        SampleRow(seq=4, sample_id="12026040115513002029",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=19.02, start_reading=0.00, net_volume=19.02,
                  reported_cod_raw="15", reported_cod=15.0,
                  cl_estimate=20.0, hgso4_added=0.04, method_level="low"),
        SampleRow(seq=5, sample_id="12026040115513002029(空白1)",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=22.45, start_reading=0.00, net_volume=22.45,
                  reported_cod_raw="4L", reported_cod=None, is_below_dl=True,
                  cl_estimate=0.0, method_level="low"),
        SampleRow(seq=6, sample_id="12026040115510008172",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=18.88, start_reading=0.00, net_volume=18.88,
                  reported_cod_raw="16", reported_cod=16.0,
                  cl_estimate=20.0, hgso4_added=0.04, method_level="low"),
        SampleRow(seq=7, sample_id="12026040115510012752",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=18.74, start_reading=0.00, net_volume=18.74,
                  reported_cod_raw="16", reported_cod=16.0,
                  is_parallel=True, parallel_pair_id="12026040115510012752",
                  cl_estimate=20.0, hgso4_added=0.04, method_level="low"),
        SampleRow(seq=8, sample_id="12026040115510012752-1-平行",
                  volume=10.00, dilution_factor=1.0, diluted_volume=10.00,
                  k2cr2o7_conc=0.0250,
                  end_reading=18.70, start_reading=0.00, net_volume=18.70,
                  reported_cod_raw="16", reported_cod=16.0,
                  is_parallel=True, parallel_pair_id="12026040115510012752",
                  cl_estimate=20.0, hgso4_added=0.04, method_level="low"),
    ]

    rec.qc = QCData(
        field_blank_sample_id="12026040115513002029(空白1)",
        field_blank_guarantee="<4(mg/L)",
        field_blank_measured="4L",
        field_blank_qualified=True,
        lab_blank_sample_ids=["实验室空白-202604-000012", "实验室空白-202604-000013"],
        parallel_sample_id="12026040115510012752",
        parallel_value1=16.0,
        parallel_value2=16.0,
        parallel_mean=16.0,
        parallel_rpd=0.0,
        parallel_qualified=True,
        std_sample_id="实验室标样-YLB20260289",
        std_guarantee_range="14.3 ± 1.1(mg/L)",
        std_measured=14.4,
        std_qualified=True,
    )

    return rec
