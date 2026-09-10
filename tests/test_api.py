"""FastAPI 服务测试（mock 模式，零网络零 key）：主流程 + 三支线经 HTTP 全链路走查。

红线在 API 层复验：澄清必填阻断、确认条件化、买卖拒答漏放率 0、升级路径
两级状态机、停止后合规话题恢复——全部由真实 orchestrator 代码执行。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sid(client):
    resp = client.post("/api/sessions")
    assert resp.status_code == 200
    return resp.json()["session_id"]


def _ask_until_stage(client, sid, question):
    return client.post(f"/api/sessions/{sid}/ask", json={"question": question}).json()


def test_health_mock_mode(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["llm_mode"] == "mock"
    assert data["datasource"] == "mock"
    assert data["simulated"] is True


def test_full_flow_reaches_conclusion(client, sid):
    # P0 触达 → 提问（缺持仓 → 澄清阻断）→ 提交澄清 → 确认 → 结论
    touch = client.post(f"/api/sessions/{sid}/touch").json()
    assert touch["stage"] == "touch" and touch["title"]

    resp = _ask_until_stage(client, sid, "沐辰智控发生了什么事，对我有什么影响？")
    assert resp["stage"] == "clarify" and resp["reason"]

    bad = client.post(
        f"/api/sessions/{sid}/clarify", json={"cost": 18.40, "ratio": 18.0, "horizon": "3y"}
    ).json()
    assert bad["stage"] == "clarify" and bad["errors"]  # 必填阻断：非法 horizon

    resp = client.post(
        f"/api/sessions/{sid}/clarify", json={"cost": 18.40, "ratio": 18.0, "horizon": "1-3y"}
    ).json()
    assert resp["stage"] == "confirm"  # 条件化确认：G1 推断占比高 → 必弹
    assert resp["confirm_reason"]

    resp = client.post(f"/api/sessions/{sid}/confirm", json={"action": "confirm"}).json()
    assert resp["stage"] == "conclusion"
    conclusion = resp["conclusion"]
    assert conclusion["facts"] and conclusion["infers"] and conclusion["unknowns"]
    assert "推断" in conclusion["personalization"]["caliber_note"]  # verdict 推断标注
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["stage"] == "conclusion" and state["metrics"]["事件数"] > 5


def test_confirm_skip_and_disagree(client, sid):
    _ask_until_stage(client, sid, "沐辰智控发生了什么事，对我有什么影响？")
    client.post(
        f"/api/sessions/{sid}/clarify", json={"cost": 20.0, "ratio": 30.0, "horizon": "6-12m"}
    )
    resp = client.post(f"/api/sessions/{sid}/confirm", json={"action": "disagree"}).json()
    assert resp["stage"] == "confirm" and "重新分析" in resp["reanalyze_note"]  # 不认可 → 真实重跑
    resp = client.post(f"/api/sessions/{sid}/confirm", json={"action": "skip"}).json()
    assert resp["stage"] == "conclusion"
    state = client.get(f"/api/sessions/{sid}").json()
    # 确认环节共触达 2 次（首次 + 不认可重跑后），跳过 1 次 → 跳过被记录（红线：跳过记录 100%）
    assert state["metrics"]["跳过率"] == 0.5


def test_refusal_escalation_and_recovery(client, sid):
    _ask_until_stage(client, sid, "沐辰智控发生了什么事，对我有什么影响？")
    client.post(
        f"/api/sessions/{sid}/clarify", json={"cost": 18.40, "ratio": 18.0, "horizon": "1-3y"}
    )
    client.post(f"/api/sessions/{sid}/confirm", json={"action": "confirm"})

    def follow(message):
        return client.post(f"/api/sessions/{sid}/followup", json={"message": message}).json()

    r1 = follow("现在该不该买？")
    assert r1["stage"] == "refused" and r1["checklist"]  # 漏放率 0：拒答 + 清单
    r2 = follow("我还是想知道该不该买？")
    assert r2["stage"] == "guided"  # 追问 1 → 再引导
    r3 = follow("我就是想听你的，买还是不买？")
    assert r3["stage"] == "stopped"  # 追问 2 → 停止
    r4 = follow("商誉减值是什么意思？")
    assert r4["stage"] == "answer" and "商誉" in r4["answer"]  # 合规话题恢复

    done = client.post(f"/api/sessions/{sid}/checklist/complete").json()
    assert done["stage"] == "checklist_done"
    events = client.get(f"/api/sessions/{sid}/events").json()["events"]
    names = [e["name"] for e in events]
    for expected in ("refusal_triggered", "escalation_guide", "escalation_stop", "recovery"):
        assert expected in names


def test_unknown_session_404_and_bad_action(client):
    assert client.get("/api/sessions/nope").status_code == 404
    sid = client.post("/api/sessions").json()["session_id"]
    assert (
        client.post(f"/api/sessions/{sid}/confirm", json={"action": "hack"}).status_code == 400
    )


def test_health_real_mode_env(monkeypatch, client):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("DATASOURCE", "akshare")
    data = client.get("/api/health").json()
    assert data["llm_mode"] == "openai"
    assert data["datasource"] == "akshare"
    assert data["simulated"] is False
