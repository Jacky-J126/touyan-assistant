"""TushareProvider：tushare pro 数据源（公告 / 新闻 / 研报 / 行情），token 可选。

接口按 tushare 官方文档实现（`pro.announcement` / `pro.news` / `pro.report_rc` /
`pro.daily`），部分接口有积分档位门槛——未达档位时 tushare 抛异常，Provider 捕获后
按源降级明示（红线：降级明示 100%）。各接口权限以用户 token 实际档位为准，
真实调用在配置 TUSHARE_TOKEN 后由用户自验（落地方案 §8「tushare token 可选」）。

tushare 为可选依赖（`pip install .[real]`）；未安装或无 token 时返回降级说明。
"""

from __future__ import annotations

import datetime
import os

from app.models import RecallItem, RecallResult, SourceType


class TushareProvider:
    """真实数据源（需 TUSHARE_TOKEN）：公告、新闻、研报、行情。"""

    name = "tushare"
    simulated = False

    def __init__(self, token: str | None = None, max_items: int = 6):
        self.token = (token or os.environ.get("TUSHARE_TOKEN", "")).strip()
        self.max_items = max_items

    def _api(self):
        """返回 (pro_api, degrade_note)；任一前置条件不满足返回 (None, 原因)。"""
        try:
            import tushare as ts
        except ImportError:
            return None, "tushare 未安装（pip install .[real]）"
        if not self.token:
            return None, "未配置 TUSHARE_TOKEN"
        try:
            return ts.pro_api(self.token), None
        except Exception as e:
            return None, f"tushare 连接失败（{type(e).__name__}）"

    # ------------------------------------------------------------------ 召回

    def recall(self, stock_code: str) -> RecallResult:
        pro, err = self._api()
        if err:
            return RecallResult(degrade_note=f"{err}；无真实数据，仅降级说明。")
        items: list[RecallItem] = []
        notes: list[str] = []
        for helper in (self._announcements, self._news, self._research, self._daily_item):
            got, note = helper(pro, stock_code)
            items += got
            if note:
                notes.append(note)
        if not items:
            notes.insert(0, f"未召回任何 {stock_code} 的真实数据")
        return RecallResult(items=items, degrade_note="；".join(notes) or None)

    def _window(self, days: int) -> tuple[str, str]:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    def _announcements(self, pro, stock_code: str) -> tuple[list[RecallItem], str | None]:
        """公告接口（需对应积分档位；ts_code 格式与 STOCK_CODE 一致：688521.SH）。"""
        try:
            start, end = self._window(30)
            df = pro.announcement(ts_code=stock_code, start_date=start, end_date=end)
            out = []
            for _, r in df.head(self.max_items).iterrows():
                out.append(
                    RecallItem(
                        source_type=SourceType.ANNOUNCEMENT,
                        source_name="tushare·公告",
                        timestamp=str(r.get("ann_date", "—")),
                        content=str(r.get("title", "")),
                    )
                )
            return out, None if out else "公告接口近 30 日无内容"
        except Exception as e:
            return [], f"公告接口不可用（{type(e).__name__}，可能未达积分档位）"

    def _news(self, pro, stock_code: str) -> tuple[list[RecallItem], str | None]:
        try:
            start, end = self._window(7)
            df = pro.news(ts_code=stock_code, start_date=start, end_date=end)
            out = []
            for _, r in df.head(self.max_items).iterrows():
                out.append(
                    RecallItem(
                        source_type=SourceType.MEDIA,
                        source_name=f"tushare·新闻（{r.get('src', '—')}）",
                        timestamp=str(r.get("datetime", "—")),
                        content=str(r.get("title", "")),
                    )
                )
            return out, None if out else "新闻接口近 7 日无内容"
        except Exception as e:
            return [], f"新闻接口不可用（{type(e).__name__}，可能未达积分档位）"

    def _research(self, pro, stock_code: str) -> tuple[list[RecallItem], str | None]:
        try:
            start, end = self._window(90)
            df = pro.report_rc(ts_code=stock_code, start_date=start, end_date=end)
            out = []
            for _, r in df.head(self.max_items).iterrows():
                out.append(
                    RecallItem(
                        source_type=SourceType.RESEARCH,
                        source_name=f"tushare·研报（{r.get('org_name', '—')}）",
                        timestamp=str(r.get("report_date", "—")),
                        content=str(r.get("title", "")),
                    )
                )
            return out, None if out else "研报接口近 90 日无内容"
        except Exception as e:
            return [], f"研报接口不可用（{type(e).__name__}，可能未达积分档位）"

    def _daily_item(self, pro, stock_code: str) -> tuple[list[RecallItem], str | None]:
        try:
            df = pro.daily(ts_code=stock_code, limit=1)
            if df.empty:
                return [], "行情接口无数据"
            r = df.iloc[0]
            return (
                [
                    RecallItem(
                        source_type=SourceType.QUOTE,
                        source_name="tushare·日线",
                        timestamp=str(r.get("trade_date", "—")),
                        content=f"收盘价 ¥{r.get('close')}，涨跌幅 {r.get('pct_chg')}%",
                    )
                ],
                None,
            )
        except Exception as e:
            return [], f"行情接口不可用（{type(e).__name__}，可能未达积分档位）"

    # ------------------------------------------------------------------ 行情

    def quote(self, stock_code: str) -> float | None:
        """个性化段现价（最新收盘）；不可用返回 None（cost_line 明示降级）。"""
        pro, err = self._api()
        if err:
            return None
        try:
            df = pro.daily(ts_code=stock_code, limit=1)
            if df.empty:
                return None
            return float(df.iloc[0]["close"])
        except Exception:
            return None
