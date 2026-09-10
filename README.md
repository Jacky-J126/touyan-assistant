# 看懂你的自选股 · AI 投研助手 / touyan-assistant

An open-source AI research assistant for A-share retail investors: **noise filtering + explainable interpretation** around your watchlist — it clarifies "what happened, and what it means to you", and never tells you to buy or sell.

围绕自选股做**噪音过滤 + 可解释解读**，看清「发生了什么、与我何干」——不做买卖决定。

> **状态：开发中**（阶段 1/4 完成：文档族入库）。mock 管线开发中，阶段 2 交付「零 key 复现 Demo 全流程」。

## 定位 / Positioning

- **核心用户**：有真实持仓、缺投研背景的普通投资者
- **不服务**：短线投机者 / 要荐股结论者 / 无持仓浏览者
- **四条信息标签**：【事实】必附信源与时间点 ·【推断】必附假设与置信度 ·【未知】必明说补充什么 ·【噪音】已过滤并附理由与判定标准（相关性/信源/时效）
- **三个 HITL 节点**：澄清（AI 不得替你假设持仓）→ 结论前确认（仅推断占比高或涉利空时）→ 买卖追问拒答（两级升级路径）
- **红线**：不做买卖决定——投顾持牌红线，任何买卖请求 100% 拒答

## 文档 / Docs

| 文件 | 内容 |
|---|---|
| [docs/prd.md](docs/prd.md) | PRD V0.2（Markdown 维护版，含评测方案裁定的两处回改） |
| [docs/eval-plan.md](docs/eval-plan.md) | 评测方案 V0.2：评测体系、Benchmark 数据集、Judge J1–J4、上线前最低验证标准、验证结论表 |
| [docs/prototype.html](docs/prototype.html) | 交互原型 V0.2（单文件 HTML，双击浏览器打开） |
| [docs/README.md](docs/README.md) | 文档族说明：阅读顺序、交互点清单、版本注记 |

## 路线图 / Roadmap

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 仓库化与基线 | 文档族入库、LICENSE、README、基线提交 | ✅ 完成 |
| 2 mock 管线 | 管线 S1–S7 + Streamlit P0–P6，零 key 复现 Demo 全流程 | 🚧 开发中 |
| 3 测试与评测 | 数据集 G1–G3/D1–D7、J1–J4 Judge harness、代码断言、红线门槛 | 待开始 |
| 4 真实数据源 + 上线 | akshare/tushare Provider、CI、GitHub 上线 | 待开始 |

## 快速开始 / Quick start

（占位——阶段 2 交付 mock 模式三步跑通；阶段 4 交付真实数据源配置。）

## 免责声明 / Disclaimer

- 本项目仅为学习与产品研究用途；全部输出**不构成投资建议**，买卖决策与责任由用户自行承担。
- 涉及买卖建议时系统一律拒答（投资顾问业务持牌红线）。
- 演示与测试使用的行情、公告、新闻、研报数据均为**模拟数据**，并显式标注。
- 真实数据源接口（akshare/tushare 等）仅供个人学习研究，请遵守各数据源的服务条款。
- 真实系统**不内置任何默认持仓参数**（「AI 不得替你假设」红线）。
