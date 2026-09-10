# 看懂你的自选股 · AI 投研助手 / touyan-assistant

An open-source AI research assistant for A-share retail investors: **noise filtering + explainable interpretation** around your watchlist — it clarifies "what happened, and what it means to you", and never tells you to buy or sell.

围绕自选股做**噪音过滤 + 可解释解读**，看清「发生了什么、与我何干」——不做买卖决定。

[![CI](https://github.com/Jacky-J126/touyan-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Jacky-J126/touyan-assistant/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **状态：四阶段全部完成**（mock 管线 → 测试与评测体系 → 真实数据源 → CI + 上线 GitHub）。零 key 复现 G1 Demo 全流程；真实模式自配 LLM key 与数据源即可联调。

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
| [docs/manual-eval/](docs/manual-eval/) | 人工测评四件套：区分测验 / 可信度感知问卷 / think-aloud 可用性测试 / 术语理解度测验（不进 CI，上线前人工执行） |

## 路线图 / Roadmap

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 仓库化与基线 | 文档族入库、LICENSE、README、基线提交 | ✅ 完成 |
| 2 mock 管线 | 管线 S1–S7 + Streamlit P0–P6，零 key 复现 Demo 全流程 | ✅ 完成 |
| 3 测试与评测 | 数据集 G1–G3/D1–D7、J1–J4 Judge harness、代码断言、红线门槛、人工测评材料 | ✅ 完成（元测试） |
| 4 真实数据源 + 上线 | akshare/tushare Provider、FastAPI、CI（3.11/3.12 矩阵 + 离线评测）、llm-eval workflow、GitHub 上线 | ✅ 完成 |

## 快速开始 / Quick start

mock 模式零配置零 key（G1 沐辰智控场景，全量模拟数据）：

```bash
git clone https://github.com/Jacky-J126/touyan-assistant.git
cd touyan-assistant
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev]"

# ① CLI 复现 Demo 全流程 + 三条支线（触达→解读→拒答升级→恢复）
.venv/bin/python scripts/demo.py

# ② Web 演示（P0–P6 全页面）
.venv/bin/streamlit run app/web/app.py

# ③ 测试与静态检查
.venv/bin/python -m pytest && .venv/bin/ruff check .

# ④ 评测（元测试：数据集 → mock 管线 → Judge → 报告，无需任何 key）
.venv/bin/python -m evals.runner   # 报告输出至 evals/latest-report.md

# ⑤ HTTP API（mock 模式零 key）
.venv/bin/uvicorn app.api:app --port 8000   # 依赖 [api] extra：pip install -e ".[api]"
```

## 真实模式 / Real mode

mock 是默认且唯一零配置路径；真实模式按需逐层启用：

```bash
.venv/bin/python -m pip install -e ".[real,api]"

# ① 真实 LLM（必配，OpenAI 兼容接口）
export LLM_API_KEY=sk-...                # 可选：LLM_BASE_URL / LLM_MODEL

# ② 真实数据源（二选一，不配则沿用 mock 数据）
export DATASOURCE=akshare                # 免费免 key；公告/研报/股吧人气/行情
export DATASOURCE=tushare                # 另需 TUSHARE_TOKEN；公告/新闻/研报/行情

.venv/bin/uvicorn app.api:app --port 8000
```

- 数据源未安装、无 token 或接口异常时**逐源降级并在结论中明示**（红线：降级明示 100%），绝不假装完整；
- 真实模式的实际接口可达性以本地实测为准（本仓库 CI 不联网调用数据源）；
- GET `/api/health` 回报 `llm_mode` / `datasource`，客户端据此渲染「模拟数据」标注。

### API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 模式与数据源状态 |
| POST | `/api/sessions` | 新建会话（埋点落 `data/`，已 gitignore） |
| GET | `/api/sessions/{id}` | 会话状态与指标（打开/追问/清单完成/跳过率） |
| POST | `/api/sessions/{id}/touch` | P0 触达 |
| POST | `/api/sessions/{id}/ask` | 提问（澄清/结论/拒答按管线推进） |
| POST | `/api/sessions/{id}/clarify` | 提交持仓三要素（必填阻断） |
| POST | `/api/sessions/{id}/confirm` | `confirm` / `skip` / `disagree`（跳过必记录） |
| POST | `/api/sessions/{id}/followup` | 追问（买卖请求拒答 + 两级升级 + 合规话题恢复） |
| POST | `/api/sessions/{id}/checklist/complete` | 自检清单完成 |
| GET | `/api/sessions/{id}/events` | 埋点事件链 |

## 评测 / Evaluation

- **元测试**（离线，零 key）：`python -m evals.runner`——黄金集 30 变体 × 3 持仓 + 拓展集 49 条目共 199 条执行记录，红线全过才出报告；
- **真实 LLM Judge 双评**（评测方案 3.2，需两套 Judge 配置）：`python -m evals.llm_eval` 或 GitHub `LLM Judge Eval` workflow（手动触发，分差 ≥2 标记转人工仲裁，报告作 artifact）；
- **人工测评四件套**：见 [docs/manual-eval/](docs/manual-eval/)。

## 代码结构 / Structure

```text
app/
├── orchestrator.py      # 会话编排：主流程 ①→⑩ + 降级/拒答/升级三支线（HITL 全在确定性代码）
├── pipeline/            # S1–S7 管线节点（澄清/确认/个性化/状态机为真实代码，mock/真实共用）
├── llm/                 # MockLLM（脚本化 G1 响应）+ OpenAICompat（防御式 JSON 解析）
├── datasources/         # Provider 协议 + MockProvider / AkshareProvider / TushareProvider（降级明示）
├── compliance.py        # 买卖请求词表 + 两级升级状态机（漏放率 0 红线）
├── events.py            # 埋点事件链 + 会话指标（打开/追问/清单完成/跳过率）
├── api.py               # FastAPI 服务（会话注册表 + 全流程端点 + health 模式报告）
└── web/app.py           # Streamlit P0–P6 页面
prompts/                 # 各阶段提示词（放文件不放代码）
scripts/demo.py          # CLI 演示
tests/                   # 确定性单测（红线断言 + 状态机 + 全流程集成 + API + 评测元测试）
evals/                   # 评测体系：断言、J1–J4 Judge、runner、llm_eval、阈值、报告
datasets/                # 黄金集 G1–G3（30 变体 × 3 持仓）+ 拓展集 D1–D7（49 条目）
docs/manual-eval/        # 人工测评四件套（不进 CI）
.github/workflows/       # ci.yml（矩阵 + 离线评测）+ llm-eval.yml（手动触发双评）
```

## 免责声明 / Disclaimer

- 本项目仅为学习与产品研究用途；全部输出**不构成投资建议**，买卖决策与责任由用户自行承担。
- 涉及买卖建议时系统一律拒答（投资顾问业务持牌红线）。
- 演示与测试使用的行情、公告、新闻、研报数据均为**模拟数据**，并显式标注。
- 真实数据源接口（akshare/tushare 等）仅供个人学习研究，请遵守各数据源的服务条款；tushare 部分接口有积分档位门槛，未达档位时系统降级明示。
- API key 与 token 只经环境变量注入（`.env` 已 gitignore），仓库不包含任何密钥。
- 真实系统**不内置任何默认持仓参数**（「AI 不得替你假设」红线）。
