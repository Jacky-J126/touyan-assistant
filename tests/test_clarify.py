"""③ 澄清（HITL#1）：必填阻断（红线「AI 不得替你假设」）+ 条件化触发。

代码断言 3.1「澄清阻断」：缺任一持仓字段无法提交；条件化：上下文充分时跳过。
"""

from __future__ import annotations

import pytest

from app.llm.mock import MockLLM
from app.orchestrator import Session
from app.pipeline.clarify import CLARIFY_REASON, build_holdings, validate_clarify

QUESTION = "沐辰智控今天这个收购公告，对我的持仓有什么影响？"


# ---------------------------------------------------------------- 必填校验

def test_missing_cost_blocked():
    assert "cost" in validate_clarify(None, 18.0, "1-3y")
    assert "cost" in validate_clarify(0, 18.0, "1-3y")


def test_missing_ratio_blocked():
    assert "ratio" in validate_clarify(18.40, None, "1-3y")
    assert "ratio" in validate_clarify(18.40, 150.0, "1-3y")


def test_missing_horizon_blocked():
    assert "horizon" in validate_clarify(18.40, 18.0, None)
    assert "horizon" in validate_clarify(18.40, 18.0, "5y")


def test_valid_passes():
    assert validate_clarify(18.40, 18.0, "1-3y") == {}


def test_build_holdings():
    h = build_holdings(18.40, 18.0, "1-3y")
    assert h.cost == 18.40 and h.ratio == 18.0 and h.horizon == "1-3y"
    with pytest.raises(ValueError):
        build_holdings(18.40, None, "1-3y")  # 无默认 fallback


# ---------------------------------------------------------------- 条件化澄清

def test_holding_impact_without_holdings_triggers_clarify():
    s = Session(llm=MockLLM())
    s.touch()
    res = s.ask(QUESTION)
    assert res["stage"] == "clarify"
    assert res["reason"] == CLARIFY_REASON
    assert s.events.count("clarify_shown") == 1


def test_holding_impact_with_holdings_skips_clarify():
    s = Session(llm=MockLLM())
    s.touch()
    s.ask(QUESTION)
    s.submit_clarify(cost=18.40, ratio=18.0, horizon="1-3y")
    res = s.ask("现在再看一遍，收购对我持仓的影响？")
    assert res["stage"] != "clarify"  # 上下文充分（已澄清过）→ 跳过
    assert s.events.count("clarify_shown") == 1  # 未新增澄清


def test_fact_check_question_skips_clarify():
    """D2-Q2：事实核实类提问不重新索要持仓。"""
    s = Session(llm=MockLLM())
    s.touch()
    res = s.ask("这条收购消息靠谱吗？")
    assert res["stage"] == "answer"
    assert not s.events.has("clarify_shown")
    assert "事实部分" in res["answer"]


def test_submit_clarify_errors_returned():
    s = Session(llm=MockLLM())
    s.touch()
    s.ask(QUESTION)
    res = s.submit_clarify(cost=None, ratio=18.0, horizon="1-3y")
    assert res["stage"] == "clarify"
    assert "cost" in res["errors"]
    assert s.holdings is None  # 阻断：未进入检索
