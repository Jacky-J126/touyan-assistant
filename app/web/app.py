"""看懂你的自选股 · Web 演示（Streamlit P0–P6）。

P0 触达 → P1 提问 → P2 澄清（HITL#1）→ P3 检索（来源清单 + 噪音折叠 + 降级说明）
→ P4 结论前确认（HITL#2）→ P5 带标签结论（事实/推断/未知 + 「与你何干」+ 术语白话）
→ P6 追问（拒答 + 自检清单 + 两级升级路径）

运行：.venv/bin/streamlit run app/web/app.py
零 key 即 mock 模式（G1 场景全量演示数据）；配置 LLM_API_KEY 后走真实管线。
"""

from __future__ import annotations

import streamlit as st

from app import mockdata as md
from app.models import HoldingParams
from app.orchestrator import Session

st.set_page_config(page_title="看懂你的自选股 · Mock 演示", page_icon="📈", layout="wide")


# ---------------------------------------------------------------- 会话状态

def _sess() -> Session:
    if "sess" not in st.session_state:
        st.session_state.sess = Session()
        st.session_state.msgs = []
    return st.session_state.sess


def _push(role: str, kind: str, payload) -> None:
    st.session_state.msgs.append({"role": role, "kind": kind, "payload": payload})


def _rerun() -> None:
    st.rerun()


# ---------------------------------------------------------------- 渲染小部件

def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};padding:1px 6px;'
        f'border-radius:4px;font-weight:600">{text}</span>'
    )


def _fact_line(f) -> str:
    return f"· {f.text}　<span style='color:#888'>（{f.source} · {f.timepoint}）</span>"


def _infer_line(i) -> str:
    bear = "　⚠️ 利空性质" if i.bearish else ""
    return (
        f"· {i.text}<br>"
        f"<span style='color:#888'>假设：{i.assumption} · 置信度：{i.confidence}</span>{bear}"
    )


def _unknown_line(u) -> str:
    act = "需你补充" if u.action == "需你补充" else "需你等待"
    return f"· {u.text}　<span style='color:#888'>【{act}】</span>"


# ---------------------------------------------------------------- 各消息渲染

def _render_touch(p) -> None:
    st.info(f"**🔔 {p['title']}**")
    st.caption(p["meta"])
    st.markdown("<br>".join(_fact_line(f) for f in p["facts"]), unsafe_allow_html=True)


def _render_clarify(p) -> None:
    st.caption(f"🤖 {p['intent_line']}")
    with st.container(border=True):
        st.markdown("**先对齐你的情况，再解读——缺失会改变结论方向，AI 不会替你假设。**")
        st.markdown(p["reason"])


def _render_confirm(p) -> None:
    st.caption(f"🤖 {p['intent_line']}")
    if p.get("reanalyze_note"):
        st.info(f"🔄 {p['reanalyze_note']}")

    # ---- P3 检索过程
    with st.container(border=True):
        st.markdown("### 检索过程")
        rec = p["recall"]
        rows = []
        for it in rec.items:
            status = {"recalled": "✓ 已召回", "partial": "△ 部分", "degraded": "✗ 降级"}[it.status]
            rows.append((it.source_type.value, it.source_name, it.timestamp, it.content, status))
        st.table({
            "来源": [r[0] for r in rows],
            "渠道": [r[1] for r in rows],
            "时间": [r[2] for r in rows],
            "内容": [r[3] for r in rows],
            "状态": [r[4] for r in rows],
        })
        if rec.degrade_note:
            st.warning(f"⚠️ 降级：{rec.degrade_note}")

        with st.expander(f"已过滤噪音（{p['noise'].summary}）——逐条附理由与命中标准"):
            for n in p["noise"].noise:
                st.markdown(
                    f"· {n.text}　<span style='color:#888'>（{n.source}）</span><br>"
                    f"<span style='color:#888'>命中标准【{n.standard}】{n.reason}</span>",
                    unsafe_allow_html=True,
                )

        st.markdown("**初步提取**")
        st.markdown(
            _badge("事实", "#2e7d32") + " " + str(len(p["facts"])) + " 条　"
            + _badge("未知", "#616161") + " " + str(len(p["unknowns"])) + " 条　"
            + _badge("推断", "#ef6c00") + " " + str(len(p["infers"])) + " 条",
            unsafe_allow_html=True,
        )

    # ---- ⑧ 确认
    with st.container(border=True):
        st.markdown("### 解读前确认")
        st.markdown(p["confirm_reason"])
        st.markdown(p["scope"])
        st.caption(p["rule_hint"])


