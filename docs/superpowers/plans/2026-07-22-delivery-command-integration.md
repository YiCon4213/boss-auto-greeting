# Safe Delivery, Natural-Language Commands, and Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让油猴脚本只消费已批准队列，按强 ID 重新定位并安全逐条发送；同时提供受限自然语言入口和可供未来上层项目调用的版本化子 Agent API。

**Architecture:** 本地服务维护唯一发送状态机并颁发短期浏览器任务；油猴只执行白名单动作并回报结构化结果。自然语言先解析为预览，不直接执行发送；外部调用使用本地令牌和 scopes，最终发送仍必须引用人工批准记录。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy 2、SQLite、原生 JavaScript、Tampermonkey、pytest。

**Prerequisite:** Phase 1–3 已完成、测试通过并提交。

**Compatibility baseline:** 固定使用 `127.0.0.1:8765` 和字符串 UUID；复用 Phase 1 的 `Batch`、`DeliveryItem`、`BrowserTask`，以及 Phase 2 已实现的租约/ack/progress/result API。`DeliveryItem` 保存业务发送状态，`BrowserTask` 保存任务租约状态，两者不得混用。Phase 4 新迁移从 `0004` 开始。

---

## Task 1: 实现发送状态机和浏览器任务 API

**Files:**
- Create: `agent_app/application/deliveries.py`
- Create: `agent_app/api/routers/deliveries.py`
- Modify: `agent_app/domain/enums.py`
- Modify: `agent_app/domain/transitions.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Modify: `agent_app/main.py`
- Modify: `agent_app/web/index.html`
- Modify: `agent_app/web/app.js`
- Create: `tests/unit/test_delivery_service.py`
- Create: `tests/api/test_delivery_api.py`

- [ ] **Step 1: 写状态机失败测试**

沿用现有单项状态：`approved -> locating -> revalidating -> sending -> sent|already_contacted|unavailable|identity_mismatch|send_failed|cancelled`；沿用现有批次状态：`approved -> executing -> completed|paused|paused_security|failed|cancelled`。`leased` 属于 `BrowserTask` 而不是 `DeliveryItem`。验证未批准批次执行返回 409，已发送项不能再次创建任务，过期任务由 Phase 2 租约协议重新领取，同一 `idempotency_key` 的结果重复上报不重复计数。

- [ ] **Step 2: 写 API 失败测试**

```text
POST /api/v1/batches/{id}/execute                    -> 200
POST /api/v1/batches/{id}/pause                      -> 200
POST /api/v1/batches/{id}/resume                     -> 200
GET  /api/v1/batches/{id}/report                     -> 200
GET  /api/v1/browser/tasks/next?worker_id=<id>       -> 200 or 204
POST /api/v1/browser/tasks/{taskId}/ack               -> 200
POST /api/v1/browser/tasks/{taskId}/progress          -> 200
POST /api/v1/browser/tasks/{taskId}/result            -> 200
```

Phase 2 的任务领取响应只能增加执行所需的批准文本、强 ID、预期公司/岗位摘要、合理等待配置和过期时间，不得包含任意 JavaScript 或 CSS 选择器代码。应用令牌负责显式执行/暂停/恢复，浏览器令牌只可领取和回报任务。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_delivery_service.py tests/api/test_delivery_api.py -q
```

Expected: service/route missing。

- [ ] **Step 4: 实现串行租赁与结果规则**

```python
class DeliveryService:
    def start(self, batch_id: str) -> DeliveryBatchView:
        raise NotImplementedError

    def lease_next(self, worker_id: str) -> BrowserTaskView | None:
        raise NotImplementedError

    def record_result(self, task_id: str, result: DeliveryResultIn) -> DeliveryItemView:
        raise NotImplementedError
```

将占位异常替换为事务实现：每批同一时刻最多一个活动 `BrowserTask` 租约；`sent`、`already_contacted`、`unavailable`、`identity_mismatch` 结束当前项并继续；`normal_failure` 映射为 `send_failed` 并继续；`captcha`、`login_required`、`security_check` 将批次置为 `paused_security`，保留当前项为可恢复状态且不自动恢复。报告按现有状态给出数量和每项安全摘要。

工作台只在批次 `approved` 时显示独立的“开始执行”按钮；它与 Phase 3 的“批准本批次”动作分离，必须由用户再次点击。执行接口使用应用令牌并记录审计事件，不能由浏览器任务结果或模型调用隐式触发。

