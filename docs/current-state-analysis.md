# 当前项目状态审计

更新时间：2026-07-22。本文描述 Phase 3“分析、话术与审批工作台”实现及退出门禁通过后的代码事实，不替代产品需求或设计规格。

## 1. 仓库与分支边界

`D:\Web\boss\boss-auto-greeting` 是独立 Git 仓库，位于另一个 Git 仓库 `D:\Web\boss` 内。Phase 1 已通过 PR #1 合入 `main`，Phase 2 已通过 PR #2 合入 `main`。Phase 3 在 `codex/phase-3-analysis-approval-workbench` 完成，等待按仓库流程审阅和集成；不得在本分支提前开始安全发送。

## 2. 已实现能力

### 2.1 Phase 1 与 Phase 2 基线

- `agent_app.main.create_app()` 提供 FastAPI 应用工厂，默认监听 `127.0.0.1:8765`。
- 应用令牌和浏览器令牌分离，模型密钥只进入 `SecretStore`。
- Alembic `0002` 的浏览器任务租约、显式浏览器令牌 CLI、默认关闭的 `AgentBridge`、只采集不发送的 `BatchCollector`、强身份不可变快照和采集闭环继续复用。
- 油猴 `ApprovedQueueRunner` 仍为明确报错的未实现占位；Phase 3 没有增加浏览器发送入口。

### 2.2 隐私安全的模型适配

- `OpenAICompatibleClient` 只调用配置的 `{base_url}/chat/completions`，分析和问候语分别使用 `AnalysisModelOutput`、`GreetingModelOutput` 校验。
- 网络错误、超时、非 JSON、字段缺失和 schema 错误最多重试一次，最终只返回固定安全错误，不保存原始响应、API Key 或画像内容。
- 模型画像直接复用 `ProfileService.model_context()`；空字段和默认私密的电话、邮箱、地址不会进入模型请求。

### 2.3 可关闭分析与事实约束问候语

- 分析关闭时不调用模型，目标分为 `None`，岗位默认进入审批；开启时只有目标分决定默认选择：`0-29` 取消、`30-59` 谨慎、`60-100` 推荐。
- 个人分只用于解释和排序；地点与经验结构字段不进入目标方向上下文，画像缺失能力只记录为未知或风险提示。
- 分析失败保存 `analysis_failed` 和安全错误码，岗位仍可见但不能被选择进入批准队列。
- 问候语关闭时使用产品基础模板；开启时 `used_facts` 必须逐项存在于授权画像，电话、邮箱和地址在保存草稿前再次清除。
- 模型失败、不可追溯事实或长度错误保存 `generation_failed`，不会静默回退为可批准话术。

### 2.4 人工审批与不可变队列

- `POST /api/v1/batches/{id}/analyze`、`GET /review`、`PATCH /drafts/{snapshot_id}` 和 `POST /approve` 形成分析、审阅、编辑与批准闭环。
- 批次按冻结快照顺序逐项分析；单项模型失败记录后继续。重复 `analyzing` 请求不会启动第二个后台任务。
- 人工批准在一个事务中创建唯一 `ApprovalVersion(batch_id, version)`，并把强身份键、JD 指纹、岗位摘要、顺序和人工终稿复制到不可变 `DeliveryItem`。
- 空选择可以形成空批准版本；重复批准返回同一版本；批准后草稿不可修改。
- 批准动作不会创建 `execute_delivery` 浏览器任务。安全发送必须等待下一阶段独立的显式执行动作。

### 2.5 本地审批工作台

- `/` 提供无构建工具的原生 HTML/CSS/JavaScript 双栏工作台，动态内容只通过 `textContent` 或表单 `value` 渲染。
- 页面支持加载批次、启动分析、查看冻结 JD/匹配依据/风险、选择岗位、编辑并保存终稿，以及批准本批次；Phase 3 不显示发送按钮。
- 首页通过路径限制为 `/api` 的 HttpOnly、SameSite=Strict 会话 cookie 使用应用权限；JavaScript 和 API 响应均不读取或显示应用令牌。

## 3. 当前测试与验证证据

- 81 项 pytest 全部通过，`agent_app` 总覆盖率 92.42%。
- Python `compileall`、`node --check agent_app/web/app.js`、`node --check zhipin-auto-greeting.user.js` 和 `git diff --check` 通过。
- Alembic 在隔离的新 SQLite 上从空库升级到 `0003 (head)`；`0003` 只增加分析查询索引和审批版本唯一约束，没有创建同义业务表。
- 仍有一条既有 FastAPI/Starlette `TestClient` 第三方弃用警告，不影响通过结果。
- 本机工作台真实浏览器检查通过：桌面双栏正常；390×844 下网格折叠为单列，视口宽度与页面滚动宽度均为 375px，无横向溢出，固定批准按钮完整位于视口内。
- 工作台验证没有访问 BOSS、没有登录或验证码操作、没有调用真实模型、没有创建发送任务；预览服务和临时数据库已停止并清理。
- Phase 2 的用户本人 Chrome 两岗位只读采集、终态幂等、无聊天/无发送和独立模式真实浏览器证据继续有效。

## 4. 尚未实现

- `ApprovedQueueRunner`、发送前强 ID/会话复核、逐项发送验证、失败继续和安全暂停执行尚未实现。
- `execute_delivery` 仍只返回“发送队列尚未实现”，批准后的队列不能用于 Agent 投递。
- 自然语言命令、外部子 Agent 契约、完整批次报告和真实模型/本人登录环境下的端到端投递尚未实现。
- 后续真实浏览器验证必须由用户本人登录并授权；遇验证码、登录失效或安全校验只暂停，不处理或绕过。

## 5. 主要风险

1. 油猴主脚本仍是大型单文件；发送阶段只能按 `ApprovedQueueRunner` 职责扩展，不能借机整体重写。
2. 模型 schema 和事实白名单能阻断已知失败，但真实提供商兼容性仍需在不记录隐私的前提下小范围验证。
3. BOSS 的 SPA、DOM 和内部接口可能变化；自动契约不能替代本人登录环境的小批量发送前身份验证。
4. 当前只支持一个活动浏览器和一个执行批次；不得扩展为云端、多用户或绕过平台限制的服务。
5. 后续命令、外部 API 和发送必须继续消费同一不可变批准队列，不能复制业务规则或伪造审批状态。
