"""真实数据源 Provider 的离线测试（CI 不安装 akshare/tushare）。

只测确定性行为：依赖缺失/无 token → 降级明示（红线：降级明示 100%）；
工厂按环境变量选择；mock 默认零 key 可跑。真实接口调用为联网行为，
由实现期实测验证（见各 provider 模块 docstring），不进 CI。
"""

from __future__ import annotations

import sys
from types import ModuleType


def _hide_module(monkeypatch, name: str) -> None:
    """让 `import {name}` 抛 ImportError（模拟未安装）。"""
    monkeypatch.setitem(sys.modules, name, None)


def test_akshare_missing_import_degrades(monkeypatch):
    from app.datasources import AkshareProvider

    _hide_module(monkeypatch, "akshare")
    provider = AkshareProvider()
    result = provider.recall("688521.SH")
    assert result.items == []
    assert result.degrade_note and "未安装" in result.degrade_note
    assert provider.quote("688521.SH") is None


def test_akshare_all_sources_fail_yield_no_fake_items(monkeypatch):
    """每个源都异常时：0 个召回项 + 降级说明，绝不产生伪装条目。"""
    from app.datasources import AkshareProvider

    class BrokenAkshare(ModuleType):
        """任何接口调用都抛异常（模拟网络异常）。"""

        def __getattr__(self, name):
            raise ConnectionError("network down")

    monkeypatch.setitem(sys.modules, "akshare", BrokenAkshare("akshare"))
    result = AkshareProvider().recall("688521.SH")
    assert result.items == []
    assert result.degrade_note and "未召回任何" in result.degrade_note
    assert "公告源不可用" in result.degrade_note


def test_tushare_missing_token_degrades(monkeypatch):
    from app.datasources import TushareProvider

    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    # 包已安装但无 token：走「未配置 token」降级分支（CI 不装 [real]，测试与环境无关）
    monkeypatch.setitem(sys.modules, "tushare", ModuleType("tushare"))
    result = TushareProvider().recall("688521.SH")
    assert result.items == []
    assert result.degrade_note and "TUSHARE_TOKEN" in result.degrade_note
    assert TushareProvider().quote("688521.SH") is None


def test_tushare_missing_package_degrades(monkeypatch):
    from app.datasources import TushareProvider

    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    _hide_module(monkeypatch, "tushare")
    result = TushareProvider().recall("688521.SH")
    assert result.degrade_note and "未安装" in result.degrade_note


def test_get_provider_factory(monkeypatch):
    from app.datasources import AkshareProvider, MockProvider, TushareProvider, get_provider

    monkeypatch.delenv("DATASOURCE", raising=False)
    assert isinstance(get_provider(), MockProvider)  # 默认 mock：零 key 可复现
    monkeypatch.setenv("DATASOURCE", "akshare")
    assert isinstance(get_provider(), AkshareProvider)
    monkeypatch.setenv("DATASOURCE", "tushare")
    assert isinstance(get_provider(), TushareProvider)
    monkeypatch.setenv("DATASOURCE", "unknown")
    assert isinstance(get_provider(), MockProvider)  # 未知值回退 mock


def test_plain_code_strips_suffix():
    from app.datasources.akshare import _plain_code

    assert _plain_code("688521.SH") == "688521"
    assert _plain_code("688521") == "688521"
