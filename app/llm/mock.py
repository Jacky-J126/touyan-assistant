"""MockLLM：G1 场景的脚本化响应。

mock 模式复现交互原型的预置演示内容；管线编排（HITL 条件判断、状态机、
个性化计算、埋点）是真实代码，只有本层的生成内容为脚本。
"""

from __future__ import annotations

from app import mockdata as md


class MockLLM:
    """脚本化 LLM：按 stage 返回 G1 演示内容，零 key 可跑。"""

    mode = "mock"

    def structured(self, stage: str, payload: dict) -> dict:
        handler = {
            "intent": self._intent,
            "noise_filter": self._noise_filter,
            "fact_infer": self._fact_infer,
            "analyze": self._analyze,
        }.get(stage)
        if handler is None:
            raise ValueError(f"MockLLM 不支持的 stage: {stage}")
        return handler(payload)

    # ------------------------------------------------------------ 各 stage 脚本

    def _intent(self, payload: dict) -> dict:
        question = str(payload.get("question", ""))
        # D2-Q2「消息靠谱吗」：事实核实类提问 → 上下文充分，跳过澄清（条件化澄清的真实分支）
        if "靠谱" in question or "真的吗" in question or "是不是真的" in question:
            return {
                "stock": md.STOCK_NAME,
                "code": md.STOCK_CODE,
                "event": md.EVENT,
                "intent_type": "事实核实",
                "needs_clarify": False,
            }
        return {
            "stock": md.STOCK_NAME,
            "code": md.STOCK_CODE,
            "event": md.EVENT,
            "intent_type": "持仓影响",
            "needs_clarify": True,
        }

    def _noise_filter(self, payload: dict) -> dict:
        return {
            "noise": [
                {"text": n.text, "source": n.source, "standard": n.standard, "reason": n.reason}
                for n in md.G1_NOISE
            ],
            "summary": md.NOISE_SUMMARY,
        }

    def _fact_infer(self, payload: dict) -> dict:
        return {
            "facts": [
                {"text": f.text, "source": f.source, "timepoint": f.timepoint}
                for f in md.G1_FACTS
            ],
            "unknowns": [
                {"text": u.text, "action": u.action} for u in md.G1_UNKNOWNS
            ],
        }

    def _analyze(self, payload: dict) -> dict:
        return {
            "infers": [
                {
                    "text": i.text,
                    "assumption": i.assumption,
                    "confidence": i.confidence,
                    "bearish": i.bearish,
                }
                for i in md.G1_INFERS
            ]
        }