- [ ] **Step 5: 测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_delivery_service.py tests/api/test_delivery_api.py -q
git add agent_app/application/deliveries.py agent_app/api/routers/deliveries.py agent_app/domain/enums.py agent_app/domain/transitions.py agent_app/infrastructure/models.py agent_app/infrastructure/repositories.py agent_app/main.py agent_app/web/index.html agent_app/web/app.js tests/unit/test_delivery_service.py tests/api/test_delivery_api.py
git commit -m "feat: add approval-gated delivery state machine"
```

Expected: tests pass。

## Task 2: 在油猴中按强 ID 重新定位并校验身份

**Files:**
- Modify: `zhipin-auto-greeting.user.js`
- Create: `tests/userscript/test_delivery_contract.py`
- Create: `tests/fixtures/job-list-reordered.html`
- Create: `tests/fixtures/job-detail-mismatch.html`

- [ ] **Step 1: 写脚本静态契约失败测试**

断言存在 `ApprovedQueueRunner`、`relocateByStrongIdentity`、`validateCurrentJobIdentity`、`reportDeliveryResult`；发送文本只能来自租赁任务的 `approvedGreeting`；不得调用调试解锁脚本、自动处理验证码、导出 Cookie 或执行服务端返回代码。

- [ ] **Step 2: 写身份匹配数据测试**

用夹具验证：列表重排后仍按 `encryptJobId` 优先找到职位；缺少主 ID 时只有 `securityId` 与 `lid` 组合一致才允许继续；强 ID 冲突返回 `identity_mismatch`；同一强 ID 即使 JD 文本变化也继续使用批准文本；页面已标记沟通过返回 `already_contacted`。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/userscript/test_delivery_contract.py -q
```

Expected: missing runner functions。

- [ ] **Step 4: 实现 ApprovedQueueRunner**

Runner 仅在 Agent 模式开启、服务健康且用户已从工作台批准后运行。每次租赁一项：在当前列表尝试定位；未找到时使用任务携带的可验证详情 URL 导航；页面稳定后重新读取强 ID 和沟通状态；校验通过才填入 `approvedGreeting` 并点击现有沟通控件。列表刷新后不依赖旧 DOM 引用或旧序号。

- [ ] **Step 5: 保持合理节奏和人工安全停点**

复用原项目已有最长/最短间隔与页面等待设置，但配置文案定义为“操作节奏”，不承诺规避检测。检测到验证码、重新登录或安全校验时立即停止点击、上报暂停原因并在面板和工作台提示用户手动处理。

- [ ] **Step 6: 测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/userscript/test_delivery_contract.py -q
node --check .\zhipin-auto-greeting.user.js
git add zhipin-auto-greeting.user.js tests/userscript/test_delivery_contract.py tests/fixtures/job-list-reordered.html tests/fixtures/job-detail-mismatch.html
git commit -m "feat: deliver approved greetings by strong job identity"
```

Expected: tests pass and Node exits 0。

## Task 3: 完成失败继续、整批暂停与独立模式回归

**Files:**
- Modify: `zhipin-auto-greeting.user.js`
- Modify: `agent_app/application/deliveries.py`
- Create: `tests/unit/test_delivery_error_policy.py`
- Create: `tests/contracts/test_standalone_mode.py`

- [ ] **Step 1: 写错误策略与兼容性失败测试**

逐一验证普通结果：`sent`、`already_contacted`、`unavailable`、`identity_mismatch`、`normal_failure`（映射为 `send_failed`）会解析当前浏览器任务并领取下一项；`captcha`、`login_required`、`security_check` 会暂停整批，且下一次 `GET /browser/tasks/next` 返回 204。静态回归验证 Agent 配置默认关闭、健康检查失败后进入独立模式、原固定问候语和原开始/停止入口仍存在。

- [ ] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_delivery_error_policy.py tests/contracts/test_standalone_mode.py -q
```

Expected: at least one policy assertion fails。

- [ ] **Step 3: 实现结果分类和 UI 提示**

服务端持有权威状态；脚本上报后以服务端响应决定继续或暂停。普通失败提示保持非阻塞，安全暂停显示明确原因和“处理后在工作台恢复”指引。恢复接口只允许 `paused` 或 `paused_security` 批次，且用户处理页面问题后必须在工作台显式点击；服务和脚本均不得自动处理验证码、登录或安全校验。

