-- COD 审核系统 SQLite 数据库建表语句

CREATE TABLE IF NOT EXISTS audit_records (
    id TEXT PRIMARY KEY,                      -- 记录编号
    task_id TEXT,
    org_name TEXT,
    analysis_date TEXT,
    method_ref TEXT,
    original_filename TEXT,                   -- 原始上传文件名
    original_file_path TEXT,                  -- 原始文件存储路径
    extracted_data TEXT,                      -- JSON: 提取的结构化数据快照
    audit_report TEXT,                        -- JSON: 完整审核报告
    overall_verdict TEXT,                     -- "通过" | "有条件通过" | "不通过"
    fail_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    pass_count INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS audit_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT REFERENCES audit_records(id) ON DELETE CASCADE,
    item_code TEXT,                           -- 规则编码 R-CAL-001
    category TEXT,                            -- 规则组
    name TEXT,                                -- 规则名称
    status TEXT,                              -- PASS/INFO/WARNING/FAIL
    actual_value TEXT,
    limit_value TEXT,
    hj_ref TEXT,
    detail TEXT,
    suggestion TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_audit_items_record
    ON audit_items(record_id);

CREATE INDEX IF NOT EXISTS idx_audit_items_status
    ON audit_items(status);

CREATE INDEX IF NOT EXISTS idx_audit_records_date
    ON audit_records(analysis_date);

CREATE INDEX IF NOT EXISTS idx_audit_records_verdict
    ON audit_records(overall_verdict);
