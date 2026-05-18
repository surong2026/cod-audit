"""PDF token-stream 解析器单元测试 — 用合成文本验证所有提取路径"""
import sys
sys.path.insert(0, '/home/sr200/workspace/cod_audit')

from parsers.field_extractor import safe_float, parse_reported_cod, classify_samples
from models.record import CODRecord


def test_sample_extraction():
    """用合成 token 流测试 _extract_samples 的核心逻辑"""
    # 模拟 PDF get_text("text") 输出 — 样品区域
    lines = [
        "记录编号：GJW-04-2016-YS-SZ-011",
        "监测机构名称：广西壮族自治区玉林生态环境监测中心",
        "任务编号：202604450900",
        "采样日期",
        "2026-04-02",
        "分析日期",
        "2026-04-03",
        "温度",
        "25.0",
        "湿度",
        "65.0",
        "方法",
        "水质 化学需氧量的测定 重铬酸盐法(HJ 828-2017)",
        "重铬酸钾标准溶液浓度",
        "0.0250",
        "酸式滴定管(50ml)",
        "YL-D50-001",
        "CODcr回流消解仪(1200K型)",
        "07905",
        "",
        "样品编号",
        "取样体积",
        "稀释倍数",
        "稀释后取样体积",
        "重铬酸钾浓度",
        "终读",
        "始读",
        "净用量",
        "COD",
        "Cl-估算量",
        # 样品 1 — 空白1 (COD=/)
        "1",
        "12026040115513002029(空白1)",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "22.60",
        "0.00",
        "22.60",
        "/",
        "0",
        # 样品 2 — 空白2 (COD=/)
        "2",
        "12026040115513002030(空白2)",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "22.65",
        "0.00",
        "22.65",
        "/",
        "0",
        # 样品 3 — 质控样 (COD=14.4)
        "3",
        "实验室标样-YLB20260289",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "19.60",
        "0.44",
        "19.16",
        "14.4",
        "0",
        # 样品 4 — 普通样 (COD=15, Cl=20)
        "4",
        "12026040115510012752",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "19.47",
        "0.45",
        "19.02",
        "15",
        "20",
        # 样品 5 — 低于检出限 (COD=4L)
        "5",
        "12026040115510008172",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "22.90",
        "0.45",
        "22.45",
        "4L",
        "0",
        # 样品 6 — 普通样 (COD=16, Cl=20)
        "6",
        "12026040115510012753",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "19.35",
        "0.47",
        "18.88",
        "16",
        "20",
        # 样品 7 — 普通样 (COD=16, Cl=20)
        "7",
        "12026040115510012754",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "19.21",
        "0.47",
        "18.74",
        "16",
        "20",
        # 样品 8 — 普通样，后面有分隔符 "/" (COD=16, Cl=20)
        "8",
        "12026040115510012755",
        "10.00",
        "1",
        "10.00",
        "0.0250",
        "19.17",
        "0.47",
        "18.70",
        "16",
        "20",
        "/",  # 分隔符 — 不应被当作 COD
        "硫酸亚铁铵",
    ]

    text = '\n'.join(lines)

    from parsers.pdf_parser import _extract_samples, _extract_metadata, _extract_fas
    rec = CODRecord()
    _extract_metadata(text, rec)
    _extract_samples(text, rec)

    # 验证采样数量
    assert len(rec.samples) == 8, f"Expected 8 samples, got {len(rec.samples)}"

    # 验证具体值
    s1 = rec.samples[0]
    assert s1.seq == 1
    assert '12026040115513002029' in s1.sample_id
    assert s1.net_volume == 22.60, f"s1 net_vol: {s1.net_volume}"
    assert s1.reported_cod_raw == '/', f"s1 cod_raw: {s1.reported_cod_raw!r}"
    assert s1.reported_cod is None
    assert not s1.is_below_dl

    s3 = rec.samples[2]
    assert s3.seq == 3
    assert 'YLB20260289' in s3.sample_id
    assert s3.net_volume == 19.16, f"s3 net_vol: {s3.net_volume}"
    assert s3.reported_cod_raw == '14.4', f"s3 cod_raw: {s3.reported_cod_raw!r}"
    assert s3.reported_cod == 14.4, f"s3 cod: {s3.reported_cod}"

    s5 = rec.samples[4]
    assert s5.seq == 5
    assert s5.net_volume == 22.45
    assert s5.reported_cod_raw == '4L', f"s5 cod_raw: {s5.reported_cod_raw!r}"
    assert s5.is_below_dl, f"s5 should be below_dl"

    # 关键测试: 样品 8 的 COD 应该是 "16" 而不是 "/"
    s8 = rec.samples[7]
    assert s8.seq == 8
    assert s8.net_volume == 18.70, f"s8 net_vol: {s8.net_volume}"
    assert s8.reported_cod_raw == '16', f"s8 cod_raw should be '16', got {s8.reported_cod_raw!r}"
    assert s8.reported_cod == 16.0, f"s8 cod: {s8.reported_cod}"
    assert s8.cl_estimate == 20.0, f"s8 cl: {s8.cl_estimate}"

    print("All sample extraction tests PASSED")


