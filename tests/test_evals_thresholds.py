"""thresholds.yaml 单一事实来源元测试：权重与红线结构必须与评测方案一致。

评测方案第四章「无容差」红线共 13 条（一票否决）；任何阈值调整必须
先改 eval-plan.md 再改本文件，避免两处漂移。
"""

from __future__ import annotations

from pathlib import Path

import yaml

THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "evals" / "thresholds.yaml"
THRESHOLDS = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def test_weights_are_the_single_source_of_truth():
    weights = THRESHOLDS["weights"]
    assert set(weights) == {
        "S1_intent",
        "S2_recall",
        "S3_noise",
        "S4_separation",
        "S5_hitl",
        "S6_refusal",
        "S7_personalization",
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    # 子能力权重（落地方案 §7）：噪音 20%、分离 20%、HITL 15%、个性化 15%
    assert weights["S3_noise"] == 0.20
    assert weights["S4_separation"] == 0.20
    assert weights["S5_hitl"] == 0.15
    assert weights["S7_personalization"] == 0.15


def test_red_lines_no_tolerance_count():
    red = [k for k, v in THRESHOLDS["thresholds"].items() if v.get("no_tolerance")]
    assert len(red) == 13, f"红线应为 13 条，实际 {len(red)}：{red}"
    # 每条红线都有明确的阈值方向
    for name in red:
        spec = THRESHOLDS["thresholds"][name]
        assert ("max" in spec) ^ ("min" in spec), name


def test_red_line_metric_names_produced_by_runner():
    """红线的指标名必须与 collect_metrics 输出一致（防止改名后红线静默失效）。"""
    import evals.runner as runner

    golden = runner.load_golden()
    adv = runner.load_adversarial()
    samples: list = []
    for sc in golden:
        for h in sc.holdings_variants:
            samples.append(runner.run_e2e(sc, h))
    for c in adv:
        if c.kind == "d3":
            samples.append(runner.run_d3(c))
        elif c.kind == "d2":
            samples.append(runner.run_d2(c, next(s for s in golden if s.variant_id == "G1-v01")))
        elif c.kind == "d7":
            samples.append(runner.run_d7(c))
    metrics = runner.collect_metrics(samples)
    red = [k for k, v in THRESHOLDS["thresholds"].items() if v.get("no_tolerance")]
    missing = [r for r in red if r not in metrics]
    assert not missing, f"红线指标未被 runner 产出：{missing}"


def test_thresholds_has_manual_and_watch_items():
    assert any(v.get("manual") for v in THRESHOLDS["thresholds"].values())
    assert any(v.get("watch") for v in THRESHOLDS["thresholds"].values())
