# 实施计划索引

书面规格已经通过，产品代码尚未开始实施。执行时必须先读总计划，再按顺序完成四个阶段；每一阶段通过退出门禁并提交后才进入下一阶段。

1. [总实施计划](2026-07-22-local-resume-delivery-agent.md)
2. [Phase 1：本地服务与数据基础](2026-07-22-agent-foundation.md)
3. [Phase 2：油猴桥接与批次采集](2026-07-22-browser-bridge-collection.md)
4. [Phase 3：分析、话术与审批工作台](2026-07-22-analysis-approval-workbench.md)
5. [Phase 4：安全发送、自然语言与外部调用](2026-07-22-delivery-command-integration.md)

执行新会话应使用 `superpowers:executing-plans`，从 Phase 1 第一个未完成复选框开始。不要跨阶段并行修改共享状态机；不要重新生成规格或计划。
