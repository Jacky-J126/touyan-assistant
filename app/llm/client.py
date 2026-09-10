"""OpenAI 兼容客户端：JSON Schema 结构化输出 + 防御式解析。

防御式解析（Wind Sleep 经验）：模型输出可能带代码围栏、前后缀文字或坏 JSON——
逐级回退：剥围栏 → 括号配对截取 → json.loads；最终失败返回空 dict，
由管线走「只给已召回事实并明示不足」的降级路径，绝不因解析失败假装完整。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(stage: str) -> str:
    """从 prompts/{stage}.md 读取提示词（提示词放文件不放代码）。"""
    return (PROMPT_DIR / f"{stage}.md").read_text(encoding="utf-8")


def parse_json_loose(text: str) -> dict | None:
    """宽松 JSON 解析：剥代码围栏、按括号配对截取首个对象；失败返回 None。"""
    if not text:
        return None
    stripped = text.strip()
    for fence in ("```json", "```"):
        if stripped.startswith(fence):
            stripped = stripped[len(fence) :].strip()
            break
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class OpenAICompat:
    """OpenAI 兼容接口的结构化调用封装。

    阶段 2 提供实现骨架（prompts/ 提示词 + 结构化请求 + 防御式解析），
    阶段 4 接入真实数据源时以真实 key 联调。
    """

    mode = "openai"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def structured(self, stage: str, payload: dict) -> dict:
        """按阶段提示词做结构化调用；解析失败返回空 dict（管线降级）。"""
        system = load_prompt(stage)
        user = json.dumps(payload, ensure_ascii=False)
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_json_loose(content) or {}
