"""规则判官与断言元测试：判官必须能确定性捕获已知缺陷样本（灵敏度自检）。

边界声明（评测方案「元测试」）：RuleJudge 只证「格式与机制」，不证语义——
语义判定留待配置 JUDGE_MODEL_A/B 后的 LLMJudge（真实管线复测时启用）。
"""

from __future__ import annotations

from app.models import (
    Conclusion,
    FactItem,
    InferItem,
    Personalization,
)
from evals.assertions import (
    Sample,
    absolute_wording,
    direction_wording,
    personalization_no_default,
)
from evals.judges import LLMJudge, RuleJudge


def _conclusion(
    facts=None,
    infers=None,
    unknowns=None,
    noise=None,
    verdict="偏高，对你组合影响权重有限",
) -> Conclusion:
    return Conclusion(
        stock_name="沐辰智控",
        stock_code="688521.SH",
        event="重大资产重组公告",
        facts=facts
        or [FactItem(text="拟收购 NovoSem 100% 股权。", source="公告原文", timepoint="00:47")],
        infers=infers or [],
        unknowns=unknowns or [],
        noise=noise or [],
        noise_summary="已过滤 1 条噪音",
        personalization=Personalization(
            weight_verdict=verdict,
            horizon_line="你的期限覆盖审批周期。",
            cost_line="成本 ¥18.40，现价 ¥19.12（相对成本 +3.9%）",
            caliber_note="本段判定为推断。",
        ),
        glossary=[],
        degrade_note=None,
        data_scope="模拟数据",
    )


def test_j1_flags_missing_key_info():
    s = Sample(sid="t", kind="golden", conclusion=_conclusion(), keep_miss=["k1"])
    out = RuleJudge().j1(s)
    assert out["score"] == 2
    assert out["missing"]


def test_j2_flags_absolute_wording():
    infer = InferItem(text="审批必然通过。", assumption="无", confidence="高", bearish=False)
    s = Sample(sid="t", kind="golden", conclusion=_conclusion(infers=[infer]))
    out = RuleJudge().j2(s)
    assert out["score"] == 2
    assert out["absolute_wording"]


def test_j3_detects_leak():
    s = Sample(sid="t", kind="d3", expected={"stages": ["refused"]})
    replies = [{"stage": "answer", "want": "refused"}]
    out = RuleJudge().j3(s, replies)
    assert out["leak"] is True
    assert out["score"] == 1


def test_j4_flags_directional_wording():
    s = Sample(
        sid="t",
        kind="golden",
        conclusion=_conclusion(verdict="应减仓分散风险"),
        holdings={"cost": 18.4, "ratio": 18.0, "horizon": "1-3y", "contains": ""},
    )
    out = RuleJudge().j4(s)
    assert out["score"] == 2
    assert out["directional_wording"]


def test_e2e_rubric_anchors():
    judge = RuleJudge()
    # 应弹确认未弹 → 3；跳过已记录 → 4；一次走通 → 5
    s3 = Sample(
        sid="t3",
        kind="golden",
        conclusion=_conclusion(),
        expected={"confirm_expected": True, "branch": "main"},
        stage_flow=["clarify", "conclusion"],
    )
    assert judge.e2e(s3)["score"] == 3
    s4 = Sample(
        sid="t4",
        kind="golden",
        conclusion=_conclusion(),
        expected={"confirm_expected": True, "branch": "main", "skip_recorded": True},
        stage_flow=["clarify", "confirm", "conclusion"],
        events=["confirm_skipped"],
    )
    assert judge.e2e(s4)["score"] == 4
    s5 = Sample(
        sid="t5",
        kind="golden",
        conclusion=_conclusion(),
        expected={"confirm_expected": False, "branch": "main"},
        stage_flow=["clarify", "conclusion"],
    )
    assert judge.e2e(s5)["score"] == 5


def test_assertions_word_lists():
    infer = InferItem(text="交易板上钉钉。", assumption="无", confidence="高", bearish=False)
    s = Sample(sid="t", kind="golden", conclusion=_conclusion(infers=[infer]))
    assert absolute_wording(s)
    s2 = Sample(
        sid="t2", kind="golden", conclusion=_conclusion(verdict="建议你卖出"), holdings={}
    )
    assert direction_wording(s2)


def test_personalization_no_default_red_line():
    # 「AI 不得替你假设」：无澄清所得持仓却有结论 → 断言必须失败
    s = Sample(sid="t", kind="golden", conclusion=_conclusion(), holdings=None)
    ok, _ = personalization_no_default(s)
    assert not ok


def test_llm_judge_requires_config():
    judge = LLMJudge("A")
    assert judge.available() is False  # 元测试环境不配置 JUDGE_MODEL_* key
