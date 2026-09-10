"""Benchmark 数据集加载（评测方案第二章）。

黄金集 G1–G3：每个 YAML 一个场景——base（场景完整内容，字符串含 {param} 模板占位）
+ variants（10 个变体 delta，变更事件细节/噪音池/行情）+ holdings_variants（3 组持仓参数，
对应「与你何干」黄金判定）。
拓展集 D1–D7：按 kind 分组的对抗样本条目（>=40 条）。

加载顺序：base 渲染 → 变体覆盖（params/quote_price/add_noise/drop_noise/bearish/
confirm_expected/degrade/recall_delta）→ Scenario 对象。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.models import (
    FactItem,
    InferItem,
    NoiseItem,
    RecallItem,
    RecallResult,
    SourceType,
    UnknownItem,
)

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets"


class _SafeDict(defaultdict):
    """模板渲染：缺失占位符原样保留（{key}），不抛 KeyError。"""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(text: str, params: dict) -> str:
    return str(text).format_map(_SafeDict(str, params))


def overlaps(a: str, b: str) -> float:
    """字符重叠率：去重字符集的 Jaccard 式对称测度（≥0.6 计命中）。

    用于黄金标准比对（keep 命中 / 噪音过滤命中）：噪音面板文本与黄金
    过滤条目通常互为摘要改写，集合测度比连续子串更稳健。
    """
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def _source_type(value: str) -> SourceType:
    return SourceType(value) if value in {s.value for s in SourceType} else SourceType.MEDIA


@dataclass
class Scenario:
    """一个可运行场景（黄金集变体或拓展集场景样本）。"""

    variant_id: str
    stock: str
    code: str
    event: str
    push_title: str
    question: str
    note: str = ""
    confirm_expected: bool = False  # 应弹确认（推断占比高/涉利空）→ 红线「应触发 100%」
    degrade: str | None = None  # research：研报超时 | quote：行情不可用 | none
    quote_price: float | None = None
    recall_items: list[RecallItem] = field(default_factory=list)
    noise: list[NoiseItem] = field(default_factory=list)
    noise_summary: str = ""
    facts: list[FactItem] = field(default_factory=list)
    unknowns: list[UnknownItem] = field(default_factory=list)
    infers: list[InferItem] = field(default_factory=list)
    gold_keep: list[dict] = field(default_factory=list)  # {id, keyword, text} 关键信息
    gold_filter: list[dict] = field(default_factory=list)  # {id, text, standard} 应过滤噪音
    raw_facts: list[dict] | None = None  # 未经校验的原始事实 dict（验证器防御样本 D4-F6）
    raw_infers: list[dict] | None = None  # 未经校验的原始推断 dict（D4-F5/F8）
    holdings_variants: list[dict] = field(default_factory=list)  # {id, cost, ratio, horizon,
    #                                                              verdict, contains}
    branch_refusal: bool = False  # 覆盖买卖拒答支线
    branch_recovery: bool = False  # 覆盖停止作答后合规话题恢复
    branch_skip: bool = False  # 覆盖确认跳过（跳过记录率）

    def recall_result(self) -> RecallResult:
        note = None
        if self.degrade == "research":
            note = (
                "研报数据缺失（接口超时）。本次解读仅基于已召回事实，"
                "不含研报观点；信息不足之处将明示。"
            )
        return RecallResult(items=self.recall_items, degrade_note=note)


@dataclass
class AdvCase:
    """拓展集条目：kind 决定 runner 的执行方式，payload 携带样本内容与期望。"""

    id: str
    kind: str  # d1 噪音干扰 / d2 模糊提问 / d3 诱导交易 / d4 事实推断混淆 /
    # d5 个性化边界 / d6 确认触发边界 / d7 升级与恢复
    description: str
    payload: dict = field(default_factory=dict)


# ------------------------------------------------------------------ YAML 读取

def _load_yaml(name: str) -> dict:
    path = DATASET_DIR / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _render_items(items: list[dict], params: dict) -> list[dict]:
    return [
        {k: render(v, params) if isinstance(v, str) else v for k, v in it.items()}
        for it in items
    ]


def _apply_variant(base: dict, v: dict, scenario_id: str) -> Scenario:
    params = {**(base.get("params") or {}), **(v.get("params") or {})}
    stock = render(base["stock"], params)
    code = render(base["code"], params)
    # 每个变体独立渲染召回层（不能复用 base 字典，否则上一变体的 params 会泄漏到下一变体）
    recall = [
        {k: render(it, params) if isinstance(it, str) else it for k, it in item.items()}
        for item in base["recall"]
    ]
    # recall_delta：按 source_type+source_name 定位替换 content（事件细节变更）
    for delta in v.get("recall_delta", []):
        for item in recall:
            if (
                item.get("source_type") == delta.get("source_type")
                and item.get("source_name") == delta.get("source_name")
            ):
                item["content"] = render(delta["content"], params)
                if "timestamp" in delta:
                    item["timestamp"] = render(delta["timestamp"], params)

    noise = [
        n
        for n in _render_items(base["noise"], params)
        if all(sub not in n["text"] for sub in v.get("drop_noise", []))
    ]
    noise += _render_items(v.get("add_noise", []), params)

    facts = _render_items(base["facts"], params)
    unknowns = _render_items(base["unknowns"], params)
    infers = _render_items(base["infers"], params)
    for infer in infers:
        override = v.get("bearish")
        if override is not None:
            infer["bearish"] = override
        elif infer.get("bearish") is None:
            infer["bearish"] = False

    gold_keep = [
        {
            "id": g.get("id", f"k{i}"),
            "keyword": render(g["keyword"], params),
            "text": render(g.get("text", ""), params),
        }
        for i, g in enumerate(base["gold"]["keep"])
    ]
    gold_filter = [
        {"id": g.get("id", f"n{i}"), "text": render(g["text"], params), "standard": g["standard"]}
        for i, g in enumerate(base["gold"]["filter"])
    ]
    # drop_noise：被移除的噪音条目同时从黄金过滤清单剔除，避免「噪音已按设计
    # 移除」被误判为「应过滤而未过滤」（误收假阳性）
    gold_filter = [
        g
        for g in gold_filter
        if not any(overlaps(g["text"], sub) >= 0.6 for sub in v.get("drop_noise", []))
    ]

    return Scenario(
        variant_id=scenario_id,
        stock=stock,
        code=code,
        event=render(base["event"], params),
        push_title=render(base["push_title"], params),
        question=render(base["question"], params),
        note=render(v.get("note", ""), params),
        confirm_expected=v.get("confirm_expected", base.get("confirm_expected", False)),
        degrade=v.get("degrade", base.get("degrade")),
        quote_price=v.get("quote_price", base.get("quote_price")),
        recall_items=[
            RecallItem(
                source_type=_source_type(it["source_type"]),
                source_name=it["source_name"],
                timestamp=it["timestamp"],
                content=it["content"],
                status=it.get("status", "recalled"),
            )
            for it in recall
        ],
        noise=[
            NoiseItem(
                text=n["text"], source=n["source"], standard=n["standard"], reason=n["reason"]
            )
            for n in noise
        ],
        noise_summary=render(base.get("noise_summary", ""), params),
        facts=[
            FactItem(text=f["text"], source=f["source"], timepoint=f["timepoint"]) for f in facts
        ],
        unknowns=[UnknownItem(text=u["text"], action=u["action"]) for u in unknowns],
        infers=[
            InferItem(
                text=i["text"],
                assumption=i["assumption"],
                confidence=i["confidence"],
                bearish=bool(i.get("bearish", False)),
            )
            for i in infers
        ],
        gold_keep=gold_keep,
        gold_filter=gold_filter,
        holdings_variants=base["holdings_variants"],
        branch_refusal=base.get("branch_refusal", True),
        branch_recovery=base.get("branch_recovery", True),
        branch_skip=base.get("branch_skip", True),
    )


# ------------------------------------------------------------------ 黄金集

def load_golden() -> list[Scenario]:
    """G1–G3 全部变体（每场景 10 变体 → >=30 条；每条内置 3 组持仓参数）。"""
    out: list[Scenario] = []
    for fname in ("golden/g1-muchen.yaml", "golden/g2-lanzhou.yaml", "golden/g3-chenghai.yaml"):
        data = _load_yaml(fname)
        base = {k: v for k, v in data.items() if k != "variants"}
        for v in data["variants"]:
            out.append(_apply_variant(base, v, v["id"]))
    return out


# ------------------------------------------------------------------ 拓展集

def load_adversarial() -> list[AdvCase]:
    """D1–D7 全部样本条目（>=40 条）。"""
    out: list[AdvCase] = []
    for fname in (
        "adversarial/d1-noise.yaml",
        "adversarial/d2-vague-question.yaml",
        "adversarial/d3-induced-trade.yaml",
        "adversarial/d4-fact-infer-mix.yaml",
        "adversarial/d5-personalization.yaml",
        "adversarial/d6-confirm-trigger.yaml",
        "adversarial/d7-escalation.yaml",
    ):
        data = _load_yaml(fname)
        for c in data["cases"]:
            out.append(AdvCase(id=c["id"], kind=c["kind"], description=c["description"], payload=c))
    return out
