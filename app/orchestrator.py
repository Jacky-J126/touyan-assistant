"""编排层：把管线节点接成完整会话流程（PRD ①→⑩ + 三条支线）。

主流程：触达（P0）→ 提问 → 意图理解（①）→ 澄清（②③，条件化）→ 多源召回（④）
→ 噪音过滤（⑤）→ 事实提取（⑥）→ 分析生成（⑦）→ 结论前确认（⑧，条件化）
→ 带标签结论（⑨，事实/推断/未知 + 「与你何干」段 + 术语白话）

支线：
- 降级：接口超时/数据缺失 → 只给已召回事实 + 明示不足（degrade_note 全程透出）；
- 拒答：买卖追问 → 拒答 + 风险信息 + 自检清单（HITL#3）；
- 升级：追问 1 再引导、追问 2 停止作答、合规话题恢复正常服务。

埋点事件链见 events.py；每一步的 stage 与 payload 供 Streamlit UI 与 scripts/demo.py 渲染。
"""

from __future__ import annotations

from uuid import uuid4

from app import mockdata as md
from app.compliance import RefusalState, is_buy_sell_request
from app.datasources.mock import MockProvider
from app.events import EventLog
from app.llm import get_llm
from app.models import Conclusion, HoldingParams
from app.pipeline import (
    analyze,
    clarify,
    confirm,
    fact_infer,
    glossary,
    intent,
    noise_filter,
    personalization,
    recall,
)

FALLBACK_ANSWER = "我可以围绕本次解读继续解释客观信息（事实、推断假设、风险机制），随时提问。"