def _render_conclusion(p) -> None:
    c = p["conclusion"]
    st.markdown(f"### {_badge('结论', '#1a73e8')}　{c.stock_name}（{c.stock_code}）· {c.event}")
    if c.degrade_note:
        st.warning(f"⚠️ {c.degrade_note}")

    st.markdown("#### " + _badge("事实", "#2e7d32") + "　发生了什么")
    st.markdown("<br>".join(_fact_line(f) for f in c.facts), unsafe_allow_html=True)

    st.markdown("#### " + _badge("推断", "#ef6c00") + "　可能的影响（附假设，可能出错）")
    st.markdown("<br>".join(_infer_line(i) for i in c.infers), unsafe_allow_html=True)

    st.markdown("#### " + _badge("未知", "#616161") + "　尚待确认")
    st.markdown("<br>".join(_unknown_line(u) for u in c.unknowns), unsafe_allow_html=True)

    with st.expander(f"已过滤的噪音（{c.noise_summary}）"):
        for n in c.noise:
            st.markdown(
                f"· {n.text}　<span style='color:#888'>（{n.source}）</span><br>"
                f"<span style='color:#888'>命中标准【{n.standard}】{n.reason}</span>",
                unsafe_allow_html=True,
            )

    # ---- 与你何干（个性化段，输入全部来自澄清所得）
    with st.container(border=True):
        st.markdown("#### 🙋 与你何干")
        per = c.personalization
        verdict = f"· 权重：{per.weight_verdict}　" + _badge("推断", "#ef6c00")
        st.markdown(verdict, unsafe_allow_html=True)
        st.markdown(f"· 期限：{per.horizon_line}")
        st.markdown(f"· 位置：{per.cost_line}")
        st.caption(per.caliber_note)

    with st.expander("术语白话（新手档）"):
        for term, plain in c.glossary:
            st.markdown(f"**{term}**：{plain}")

    st.caption(f"📌 {c.data_scope}")


def _render_answer(p) -> None:
    if p.get("intent_line"):
        st.caption(f"🤖 {p['intent_line']}")
    st.markdown(p["answer"])


def _render_refused(p) -> None:
    st.markdown(f"### 🛡️ {p['opening']}")
    for title, detail in p["reasons"]:
        st.markdown(f"**{title}**：{detail}")
    with st.expander("本次事件的风险信息（4 条 · 已按客观事实整理）"):
        for title, detail in p["risks"]:
            st.markdown(f"**{title}**：{detail}")
    st.markdown("**自检清单（勾出你认同的理由，决定由你作出）**")
    for section, items in p["checklist"].items():
        st.markdown(f"*{section}*")
        for item in items:
            st.markdown(f"· {item}")
    st.caption(p["guide_hint"])


def _render_guided(p) -> None:
    st.info(p["text"])


def _render_stopped(p) -> None:
    st.warning(p["text"])


def _render_checklist_done(p) -> None:
    st.success(p["text"])


_RENDERERS = {
    "touch": _render_touch,
    "clarify": _render_clarify,
    "confirm": _render_confirm,
    "conclusion": _render_conclusion,
    "answer": _render_answer,
    "refused": _render_refused,
    "guided": _render_guided,
    "stopped": _render_stopped,
    "checklist_done": _render_checklist_done,
}


def _render_messages() -> None:
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]):
            _RENDERERS[m["kind"]](m["payload"])


# ---------------------------------------------------------------- 交互区

