"""数据源层：Provider 抽象 + mock/真实实现与工厂。

- MockProvider：内置 G1 场景（零依赖零 key，Demo/测试/评测基线）
- AkshareProvider（阶段 4）：公告/研报/股吧人气/行情，免费免 key
- TushareProvider（阶段 4）：公告/新闻/研报/行情，TUSHARE_TOKEN 可选

工厂规则：环境变量 DATASOURCE 显式选择（默认 mock，保证零 key 可复现）；
真实数据只影响本层，管线代码不变。未安装/无权限时 Provider 降级明示
（红线：降级明示 100%），绝不假装完整。
"""

from __future__ import annotations

import os

from app.datasources.akshare import AkshareProvider
from app.datasources.base import DataProvider
from app.datasources.mock import MockProvider
from app.datasources.tushare import TushareProvider


def get_provider() -> DataProvider:
    """按环境变量选择数据源：DATASOURCE=akshare|tushare|mock（默认 mock）。"""
    ds = os.environ.get("DATASOURCE", "mock").strip().lower()
    if ds == "akshare":
        return AkshareProvider()
    if ds == "tushare":
        return TushareProvider()
    return MockProvider()


__all__ = ["AkshareProvider", "DataProvider", "MockProvider", "TushareProvider", "get_provider"]
