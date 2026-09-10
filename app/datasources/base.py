"""数据源 Provider 协议。

约定：超时 / 数据缺失时，Provider 在 RecallResult.degrade_note 写明降级原因，
管线负责「只给已召回事实并明示不足」（PRD 异常降级条款），不得假装完整。
"""

from __future__ import annotations

from typing import Protocol

from app.models import RecallResult


class DataProvider(Protocol):
    """多源召回协议：公告 / 交易所披露 / 行情 / 媒体 / 股吧 / 研报。"""

    def recall(self, stock_code: str) -> RecallResult: ...

    def quote(self, stock_code: str) -> float | None:
        """现价快照，用于「与你何干」成本相对现价 ±X%；不可用时返回 None 并降级。"""
        ...
