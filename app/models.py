"""核心数据模型：管线各阶段的输入输出结构。

标签体系（PRD V0.2）：
- 【事实】已发生、有信源，必附信源与时间点；
- 【推断】可能出错、必附假设，结构为影响面+关键假设，禁「必然肯定」；
- 【未知】信息缺失，必明说需要补充什么，区分「需你补充/需你等待」；
- 【噪音】已过滤，不进结论，必附过滤理由与命中标准（信源/时效/相关性）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceType(StrEnum):
    """六类召回来源白名单（评测方案 S2 代码断言依赖此枚举）。"""

    ANNOUNCEMENT = "公告"
    EXCHANGE = "交易所披露"
    QUOTE = "行情"
    MEDIA = "媒体"
    GUBA = "股吧"
    RESEARCH = "研报"


#: 噪音过滤的三条判定标准（PRD「噪音的三条标准」）
NOISE_STANDARDS = ("信源", "时效", "相关性")


@dataclass
class RecallItem:
    """一条召回信息（多源召回 ④ 的输出单元）。"""

    source_type: SourceType
    source_name: str  # 巨潮资讯 / 上交所 / 模拟行情接口 …
    timestamp: str  # 展示用时间点
    content: str
    status: str = "recalled"  # recalled | partial | degraded


@dataclass
class RecallResult:
    items: list[RecallItem] = field(default_factory=list)
    degrade_note: str | None = None  # 超时/缺失时的降级说明（必须明示）


@dataclass
class NoiseItem:
    """一条被过滤的噪音（⑤ 的输出单元，必须可解释）。"""

    text: str
    source: str
    standard: str  # 命中标准 ∈ NOISE_STANDARDS
    reason: str


@dataclass
class FactItem:
    """一条【事实】：已发生、有出处、可溯源。"""

    text: str
    source: str
    timepoint: str


@dataclass
class InferItem:
    """一条【推断】：未发生、附假设、有置信。"""

    text: str
    assumption: str
    confidence: str  # 高 | 中 | 低 | 低–中 …
    bearish: bool = False  # 是否含利空性质（结论前确认的触发条件之一）


@dataclass
class UnknownItem:
    """一条【未知】：信息缺失，明说需补充什么。"""

    text: str
    action: str  # 需你补充 | 需你等待


@dataclass
class HoldingParams:
    """澄清所得的持仓三要素（个性化段的唯一数据来源，禁止默认值）。"""

    cost: float  # 持仓成本（元）
    ratio: float  # 占总资产比（%）
    horizon: str  # <6m | 6-12m | 1-3y | 3y+

    HORIZONS = ("<6m", "6-12m", "1-3y", "3y+")


@dataclass
class Personalization:
    """「与你何干」段：判定与持仓参数严格一致、措辞中性、口径显式化。

    verdict 本身是推断（依赖口径假设），呈现时须标【推断】并附口径说明。
    """

    weight_verdict: str  # 权重判定（如「高于多数持有人（中位数约 5–8%，模拟口径）…」）
    horizon_line: str  # 期限 vs 审批周期（中性陈述）
    cost_line: str  # 成本相对现价 ±X%（客观并置，不构成方向判断）
    caliber_note: str  # 统计口径显式声明


@dataclass
class Conclusion:
    """带标签的可解释结论（⑨ 的输出）。"""

    stock_name: str
    stock_code: str
    event: str
    facts: list[FactItem]
    infers: list[InferItem]
    unknowns: list[UnknownItem]
    noise: list[NoiseItem]  # 已过滤噪音（折叠面板，逐条附理由与标准）
    noise_summary: str  # 如「股吧 18 条 · 16 条待过滤」
    personalization: Personalization
    glossary: list[tuple[str, str]]  # 术语白话（新手档）
    degrade_note: str | None  # 降级说明（无则 None）
    data_scope: str  # 数据来源 + 模拟声明
