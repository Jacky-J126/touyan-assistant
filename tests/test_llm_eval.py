"""LLM Judge 双评执行层的离线测试：变量渲染完整性与无 key 时的失败行为。

判官提示词占位符必须是渲染闭包的超集——缺一个占位符，真实渲染会把
{...} 原文送进模型（静默损坏输入）。此测试锁住 j1–j4 的占位符 ↔ 渲染键。
"""

from __future__ import annotations

import re

import pytest

from evals.judges import JUDGE_DIR
from evals.llm_eval import PROMPT_FILES, render_j1, render_j2, render_j3, render_j4
from evals.runner import load_golden, run_e2e

SC = load_golden()[0]
H = SC.holdings_variants[0]
SAMPLE = run_e2e(SC, H)


@pytest.mark.parametrize("dim", ["j1", "j2", "j3", "j4"])
def test_render_vars_cover_all_placeholders(dim):
    if dim == "j3":
        variables = render_j3(SC, H)
    else:
        variables = {
            "j1": render_j1(SC, SAMPLE),
            "j2": render_j2(SC, SAMPLE),
            "j4": render_j4(H, SAMPLE),
        }[dim]
    prompt = (JUDGE_DIR / PROMPT_FILES[dim]).read_text(encoding="utf-8")
    raw = set(re.findall(r"\{([^{}]*)\}", prompt))
    # 提示词内嵌的输出 JSON 示例（{"desc": "…"}）不是渲染变量：含引号或冒号即视为示例
    placeholders = {p for p in raw if '"' not in p and ":" not in p}
    assert placeholders, f"{dim} 提示词没有任何渲染占位符"
    missing = placeholders - set(variables)
    assert not missing, f"{dim} 占位符未提供渲染值：{missing}"
    for value in variables.values():
        assert isinstance(value, str) and value


def test_j1_lists_are_distinct():
    v = render_j1(SC, SAMPLE)
    assert "1. " in v["关键信息编号列表"]
    assert "命中标准" in v["噪音编号列表"]
    assert v["关键信息编号列表"] != v["噪音编号列表"]  # 拆分占位符后两列表各自渲染


def test_j3_replies_cover_escalation_chain():
    v = render_j3(SC, H)
    for stage in ("拒答", "再引导", "停止作答", "恢复"):
        assert stage in v["待评测回复全文"]


def test_main_exits_without_judge_keys(monkeypatch, capsys):
    for key in ("JUDGE_MODEL_A_BASE_URL", "JUDGE_MODEL_A_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    import evals.llm_eval as llm_eval

    with pytest.raises(SystemExit) as exc:
        llm_eval.main()
    assert exc.value.code == 1
    assert "缺少 Judge 配置" in capsys.readouterr().out
