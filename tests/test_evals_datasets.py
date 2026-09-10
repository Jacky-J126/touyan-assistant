"""评测数据集元测试（评测方案「元测试」边界：数据加载是评测体系自身代码）。

验证：
- 黄金集 G1–G3 规模（>=30 变体，每变体 3 组持仓参数）；
- 拓展集 D1–D7 规模（>=40 条目）与 kind 分布；
- 变体渲染（模板占位符全部替换、drop_noise 生效、gold_filter 同步剔除）；
- 所有场景的持仓参数合法（澄清校验可过）。
"""

from __future__ import annotations

from app.pipeline.clarify import validate_clarify
from evals.datasets import load_adversarial, load_golden, overlaps


def test_golden_scale_and_holdings():
    golden = load_golden()
    assert len(golden) >= 30
    assert {s.variant_id.split("-")[0] for s in golden} == {"G1", "G2", "G3"}
    for s in golden:
        assert len(s.holdings_variants) == 3
        for h in s.holdings_variants:
            # 每一组持仓参数都必须能通过真实澄清校验（「AI 不得替你假设」）
            assert not validate_clarify(h["cost"], h["ratio"], h["horizon"])


def test_adversarial_scale_and_kinds():
    adv = load_adversarial()
    assert len(adv) >= 40
    kinds = {c.kind for c in adv}
    assert kinds == {"d1", "d2", "d3", "d4", "d5", "d6", "d7"}


def test_golden_variant_rendering_no_placeholder_leak():
    """模板占位符必须全部渲染（{xxx} 残留 = 渲染失败）。"""
    golden = load_golden()
    for s in golden:
        joined = "".join(
            [s.event, s.push_title, s.question]
            + [i.content for i in s.recall_items]
            + [f.text for f in s.facts]
            + [i.text for i in s.infers]
            + [g["keyword"] + g["text"] for g in s.gold_keep]
        )
        assert "{" not in joined and "}" not in joined, f"{s.variant_id} 存在未渲染占位符"


def test_drop_noise_variants_remove_noise_and_gold_filter():
    golden = load_golden()
    dropped = [s for s in golden if s.variant_id.endswith("-v05")]
    assert dropped, "应有 drop_noise 变体（v05）"
    for s in dropped:
        # v05 场景噪音池少于同场景 v01，且黄金过滤清单同步剔除
        v01 = next(x for x in golden if x.variant_id == s.variant_id.split("-")[0] + "-v01")
        assert len(s.noise) < len(v01.noise)
        assert len(s.gold_filter) < len(v01.gold_filter)


def test_overlaps_measure():
    assert overlaps("半导体设备板块大涨", "半导体设备板块因海外政策大涨，多股涨停。") >= 0.6
    assert overlaps("三个月前拟回购公告", "三个月前公告：拟回购不超过 5 亿元") >= 0.6
    assert overlaps("完全无关", "沐辰智控拟收购 NovoSem 100% 股权") < 0.6
    assert overlaps("", "任意文本") == 0.0
