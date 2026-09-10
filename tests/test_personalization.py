"""「与你何干」个性化段（S7）红线断言：判定与参数严格一致、措辞中性、口径显式化。

D5 边界样本：P1 阈值翻转 / P2 成本≈现价 / P3 占比极值 / P4 口径事实化。
"""

from __future__ import annotations

from app.models import HoldingParams
from app.pipeline.personalization import (
    cost_line,
    horizon_line,
    run_personalization,
    weight_verdict,
)

#: 红线词表：个性化段出现方向性词即失败（绝对化/方向化表述 0 容差）
FORBIDDEN_WORDS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "该买",
    "该卖",
    "建议",
    "应买",
    "应卖",
    "应持有",
    "值得买",
    "止盈",
    "止损",
    "抄底",
)


def assert_neutral(text: str) -> None:
    for w in FORBIDDEN_WORDS:
        assert w not in text, f"中性红线：'{w}' 出现在「{text}」"


# ---------------------------------------------------------------- P1 阈值翻转

def test_p1_threshold_flip():
    lo = weight_verdict(14.9)
    hi = weight_verdict(15.1)
    assert "偏低" in lo
    assert "高于多数持有人" in hi
    assert "模拟口径" in hi  # 相对判定必须附口径（P4）


# ---------------------------------------------------------------- P2 成本≈现价

def test_p2_cost_price_parity_exact():
    assert cost_line(18.40, 18.40) == "成本 ¥18.40，现价 ¥18.40（相对成本 +0.0%）"


def test_p2_cost_price_tenth_percent():
    assert "+0.1%" in cost_line(18.40, 18.42)
    assert "-0.1%" in cost_line(18.40, 18.38)


# ---------------------------------------------------------------- P3 占比极值

def test_p3_high_ratio_high_weight_neutral():
    v = weight_verdict(80.0)
    assert "高" in v
    assert_neutral(v)


# ---------------------------------------------------------------- P4 口径事实化

def test_p4_caliber_explicit_in_run():
    # 相对判定（中间档）必须附口径（P4）；任意档位的 caliber_note 都显式声明口径
    per = run_personalization(HoldingParams(cost=18.40, ratio=18.0, horizon="1-3y"), price=19.12)
    assert "模拟口径" in per.weight_verdict
    assert "模拟口径" in per.caliber_note
    per_hi = run_personalization(HoldingParams(cost=18.40, ratio=80.0, horizon="1-3y"), price=19.12)
    assert "模拟口径" in per_hi.caliber_note


def test_price_none_degraded_line():
    line = cost_line(18.40, None)
    assert "行情接口降级" in line  # 降级路径明示 100%


# ---------------------------------------------------------------- 全量中性断言

def test_all_outputs_neutral():
    outputs = [
        weight_verdict(5.0),
        weight_verdict(14.9),
        weight_verdict(15.1),
        weight_verdict(39.9),
        weight_verdict(40.1),
        weight_verdict(80.0),
        horizon_line("<6m"),
        horizon_line("6-12m"),
        horizon_line("1-3y"),
        horizon_line("3y+"),
        cost_line(18.40, 19.12),
        cost_line(18.40, None),
    ]
    for text in outputs:
        assert_neutral(text)
