"""⑧ 结论前确认（HITL#2）：条件化触发 + 跳过必被记录。

D6 样本：H1 低推断无利空不弹 / H2 全事实不弹 / H3 高推断含利空必弹且注明原因 /
H4 应弹场景点跳过 → 结论照常输出且跳过被记录。
"""

from __future__ import annotations

from app import mockdata as md
from app.llm.mock import MockLLM
from app.models import FactItem, InferItem
from app.orchestrator import Session
from app.pipeline.confirm import CONFIRM_INFER_RATIO, confirm_needed, infer_ratio

QUESTION = "沐辰智控今天这个收购公告，对我的持仓有什么影响？"


def _fact(text: str) -> FactItem:
    return FactItem(text=text, source="s", timepoint="t")


def _infer(text: str, bearish: bool = False) -> InferItem:
    return InferItem(text=text, assumption="a", confidence="中", bearish=bearish)


def _session_to_confirm() -> Session:
    s = Session(llm=MockLLM())
    s.touch()
    s.ask(QUESTION)
    res = s.submit_clarify(cost=18.40, ratio=18.0, horizon="1-3y")
    assert res["stage"] == "confirm"  # G1：3 推断（含 1 利空）/ 4 事实 → 必弹（H3）
    return s


# ---------------------------------------------------------------- 触发判断

def test_h1_low_inference_no_bearish_not_needed():
    needed, reason = confirm_needed([_fact("f") for _ in range(5)], [_infer("i")])
    assert not needed
    assert reason == ""


def test_h2_all_facts_not_needed():
    needed, _ = confirm_needed([_fact("f") for _ in range(4)], [])
    assert not needed


def test_h3_g1_scenario_needed_with_reason():
    needed, reason = confirm_needed(md.G1_FACTS, md.G1_INFERS)
    assert needed
    assert "推断占比高" in reason
    assert "利空" in reason


def test_bearish_alone_triggers():
    needed, reason = confirm_needed([_fact("f") for _ in range(10)], [_infer("i", bearish=True)])
    assert needed
    assert "利空" in reason
    assert "推断占比高" not in reason


def test_ratio_boundary():
    ratio = infer_ratio([_fact("a"), _fact("b"), _fact("c")], [_infer("x"), _infer("y")])
    assert ratio >= CONFIRM_INFER_RATIO
    assert infer_ratio([], []) == 0.0


# ---------------------------------------------------------------- H4 跳过必记录

def test_h4_skip_recorded_and_conclusion_delivered():
    s = _session_to_confirm()
    res = s.confirm("skip")
    assert res["stage"] == "conclusion"
    assert s.confirm_skipped == 1
    assert s.events.count("confirm_skipped") == 1
    assert s.events.count("confirm_shown") == 1


def test_confirm_action_recorded():
    s = _session_to_confirm()
    s.confirm("confirm")
    assert s.events.has("confirm_confirmed")


def test_decline_reruns_analysis():
    """不认可 → 真实重跑 ⑦，不是换话术。"""
    s = _session_to_confirm()
    res = s.confirm("decline")
    assert s.reanalyze_count == 1
    assert s.events.count("reanalyze") == 1
    assert res["stage"] in ("confirm", "conclusion")
    if res["stage"] == "confirm":
        assert "重新分析" in res["reanalyze_note"]
