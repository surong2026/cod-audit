"""AI 字段映射 fallback — 当启发式解析漏掉必填字段时，用 LLM 从原始文本提取

用法:
    from parsers.ai_mapper import AIFieldMapper
    mapper = AIFieldMapper(api_key="...")
    rec = mapper.fill_gaps(raw_text, partial_record)

模型选择: Claude Haiku (快速/便宜), 可切换为 Sonnet 处理复杂布局
"""

import hashlib
import json
import os
from typing import Optional

from models.record import CODRecord, SampleRow, FASStandardization, QCData


# 必填字段 — 缺了任一就无法审核
REQUIRED_SAMPLE_FIELDS = [
    "sample_id", "volume", "dilution_factor", "diluted_volume",
    "end_reading", "start_reading", "net_volume", "reported_cod_raw",
]
REQUIRED_GLOBAL_FIELDS = [
    "record_id", "org_name",
]
REQUIRED_FAS_FIELDS = [
    "date", "volumes", "reported_conc",
]


class AIFieldMapper:
    """LLM 回退字段提取器"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-haiku-4-5-20251001"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._cache: dict[str, dict] = {}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def fill_gaps(self, raw_text: str, rec: CODRecord) -> tuple[CODRecord, bool]:
        """补齐缺失字段。返回 (更新后的record, 是否有改动)"""
        if not self.available:
            return rec, False

        missing = self._find_missing(rec)
        if not missing:
            return rec, False

        # 缓存 key: 文本 hash + 缺失字段列表
        text_hash = hashlib.sha256(raw_text.encode()).hexdigest()[:16]
        cache_key = f"{text_hash}:{','.join(sorted(missing))}"
        if cache_key in self._cache:
            self._apply_extracted(rec, self._cache[cache_key])
            return rec, True

        extracted = self._call_llm(raw_text, rec, missing)
        if extracted:
            self._cache[cache_key] = extracted
            self._apply_extracted(rec, extracted)
            return rec, True

        return rec, False

    # ----------------------------------------------------------
    # 内部
    # ----------------------------------------------------------

    def _find_missing(self, rec: CODRecord) -> list[str]:
        missing = []

        # 全局字段
        if not rec.record_id:
            missing.append("record_id")
        if not rec.org_name:
            missing.append("org_name")
        if rec.sampling_date is None:
            missing.append("sampling_date")
        if rec.analysis_date is None:
            missing.append("analysis_date")
        if rec.k2cr2o7_conc is None:
            missing.append("k2cr2o7_conc")

        # 样品字段
        if not rec.samples:
            missing.append("samples")
        else:
            for i, s in enumerate(rec.samples):
                if not s.sample_id:
                    missing.append(f"samples[{i}].sample_id")
                if s.net_volume == 0:
                    missing.append(f"samples[{i}].net_volume")
                if not s.reported_cod_raw:
                    missing.append(f"samples[{i}].reported_cod_raw")

        # FAS 字段
        if rec.fas_std.date is None:
            missing.append("fas_std.date")
        if not rec.fas_std.volumes:
            missing.append("fas_std.volumes")
        if rec.fas_std.reported_conc is None:
            missing.append("fas_std.reported_conc")

        return missing

    def _call_llm(self, raw_text: str, rec: CODRecord, missing: list[str]) -> Optional[dict]:
        """调用 Claude API 提取缺失字段"""
        import urllib.request
        import urllib.error

        prompt = self._build_prompt(raw_text, rec, missing)

        body = json.dumps({
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            content = result["content"][0]["text"]
            return self._parse_response(content)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            return None

    def _build_prompt(self, raw_text: str, rec: CODRecord, missing: list[str]) -> str:
        text_snippet = raw_text[:8000]

        prompt = f"""从以下 COD 分析原始记录文本中提取缺失的字段。只返回 JSON，不要其他内容。

缺失字段: {json.dumps(missing, ensure_ascii=False)}

已提取的部分数据:
{json.dumps(self._serialize_partial(rec), ensure_ascii=False, indent=2)}

原始记录文本（可能来自 OCR，含识别错误）:
---
{text_snippet}
---

返回格式: 只返回一个 JSON 对象，键为缺失字段路径，值为提取的数据。"""

        if "samples" in missing:
            prompt += """
样品数组格式示例:
  "samples": [
    {"seq": 1, "sample_id": "12026040115513002029(空白1)", "volume": 10.0, "dilution_factor": 1, "diluted_volume": 10.0, "k2cr2o7_conc": 0.025, "end_reading": 22.6, "start_reading": 0.0, "net_volume": 22.6, "reported_cod_raw": "/", "cl_estimate": 0},
    ...
  ]
