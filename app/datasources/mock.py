"""MockProvider：内置 G1 演示场景（沐辰智控 688521.SH），零依赖零 key 可跑。

研报源固定超时（status="degraded"），用于演示「接口超时 → 只给已召回事实 + 明示不足」
降级支线——这正是交互原型 P2 的固定用例（评测方案 S2 细则）。
"""

from app.mockdata import G1_RECALL, QUOTE_PRICE, STOCK_CODE
from app.models import RecallResult


class MockProvider:
    """G1 场景数据源：召回结果与行情均为模拟数据。"""

    name = "mock"
    simulated = True  # UI 与免责声明据此标注「模拟数据」

    def recall(self, stock_code: str) -> RecallResult:
        if stock_code != STOCK_CODE:
            return RecallResult(
                degrade_note=f"模拟数据源仅内置 {STOCK_CODE}（G1 场景），无 {stock_code} 的数据。"
            )
        return G1_RECALL

    def quote(self, stock_code: str) -> float | None:
        if stock_code != STOCK_CODE:
            return None
        return QUOTE_PRICE
