"""LLM 层：统一接口 + 工厂。

- MockLLM：脚本化响应（G1 场景），零 key 复现 Demo——mock 模式下管线代码与真实模式完全相同
- OpenAICompat：OpenAI 兼容接口 + JSON Schema + 防御式解析（坏 JSON → 空 dict → 管线降级）

工厂规则：环境变量 LLM_API_KEY 存在 → 真实客户端；否则 → MockLLM。
"""

from __future__ import annotations

import os

from app.llm.client import OpenAICompat
from app.llm.mock import MockLLM


def get_llm():
    """按环境变量选择 LLM 后端；未配置 key 时回退 mock（零依赖可跑）。"""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if api_key:
        return OpenAICompat(
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )
    return MockLLM()


__all__ = ["get_llm", "MockLLM", "OpenAICompat"]