每个样品必须有 seq(序号) 和 sample_id(样品编号)."""

        prompt += "\n\nJSON:"
        return prompt

    def _serialize_partial(self, rec: CODRecord) -> dict:
        return {
            "record_id": rec.record_id,
            "org_name": rec.org_name,
            "sampling_date": str(rec.sampling_date) if rec.sampling_date else None,
            "analysis_date": str(rec.analysis_date) if rec.analysis_date else None,
            "k2cr2o7_conc": rec.k2cr2o7_conc,
            "sample_count": len(rec.samples),
            "samples": [
                {
                    "seq": s.seq,
                    "sample_id": s.sample_id,
                    "volume": s.volume,
                    "dilution_factor": s.dilution_factor,
                    "net_volume": s.net_volume,
                    "reported_cod_raw": s.reported_cod_raw,
                }
                for s in rec.samples
            ],
            "fas_std": {
                "date": str(rec.fas_std.date) if rec.fas_std.date else None,
                "volumes": rec.fas_std.volumes,
                "reported_conc": rec.fas_std.reported_conc,
            },
        }

    def _parse_response(self, content: str) -> Optional[dict]:
        # 提取 JSON 块 (可能被 markdown 包裹)
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试找 { } 块
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError:
                    pass
        return None

    def _apply_extracted(self, rec: CODRecord, data: dict) -> None:
        """将 AI 提取的字段写回 CODRecord"""
        from parsers.field_extractor import safe_float, safe_date, parse_reported_cod

        for path, value in data.items():
            if value is None:
                continue

            if path == "record_id":
                rec.record_id = str(value)
            elif path == "org_name":
                rec.org_name = str(value)
            elif path == "sampling_date":
                d = safe_date(value)
                if d:
                    rec.sampling_date = d
            elif path == "analysis_date":
                d = safe_date(value)
                if d:
                    rec.analysis_date = d
            elif path == "k2cr2o7_conc":
                f = safe_float(value)
                if f:
                    rec.k2cr2o7_conc = f
            elif path == "fas_std.date":
                d = safe_date(value)
                if d:
                    rec.fas_std.date = d
            elif path == "fas_std.volumes":
                if isinstance(value, list):
                    rec.fas_std.volumes = [v for v in (safe_float(x) for x in value) if v]
            elif path == "fas_std.reported_conc":
                f = safe_float(value)
                if f:
                    rec.fas_std.reported_conc = f
            elif path == "samples" and isinstance(value, list):
                if not rec.samples:
                    self._create_samples_from_ai(rec, value)
                else:
                    self._fill_sample_gaps(rec, value)

    def _create_samples_from_ai(self, rec: CODRecord, ai_samples: list) -> None:
        """当启发式解析未提取到任何样品时，从 AI 数据创建 SampleRow"""
        from parsers.field_extractor import safe_float, parse_reported_cod
        from models.record import SampleRow

        for ai_s in ai_samples:
            seq = ai_s.get("seq")
            if seq is None:
                continue
            s = SampleRow(
                seq=int(seq),
                sample_id=str(ai_s.get("sample_id", "")),
            )
            for field, attr in [
                ("volume", "volume"),
                ("dilution_factor", "dilution_factor"),
                ("diluted_volume", "diluted_volume"),
                ("k2cr2o7_conc", "k2cr2o7_conc"),
                ("end_reading", "end_reading"),
                ("start_reading", "start_reading"),
                ("net_volume", "net_volume"),
                ("cl_estimate", "cl_estimate"),
            ]:
                v = safe_float(ai_s.get(field))
                if v is not None:
                    setattr(s, attr, v)
            if ai_s.get("reported_cod_raw"):
                s.reported_cod_raw = str(ai_s["reported_cod_raw"])
                cod_val, is_below = parse_reported_cod(s.reported_cod_raw)
                s.reported_cod = cod_val
                s.is_below_dl = is_below
            rec.samples.append(s)

    def _fill_sample_gaps(self, rec: CODRecord, ai_samples: list) -> None:
        """用 AI 返回的样品数据补齐现有样品"""
        from parsers.field_extractor import safe_float, parse_reported_cod

        for ai_s in ai_samples:
            seq = ai_s.get("seq")
            if seq is None:
                continue
            target = None
            for s in rec.samples:
                if s.seq == seq:
                    target = s
                    break
            if target is None:
                continue
            if not target.sample_id and ai_s.get("sample_id"):
                target.sample_id = str(ai_s["sample_id"])
            if target.net_volume == 0 and ai_s.get("net_volume"):
                v = safe_float(ai_s["net_volume"])
                if v:
                    target.net_volume = v
            if not target.reported_cod_raw and ai_s.get("reported_cod_raw"):
                target.reported_cod_raw = str(ai_s["reported_cod_raw"])
                cod_val, is_below = parse_reported_cod(target.reported_cod_raw)
                target.reported_cod = cod_val
                target.is_below_dl = is_below
