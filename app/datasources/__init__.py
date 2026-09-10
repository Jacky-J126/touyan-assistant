"""数据源层：Provider 抽象 + mock/真实实现。

阶段 2 仅提供 MockProvider（内置 G1 场景）；akshare/tushare Provider 在阶段 4 接入，
真实数据只影响本层，管线代码不变。
"""

from app.datasources.base import DataProvider
from app.datasources.mock import MockProvider

__all__ = ["DataProvider", "MockProvider"]
