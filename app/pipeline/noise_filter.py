"""⑤ 噪音过滤（S3）：三标准判定 + 逐条附理由与标准标注。

红线（评测方案 3.1）：每条过滤必须标注命中标准 ∈ 信源/时效/相关性——
`validate_noise` 是代码断言，mock/真实模式共用；不达标条目直接拒绝进入噪音面板。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import NOISE_STANDARDS, NoiseItem, RecallResult


@dataclass
class NoiseResult:
    noise: list[NoiseItem] = field(default_factory=list)
    summary: str = ""


def validate_noise(raw: dict) -> NoiseItem | None:
    """防御式字段校验 + 标准白名单断言；不合格返回 None。"""
    standard = raw.get("standard", "")
    if standard not in NOISE_STANDARDS:
        return None
    text = str(raw.get("text", "")).strip()
    reason = str(raw.get("reason", "")).strip()
    if not text or not reason:
        return None
    return NoiseItem(text=text, source=str(raw.get("source", "")), standard=standard, reason=reason)


def run_noise_filter(llm, recall: RecallResult) -> NoiseResult:
    payload = {
        "recall": [
            {
                "source_type": item.source_type.value,
                "source_name": item.source_name,
                "timestamp": item.timestamp,
                "content": item.content,
                "status": item.status,
            }
            for item in recall.items
        ]
    }
    out = llm.structured("noise_filter", payload)
    noise = [n for n in (validate_noise(x) for x in out.get("noise", [])) if n]
    return NoiseResult(noise=noise, summary=str(out.get("summary", "")))
