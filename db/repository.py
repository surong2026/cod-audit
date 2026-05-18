"""数据库读写封装 — SQLite"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from models.record import CODRecord
from models.audit_result import AuditReport, AuditItem, AuditStatus


DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "cod_audit.db"


def _get_schema_path():
    return Path(__file__).parent / "schema.sql"


def init_db():
    """初始化数据库 — 建表"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    schema = _get_schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
    conn.close()


def get_conn():
    """获取数据库连接"""
    if not DB_PATH.exists():
        init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def save_audit(record: CODRecord, report: AuditReport,
               original_filename: str = "",
               original_file_path: str = "") -> str:
    """保存审核记录到数据库

    Returns:
        record_id
    """
    conn = get_conn()
    try:
        report_dict = report.to_dict()

        conn.execute("""
            INSERT OR REPLACE INTO audit_records
                (id, task_id, org_name, analysis_date, method_ref,
                 original_filename, original_file_path,
                 extracted_data, audit_report,
                 overall_verdict, fail_count, warning_count,
                 pass_count, info_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.record_id or f"record_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            record.task_id,
            record.org_name,
            record.analysis_date.isoformat() if record.analysis_date else None,
            record.method_ref,
            original_filename,
            original_file_path,
            json.dumps(record.to_dict(), ensure_ascii=False, default=str),
            json.dumps(report_dict, ensure_ascii=False),
            report.overall_verdict,
            report.fail_count,
            report.warning_count,
            report.pass_count,
            report.info_count,
            datetime.now().isoformat(),
        ))

        # 同时保存审核项明细
        record_id = record.record_id or ""
        conn.execute("DELETE FROM audit_items WHERE record_id = ?", (record_id,))
        for item in report.items:
            conn.execute("""
                INSERT INTO audit_items
                    (record_id, item_code, category, name, status,
                     actual_value, limit_value, hj_ref, detail, suggestion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                item.code, item.category, item.name,
                item.status.value if isinstance(item.status, AuditStatus) else str(item.status),
                item.actual_value, item.limit_value,
                item.hj_ref, item.detail, item.suggestion,
            ))

        conn.commit()
        return record_id
    finally:
        conn.close()


def load_audit(record_id: str) -> tuple[CODRecord | None, AuditReport | None]:
    """从数据库加载审核记录

    Returns:
        (record, report) 或 (None, None)
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM audit_records WHERE id = ?", (record_id,)
        ).fetchone()

        if not row:
            return None, None

        record_data = json.loads(row["extracted_data"])
        record = CODRecord()
        # 简化: 从 JSON 完整恢复 (实际生产需逐字段恢复)
        # 此处仅恢复关键信息
        record.record_id = row["id"]
        record.task_id = row["task_id"] or ""
        record.org_name = row["org_name"] or ""

        report_data = json.loads(row["audit_report"])
        report = AuditReport(record_id=row["id"])
        for item_data in report_data.get("items", []):
            report.items.append(AuditItem(
                code=item_data.get("code", ""),
                category=item_data.get("category", ""),
                name=item_data.get("name", ""),
                status=AuditStatus(item_data.get("status", "INFO")),
                actual_value=item_data.get("actual_value", ""),
                limit_value=item_data.get("limit_value", ""),
                hj_ref=item_data.get("hj_ref", ""),
                detail=item_data.get("detail", ""),
                suggestion=item_data.get("suggestion", ""),
            ))

        return record, report
    finally:
        conn.close()


def list_records(limit: int = 50, offset: int = 0) -> list[dict]:
    """列出最近审核记录"""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, task_id, org_name, analysis_date, method_ref,
                   overall_verdict, fail_count, warning_count, pass_count,
                   info_count, created_at
            FROM audit_records
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_record(record_id: str):
    """删除审核记录"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM audit_records WHERE id = ?", (record_id,))
        conn.commit()
    finally:
        conn.close()