- [ ] **Step 4: 全部测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_delivery_error_policy.py tests/contracts/test_standalone_mode.py -q
node --check .\zhipin-auto-greeting.user.js
git add zhipin-auto-greeting.user.js agent_app/application/deliveries.py tests/unit/test_delivery_error_policy.py tests/contracts/test_standalone_mode.py
git commit -m "fix: enforce delivery pause and continuation policy"
```

Expected: tests pass。

## Task 4: 添加受限自然语言任务入口

**Files:**
- Create: `agent_app/application/commands.py`
- Create: `agent_app/api/routers/commands.py`
- Modify: `agent_app/main.py`
- Modify: `agent_app/web/index.html`
- Modify: `agent_app/web/app.js`
- Create: `tests/unit/test_command_service.py`
- Create: `tests/api/test_command_api.py`

- [ ] **Step 1: 写命令白名单失败测试**

支持的意图仅为 `create_batch`、`show_batch`、`open_approval`、`pause_delivery`、`resume_delivery`、`show_report`。自然语言“帮我筛选当前页面的 10 个岗位”解析为待确认预览；“直接给全部 HR 发消息”不得绕过批准；未知或含任意脚本/URL 导航指令的输入返回 `unsupported`。

- [ ] **Step 2: 写两阶段 API 失败测试**

```text
POST /api/v1/commands/preview -> 200, command_id + normalized intent + effects
POST /api/v1/commands/{id}/confirm -> 200
```

确认只能执行预览中冻结的白名单参数；`create_batch` 可创建采集任务，`open_approval` 只返回本地工作台路径，发送相关命令仍检查批次已批准。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_command_service.py tests/api/test_command_api.py -q
```

Expected: command modules missing。

- [ ] **Step 4: 实现确定性优先的解析器**

先用关键词和显式数字解析；仅在无法确定意图且模型已配置时请求结构化 `CommandIntent`。不把命令当代码执行，不让模型生成浏览器动作。所有改变状态的命令先预览后确认；确认记录操作者、时间和规范化参数。

- [ ] **Step 5: 在工作台加入简洁命令框并提交**

命令框显示解析预览和确认按钮；确认 `open_approval` 后在当前窗口跳到对应批次，不自动打开外部 BOSS 页面。执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_command_service.py tests/api/test_command_api.py -q
node --check .\agent_app\web\app.js
git add agent_app/application/commands.py agent_app/api/routers/commands.py agent_app/main.py agent_app/web/index.html agent_app/web/app.js tests/unit/test_command_service.py tests/api/test_command_api.py
git commit -m "feat: add confirmed natural-language commands"
```

Expected: tests pass。

## Task 5: 固化外部子 Agent API 与权限范围

**Files:**
- Modify: `agent_app/api/dependencies.py`
- Create: `agent_app/api/routers/integrations.py`
- Modify: `agent_app/main.py`
- Create: `agent_app/client.py`
- Create: `tests/api/test_integration_auth.py`
- Create: `tests/api/test_integration_contract.py`
- Create: `docs/api-v1.md`
- Create: `alembic/versions/0004_integration_tokens.py`

- [ ] **Step 1: 写认证和越权失败测试**

令牌 scope 固定为 `jobs:collect`、`batches:read`、`batches:write`、`approvals:read`、`delivery:start`。无令牌返回 401，scope 不足返回 403；即使有 `delivery:start`，未批准批次仍返回 409；任何 API 都不能提交“批准”动作或批准文本。

- [ ] **Step 2: 写客户端契约失败测试**

`ResumeDeliveryAgentClient` 提供 `create_batch()`、`get_batch()`、`start_analysis()`、`get_review()`、`start_delivery()`、`get_report()`；默认 `base_url=http://127.0.0.1:8765/api/v1`，明确超时，不自动重试改变状态的请求。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_integration_auth.py tests/api/test_integration_contract.py -q
```

Expected: auth/client missing。

- [ ] **Step 4: 实现本地令牌和客户端**

复用 Phase 1 的应用令牌和浏览器令牌校验，不改变其 scope；迁移 `0004_integration_tokens` 新增独立的集成令牌元数据表，只保存哈希、名称、scopes、创建/撤销时间。集成令牌明文只在创建时显示一次，且不得经普通查询接口回显。服务仍只绑定 `127.0.0.1`。客户端只封装版本化 HTTP API，不导入应用内部仓储或数据库。

- [ ] **Step 5: 编写可调用契约文档并提交**

`docs/api-v1.md` 必须列出认证、每个端点的请求/响应示例、状态机、幂等规则、错误码，以及“外部 Agent 无权替代人工批准”的安全边界。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_integration_auth.py tests/api/test_integration_contract.py -q
git add agent_app/api/dependencies.py agent_app/api/routers/integrations.py agent_app/main.py agent_app/client.py alembic/versions/0004_integration_tokens.py tests/api/test_integration_auth.py tests/api/test_integration_contract.py docs/api-v1.md
git commit -m "feat: expose scoped resume delivery agent api"
```

