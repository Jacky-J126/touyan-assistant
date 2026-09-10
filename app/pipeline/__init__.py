"""处理管线：PRD 流程 ①→⑩ 的逐节点实现。

各节点对应评测方案子能力：intent(S1) → clarify(S5) → recall(S2) →
noise_filter(S3) → fact_infer(S4) → analyze(S4/S7) → confirm(S5) →
personalization(S7)；拒答/升级状态机在 compliance.py（S6）。
"""
