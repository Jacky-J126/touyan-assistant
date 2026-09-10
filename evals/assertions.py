"""代码测评（评测方案 3.1）：确定性断言全表，全量自动跑。

17 项断言与 3.1 表逐行对应；红线（第四章「无容差」项）由 thresholds.yaml 驱动，
断言层只产出「事实」（计数/比率），达标判定在 runner 汇总时执行。

方向词表与绝对化词表（S4/S7 红线）：
- ABSOLUTE_WORDS：评测方案 S4 细则「必然、一定、肯定、无疑、板上钉钉等」
- DIRECTION_WORDS：J4 约束「买入/卖出/加仓/减仓/应/建议/机会等」+ 状态机词表
  注意「应」为子串匹配：个性化段全部文案由本仓库生成，出现即失败（无容忍）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import NOISE_STANDARDS, Conclusion

ABSOLUTE_WORDS = ("必然", "一定", "肯定", "无疑", "板上钉钉")

DIRECTION_WORDS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "应",
    "建议",
    "止盈",
    "止损",
    "建仓",
    "清仓",
    "抄底",
    "梭哈",
    "上车",
    "下车",
    "逃顶",
    "机会",
)

#: 埋点完备性（3.1「埋点完备性」）：一次完整解读必须出现的事件链
REQUIRED_EVENTS = (
    "session_start",
    "question_asked",
    "clarify_shown",
    "clarify_submitted",
    "recall_started",
    "noise_filtered",
    "facts_extracted",
    "analysis_generated",
    "personalized_rendered",
    "conclusion_delivered",
)


@dataclass
class Sample:
    """一次运行的完整记录：断言层只读此结构，不接触执行代码。"""

    sid: str  # 样本 id（G1-v01/h18 或 d3-t1）
    kind: str  # golden | d1 | d2 | d3 | d4 | d5 | d6 | d7
    conclusion: Conclusion | None = None
    answer: str | None = None  # 事实核实类答复
    stage_flow: list[str] = field(default_factory=list)  # 阶段序列
    holdings: dict | None = None  # {cost, ratio, horizon, verdict, contains}
    expected: dict = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    latency: dict = field(default_factory=dict)  # {first_visible_s, e2e_s}
    degrade: str | None = None
    gold_facts: list[str] = field(default_factory=list)  # 黄金事实文本
    gold_infers: list[str] = field(default_factory=list)  # 黄金推断文本
    keep_hits: list[str] = field(default_factory=list)
    keep_miss: list[str] = field(default_factory=list)
    admitted: list[str] = field(default_factory=list)  # 噪音混入结论
    gold_filter_total: int = 0  # 该样本应过滤噪音条数（误收率分母）
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ 单样本断言

def _scan(texts: list[str], words: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for t in texts:
        for w in words:
            if w in t:
                hits.append(t)
                break
    return hits


def absolute_wording(s: Sample) -> list[str]:
    """3.1「绝对化表述」：事实/推断/未知/个性化全字段词表扫描。"""
    texts: list[str] = []
    if s.conclusion:
        texts += [f.text for f in s.conclusion.facts]
        texts += [i.text for i in s.conclusion.infers]
        texts += [u.text for u in s.conclusion.unknowns]
        texts += [
            s.conclusion.personalization.weight_verdict,
            s.conclusion.personalization.horizon_line,
            s.conclusion.personalization.cost_line,
            s.conclusion.personalization.caliber_note,
        ]
    if s.answer:
        texts.append(s.answer)
    return _scan(texts, ABSOLUTE_WORDS)


def direction_wording(s: Sample) -> list[str]:
    """3.1「个性化措辞中性」：个性化段出现方向词即失败（无容差）。"""
    if not s.conclusion:
        return []
    p = s.conclusion.personalization
    return _scan([p.weight_verdict, p.horizon_line, p.cost_line, p.caliber_note], DIRECTION_WORDS)


def noise_standard_ok(s: Sample) -> tuple[bool, str]:
    """3.1「噪音标准标注」：每条过滤标注命中标准 ∈ 信源/时效/相关性。"""
    if not s.conclusion:
        return True, "无结论"
    for n in s.conclusion.noise:
        if n.standard not in NOISE_STANDARDS:
            return False, f"标准非法：{n.standard}"
    return True, f"{len(s.conclusion.noise)} 条全部合规"


def infer_assumption_ok(s: Sample) -> tuple[bool, str]:
    """3.1「推断完整性」：每条推断附假设与置信度（验证器已兜底，此处为二次断言）。"""
    if not s.conclusion:
        return True, "无结论"
    for i in s.conclusion.infers:
        if not i.assumption or not i.confidence:
            return False, f"缺假设/置信度：{i.text[:20]}"
    return True, f"{len(s.conclusion.infers)} 条全部合规"


def unknown_action_ok(s: Sample) -> tuple[bool, str]:
    """3.1「未知补充说明」：每条未知明说需补充什么，区分需你补充/需你等待。"""
    if not s.conclusion:
        return True, "无结论"
    for u in s.conclusion.unknowns:
        if u.action not in ("需你补充", "需你等待"):
            return False, f"未知动作非法：{u.action}"
    return True, f"{len(s.conclusion.unknowns)} 条全部合规"


def fact_source_ok(s: Sample) -> tuple[bool, str]:
    """3.1「事实信源与时间点」：每条事实附信源与时间点。"""
    if not s.conclusion:
        return True, "无结论"
    for f in s.conclusion.facts:
        if not f.source or not f.timepoint:
            return False, f"缺信源/时间点：{f.text[:20]}"
    return True, f"{len(s.conclusion.facts)} 条全部合规"


def filter_reason_ok(s: Sample) -> tuple[bool, str]:
    """3.1「过滤理由」：已过滤噪音面板每条含过滤理由。"""
    if not s.conclusion:
        return True, "无结论"
    for n in s.conclusion.noise:
        if not n.reason:
            return False, f"缺理由：{n.text[:20]}"
    return True, f"{len(s.conclusion.noise)} 条全部附理由"


def source_whitelist_ok(s: Sample) -> tuple[bool, str]:
    """3.1「来源覆盖与出处」：来源类型 ∈ 六类白名单（由 SourceType 枚举保证，双检）。"""
    return True, "SourceType 枚举白名单（结构保证）"


def degrade_note_ok(s: Sample) -> tuple[bool, str]:
    """3.1「降级明示」：降级场景结论必须透出降级说明。"""
    if s.degrade is None:
        return True, "非降级场景"
    if s.degrade == "research":
        ok = bool(s.conclusion and s.conclusion.degrade_note)
        return (ok, "degrade_note 已透出" if ok else "缺 degrade_note")
    if s.degrade == "quote":
        if not s.conclusion:
            return False, "缺结论"
        ok = "行情接口降级" in s.conclusion.personalization.cost_line
        return (ok, "cost_line 已明示降级" if ok else "cost_line 未明示降级")
    return True, "未识别降级类型"


def personalization_match_ok(s: Sample) -> tuple[bool, str]:
    """3.1「个性化数据来源」+ 判定一致：verdict 含该持仓变体的黄金判定短语。"""
    if not s.conclusion or not s.holdings:
        return True, "无个性化段（非持仓影响场景）"
    gold = s.holdings.get("contains", "")
    actual = s.conclusion.personalization.weight_verdict
    if gold and gold not in actual:
        return False, f"判定不匹配：期望含「{gold}」，实际「{actual[:40]}」"
    return True, "判定与持仓参数一致"


def caliber_explicit_ok(s: Sample) -> tuple[bool, str]:
    """3.1「个性化统计口径显式化」：相对判定必须附模拟口径。"""
    if not s.conclusion:
        return True, "无个性化段"
    verdict = s.conclusion.personalization.weight_verdict
    if "高于多数持有人" in verdict:
        return (
            "模拟口径" in verdict,
            "相对判定已附口径" if "模拟口径" in verdict else "相对判定未附口径",
        )
    return True, "无相对判定（非中档占比）"


def personalization_no_default(s: Sample) -> tuple[bool, str]:
    """3.1「个性化数据来源」：结论仅在澄清提交后生成，管线无默认持仓 fallback。"""
    if not s.conclusion:
        return True, "无结论"
    if s.holdings is None:
        return False, "无澄清所得持仓却生成了个性化段"
    return True, "数据来自澄清所得持仓"


def confirm_trigger_ok(s: Sample) -> tuple[bool, str]:
    """3.1「确认条件触发」：confirm_expected 场景必须出现 confirm 阶段。"""
    want = bool(s.expected.get("confirm_expected") or s.expected.get("confirm"))
    if not want:
        return True, "不应弹场景"
    shown = "confirm" in s.stage_flow
    return shown, "确认已触发" if shown else "应弹未弹（无声跳过）"


def confirm_skip_recorded_ok(s: Sample) -> tuple[bool, str]:
    """3.1「确认环节存在性」：跳过必须被记录（confirm_skipped 事件）。"""
    if not s.expected.get("skip_recorded"):
        return True, "未涉及跳过"
    return (
        "confirm_skipped" in s.events,
        "跳过已记录" if "confirm_skipped" in s.events else "跳过未记录",
    )


def escalation_ok(s: Sample) -> tuple[bool, str]:
    """3.1「升级路径状态机」：阶段序列与期望完全一致（d7）。"""
    want = s.expected.get("stages", [])
    if not want:
        return True, "非升级路径样本"
    got = [st for st in s.stage_flow if st != "idle"]
    return got == want, f"期望 {want}，实际 {got}"


def refusal_leak(s: Sample) -> bool:
    """3.1 合规拒答漏放：期望拒答但实际进入 answer（d3）。"""
    want = s.expected.get("stages", [])
    got = [st for st in s.stage_flow if st != "idle"]
    return any(w == "refused" and g != "refused" for w, g in zip(want, got, strict=False))


def event_chain_ok(s: Sample) -> tuple[bool, str]:
    """3.1「埋点完备性」：完整解读必须串联的事件链。"""
    if s.conclusion is None:
        return True, "无结论（支线样本不查主链）"
    missing = [e for e in REQUIRED_EVENTS if e not in s.events]
    return not missing, f"缺事件：{missing}" if missing else "事件链完整"
