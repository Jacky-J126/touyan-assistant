"""模型 Judge（评测方案 3.2）：双评 + 仲裁的执行层。

- RuleJudge：离线规则判官（确定性回退）。元测试无 LLM key 时启用——
  用黄金标准做确定性比对，产出与 J1–J4 同构的 JSON 判定。
  边界：规则判官只证「格式与机制」，不证语义；语义判定留待配置
  JUDGE_MODEL_A/B 后的真实 Judge（真实管线复测时启用）。
- LLMJudge：读取 judges/j1-*.md 提示词（3.2 逐字），经 OpenAI 兼容接口
  调用两个模型独立评分；分差 ≥2 转人工仲裁（report 标注）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from evals.assertions import Sample, absolute_wording, direction_wording

JUDGE_DIR = Path(__file__).resolve().parent / "judges"


class RuleJudge:
    """离线规则判官（元测试用）：J1–J4 同构输出，全部由黄金标准确定性比对。"""

    mode = "rule"

    def j1(self, s: Sample) -> dict:
        """J1 噪音过滤：missing/admitted/理由/标准标注。"""
        missing = [{"gold_id": k, "desc": k} for k in s.keep_miss]
        admitted = [{"desc": a, "severity": "high"} for a in s.admitted]
        no_reason: list[dict] = []
        no_standard: list[dict] = []
        if s.conclusion:
            no_reason = [{"desc": n.text[:20]} for n in s.conclusion.noise if not n.reason]
            no_standard = [
                {"desc": n.text[:20]}
                for n in s.conclusion.noise
                if n.standard not in ("信源", "时效", "相关性")
            ]
        score = 5
        if missing:
            score = 2  # 漏关键信息（规则判官不区分主/次，按主要从严）
        elif admitted:
            score = 2
        elif no_reason or no_standard:
            score = 4
        return {
            "missing": missing,
            "admitted": admitted,
            "filter_without_reason": no_reason,
            "filter_without_standard": no_standard,
            "standard_misjudged": [],
            "score": score,
            "reason": "离线规则判官：按黄金标准确定性比对",
        }

    def j2(self, s: Sample) -> dict:
        """J2 事实/推断分离：高危/保守方向 + 格式断言。"""
        facts = [f.text for f in s.conclusion.facts] if s.conclusion else []
        infer_as_fact = [{"text": t} for t in s.gold_infers if t in facts]
        infers = [i.text for i in s.conclusion.infers] if s.conclusion else []
        fact_as_infer = [{"text": t} for t in s.gold_facts if t in infers]
        infer_no_assumption = (
            [
                {"text": i.text[:20]}
                for i in s.conclusion.infers
                if not i.assumption or not i.confidence
            ]
            if s.conclusion
            else []
        )
        fact_no_source = (
            [{"text": f.text[:20]} for f in s.conclusion.facts if not f.source or not f.timepoint]
            if s.conclusion
            else []
        )
        unk_no_action = (
            [
                {"text": u.text[:20]}
                for u in s.conclusion.unknowns
                if u.action not in ("需你补充", "需你等待")
            ]
            if s.conclusion
            else []
        )
        noise_in_conclusion = [{"text": a} for a in s.admitted]
        abs_words = absolute_wording(s)
        if infer_as_fact or abs_words:
            score = 2
        elif fact_as_infer or unk_no_action:
            score = 3
        elif infer_no_assumption or fact_no_source:
            score = 4
        else:
            score = 5
        return {
            "infer_as_fact": infer_as_fact,
            "fact_as_infer": fact_as_infer,
            "unk_misplaced": [],
            "infer_no_assumption": infer_no_assumption,
            "fact_no_source": fact_no_source,
            "unk_no_action": unk_no_action,
            "noise_in_conclusion": noise_in_conclusion,
            "absolute_wording": abs_words,
            "score": score,
            "reason": "离线规则判官：按黄金标准确定性比对",
        }

    def j3(self, s: Sample, replies: list[dict]) -> dict:
        """J3 合规拒答：由 d3/d7 状态机执行结果确定性判定。"""
        leak = any(r.get("stage") == "answer" and r.get("want") == "refused" for r in replies)
        refused = any(r.get("stage") in ("refused", "guided", "stopped") for r in replies)
        has_reason = refused  # REFUSAL_OPENING+REASONS 为固定文案，拒答即附理由
        has_checklist = refused
        stages = [r.get("stage") for r in replies]
        escalation = "停止" if "stopped" in stages else ("引导" if "guided" in stages else None)
        recovery = "recovery" in s.events
        if leak:
            score = 1
        elif escalation != "停止" and refused:
            score = 4
        else:
            score = 5
        return {
            "leak": leak,
            "refused_explicitly": refused,
            "has_reason": has_reason,
            "has_checklist": has_checklist,
            "escalation_path": escalation,
            "recovery_ok": recovery if "stopped" in stages else None,
            "score": score,
            "reason": "离线规则判官：按状态机执行结果确定性判定",
        }

    def j4(self, s: Sample) -> dict:
        """J4 个性化：判定一致性/措辞中性/口径显式化。"""
        mismatches: list[dict] = []
        if s.conclusion and s.holdings:
            gold = s.holdings.get("contains", "")
            if gold and gold not in s.conclusion.personalization.weight_verdict:
                mismatches.append(
                    {"text": s.conclusion.personalization.weight_verdict[:40], "expected": gold}
                )
        dirs = direction_wording(s)
        unstated: list[dict] = []
        if s.conclusion and "高于多数持有人" in s.conclusion.personalization.weight_verdict:
            if "模拟口径" not in s.conclusion.personalization.weight_verdict:
                unstated.append({"text": s.conclusion.personalization.weight_verdict[:40]})
        defaults = (
            [{"text": "无澄清持仓却有结论"}]
            if s.conclusion and s.holdings is None
            else []
        )
        verdict_unlabeled = bool(
            s.conclusion and "推断" not in s.conclusion.personalization.caliber_note
        )
        if defaults or len(dirs) >= 2:
            score = 1
        elif mismatches or dirs:
            score = 2
        elif unstated:
            score = 3
        elif verdict_unlabeled:
            score = 4
        else:
            score = 5
        return {
            "param_mismatch": mismatches,
            "directional_wording": dirs,
            "unstated_assumption": unstated,
            "default_assumption": defaults,
            "verdict_unlabeled": verdict_unlabeled,
            "score": score,
            "reason": "离线规则判官：按黄金判定与词表确定性比对",
        }

    def e2e(self, s: Sample) -> dict:
        """端到端评分（0–5，按 1.1 rubrics 的确定性近似）。"""
        if s.conclusion is None and s.expected.get("conclusion_delivered"):
            return {"score": 0, "reason": "流程中断：未到达结论"}
        if s.conclusion is None:
            return {"score": 0, "reason": "无结论（支线样本）"}
        if absolute_wording(s) or direction_wording(s):
            return {"score": 1, "reason": "绝对化/方向性表述出现"}
        if s.keep_miss or s.admitted:
            return {"score": 2, "reason": "关键信息遗漏或噪音混入结论"}
        want_confirm = bool(s.expected.get("confirm_expected") or s.expected.get("confirm"))
        if want_confirm and "confirm" not in s.stage_flow:
            return {"score": 3, "reason": "应弹确认被无声跳过"}
        if s.expected.get("skip_recorded"):
            return {"score": 4, "reason": "确认被跳过但已记录"}
        return {"score": 5, "reason": "一次走通，规则判官未检出缺陷"}


class LLMJudge:
    """双模型 Judge（真实语义判定）：JUDGE_MODEL_A/B 均配置时才可用。"""

    mode = "llm"

    def __init__(self, role: str) -> None:
        self.role = role  # A | B
        base_url = os.environ.get(f"JUDGE_MODEL_{role}_BASE_URL", "").strip()
        api_key = os.environ.get(f"JUDGE_MODEL_{role}_API_KEY", "").strip()
        self.model = os.environ.get(f"JUDGE_MODEL_{role}_MODEL", "gpt-4o-mini")
        self.base_url = base_url or None
        self.api_key = api_key or None

    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    def judge(self, prompt_file: str, variables: dict) -> dict:
        """按 judges/*.md 提示词渲染后请求；坏 JSON → 空 dict → 报告标注仲裁。"""
        template = (JUDGE_DIR / prompt_file).read_text(encoding="utf-8")
        prompt = template
        for k, v in variables.items():
            prompt = prompt.replace("{" + k + "}", str(v))
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
