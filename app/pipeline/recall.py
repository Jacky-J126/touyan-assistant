"""④ 多源召回（S2）：六类来源聚合 + 降级明示。

降级约定（PRD 异常降级条款）：Provider 在 degrade_note 写明原因，
管线只使用已召回内容并原样透出降级说明，不得假装完整。
"""

from __future__ import annotations

from app.models import RecallResult


def run_recall(provider, stock_code: str) -> RecallResult:
    return provider.recall(stock_code)
