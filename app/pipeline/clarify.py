"""③ 澄清（HITL#1 · S5）：持仓三要素必填校验，AI 不得替你假设。

代码断言（评测方案 3.1「澄清阻断」）：缺任一持仓字段无法提交——
校验是确定性代码，mock/真实模式共用。
"""

from __future__ import annotations

from app.models import HoldingParams

CLARIFY_REASON = (
    "占比决定影响权重、期限决定你承受的是波动还是审批结果、成本决定价格相对你的"
    "盈亏位置——三个字段会改变结论方向，缺失时停下来问，而不是替你假设。"
    "（上下文充分时跳过此步）"
)


def validate_clarify(cost, ratio, horizon) -> dict[str, str]:
    """逐字段校验；返回错误 dict（空 = 通过）。缺任一字段必须阻断提交。"""
    errors: dict[str, str] = {}
    if cost is None or cost <= 0:
        errors["cost"] = "请填写持仓成本（元）"
    if ratio is None or not (0 < ratio <= 100):
        errors["ratio"] = "请填写占总资产比（%，0–100）"
    if horizon not in HoldingParams.HORIZONS:
        errors["horizon"] = "请选择计划持有期限"
    return errors


def build_holdings(cost, ratio, horizon) -> HoldingParams:
    """校验通过后构造持仓参数（个性化段的唯一数据来源，无默认 fallback）。"""
    errors = validate_clarify(cost, ratio, horizon)
    if errors:
        raise ValueError(f"持仓信息不完整：{errors}")
    return HoldingParams(cost=float(cost), ratio=float(ratio), horizon=horizon)
