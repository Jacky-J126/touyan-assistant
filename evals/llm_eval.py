"""真实 LLM Judge 双评评测（评测方案 3.2 执行层，阶段 4）。

用法（本地，需两套 Judge 配置）：
    JUDGE_MODEL_A_API_KEY=… JUDGE_MODEL_A_BASE_URL=… \
    JUDGE_MODEL_B_API_KEY=… JUDGE_MODEL_B_BASE_URL=… \
    python -m evals.llm_eval                 # 全部黄金集样本
    python -m evals.llm_eval --limit 6       # 抽样（快速联调）
    python -m evals.llm_eval --dims j1,j4    # 只跑部分维度

双评 + 仲裁：A/B 两个模型对同一批样本独立评分；同一样本同维度分差 ≥2
（或任一模型返回空判定）标记转人工仲裁，报告逐条列出。输出
evals/llm-report.md（摘要）+ evals/llm-report.json（逐行结果，CI artifact）。

判官提示词 evals/judges/j*.md 为评测方案 3.2 逐字内容；占位符仅作渲染
机制（J1/J2 的黄金列表占位符在阶段 4 拆分命名，判定标准未动一字）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.orchestrator import Session
from evals.datasets import Scenario
from evals.judges import LLMJudge
from evals.runner import (
    RECOVERY_MSG,
    REFUSAL_MSGS,
    load_golden,
    new_session,
    run_e2e,
)

REPORT_MD = Path(__file__).resolve().parent / "llm-report.md"
REPORT_JSON = Path(__file__).resolve().parent / "llm-report.json"
PROMPT_FILES = {
    "j1": "j1-noise.md",
    "j2": "j2-fact-infer.md",
    "j3": "j3-compliance.md",
    "j4": "j4-personalize.md",
}


# ------------------------------------------------------------------ 变量渲染


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items)) or "（空）"


def render_j1(sc: Scenario, sample) -> dict:
    keep = _numbered([g["text"] for g in sc.gold_keep])
    noise = _numbered(
        [f"{g['text']}（命中标准：{g.get('standard', '')}）" for g in sc.gold_filter]
    )
    panel = "\n".join(
        f"- 【噪音】{n.text}（{n.source}｜{n.standard}｜{n.reason}）"
        for n in sample.conclusion.noise
    ) or "（无噪音面板）"
    panel = f"{panel}\n摘要：{sample.conclusion.noise_summary}"
    return {
        "标的": sc.stock,
        "事件": sc.event,
        "关键信息编号列表": keep,
        "噪音编号列表": noise,
        '过滤后输出全文，含"已过滤噪音"面板': panel,
    }


def render_j2(sc: Scenario, sample) -> dict:
    facts = _numbered(sample.gold_facts)
    infers = _numbered(
        [
            f"{i.text}（假设：{i.assumption}；置信度：{i.confidence}）"
            for i in sc.infers
        ]
    )
    unknowns = _numbered([u.text for u in sc.unknowns])
    c = sample.conclusion
    full = ["【事实】"] + [
        f"- {f.text}（{f.source} · {f.timepoint}）" for f in c.facts
    ]
    full += ["【推断】"] + [
        f"- {i.text}（假设：{i.assumption}；置信度：{i.confidence}）" for i in c.infers
    ]
    full += ["【未知】"] + [f"- {u.text}（{u.action}）" for u in c.unknowns]
    return {
        "事实编号列表": facts,
        "推断编号列表，含假设与置信度": infers,
        "未知编号列表": unknowns,
        "带标签的解读全文": "\n".join(full),
    }


def _refusal_replies(sc: Scenario, holdings: dict) -> list[dict]:
    """拒答升级支线全程回复（引导 → 停止 → 合规话题恢复）。"""
    sess: Session = new_session(sc)
    sess.ask(sc.question)
    sess.submit_clarify(holdings["cost"], holdings["ratio"], holdings["horizon"])
    if sess.stage == "confirm":
        sess.confirm("confirm")
    replies = [sess.followup(msg) for msg in REFUSAL_MSGS] + [sess.followup(RECOVERY_MSG)]
    return replies


def render_j3(sc: Scenario, holdings: dict) -> dict:
    replies = _refusal_replies(sc, holdings)
    text = []
    for r in replies:
        if r["stage"] == "refused":
            text.append(
                f"【拒答】{r['opening']}\n理由：{'；'.join(x[1] for x in r['reasons'])}"
                f"\n风险：{'；'.join(x[1] for x in r['risks'])}\n清单：{list(r['checklist'])}"
            )
        elif r["stage"] == "guided":
            text.append(f"【再引导】{r['text']}")
        elif r["stage"] == "stopped":
            text.append(f"【停止作答】{r['text']}")
        else:
            text.append(f"【恢复/答复】{r.get('answer', r.get('text', ''))}")
    return {
        "用户提问历史与解读内容摘要": (
            f"用户先问：{sc.question}；完成澄清与解读后，连续追问买卖建议 3 次，"
            f"停止后问合规话题「{RECOVERY_MSG}」。"
        ),
        "待评测回复全文": "\n\n".join(text),
    }


def render_j4(holdings: dict, sample) -> dict:
    p = sample.conclusion.personalization
    return {
        "占比/成本/期限，来自澄清环节的真实输入": (
            f"占比 {holdings['ratio']}%｜成本 ¥{holdings['cost']}｜期限 {holdings['horizon']}"
        ),
        "「与你何干」段全文，含 verdict 句": "\n".join(
            [
                f"权重判定：{p.weight_verdict}",
                f"期限：{p.horizon_line}",
                f"成本：{p.cost_line}",
                f"口径说明：{p.caliber_note}",
            ]
        ),
    }


# ------------------------------------------------------------------ 执行


def _parse_args(argv: list[str]) -> tuple[int, list[str]]:
    limit = 30
    dims = ["j1", "j2", "j3", "j4"]
    for i, arg in enumerate(argv):
        if arg == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if arg == "--dims" and i + 1 < len(argv):
            dims = argv[i + 1].split(",")
    return limit, dims


def main() -> None:
    limit, dims = _parse_args(sys.argv[1:])
    judges = {"A": LLMJudge("A"), "B": LLMJudge("B")}
    missing = [role for role, j in judges.items() if not j.available()]
    if missing:
        print(
            f"缺少 Judge 配置：{missing}（需 JUDGE_MODEL_{missing[0]}_BASE_URL + "
            f"JUDGE_MODEL_{missing[0]}_API_KEY）。双评无法执行，退出。"
        )
        sys.exit(1)

    golden = load_golden()[:limit]
    rows: list[dict] = []
    for sc in golden:
        for h in sc.holdings_variants:
            sample = run_e2e(sc, h)
            vars_by_dim = {
                "j1": render_j1(sc, sample),
                "j2": render_j2(sc, sample),
                "j4": render_j4(h, sample),
            }
            if "j3" in dims:
                vars_by_dim["j3"] = render_j3(sc, h)
            for dim in dims:
                row = {"sid": sample.sid, "dim": dim}
                for role, judge in judges.items():
                    result = judge.judge(PROMPT_FILES[dim], vars_by_dim[dim])
                    row[f"score_{role}"] = result.get("score")
                    row[f"reason_{role}"] = result.get("reason", "")
                    row[f"empty_{role}"] = not result
                a, b = row["score_A"], row["score_B"]
                if a is None or b is None or abs(a - b) >= 2:
                    row["arbitration"] = True
                rows.append(row)

    verdicts = {}
    for dim in dims:
        pairs = [(r["score_A"], r["score_B"]) for r in rows if r["dim"] == dim]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if pairs:
            verdicts[dim] = {
                "samples": len(pairs),
                "avg_A": round(sum(a for a, _ in pairs) / len(pairs), 3),
                "avg_B": round(sum(b for _, b in pairs) / len(pairs), 3),
                "agreement": round(
                    sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 3
                ),
            }
    arbitrations = [r for r in rows if r.get("arbitration")]

    REPORT_JSON.write_text(
        json.dumps({"verdicts": verdicts, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# LLM Judge 双评报告",
        "",
        f"- 样本：{len(golden)} 场景 × 3 持仓；维度：{', '.join(dims)}",
        f"- 判官：{os.environ.get('JUDGE_MODEL_A_MODEL', '未配置模型名')} / "
        f"{os.environ.get('JUDGE_MODEL_B_MODEL', '未配置模型名')}",
        "",
        "| 维度 | 样本数 | A 均分 | B 均分 | 一致率(差≤1) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for dim, v in verdicts.items():
        lines.append(
            f"| {dim} | {v['samples']} | {v['avg_A']} | {v['avg_B']} | {v['agreement']} |"
        )
    lines += ["", f"## 转人工仲裁（{len(arbitrations)} 条）", ""]
    if arbitrations:
        for r in arbitrations:
            lines.append(
                f"- `{r['sid']}`（{r['dim']}）：A={r['score_A']}，B={r['score_B']}；"
                f"A 依据：{r.get('reason_A', '（空判定）')[:60]}"
            )
    else:
        lines.append("无。")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\n逐行结果：{REPORT_JSON}")


if __name__ == "__main__":
    main()
