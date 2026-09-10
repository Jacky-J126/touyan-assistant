"""「与你何干」个性化解读（S7）：纯函数计算，红线约束内置于代码。

红线（评测方案第四章，全部无容差）：
- 数据 100% 来自澄清所得：本模块不接受任何默认持仓参数（无 default fallback）；
- 措辞中性：方向词表（买入/卖出/加仓/减仓/应/建议…）出现即失败——本模块词库不含方向词；
- 统计口径显式化：相对判定（如「高于多数持有人」）必须附口径与数据来源；
- verdict 推断性质声明：相对判定依赖口径分布，呈现时标【推断】。

边界样本（D5）：P1 阈值翻转（14.9%/15.1% 两侧 verdict 相反且各与参数一致）；
P2 成本≈现价（±0.1% 精确并置）；P3 占比极值（80% 提示权重高但不得暗示减仓）；
P4 口径事实化（无口径 = 无依据的推断，禁止）。
"""

from __future__ import annotations

from app.models import HoldingParams, Personalization

#: 占比判定阈值（Demo verdict 口径：15% 两侧翻转，D5-P1）
RATIO_LOW = 15.0
RATIO_HIGH = 40.0

#: 「高于多数持有人」的对比口径（必须显式标注为模拟口径）
MEDIAN_CALIBER = "中位数约 5–8%，模拟口径"

CALIBER_NOTE = (
    "「高于多数持有人」等相对判断依赖持有人分布口径（中位数约 5–8%，模拟口径）；"
    "本段判定为推断，可能随口径修正。"
)

DEFAULT_APPROVAL_CYCLE = "董事会、股东大会及境内外监管审批"


def weight_verdict(ratio: float) -> str:
    """权重判定：与持仓占比严格一致，措辞中性。"""
    if ratio < RATIO_LOW:
        return "偏低，对你组合影响权重有限"
    if ratio < RATIO_HIGH:
        return f"高于多数持有人（{MEDIAN_CALIBER}），此项不确定性对你组合影响权重偏高"
    return "高，此项不确定性对你组合影响权重高"


def horizon_line(horizon: str, approval_cycle: str = DEFAULT_APPROVAL_CYCLE) -> str:
    """期限 vs 审批周期：只做事实并置，不构成方向判断。"""
    if horizon == "<6m":
        return (
            f"你的期限短于审批周期（{approval_cycle}），"
            "你承受的主要是审批结果的不确定性"
        )
    if horizon == "6-12m":
        return (
            f"你的期限部分覆盖审批周期（{approval_cycle}），"
            "短期波动仍会影响你的计划"
        )
    if horizon == "1-3y":
        return (
            f"你的期限覆盖审批周期（{approval_cycle}），"
            "整合是否兑现将在你的持有期内逐渐明朗"
        )
    return "你的期限远超审批周期，此项事件的不确定性对你长期持有的影响有限"


def cost_line(cost: float, price: float | None) -> str:
    """成本相对现价 ±X%：客观并置，附加方向结论不允许（J4 约束）。"""
    if price is None:
        return f"成本 ¥{cost:.2f}；现价数据不可用（行情接口降级）"
    pct = (price - cost) / cost * 100
    return f"成本 ¥{cost:.2f}，现价 ¥{price:.2f}（相对成本 {pct:+.1f}%）"


def run_personalization(
    holdings: HoldingParams,
    price: float | None,
    approval_cycle: str = DEFAULT_APPROVAL_CYCLE,
) -> Personalization:
    """输入全部来自澄清所得；holdings 为 None 时调用方必须走澄清，不得传入默认值。"""
    return Personalization(
        weight_verdict=weight_verdict(holdings.ratio),
        horizon_line=horizon_line(holdings.horizon, approval_cycle),
        cost_line=cost_line(holdings.cost, price),
        caliber_note=CALIBER_NOTE,
    )
