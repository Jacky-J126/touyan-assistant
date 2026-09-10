"""⑥ 事实/推断分离（S4）：提取【事实】与【未知】。

格式断言（评测方案 3.1）：
- 每条【事实】必附信源与时间点；
- 每条【未知】必明说需补充什么，且区分「需你补充/需你等待」。
防御式校验同上——不合格条目丢弃（真实模式下由 3.1 断言兜底统计）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import FactItem, RecallResult, UnknownItem


@dataclass
class FactInferResult:
    facts: list[FactItem] = field(default_factory=list)
    unknowns: list[UnknownItem] = field(default_factory=list)


def _validate_fact(raw: dict) -> FactItem | None:
    text = str(raw.get("text", "")).strip()
    source = str(raw.get("source", "")).strip()
    timepoint = str(raw.get("timepoint", "")).strip()
    if not text or not source or not timepoint:
        return None
    return FactItem(text=text, source=source, timepoint=timepoint)


def _validate_unknown(raw: dict) -> UnknownItem | None:
    text = str(raw.get("text", "")).strip()
    action = str(raw.get("action", "")).strip()
    if not text or action not in ("需你补充", "需你等待"):
        return None
    return UnknownItem(text=text, action=action)


def run_fact_infer(llm, recall: RecallResult) -> FactInferResult:
    payload = {
        "recall": [
            {"source_type": i.source_type.value, "source_name": i.source_name, "content": i.content}
            for i in recall.items
        ]
    }
    out = llm.structured("fact_infer", payload)
    return FactInferResult(
        facts=[f for f in (_validate_fact(x) for x in out.get("facts", [])) if f],
        unknowns=[u for u in (_validate_unknown(x) for x in out.get("unknowns", [])) if u],
    )
