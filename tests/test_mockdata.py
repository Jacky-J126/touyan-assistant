"""G1 场景模拟数据完整性：数量、标签格式、降级与模拟声明。

内容与交互原型 V0.2 逐字对应；测试锁定这些基线，防止改坏演示场景。
"""

from __future__ import annotations

from app import mockdata as md
from app.models import NOISE_STANDARDS, HoldingParams, SourceType


def test_g1_counts():
    assert len(md.G1_RECALL.items) == 6
    assert len(md.G1_NOISE) == 5
    assert len(md.G1_FACTS) == 4
    assert len(md.G1_UNKNOWNS) == 2
    assert len(md.G1_INFERS) == 3
    assert len(md.G1_GLOSSARY) == 5


def test_recall_sources_cover_six_types():
    types = {i.source_type for i in md.G1_RECALL.items}
    assert types == set(SourceType)


def test_noise_standards_whitelist_and_reasons():
    for n in md.G1_NOISE:
        assert n.standard in NOISE_STANDARDS
        assert n.text and n.source and n.reason  # 每条附理由与标准（红线）


def test_facts_have_source_and_timepoint():
    for f in md.G1_FACTS + md.TOUCH_FACTS:
        assert f.text and f.source and f.timepoint


def test_unknowns_have_action():
    assert all(u.action in ("需你补充", "需你等待") for u in md.G1_UNKNOWNS)


def test_infers_have_assumption_confidence_bearish():
    for i in md.G1_INFERS:
        assert i.text and i.assumption and i.confidence
    assert [i.bearish for i in md.G1_INFERS] == [False, True, False]


def test_research_degraded_with_note():
    degraded = [i for i in md.G1_RECALL.items if i.status == "degraded"]
    assert len(degraded) == 1
    assert degraded[0].source_type == SourceType.RESEARCH
    assert "研报" in md.G1_RECALL.degrade_note


def test_demo_holdings_valid_and_not_default():
    assert md.DEMO_HOLDINGS["horizon"] in HoldingParams.HORIZONS
    assert 0 < md.DEMO_HOLDINGS["ratio"] <= 100
    # 模拟声明覆盖所有对外文案
    assert "模拟" in md.DATA_SCOPE
    assert "不构成投资建议" in md.DATA_SCOPE
