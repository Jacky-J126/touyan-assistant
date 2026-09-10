"""评测体系（阶段 3 · docs/eval-plan.md 的代码实现）。

- datasets/  黄金集 G1–G3（30 条）与拓展集 D1–D7（>=40 条）
- judges/    J1–J4 判官提示词（eval-plan 3.2 逐字入库）+ judges.py 实现
- assertions.py  3.1 确定性断言全表（17 项）
- runner.py  全量执行：黄金集 E2E + 拓展集定向执行 + 指标汇总
- report.py  报告输出：40/60 总分、红线否决、四态结论表
- thresholds.yaml  第四章阈值与红线的单一事实来源

元测试边界：mock 只替换「生成内容」（场景化 LLM/数据源），
管线编排、校验器、状态机、个性化纯函数、埋点均为真实代码。
"""
