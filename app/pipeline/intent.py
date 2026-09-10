"""① 意图理解（S1）：识别标的与事件、判定提问类型。

澄清的最终触发规则（条件化澄清，S5）在编排层：
`needs_clarify = (intent_type == "持仓影响") and (holdings is None)`
——「缺失会改变结论方向才问」，事实核实类提问不重新索要持仓（D2-Q2）。
"""

from __future__ import annotations

from dataclasses import dataclass

INTENT_TYPES = ("持仓影响", "事实核实")


@dataclass
class IntentResult:
    stock: str
    code: str
    event: str | None
    intent_type: str  # 持仓影响 | 事实核实


def run_intent(llm, question: str) -> IntentResult:
    out = llm.structured("intent", {"question": question})
    # 防御式兜底：字段缺失时宁可判为持仓影响（会触发澄清），也不乱猜标的后直接解读
    return IntentResult(
        stock=out.get("stock") or "",
        code=out.get("code") or "",
        event=out.get("event"),
        intent_type=(
            out.get("intent_type") if out.get("intent_type") in INTENT_TYPES else "持仓影响"
        ),
    )