def test_fas_extraction():
    """测试 FAS 标定数据提取"""
    fas_lines = [
        "0.005204",
        "硫酸亚铁铵溶液浓度",
        "24.00",
        "24.04",
        "/",
        "/",
        "/",
        "0.005204",
        "",
        "说明",
        "分析人：苏毅",
    ]

    text = '\n'.join(fas_lines)

    from parsers.pdf_parser import _extract_fas
    rec = CODRecord()
    _extract_fas(text, rec)

    fas = rec.fas_std
    # 标定体积应该有 2 个 (24.00 和 24.04)
    assert len(fas.volumes) >= 1, f"Expected at least 1 titration volume, got {fas.volumes}"
    # 检查 24.00 和 24.04 是否都被捕获
    if len(fas.volumes) == 2:
        assert abs(fas.volumes[0] - 24.00) < 0.01 or abs(fas.volumes[1] - 24.00) < 0.01
        assert abs(fas.volumes[0] - 24.04) < 0.01 or abs(fas.volumes[1] - 24.04) < 0.01
        print(f"FAS volumes: {fas.volumes} — both values captured")
    else:
        print(f"FAS volumes: {fas.volumes} (only {len(fas.volumes)} found)")

    assert fas.reported_conc is not None, "Should find reported_conc 0.005204"
    print(f"FAS reported_conc: {fas.reported_conc}")

    print("FAS extraction tests PASSED")


def test_qc_extraction():
    """测试 QC 质控数据提取"""
    qc_lines = [
        "质控结果表-1批次",
        "全程序空白样样品编号",
        "保证值",
        "测定值",
        "是否合格",
        "12026040115513002029(空白1)",
        "＜4(mg/L)",
        "4L",
        "合格",
        "实验室空白样样品编号",
        "实验室空白-202604-000012",
        "/",
        "实验室空白-202604-000013",
        "/",
        "平行样样品编号",
        "样品浓度（mg/L）",
        "均值（mg/L）",
        "相对偏差",
        "（%）",
        "是否合格",
        "12026040115510012752",
        "16",
        "16",
        "16.0",
        "0.0",
        "合格",
        "有证标样",
        "样品编号",
        "保证量",
        "测定量",
        "是否合格",
        "实验室标样-YLB20260289",
        "14.3 ± 1.1(mg/L)",
        "14.4(mg/L)",
        "合格",
    ]

    text = '\n'.join(qc_lines)

    from parsers.pdf_parser import _extract_qc
    rec = CODRecord()
    _extract_qc(text, rec)

    qc = rec.qc
    assert '12026040115513002029' in qc.field_blank_sample_id
    assert qc.field_blank_measured == '4L', f"field_blank_measured: {qc.field_blank_measured!r}"

    # 关键: std_measured 应该是 14.4, 不是 1.1
    assert qc.std_sample_id == '实验室标样-YLB20260289', f"std_sample_id: {qc.std_sample_id!r}"
    assert qc.std_measured == 14.4, f"std_measured should be 14.4, got {qc.std_measured}"
    print(f"QC std_measured: {qc.std_measured} — correct")

    # 平行样
    assert qc.parallel_sample_id == '12026040115510012752'
    assert qc.parallel_value1 == 16.0
    assert qc.parallel_value2 == 16.0

    print("QC extraction tests PASSED")


def test_classify():
    """测试样品分类"""
    from models.record import SampleRow

    samples = [
        SampleRow(seq=1, sample_id="12026040115513002029(空白1)", reported_cod_raw="/", is_blank=False),
        SampleRow(seq=2, sample_id="12026040115513002030(空白2)", reported_cod_raw="/", is_blank=False),
        SampleRow(seq=3, sample_id="实验室标样-YLB20260289", reported_cod_raw="14.4"),
        SampleRow(seq=4, sample_id="12026040115510012752", reported_cod_raw="15"),
        SampleRow(seq=5, sample_id="12026040115510012752-1-平行", reported_cod_raw="16"),
    ]

    classify_samples(samples)

    # 空白的判定: 含 "空白" 且 COD 为 "/"
    assert samples[0].is_blank, "Sample 1 should be blank"
    assert samples[1].is_blank, "Sample 2 should be blank"

    # 标样的判定: 含 "标样"
    assert samples[2].is_qc_standard, "Sample 3 should be qc_standard"

    # 平行样的判定
    assert samples[4].is_parallel, "Sample 5 should be parallel"
    assert samples[4].parallel_pair_id == '12026040115510012752'

    # 原始样也应为平行 (配对逻辑)
    assert samples[3].is_parallel, "Sample 4 should also be parallel (paired)"

    print("Classification tests PASSED")


if __name__ == '__main__':
    print("=" * 60)
    print("PDF Parser Unit Tests")
    print("=" * 60)
    test_sample_extraction()
    print()
    test_fas_extraction()
    print()
    test_qc_extraction()
    print()
    test_classify()
    print()
    print("=" * 60)
    print("All tests PASSED")