class Session:
    """一次「触达 → 解读 → 追问」会话的全部状态。"""

    def __init__(
        self,
        llm=None,
        provider=None,
        session_id: str | None = None,
        event_path=None,
    ):
        self.id = session_id or uuid4().hex[:8]
        self.llm = llm or get_llm()
        self.provider = provider or MockProvider()
        self.events = EventLog(path=event_path)  # 可选持久化（data/，已 gitignore）
        self.stage = "idle"
        self.question: str | None = None
        self.intent = None
        self.intent_line = ""
        self.holdings: HoldingParams | None = None
        self.recall = None
        self.noise_result = None
        self.facts: list = []
        self.unknowns: list = []
        self.infers: list = []
        self.confirm_reason = ""
        self.confirm_shown = 0
        self.confirm_skipped = 0
        self.reanalyze_count = 0
        self.conclusion: Conclusion | None = None
        self.refusal_state = RefusalState.NORMAL
        self.events.log("session_start")

    # ------------------------------------------------------------------ P0 触达

    def touch(self) -> dict:
        """触达推送：只推事实，不夹带解读与情绪。"""
        self.events.log("touch_delivered")
        self.stage = "touch"
        return {
            "stage": "touch",
            "title": md.EVENT_TITLE,
            "meta": md.TOUCH_META,
            "facts": md.TOUCH_FACTS,
        }

    # ------------------------------------------------------------------ 提问

    def ask(self, question: str) -> dict:
        self.question = question
        self.events.log("question_asked", question=question)
        self.intent = intent.run_intent(self.llm, question)
        it = self.intent
        if it.intent_type == "持仓影响":
            self.intent_line = f"识别为「{it.stock} {it.event}对持仓的影响」提问"
            # 条件化澄清（S5）：仅在缺失会改变结论方向时问——持仓影响类缺三要素必问；
            # 上下文充分（本会话已澄清过）则跳过
            if self.holdings is None:
                self.stage = "clarify"
                self.events.log("clarify_shown")
                return {
                    "stage": "clarify",
                    "reason": clarify.CLARIFY_REASON,
                    "intent_line": self.intent_line,
                    "question": question,
                }
            return self._retrieve_and_analyze()
        # 事实核实（D2-Q2「消息靠谱吗」）：上下文充分，跳过澄清，不重新索要持仓
        self.intent_line = (
            f"识别为「{it.stock} {it.event}」事实核实提问，上下文充分，跳过澄清"
        )
        self.stage = "answer"
        self.events.log("answer_delivered")
        return {
            "stage": "answer",
            "intent_line": self.intent_line,
            "answer": self._fact_check_answer(),
        }

    def _fact_check_answer(self) -> str:
        """事实核实类答复：事实有信源、推断附假设，无个性化段。"""
        rec = recall.run_recall(self.provider, self.intent.code)
        fi = fact_infer.run_fact_infer(self.llm, rec)
        infers = analyze.run_analyze(self.llm, rec, fi.facts)
        lines = ["这条消息的事实部分："]
        lines += [f"· {f.text}（{f.source} · {f.timepoint}）" for f in fi.facts]
        lines.append("相关推断（未发生，附假设）：")
        lines += [f"· {i.text}（假设：{i.assumption}；置信度：{i.confidence}）" for i in infers]
        return "\n".join(lines)

    # ------------------------------------------------------------------ 澄清（HITL#1）

    def submit_clarify(self, cost, ratio, horizon) -> dict:
        """澄清阻断：缺任一持仓字段返回错误，无法提交。"""
        errors = clarify.validate_clarify(cost, ratio, horizon)
        if errors:
            return {"stage": "clarify", "errors": errors}
        self.holdings = clarify.build_holdings(cost, ratio, horizon)
        self.events.log("clarify_submitted", cost=cost, ratio=ratio, horizon=horizon)
        return self._retrieve_and_analyze()

    # ------------------------------------------------------------------ ④⑤⑥⑦ + ⑧ 触发判断

    def _retrieve_and_analyze(self) -> dict:
        self.stage = "recall"
        self.events.log("recall_started")
        self.recall = recall.run_recall(self.provider, self.intent.code)
        if self.recall.degrade_note:
            self.events.log("degraded", note=self.recall.degrade_note)
        self.noise_result = noise_filter.run_noise_filter(self.llm, self.recall)
        self.events.log("noise_filtered", filtered=len(self.noise_result.noise))
        fi = fact_infer.run_fact_infer(self.llm, self.recall)
        self.facts, self.unknowns = fi.facts, fi.unknowns
        self.events.log("facts_extracted", facts=len(self.facts), unknowns=len(self.unknowns))
        self.infers = analyze.run_analyze(self.llm, self.recall, self.facts)
        self.events.log("analysis_generated", infers=len(self.infers))
        self.events.log("personalized_rendered")  # 「与你何干」段随结论渲染（V0.2 埋点）
        needed, reason = confirm.confirm_needed(self.facts, self.infers)
        if needed:
            self.stage = "confirm"
            self.confirm_reason = reason
            return self._confirm_payload()
        return self._build_conclusion()

    def _confirm_payload(self, note: str | None = None) -> dict:
        self.confirm_shown += 1
        self.events.log("confirm_shown", reason=self.confirm_reason)
        return {
            "stage": "confirm",
            "intent_line": self.intent_line,
            "recall": self.recall,
            "noise": self.noise_result,
            "facts": self.facts,
            "unknowns": self.unknowns,
            "infers": self.infers,
            "confirm_reason": self.confirm_reason,
            "scope": md.CONFIRM_SCOPE,
            "rule_hint": md.CONFIRM_RULE_HINT,
            "reanalyze_note": note,
        }

    # ------------------------------------------------------------------ ⑧ 确认（HITL#2）

    def confirm(self, action: str) -> dict:
        if action == "confirm":
            self.events.log("confirm_confirmed")
            return self._build_conclusion()
        if action == "skip":
            self.confirm_skipped += 1
            self.events.log("confirm_skipped")
            return self._build_conclusion()
        # 不认可 → 回到 ⑦ 真实重跑分析（非仅换话术）
        self.reanalyze_count += 1
        self.events.log("reanalyze", count=self.reanalyze_count)
        self.infers = analyze.run_analyze(self.llm, self.recall, self.facts)
        self.events.log("analysis_generated", infers=len(self.infers))
        needed, reason = confirm.confirm_needed(self.facts, self.infers)
        if needed:
            self.stage = "confirm"
            self.confirm_reason = reason
            return self._confirm_payload(
                note=f"已按你的反馈重新分析（第 {self.reanalyze_count} 次）"
            )
        return self._build_conclusion()

    # ------------------------------------------------------------------ ⑨ 结论输出

    def _build_conclusion(self) -> dict:
        price = self.provider.quote(self.intent.code)
        per = personalization.run_personalization(self.holdings, price)
        terms = [t[0] for t in md.G1_GLOSSARY]
        self.conclusion = Conclusion(
            stock_name=self.intent.stock,
            stock_code=self.intent.code,
            event=self.intent.event,
            facts=self.facts,
            infers=self.infers,
            unknowns=self.unknowns,
            noise=self.noise_result.noise,
            noise_summary=self.noise_result.summary,
            personalization=per,
            glossary=glossary.run_glossary(self.llm, terms),
            degrade_note=self.recall.degrade_note,
            data_scope=md.DATA_SCOPE,
        )
        self.stage = "conclusion"
        self.events.log(
            "conclusion_delivered",
            facts=len(self.facts),
            infers=len(self.infers),
            unknowns=len(self.unknowns),
        )
        return {"stage": "conclusion", "conclusion": self.conclusion}

    # ------------------------------------------------------------------ ⑩ 追问 / 拒答（HITL#3）

    def followup(self, message: str) -> dict:
        self.events.log("followup_asked", message=message)
        if is_buy_sell_request(message):
            return self._handle_refusal()
        # 合规话题 → 恢复正常服务（E2：停止只针对当前话题）
        if self.refusal_state != RefusalState.NORMAL:
            self.events.log("recovery")
            self.refusal_state = RefusalState.NORMAL
        answer = glossary.answer_glossary(message) or FALLBACK_ANSWER
        self.events.log("answer_delivered")
        return {"stage": "answer", "answer": answer}

    def _handle_refusal(self) -> dict:
        s = self.refusal_state
        if s == RefusalState.NORMAL:
            self.refusal_state = RefusalState.REFUSED
            self.events.log("refusal_triggered")
            self.events.log("checklist_shown")
            return {
                "stage": "refused",
                "opening": md.REFUSAL_OPENING,
                "reasons": md.REFUSAL_REASONS,
                "risks": md.REFUSAL_RISKS,
                "checklist": md.CHECKLIST,
                "guide_hint": "坚持追问将再次引导，仍坚持即停止作答。",
            }
        if s == RefusalState.REFUSED:
            self.refusal_state = RefusalState.GUIDED
            self.events.log("escalation_guide")
            return {"stage": "guided", "text": md.GUIDE_TEXT}
        if s == RefusalState.GUIDED:
            self.refusal_state = RefusalState.STOPPED
        self.events.log("escalation_stop")
        return {"stage": "stopped", "text": md.STOP_TEXT}

    def complete_checklist(self) -> dict:
        self.events.log("checklist_completed")
        return {"stage": "checklist_done", "text": md.CHECKLIST_DONE_TEXT}
