"""术语白话（P4 · S7）：MVP 用预置词典（新手档）。

按熟悉度自适应（历史浏览版）在评测方案中标注「待验证」，MVP 不实现，
用户档位由 UI 自报；mock 模式返回 G1 场景词典。
"""

from __future__ import annotations

from app import mockdata as md


def run_glossary(llm, terms: list[str]) -> list[tuple[str, str]]:
    """返回 [(术语, 白话解释)]；mock 模式用 G1 预置词典。"""
    if llm.mode == "mock":
        return [t for t in md.G1_GLOSSARY if t[0] in terms]
    # 真实模式（阶段 4 联调）：LLM 按档位生成
    return []


def answer_glossary(message: str) -> str | None:
    """从 G1 词典直接应答术语解释类提问（E2：停止作答后合规话题恢复正常服务）。"""
    for term, plain in md.G1_GLOSSARY:
        if term in message:
            return f"{term}：{plain}"
    return None
