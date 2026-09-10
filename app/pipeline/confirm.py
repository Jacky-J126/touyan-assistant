"""⑧ 结论呈现前确认（HITL#2 · S5）：条件化触发，跳过必须被记录。

触发条件（PRD V0.2 / D6 样本）：仅在「推断占比高」或「涉利空」时弹。
- H1 低推断无利空 / H2 全事实 → 不弹
- H3 高推断含利空（Demo G1 场景）→ 必弹且注明触发原因
- H4 应弹场景用户点跳过 → 结论照常输出且跳过被记录（跳过率指标口径）
"""

from __future__ import annotations

from app.models import FactItem, InferItem

#: 推断占比高阈值（Demo 触发口径：3/7 ≈ 0.43）
CONFIRM_INFER_RATIO = 0.4


def infer_ratio(facts: list[FactItem], infers: list[InferItem]) -> float:
    total = len(facts) + len(infers)
    if total == 0:
        return 0.0
    return len(infers) / total


def confirm_needed(facts: list[FactItem], infers: list[InferItem]) -> tuple[bool, str]:
    """返回 (是否弹确认, 触发原因文案)。"""
    ratio = infer_ratio(facts, infers)
    ratio_high = ratio >= CONFIRM_INFER_RATIO
    bearish = any(i.bearish for i in infers)
    if not (ratio_high or bearish):
        return False, ""
    parts: list[str] = []
    if ratio_high:
        parts.append(f"本次解读推断占比高（{len(infers)}/{len(facts) + len(infers)}）")
    if bearish:
        parts.append("包含利空性质的不确定性")
    return True, "且".join(parts) + "——按规则仅在此时请你确认。"
