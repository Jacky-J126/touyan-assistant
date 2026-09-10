"""CLI 复现 G1 场景全流程与三条支线。

运行：.venv/bin/python scripts/demo.py（零 key，mock 模式）

三个演示：
1. 主流程：触达 → 提问 → 澄清（HITL#1）→ 检索（含降级）→ 确认（HITL#2）→ 带标签结论
   → 买卖追问拒答 → 追问 1 再引导 → 追问 2 停止作答 → 合规话题恢复（HITL#3 全链）
2. 事实核实支线：D2-Q2「消息靠谱吗」→ 跳过澄清直接答复
3. 降级支线：行情不可用 → 结论中明示降级，个性化段口径显式化
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import mockdata as md  # noqa: E402
from app.datasources.mock import MockProvider  # noqa: E402
from app.llm.mock import MockLLM  # noqa: E402
from app.orchestrator import Session  # noqa: E402

QUESTION = "沐辰智控今天这个收购公告，对我的持仓有什么影响？"


def hr(title: str) -> None:
    print()
    print("═" * 72)
    print(f"  {title}")
    print("═" * 72)


def show_facts(items) -> None:
    for f in items:
        print(f"  · {f.text}")
        print(f"      （{f.source} · {f.timepoint}）")


def show_infers(items) -> None:
    for i in items:
        print(f"  · {i.text}")
        tags = f"      [假设] {i.assumption}　[置信度] {i.confidence}"
        print(tags + ("　[利空性质]" if i.bearish else ""))


def show_unknowns(items) -> None:
    for u in items:
        print(f"  · {u.text}　【{u.action}】")


def show_recall(res) -> None:
    for it in res["recall"].items:
        mark = {"recalled": "✓", "partial": "△", "degraded": "✗"}[it.status]
        print(f"  {mark} [{it.source_type.value}] {it.source_name} · {it.timestamp}")
        print(f"      {it.content}")
    if res["recall"].degrade_note:
        print(f"  ⚠ 降级：{res['recall'].degrade_note}")
    print(f"  🗑 已过滤噪音：{res['noise'].summary}")
    for n in res["noise"].noise:
        print(f"      · {n.text}（{n.source}）")
        print(f"        [命中标准·{n.standard}] {n.reason}")


def show_conclusion(res) -> None:
    c = res["conclusion"]
    print(f"  {c.stock_name}（{c.stock_code}）· {c.event}")
    if c.degrade_note:
        print(f"  ⚠ {c.degrade_note}")
    print("  【事实】发生了什么")
    show_facts(c.facts)
    print("  【推断】可能的影响（附假设，可能出错）")
    show_infers(c.infers)
    print("  【未知】尚待确认")
    show_unknowns(c.unknowns)
    print(f"  🗑 已过滤的噪音：{c.noise_summary}（{len(c.noise)} 条，逐条附理由与标准）")
    print("  🙋 与你何干")
    print(f"     · 权重：{c.personalization.weight_verdict}")
    print(f"     · 期限：{c.personalization.horizon_line}")
    print(f"     · 位置：{c.personalization.cost_line}")
    print(f"     · 口径：{c.personalization.caliber_note}")
    print(f"     · 术语白话（{len(c.glossary)} 条）: " + "、".join(t for t, _ in c.glossary))
    print(f"  📌 {c.data_scope}")


def show_metrics(s: Session, title: str = "会话指标") -> None:
    print(f"\n  {title}: {s.events.metrics()}")


def run_main_flow() -> None:
    """主流程 + 拒答升级全链（HITL#1/#2/#3）。"""
    s = Session(llm=MockLLM(), provider=MockProvider())
    hr("演示 1/3 · 主流程（触达 → 解读 → 拒答升级 → 恢复）")

    res = s.touch()
    print(f"\n🔔 P0 触达：{res['title']}")
    print(f"   {res['meta']}")
    show_facts(res["facts"])

    print(f"\n🙋 P1 提问：{QUESTION}")
    res = s.ask(QUESTION)
    print(f"   ① 意图理解 → {res['intent_line']}")
    print(f"   ② 澄清（HITL#1）：{res['reason']}")

    print("\n📝 P2 澄清提交：成本 ¥18.40 · 占比 18.0% · 期限 1-3y（示例持仓，演示数据）")
    res = s.submit_clarify(cost=18.40, ratio=18.0, horizon="1-3y")
    print("\n🔍 P3 检索（多源召回 + 噪音过滤 + 降级明示）：")
    show_recall(res)
    counts = (
        f"事实 {len(res['facts'])} 条 / 未知 {len(res['unknowns'])} 条 / "
        f"推断 {len(res['infers'])} 条"
    )
    print(f"   ⑥ {counts}")
    print(f"\n⚖ P4 结论前确认（HITL#2）触发：{res['confirm_reason']}")
    print(f"   {res['scope']}")

    print("\n✅ 用户：认可，按此范围生成解读")
    res = s.confirm("confirm")
    print("\n📄 P5 带标签结论：")
    show_conclusion(res)

    print("\n🛡 P6 追问 1（买卖请求）→ 拒答")
    res = s.followup("那我该买入还是卖出？")
    print(f"   {res['opening']}")
    for title, detail in res["reasons"]:
        print(f"   · {title}：{detail}")
    print("   · 风险信息 " + "、".join(t for t, _ in res["risks"]))
    print("   · 自检清单：买 / 卖 / 持有各 2 条")

    print("\n🛡 追问 2（坚持）→ 再引导")
    res = s.followup("还是想加仓，能不能买？")
    print(f"   {res['text']}")

    print("\n🛡 追问 3（仍坚持）→ 停止作答")
    res = s.followup("别绕了，就告诉我能不能买")
    print(f"   {res['text']}")

    print("\n🔁 合规话题 → 恢复正常服务")
    res = s.followup("重大资产重组是什么意思？")
    print(f"   {res['answer']}")

    show_metrics(s)