Expected: tests pass。

## Task 6: 端到端验证、运行说明与发布门禁

**Files:**
- Create: `tests/api/test_end_to_end_batch.py`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `scripts/start-agent.ps1`

- [ ] **Step 1: 写无真实发送的端到端测试**

使用内存数据库、假模型和假浏览器结果验证完整链路：创建批次 → 采集 3 个快照 → 分析（含一个模型失败）→ 修改问候语 → 批准 2 个 → 租赁 → 一个 sent、一个 unavailable → 批次 completed → 报告计数正确。另测未经批准无法租赁。

- [ ] **Step 2: 运行端到端测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_end_to_end_batch.py -q
```

Expected: orchestration assertion fails until wiring is complete。

- [ ] **Step 3: 补齐启动和用户文档**

`scripts/start-agent.ps1` 校验虚拟环境后执行 `uvicorn agent_app.main:app --host 127.0.0.1 --port 8765`。README 依次说明：安装、初始化数据库、配置画像/模型、安装油猴、独立模式、Agent 模式、审批与显式执行、安全暂停、数据清理和外部 API。`.env.example` 只含非秘密示例值；`.gitignore` 排除 `.env`、`data/`、数据库、日志和测试缓存。

- [ ] **Step 4: 执行自动化发布门禁**

```powershell
.\.venv\Scripts\python.exe -m pytest -q --cov=agent_app --cov-report=term-missing --cov-fail-under=80
node --check .\zhipin-auto-greeting.user.js
node --check .\agent_app\web\app.js
.\.venv\Scripts\alembic.exe upgrade head
git diff --check
git status --short
```

Expected: tests pass且总覆盖率至少 80%；JavaScript 语法检查成功；迁移成功；`git diff --check` 无输出；状态只包含本任务文件。

- [ ] **Step 5: 执行真实浏览器小批量人工验收**

在用户本人已登录环境、合法筛选页面中使用 2–3 个岗位：先确认独立模式仍工作；Agent 模式采集后检查快照、分析和问候语；批准前确认没有发送；批准后再次确认仍未发送，再由用户点击“开始执行”观察逐条定位；人为触发停止并确认不会继续；若出现验证码/登录/安全校验，只验证暂停，不尝试自动处理。记录岗位强 ID、结果类别和时间，不记录 Cookie、联系方式或 API Key。

- [ ] **Step 6: 提交最终文档与端到端测试**

```powershell
git add tests/api/test_end_to_end_batch.py README.md docs/README.md .gitignore .env.example scripts/start-agent.ps1
git commit -m "docs: complete local resume delivery agent workflow"
git status --short
```

Expected: commit succeeds；最终工作树为空。

## Final Acceptance Gate

- [ ] 油猴独立模式在 Agent 关闭和服务不可用时都可用。
- [ ] Agent 完整链路只处理一个批准批次，然后停止。
- [ ] 列表刷新/重排不依赖旧 DOM；强 ID 不匹配绝不发送。
- [ ] 同强 ID 的 JD 更新不改变已批准问候语。
- [ ] 单项普通失败继续；验证码、登录和安全校验整批暂停。
- [ ] 模型、工作台、自然语言和外部 API 均不能绕过人工批准。
- [ ] 密钥和默认排除的个人字段不进入数据库普通表、日志或导出。
- [ ] 自动化门禁和 2–3 条人工验收均通过，文档可让新会话和普通用户复现。
- [ ] 按 `AGENTS.md` 更新所有受影响文档，清理确认无独有决策或证据的过时过程文件，并确认工作树只包含本阶段预期改动。
