# 当前项目状态审计

更新时间：2026-07-22。本文描述 Phase 2 自动化实现完成、首次真实浏览器退出门禁因 BOSS 安全验证阻塞时的代码事实，不替代产品需求或设计规格。

## 1. 仓库与分支边界

`D:\Web\boss\boss-auto-greeting` 是独立 Git 仓库，位于另一个 Git 仓库 `D:\Web\boss` 内。Phase 1 已通过 PR #1 合入 `main`；Phase 2 位于 `codex/phase-2-browser-bridge-collection`，不得在人工退出门禁通过前开始 Phase 3。

## 2. 已实现能力

### 2.1 Phase 1 基础

- `agent_app.main.create_app()` 提供 FastAPI 应用工厂，默认监听 `127.0.0.1:8765`。
- 应用令牌和浏览器令牌分离，模型密钥只进入 `SecretStore`。
- 画像、模型非敏感配置、批次基础状态机和 11 张业务表继续复用。

### 2.2 浏览器任务协议

- Alembic head 为 `0002`；只给既有 `browser_tasks` 增加 `leased_by`、`attempt_count`、`progress_sequence`、`acked_at` 和 `resolved_at`。
- 浏览器任务只允许 `collect_batch`、`execute_delivery` 和 `pause`，采用 30 秒租约、worker 所有权、单调进度序号和“首个终态获胜”的幂等规则。
- 浏览器桥接接口位于 `/api/v1/browser/*` 并只接受浏览器令牌；应用令牌不能调用。
- `python -m agent_app.cli show-browser-token` 是唯一显式读取浏览器令牌的本机入口，HTTP API 不回显任何令牌。

### 2.3 油猴 AgentBridge 与采集

- `agentModeEnabled` 默认 `false`；Agent 不在线或开关关闭时仍走原 `StandaloneAutomation`。
- Agent 地址只允许 `http://127.0.0.1:8765` 或同端口 `localhost`，不执行后端返回的任意代码、选择器或 URL。
- `BatchCollector` 使用独立的 `__zhipin_agent_task_state__`，只选择岗位卡片、等待稳定详情并提交快照。
- 采集代码不调用聊天按钮点击或 `GreetingService.sendCurrent`；`ApprovedQueueRunner` 仍是明确报错的未实现占位。
- 验证码、登录失效和安全校验产生 `paused_security` 并停止继续领取智能任务。

### 2.4 不可变职位快照与批次闭环

- 服务端只从 `encryptJobId`、`securityId`、`lid` 计算强身份键，并对规范化 JD 计算 SHA-256 指纹；客户端不能提供受信身份键或指纹。
- 同一批次同一强身份重复提交返回原快照，不改 payload 或指纹，并写 `job_snapshot_duplicate` 审计事件。
- `POST /api/v1/batches/{id}/collect` 幂等创建一个 `collect_batch` 任务。
- 成功结果必须与 SQLite 实际快照数一致；任务终结、审计、计数和 `collecting -> collected` 在同一事务提交。
- 普通失败进入 `failed`，安全错误进入 `paused_security`，已有快照不会删除。

## 3. 当前测试与验证证据

- 45 项 pytest 全部通过。
- `agent_app` 总覆盖率 93%。
- Python `compileall`、`node --check zhipin-auto-greeting.user.js` 和 `git diff --check` 通过。
- Alembic 在新 SQLite 上从空库升级到 `0002 (head)`。
- 仍有一条既有 FastAPI/Starlette `TestClient` 第三方弃用警告，不影响通过结果。
- 2026-07-22 首次打开真实 BOSS 岗位列表即出现“当前 IP 地址可能存在异常访问行为”的安全验证；未点击验证按钮，未进入聊天或发送。本地任务尚未创建，因此本次不能作为 `paused_security` 服务端状态证据；两岗位采集和独立模式回归仍未执行，Phase 2 退出门禁未通过。

## 4. 尚未实现或未验证

- 模型分析、个性化话术、审批工作台、不可变批准队列执行和自然语言命令尚未实现。
- `execute_delivery` 仍只返回“发送队列尚未实现”，不能用于 Agent 投递。
- 真实浏览器验证必须按 `docs/manual-testing/phase-2-collection.md` 在用户本人登录环境执行；遇验证码或安全校验只确认暂停，不处理或绕过。

## 5. 主要风险

1. 油猴主脚本仍是大型单文件；后续只能按职责扩展，不能借机整体重写。
2. BOSS 的 SPA、DOM 和内部接口可能变化，自动契约不能替代本人登录环境的小批量验证。
3. 当前只支持一个活动浏览器和一个执行批次；不得扩展为云端、多用户或绕过平台限制的服务。
4. 后续分析、审批和发送必须继续消费同一应用服务，不能复制业务规则或绕过人工审批。
