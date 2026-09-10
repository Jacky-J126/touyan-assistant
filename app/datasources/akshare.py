"""AkshareProvider：akshare 免费数据源（公告 / 研报 / 股吧人气 / 行情）。

接口名实现期逐一验证（akshare 1.18.94，2026-09-10 实测）：
- `stock_notice_report(symbol=公告类型, date=YYYYMMDD)` → 全市场公告，按 代码 客户端过滤 ✅
  （symbol 参数是公告类型而非股票代码，按「资产重组」「重大事项」两档收窄）
- `stock_research_report_em(symbol)` ✅　`stock_hot_rank_em()` ✅（股吧人气榜，近似社区热度）
- `stock_news_em` / `stock_bid_ask_em` / `stock_zh_a_spot_em`：本机实测网络异常
  （ArrowInvalid / RemoteDisconnected），全部包在 try/except → 降级明示。

红线（评测方案第四章）：降级明示 100%——任何源失败只写进 degrade_note、
不产生伪装条目（失败的源绝不生成可被当作内容的召回项），管线「只给已召回事实并明示不足」。
akshare 为可选依赖（`pip install .[real]`）；未安装或接口异常时返回降级说明而非空跑。
"""

from __future__ import annotations

import datetime
import warnings

from app.models import RecallItem, RecallResult, SourceType

#: 公告类型档位（东财公告大全口径）：只取对投研解读有信息增量的类型
NOTICE_TYPES = ("资产重组", "重大事项")


def _plain_code(stock_code: str) -> str:
    """688521.SH → 688521（akshare 个股接口用纯数字代码）。"""
    return stock_code.split(".")[0]


class AkshareProvider:
    """真实数据源：公告、研报、股吧人气、行情（免费、无需 key）。"""

    name = "akshare"
    simulated = False

    def __init__(self, lookback_days: int = 3, max_items: int = 6):
        self.lookback_days = lookback_days
        self.max_items = max_items

    # ------------------------------------------------------------------ 召回

    def recall(self, stock_code: str) -> RecallResult:
        try:
            import akshare as ak
        except ImportError:
            return RecallResult(
                degrade_note="akshare 未安装（pip install .[real]）；无真实数据，仅降级说明。"
            )
        code = _plain_code(stock_code)
        items: list[RecallItem] = []
        notes: list[str] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            helpers = (self._notices, self._research, self._guba, self._quote_item, self._media)
            for helper in helpers:
                got, note = helper(ak, code)
                items += got
                if note:
                    notes.append(note)
        if not items:
            notes.insert(0, f"未召回任何 {stock_code} 的真实数据")
        return RecallResult(items=items, degrade_note="；".join(notes) or None)

    def _notices(self, ak, code: str) -> tuple[list[RecallItem], str | None]:
        """近 N 日公告（资产重组/重大事项两档）。全市场按日拉取，客户端按代码过滤。"""
        out: list[RecallItem] = []
        try:
            today = datetime.date.today()
            for offset in range(self.lookback_days):
                day = (today - datetime.timedelta(days=offset)).strftime("%Y%m%d")
                for notice_type in NOTICE_TYPES:
                    df = ak.stock_notice_report(symbol=notice_type, date=day)
                    rows = df[df["代码"] == code]
                    for _, r in rows.head(self.max_items).iterrows():
                        out.append(
                            RecallItem(
                                source_type=SourceType.ANNOUNCEMENT,
                                source_name="东方财富·公告大全",
                                timestamp=str(r.get("公告日期", day)),
                                content=f"【{notice_type}】{r.get('公告标题', '')}"
                                f"（{r.get('网址', '')}）",
                            )
                        )
        except Exception as e:  # 网络/接口异常 → 降级明示，不产生伪装条目
            return [], f"公告源不可用（{type(e).__name__}）"
        return out, None

    def _research(self, ak, code: str) -> tuple[list[RecallItem], str | None]:
        try:
            df = ak.stock_research_report_em(symbol=code)
            out = []
            for _, r in df.head(self.max_items).iterrows():
                out.append(
                    RecallItem(
                        source_type=SourceType.RESEARCH,
                        source_name=f"{r.get('机构', '机构')}·东财研报",
                        timestamp=str(r.get("日期", "—")),
                        content=f"{r.get('报告名称', '')}（评级：{r.get('东财评级', '—')}）",
                    )
                )
            return out, None if out else "研报源当日无内容"
        except Exception as e:
            return [], f"研报源不可用（{type(e).__name__}）"

    def _guba(self, ak, code: str) -> tuple[list[RecallItem], str | None]:
        """股吧人气榜：个股上榜则给排名与涨跌幅；未上榜不视为失败（不是热门股）。"""
        try:
            df = ak.stock_hot_rank_em()
            rows = df[df["代码"] == code]
            if rows.empty:
                return [], None
            r = rows.iloc[0]
            return (
                [
                    RecallItem(
                        source_type=SourceType.GUBA,
                        source_name="股吧人气榜（东财）",
                        timestamp="实时",
                        content=(
                            f"人气榜第 {r.get('当前排名')} 名，最新价 ¥{r.get('最新价')}，"
                            f"涨跌幅 {r.get('涨跌幅')}%"
                        ),
                    )
                ],
                None,
            )
        except Exception as e:
            return [], f"股吧人气榜不可用（{type(e).__name__}）"

    def _quote_item(self, ak, code: str) -> tuple[list[RecallItem], str | None]:
        try:
            price = self._fetch_quote(ak, code)
            if price is None:
                return [], "行情快照不可用（接口异常）"
            return (
                [
                    RecallItem(
                        source_type=SourceType.QUOTE,
                        source_name="东方财富行情",
                        timestamp="实时",
                        content=f"现价 ¥{price}",
                    )
                ],
                None,
            )
        except Exception as e:
            return [], f"行情快照不可用（{type(e).__name__}）"

    def _media(self, ak, code: str) -> tuple[list[RecallItem], str | None]:
        """媒体新闻源：akshare 1.18.94 实测 stock_news_em 异常，异常即降级并注明。"""
        try:
            df = ak.stock_news_em(symbol=code)
            return [], None if len(df) else "媒体新闻源当日无内容"
        except Exception as e:
            return [], f"媒体新闻源不可用（{type(e).__name__}）"

    # ------------------------------------------------------------------ 行情

    def _fetch_quote(self, ak, code: str) -> float | None:
        """现价快照：五档 → 全市场快照逐级回退；任一成功即返回价格。"""
        try:
            df = ak.stock_bid_ask_em(symbol=code)
            for col in ("最新", "最新价"):
                if col in df.columns:
                    return float(df.iloc[0][col])
        except Exception:
            pass
        try:
            df = ak.stock_zh_a_spot_em()
            rows = df[df["代码"] == code]
            if not rows.empty:
                return float(rows.iloc[0]["最新价"])
        except Exception:
            pass
        return None

    def quote(self, stock_code: str) -> float | None:
        """个性化段现价；不可用返回 None（cost_line 明示「行情接口降级」）。"""
        try:
            import akshare as ak
        except ImportError:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return self._fetch_quote(ak, _plain_code(stock_code))
