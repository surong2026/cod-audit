# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — COD 审核系统桌面打包 (文件夹模式, 不含 EasyOCR)"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# ---- 项目根目录 ----
PROJ = Path(SPECPATH).resolve()  # /home/sr200/workspace/cod_audit

# ---- 收集 streamlit 所有子模块/模板/静态文件 ----
s_datas, s_bins, s_hidden = collect_all("streamlit")

# ---- 收集其他主要依赖 ----
pymupdf_datas, pymupdf_bins, pymupdf_hidden = collect_all("pymupdf")

# ---- 项目源文件 → 作为 data 打进包内 ----
datas = []
for dirpath, dirnames, filenames in os.walk(PROJ):
    rel = os.path.relpath(dirpath, PROJ)
    # 跳过不需要的目录
    dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "dist", "build")]
    if (rel.startswith(".") and rel != ".") or "__pycache__" in rel:
        continue
    for f in filenames:
        if f.endswith((".py", ".toml", ".md", ".txt")):
            src = os.path.join(dirpath, f)
            dst = rel if rel != "." else "."
            datas.append((src, dst))

# ---- 隐藏导入 ----
hiddenimports = (
    s_hidden
    + pymupdf_hidden
    + [
        # 项目模块
        "models",
        "models.record",
        "models.audit_result",
        "parsers",
        "parsers.ai_mapper",
        "parsers.docx_parser",
        "parsers.excel_layout",
        "parsers.excel_parser",
        "parsers.field_extractor",
        "parsers.image_parser",
        "parsers.pdf_parser",
        "engine",
        "engine.auditor",
        "engine.batch_context",
        "engine.calculator",
        "rules",
        "rules.accuracy",
        "rules.base",
        "rules.blank",
        "rules.calculation",
        "rules.calibration",
        "rules.chloride",
        "rules.detection_range",
        "rules.dilution",
        "rules.instrument",
        "rules.method_params",
        "rules.precision",
        "rules.result_format",
        "db",
        "db.repository",
        "ui",
        "utils",
        "utils.chloride_calc",
        "utils.cod_calc",
        "utils.rounding",
        "tests",
        # 第三方
        "tornado",
        "watchdog",
        "openpyxl",
        "xlrd",
        "docx",
        "PIL",
        "PIL.Image",
        "anthropic",
        "numpy",
        "pandas",
        "altair",
        "packaging",
        "yaml",
        "requests",
        "urllib3",
    ]
)

# ---- 排除 (减小体积) ----
excluded = ["easyocr", "torch", "torchvision", "tokenizers", "scipy", "matplotlib", "cv2", "opencv_python_headless", "onnxruntime", "onnx"]

# ============================================================
a = Analysis(
    ["run_app.py"],
    pathex=[str(PROJ)],
    binaries=s_bins + pymupdf_bins,
    datas=datas + s_datas + pymupdf_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excluded,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="COD_Audit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

# 收集目录输出
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="COD_Audit",
)