def run_fact_check_branch() -> None:
    """D2-Q2 事实核实支线：跳过澄清。"""
    s = Session(llm=MockLLM(), provider=MockProvider())
    hr("演示 2/3 · 事实核实支线（D2-Q2「消息靠谱吗」，跳过澄清）")

    s.touch()
    print("\n🙋 提问：这条收购消息靠谱吗？")
    res = s.ask("这条收购消息靠谱吗？")
    print(f"   ① 意图理解 → {res['intent_line']}")
    print("   答复：")
    for line in res["answer"].splitlines():
        print(f"   {line}")
    show_metrics(s)


class NoQuoteProvider(MockProvider):
    """行情接口不可用（降级支线演示）。"""

    def quote(self, stock_code: str) -> float | None:
        return None


def run_degraded_branch() -> None:
    """降级支线：行情不可用 → 个性化段明示降级。"""
    s = Session(llm=MockLLM(), provider=NoQuoteProvider())
    hr("演示 3/3 · 降级支线（行情接口不可用 → 明示不足，不假装完整）")

    s.touch()
    s.ask(QUESTION)
    res = s.submit_clarify(cost=18.40, ratio=18.0, horizon="1-3y")
    print(f"   ⚖ 确认触发：{res['confirm_reason']}")
    res = s.confirm("skip")
    print("\n   📄 结论（跳过确认，跳过被记录）：")
    show_conclusion(res)
    assert s.confirm_skipped == 1
    show_metrics(s)


def main() -> None:
    print(f"看懂你的自选股 · Mock 演示（G1：{md.STOCK_NAME} {md.STOCK_CODE}）")
    print("全部为模拟数据，不构成投资建议。零 key 可跑；配置 LLM_API_KEY 后走真实管线。")
    run_main_flow()
    run_fact_check_branch()
    run_degraded_branch()
    print("\n✅ 三支线全部跑通。")


if __name__ == "__main__":
    main()
