"""FastAPI 服务（阶段 4）：把 Session 编排管线包装为 HTTP API。

会话注册表在内存中（uvicorn 单进程联调；埋点事件经 EventLog 落 data/ 持久化，
data/ 已 gitignore——真实用户数据不随仓库分发）。

模式：
- mock（默认，零 key）：不配任何环境变量 → MockLLM + MockProvider，G1 演示全流程
- 真实：LLM_API_KEY（OpenAI 兼容，必配）+ DATASOURCE=akshare|tushare（可选，默认 mock）
- GET /api/health 回报当前模式，客户端据此渲染「模拟数据」标注与免责声明

红线复述（API 层不改变管线行为）：澄清必填阻断、确认条件化、买卖拒答与
升级路径全部由 orchestrator 真实代码执行，本层只做参数透传与序列化。
"""

from __future__ import annotations

import threading
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.datasources import get_provider
from app.llm import get_llm
from app.orchestrator import Session

EVENT_DIR = Path("data")

app = FastAPI(title="touyan-assistant", version="0.2.0")
_lock = threading.Lock()
_sessions: dict[str, Session] = {}


def _get_session(session_id: str) -> Session:
    with _lock:
        session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session


def _json(data) -> dict:
    """dataclass / StrEnum 安全序列化（fastapi 的 jsonable_encoder）。"""
    return jsonable_encoder(data)


# ------------------------------------------------------------------ 请求模型


class AskRequest(BaseModel):
    question: str


class ClarifyRequest(BaseModel):
    cost: float
    ratio: float
    horizon: str


class ConfirmRequest(BaseModel):
    action: str  # confirm | skip | disagree


class FollowupRequest(BaseModel):
    message: str


# ------------------------------------------------------------------ 端点


@app.get("/api/health")
def health() -> dict:
    llm = get_llm()
    provider = get_provider()
    return {
        "status": "ok",
        "llm_mode": getattr(llm, "mode", "unknown"),
        "datasource": provider.name,
        "simulated": bool(getattr(provider, "simulated", True)),
    }


@app.post("/api/sessions")
def create_session() -> dict:
    session_id = uuid4().hex[:8]
    session = Session(
        llm=get_llm(),
        provider=get_provider(),
        session_id=session_id,
        event_path=EVENT_DIR / f"{session_id}.jsonl",
    )
    with _lock:
        _sessions[session.id] = session
    return {"session_id": session.id}


@app.get("/api/sessions/{session_id}")
def session_state(session_id: str) -> dict:
    s = _get_session(session_id)
    return {
        "session_id": s.id,
        "stage": s.stage,
        "intent_line": s.intent_line,
        "holdings": _json(s.holdings),
        "refusal_state": s.refusal_state.value,
        "metrics": s.events.metrics(),
    }


@app.get("/api/sessions/{session_id}/events")
def session_events(session_id: str) -> dict:
    s = _get_session(session_id)
    return {"events": _json(s.events.events)}


@app.post("/api/sessions/{session_id}/touch")
def touch(session_id: str) -> dict:
    s = _get_session(session_id)
    payload = s.touch()
    if not s.provider.simulated:
        payload["note"] = (
            "触达内容为 G1 演示预置（真实推送链路不在 MVP 范围）；"
            "真实模式请直接从 /ask 开始解读。"
        )
    return _json(payload)


@app.post("/api/sessions/{session_id}/ask")
def ask(session_id: str, body: AskRequest) -> dict:
    s = _get_session(session_id)
    return _json(s.ask(body.question))


@app.post("/api/sessions/{session_id}/clarify")
def clarify(session_id: str, body: ClarifyRequest) -> dict:
    s = _get_session(session_id)
    return _json(s.submit_clarify(body.cost, body.ratio, body.horizon))


@app.post("/api/sessions/{session_id}/confirm")
def confirm(session_id: str, body: ConfirmRequest) -> dict:
    if body.action not in ("confirm", "skip", "disagree"):
        raise HTTPException(status_code=400, detail="action 必须是 confirm / skip / disagree")
    s = _get_session(session_id)
    return _json(s.confirm(body.action))


@app.post("/api/sessions/{session_id}/followup")
def followup(session_id: str, body: FollowupRequest) -> dict:
    s = _get_session(session_id)
    return _json(s.followup(body.message))


@app.post("/api/sessions/{session_id}/checklist/complete")
def complete_checklist(session_id: str) -> dict:
    s = _get_session(session_id)
    return _json(s.complete_checklist())


# ------------------------------------------------------------------ 服务入口

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8000)