def _render_inputs() -> None:
    sess = _sess()

    if sess.stage in ("idle", "touch"):
        q = st.chat_input("就这次推送提问（例：收购对沐辰智控持仓有什么影响？）")
        if q:
            res = sess.ask(q)
            _push("user", "question", q)
            _push("assistant", res["stage"], res)
            _rerun()
        return

    if sess.stage == "clarify":
        with st.form("clarify_form"):
            st.markdown("#### 持仓信息（仅用于本次解读，不落库演示数据）")
            st.caption("默认已填入示例持仓（演示数据），可直接提交或自行修改。")
            c1, c2, c3 = st.columns(3)
            cost = c1.number_input(
                "持仓成本（元）", min_value=0.01, value=float(md.DEMO_HOLDINGS["cost"]),
                step=0.01, format="%.2f",
            )
            ratio = c2.number_input(
                "占总资产比（%）", min_value=0.01, max_value=100.0,
                value=float(md.DEMO_HOLDINGS["ratio"]), step=0.1,
            )
            horizon = c3.selectbox(
                "计划持有期限", HoldingParams.HORIZONS,
                index=HoldingParams.HORIZONS.index(md.DEMO_HOLDINGS["horizon"]),
            )
            submitted = st.form_submit_button("提交并开始解读")
        if st.session_state.get("clarify_errors"):
            for msg in st.session_state["clarify_errors"].values():
                st.error(msg)
            st.session_state.pop("clarify_errors")
        if submitted:
            res = sess.submit_clarify(cost, ratio, horizon)
            if res["stage"] == "clarify":
                st.session_state["clarify_errors"] = res["errors"]
                _rerun()
            submitted_text = f"成本 ¥{cost:.2f} · 占比 {ratio:.1f}% · 期限 {horizon}"
            _push("user", "clarify_submitted", submitted_text)
            _push("assistant", res["stage"], res)
            _rerun()
        return

    if sess.stage == "confirm":
        st.markdown("**请确认解读范围：**")
        c1, c2, c3 = st.columns(3)
        if c1.button("✓ 认可，按此范围生成解读", type="primary", use_container_width=True):
            res = sess.confirm("confirm")
            _push("user", "confirm_action", "认可，按此范围生成解读")
            _push("assistant", res["stage"], res)
            _rerun()
        if c2.button("↺ 不认可，重新分析", use_container_width=True):
            res = sess.confirm("decline")
            _push("user", "confirm_action", "不认可，重新分析")
            _push("assistant", res["stage"], res)
            _rerun()
        if c3.button("→ 跳过，直接生成（将计入产品信号）", use_container_width=True):
            res = sess.confirm("skip")
            _push("user", "confirm_action", "跳过，直接生成")
            _push("assistant", res["stage"], res)
            _rerun()
        return

    if sess.stage == "refused":
        st.markdown("**完成自检清单（可选，勾完代表完成一次自检）**")
        done = True
        for section, items in md.CHECKLIST.items():
            for i, item in enumerate(items):
                checked = st.checkbox(item, key=f"chk-{section}-{i}")
                done = done and checked
        if st.button("完成勾选", disabled=not done, type="primary"):
            res = sess.complete_checklist()
            _push("user", "checklist", "完成自检清单勾选")
            _push("assistant", res["stage"], res)
            _rerun()

    q = st.chat_input("继续提问…（买卖方向问题将触发拒答，合规话题恢复正常服务）")
    if q:
        _push("user", "followup", q)
        res = sess.followup(q)
        _push("assistant", res["stage"], res)
        _rerun()


# ---------------------------------------------------------------- 页面骨架

def main() -> None:
    sess = _sess()
    with st.sidebar:
        st.markdown("### 看懂你的自选股")
        st.caption(f"Mock 演示（G1 沐辰智控场景）· 会话 {sess.id}")
        st.caption(
            f"LLM 后端：{'模拟（未配置 LLM_API_KEY）' if sess.llm.mode == 'mock' else '真实接口'}　"
            f"数据源：{'模拟（provider 内置 G1）' if sess.provider.simulated else '真实'}"
        )
        st.divider()
        st.markdown("**本次会话指标**")
        st.json(sess.events.metrics())
        st.divider()
        st.caption(
            "红线：不内置默认持仓参数 · 买卖建议漏放率 0 · 标签格式断言 · "
            "统计口径显式化 · 降级路径明示。全部为模拟数据，不构成投资建议。"
        )
        if st.button("↺ 重新开始会话"):
            st.session_state.sess = Session()
            st.session_state.msgs = []
            _rerun()

    st.title("📈 看懂你的自选股")
    st.caption("噪音过滤 · 可解释解读 · 结论前确认 · 买卖拒答——AI 投研助手开源项目 Mock 演示")

    if not st.session_state.msgs:
        res = sess.touch()
        _push("assistant", res["stage"], res)
    _render_messages()
    _render_inputs()


main()
