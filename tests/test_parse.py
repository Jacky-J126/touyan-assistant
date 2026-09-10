"""JSON 防御式解析：剥围栏 → 括号配对截取 → json.loads；失败返回 None。

坏 JSON 不得让管线崩溃——由管线走「只给已召回事实并明示不足」的降级路径。
"""

from __future__ import annotations

from app.llm.client import parse_json_loose


def test_bare_json():
    assert parse_json_loose('{"a": 1}') == {"a": 1}


def test_code_fence():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('```\n{"a": 1}\n```') == {"a": 1}


def test_prefix_and_suffix_text():
    out = parse_json_loose('前面有些说明文字 {"a": {"b": [1, 2]}} 后面还有文字')
    assert out == {"a": {"b": [1, 2]}}


def test_nested_braces_in_string():
    out = parse_json_loose('{"text": "含 { 括号 } 的字符串", "n": 3}')
    assert out == {"text": "含 { 括号 } 的字符串", "n": 3}


def test_garbage_returns_none():
    assert parse_json_loose("这不是 JSON") is None


def test_empty_returns_none():
    assert parse_json_loose("") is None


def test_broken_json_returns_none():
    assert parse_json_loose('{"a": ') is None


def test_array_only_returns_none():
    assert parse_json_loose('[1, 2, 3]') is None
