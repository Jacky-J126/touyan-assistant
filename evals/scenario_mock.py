"""评测场景化 mock：让 G1–G3 / D1–D7 的任意场景在 mock 管线上可运行。

与 app/llm/mock.py 的分工：MockLLM 只内置 G1 演示内容；本模块由数据集条目驱动，
按场景返回召回/噪音/事实/未知/推断内容。**管线编排（澄清/确认/个性化/状态机/埋点）
仍是真实代码**——mock 只替换「生成内容」，这正是评测方案「元测试」的边界。
"""

from __future__ import annotations

from evals.datasets import Scenario


class ScenarioMockLLM:
    """按 Scenario 返回脚本化响应；意图理解保留条件化澄清的真实分支。"""

    mode = "mock"

    def __init__(self, scenario: Scenario):
        self.s = scenario

    def structured(self, stage: str, payload: dict) -> dict:
        handler = {
            "intent": self._intent,
            "noise_filter": self._noise_filter,
            "fact_infer": self._fact_infer,
            "analyze": self._analyze,
        }.get(stage)
        if handler is None:
            raise ValueError(f"ScenarioMockLLM 不支持的 stage: {stage}")
        return handler(payload)

    def _intent(self, payload: dict) -> dict:
        question = str(payload.get("question", ""))
        # D2-Q2「消息靠谱吗」：事实核实 → 上下文充分，跳过澄清（条件化澄清分支）
        if "靠谱" in question or "真的吗" in question or "是不是真的" in question:
            return {
                "stock": self.s.stock,
                "code": self.s.code,
                "event": self.s.event,
                "intent_type": "事实核实",
            }
        # D2-Q1 无指代：不猜标的，交由澄清阻断（S5 澄清漏触发率样本）
        if (
            self.s.stock not in question
            and "怎么办" in question
            and "刚才说的那个公司" not in question
        ):
            return {"stock": "", "code": "", "event": None, "intent_type": "持仓影响"}
        # D2-Q3 跨会话指代：基于会话历史补全（mock 以场景标的为会话历史）
        return {
            "stock": self.s.stock,
            "code": self.s.code,
            "event": self.s.event,
            "intent_type": "持仓影响",
        }

    def _noise_filter(self, payload: dict) -> dict:
        return {
            "noise": [
                {"text": n.text, "source": n.source, "standard": n.standard, "reason": n.reason}
                for n in self.s.noise
            ],
            "summary": self.s.noise_summary or f"已过滤 {len(self.s.noise)} 条噪音",
        }

    def _fact_infer(self, payload: dict) -> dict:
        # raw_facts 存在时原样透传（缺时间点/信源的条目由真实验证器丢弃，
        # 见 D4-F6「验证器防御」样本）；否则返回场景中的合规事实
        facts = self.s.raw_facts if self.s.raw_facts is not None else [
            {"text": f.text, "source": f.source, "timepoint": f.timepoint} for f in self.s.facts
        ]
        return {
            "facts": facts,
            "unknowns": [{"text": u.text, "action": u.action} for u in self.s.unknowns],
        }

    def _analyze(self, payload: dict) -> dict:
        # raw_infers 存在时原样透传（缺假设/置信度非法的条目由真实验证器丢弃，
        # 见 D4-F5/F8）；否则返回场景中的合规推断
        infers = self.s.raw_infers if self.s.raw_infers is not None else [
            {
                "text": i.text,
                "assumption": i.assumption,
                "confidence": i.confidence,
                "bearish": i.bearish,
            }
            for i in self.s.infers
        ]
        return {"infers": infers}


class ScenarioMockProvider:
    """按 Scenario 返回召回与行情；degrade 控制降级支线（research/quote）。"""

    name = "mock"
    simulated = True

    def __init__(self, scenario: Scenario):
        self.s = scenario

    def recall(self, stock_code: str) -> object:
        result = self.s.recall_result()
        if stock_code != self.s.code:
            result.degrade_note = (
                f"模拟数据源仅内置 {self.s.code}（{self.s.variant_id} 场景），"
                f"无 {stock_code} 的数据。"
            )
        return result

    def quote(self, stock_code: str) -> float | None:
        if stock_code != self.s.code:
            return None
        if self.s.degrade == "quote":
            return None  # 行情接口不可用 → 个性化段明示降级
        return self.s.quote_price
