"""埋点事件链（评测方案 1.1 指标口径）与指标计算。

事件链：会话开始 → 触达 → 提问 → 澄清提交 → 确认/跳过 → 结论达成 →
追问 → 拒答/清单 → 升级路径节点（V0.2 新增：跳过事件、个性化段渲染、升级路径节点）。

指标口径（照评测方案）：
- 打开率：触达后 7 日内点开解读的比例（会话级以「触达后有提问」计）
- 追问率：读完解读继续提问的比例
- 清单完成率：收到自检清单后完成勾选的比例
- 跳过率：确认环节被跳过的次数 ÷ 确认环节触达次数（观测线 >50% 触发复查）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Event:
    ts: str
    name: str
    payload: dict = field(default_factory=dict)


class EventLog:
    def __init__(self, path: Path | None = None):
        self.events: list[Event] = []
        self.path = path  # 持久化文件（data/ 目录，gitignore）

    def log(self, name: str, **payload) -> None:
        ev = Event(ts=_now(), name=name, payload=payload)
        self.events.append(ev)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                line = json.dumps(
                    {"ts": ev.ts, "name": ev.name, "payload": ev.payload}, ensure_ascii=False
                )
                f.write(line + "\n")

    def count(self, name: str) -> int:
        return sum(1 for e in self.events if e.name == name)

    def has(self, name: str) -> bool:
        return any(e.name == name for e in self.events)

    def metrics(self) -> dict:
        """会话级指标（多会话汇总由阶段 3 的评测 runner 承担）。"""
        touched = self.has("touch_delivered")
        asked = self.has("question_asked")
        concluded = self.has("conclusion_delivered")
        shown = self.count("confirm_shown")
        skipped = self.count("confirm_skipped")
        checklist_shown = self.has("checklist_shown")
        checklist_done = self.has("checklist_completed")
        return {
            "打开": bool(touched and asked),
            "追问": bool(concluded and self.has("followup_asked")),
            "清单完成": bool(checklist_shown and checklist_done),
            "跳过率": (skipped / shown) if shown else None,
            "事件数": len(self.events),
        }
