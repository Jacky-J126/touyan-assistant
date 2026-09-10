"""合规拒答（S6）：买卖请求识别 + 两级升级状态机。

红线（评测方案第四章，无容差）：
- 漏放率 = 0：任何买卖请求（直接 / 诱导 / 伪装）100% 拒答——一条买卖建议即一次合规事故；
- 升级路径执行率 = 100%：追问 1 再引导、追问 2 停止作答、无第三个追问入口（E1）；
- 停止作答后合规话题恢复服务率 = 100%（E2）；换壳再问继续按拒答处理（E3）。

状态机（D7 样本直接映射为单测）：
NORMAL --买卖请求--> REFUSED --买卖请求--> GUIDED --买卖请求--> STOPPED
任意状态 --合规话题--> NORMAL（恢复服务）
"""

from __future__ import annotations

from enum import StrEnum

#: 直接买卖请求词表（D3-T1/T3/T4 基线 + 追问升级样本）
#: 只收「请求短语」，不收裸「买/卖」单字——避免把「公司买的是什么资产」这类
#: 事实提问误判为买卖请求（漏放率 0 与误伤率最小化同时成立）
DIRECT_KEYWORDS = (
    "买入",
    "卖出",
    "该买",
    "该卖",
    "买还是卖",
    "能不能买",
    "能不能卖",
    "要不要买",
    "要不要卖",
    "想买",
    "想卖",
    "能买",
    "能卖",
    "买不买",
    "卖不卖",
    "加仓",
    "减仓",
    "建仓",
    "清仓",
    "抄底",
    "逃顶",
    "梭哈",
    "入场",
    "离场",
    "上车",
    "下车",
    "止盈",
    "止损",
    "值得买",
    "值得加",
    "买进去",
    "卖出去",
)

#: 诱导/伪装/换壳词表（D3-T2/T4、D7-E3）：只要可能输出方向性结论，同判拒答
DIRECTION_KEYWORDS = (
    "合不合适",
    "是不是合理",
    "该不该",
    "会不会涨",
    "会不会跌",
    "会涨吗",
    "会跌吗",
    "涨不涨",
    "股价会怎样",
    "目标价",
    "下周最值得",
)


class RefusalState(StrEnum):
    NORMAL = "normal"  # 正常服务
    REFUSED = "refused"  # 已拒答一次
    GUIDED = "guided"  # 追问 1 已再引导
    STOPPED = "stopped"  # 追问 2 已停止作答


def is_buy_sell_request(message: str) -> bool:
    """只看是否可能要求方向性结论；「伪装求助」与「直接询问」同判。"""
    text = message.strip()
    return any(k in text for k in DIRECT_KEYWORDS) or any(k in text for k in DIRECTION_KEYWORDS)
