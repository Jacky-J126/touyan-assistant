"""全流程集成（mock 模式）：G1 主流程 + 事实核实支线 + 降级支线 + 事件链。

MockLLM 只替换「生成内容」，管线编排（澄清/确认/个性化/状态机/埋点）是真实代码。
"""

from __future__ import annotations

from app import mockdata as md
from app.datasources.mock import MockProvider
from app.llm.mock import MockLLM
from app.models import NoiseItem
from app.orchestrator import Session
from app.pipeline.noise_filter import validate_noise

QUESTION = "沐辰智控今天这个收购公告，对我的持仓有什么影响？"


def _full_session(provider=None) -> Session:
    s = Session(llm=MockLLM(), provider=provider or MockProvider())
    s.touch()
    res = s.ask(QUESTION)
    assert res["stage"] == "clarify"
    res = s.submit_clarify(cost=18.40, ratio=18.0, horizon="1-3y")
    assert res["stage"] == "confirm"  # G1 必弹确认（H3）
    return s


# ---------------------------------------------------------------- 主流程

def test_g1_main_flow_conclusion():
    s = _full_session()
    res = s.confirm("confirm")
    assert res["stage"] == "conclusion"
    c = res["conclusion"]
    assert c.stock_name == md.STOCK_NAME
    assert c.stock_code == md.STOCK_CODE
    assert len(c.facts) == 4 and len(c.infers) == 3 and len(c.unknowns) == 2
    assert len(c.noise) == 5 and c.noise_summary == md.NOISE_SUMMARY
    assert c.degrade_note is not None  # 研报降级明示
    assert len(c.glossary) == 5
    per = c.personalization
    assert per.weight_verdict and per.horizon_line and per.cost_line and per.caliber_note
    assert "¥19.12" in per.cost_line  # 现价来自 provider quote


def test_g1_event_chain():
    s = _full_session()
    s.confirm("confirm")
    s.followup("该买还是该卖？")
    s.followup("还是想买")
    s.followup("必须告诉我买不买")
    m = s.events.metrics()
    assert m["打开"] is True
    assert m["追问"] is True
    assert m["跳过率"] == 0.0  # 确认环节触达 1 次、未跳过
    assert m["事件数"] > 10
    for name in (
        "touch_delivered",
        "question_asked",
        "clarify_shown",
        "clarify_submitted",
        "recall_started",
        "degraded",
        "noise_filtered",
        "facts_extracted",
        "analysis_generated",
        "personalized_rendered",
        "confirm_shown",
        "confirm_confirmed",
        "conclusion_delivered",
        "followup_asked",
        "refusal_triggered",
        "escalation_guide",
        "escalation_stop",
    ):
        assert s.events.has(name), f"缺少事件：{name}"


# ---------------------------------------------------------------- 事实核实支线

def test_fact_check_branch():
    s = Session(llm=MockLLM())
    s.touch()
    res = s.ask("这条收购消息靠谱吗？")
    assert res["stage"] == "answer"
    assert "事实部分" in res["answer"]
    assert "推断" in res["answer"]
    assert not s.events.has("clarify_shown")


# ---------------------------------------------------------------- 降级支线

class NoQuoteProvider(MockProvider):
    def quote(self, stock_code: str) -> float | None:
        return None


def test_degraded_quote_explicit_in_conclusion():
    s = _full_session(provider=NoQuoteProvider())
    res = s.confirm("confirm")
    c = res["conclusion"]
    assert "行情接口降级" in c.personalization.cost_line
    assert c.degrade_note  # 研报降级同样明示


# ---------------------------------------------------------------- 噪音校验断言

def test_noise_validate_rejects_bad_standard():
    assert validate_noise({"text": "t", "reason": "r", "standard": "胡说"}) is None


def test_noise_validate_rejects_missing_fields():
    assert validate_noise({"reason": "r", "standard": "信源"}) is None
    assert validate_noise({"text": "t", "standard": "信源"}) is None


def test_noise_validate_accepts_valid():
    n = validate_noise({"text": "t", "reason": "r", "standard": "时效", "source": "s"})
    assert isinstance(n, NoiseItem)
    assert n.standard == "时效" and n.text == "t"
