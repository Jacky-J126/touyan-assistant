"""⑦ 分析生成（S4/S7）：基于事实生成影响面推断。

格式断言：每条推断结构为「影响面 + 关键假设」，附置信度，禁「必然」表述；
bearish 标记供 ⑧ 结论前确认的触发判断使用。
信息不足以支撑推断时返回空列表（降级条款：不做推断，只梳理事实）。
"""

from __future__ import annotations

from app.models import FactItem, InferItem, RecallResult

CONFIDENCES = ("高", "中", "低", "低–中", "中–高")


def _validate_infer(raw: dict) -> InferItem | None:
    text = str(raw.get("text", "")).strip()
    assumption = str(raw.get("assumption", "")).strip()
    confidence = str(raw.get("confidence", "")).strip()
    if not text or not assumption or confidence not in CONFIDENCES:
        return None
    return InferItem(
        text=text,
        assumption=assumption,
        confidence=confidence,
        bearish=bool(raw.get("bearish", False)),
    )


def run_analyze(llm, recall: RecallResult, facts: list[FactItem]) -> list[InferItem]:
    payload = {
        "facts": [{"text": f.text, "source": f.source, "timepoint": f.timepoint} for f in facts],
        "degrade_note": recall.degrade_note,
    }
    out = llm.structured("analyze", payload)
    return [i for i in (_validate_infer(x) for x in out.get("infers", [])) if i]
