"""评测 runner 全链路冒烟元测试：数据集 → 管线 → Judge → 报告。

本测试跑完整评测（约 200 条执行记录，mock 环境秒级完成），断言：
- 红线（无容差 13 条）全部通过、门槛全部通过；
- 灵敏度样本（d4-f7 绝对化表述）被断言捕获；
- Demo 漂移防护通过（G1-v01 与演示内容逐字一致）；
- 报告文件落盘。

红线不过时本测试必须失败——评测体系的存在意义就是拦住回归。
"""

from __future__ import annotations

from pathlib import Path

from evals.report import REPORT_PATH
from evals.runner import (
    check_demo_drift,
    collect_metrics,
    evaluate_thresholds,
    load_adversarial,
    load_golden,
    main,
    run_e2e,
)


def test_full_chain_all_red_lines_pass():
    main()  # 全量执行 + 报告落盘
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert "✅ 全部通过" in report  # 红线总体
    assert "d4-f7" in report  # 灵敏度样本捕获
    assert "逐字一致" in report  # Demo 漂移防护


def test_demo_drift_guard():
    g1_v01 = next(s for s in load_golden() if s.variant_id == "G1-v01")
    assert check_demo_drift(g1_v01) == []


def test_runner_pieces_compose():
    """runner 各段可独立组合：加载 → 执行 → 汇总 → 阈值判定。"""
    golden = load_golden()
    adversarial = load_adversarial()
    assert len(golden) == 30 and len(adversarial) >= 40
    # 冒烟：每个黄金变体跑一组持仓即可验证汇总口径
    samples = []
    for sc in golden[:3]:
        samples.append(run_e2e(sc, sc.holdings_variants[0]))
    metrics = collect_metrics(samples)
    verdict = evaluate_thresholds(metrics)
    assert verdict["red_line_pass"] is True
    assert "total" in metrics and 0.0 <= metrics["total"] <= 1.0


def test_report_path_is_in_evals_dir():
    assert REPORT_PATH == Path(__file__).resolve().parent.parent / "evals" / "latest-report.md"
