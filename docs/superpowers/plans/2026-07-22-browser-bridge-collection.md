# Browser Bridge and Batch Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让本地 Agent 通过受限、幂等、可续租的任务协议控制油猴脚本采集职位快照，同时确保 Agent 不在线时原有独立模式不受影响。

**Architecture:** 后端 `BrowserTaskService` 发布白名单任务并管理租约；油猴 `AgentBridge` 只在用户启用 Agent 模式后轮询本机服务。`BatchCollector` 复用现有 JobRepository 和详情抓取能力，只选择卡片、保存快照，不点击沟通按钮。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、pytest、原生 JavaScript、Tampermonkey、Node syntax checker。

## Global Constraints

- 先完成并通过 `2026-07-22-agent-foundation.md`。
- 浏览器任务类型首版只允许 `collect_batch`、`execute_delivery`、`pause`。
- 后端不得下发任意代码、任意 DOM 选择器或任意 URL。
- Agent 模式默认关闭；连接失败不会影响独立模式 UI 和状态机。
- 采集阶段禁止调用 `findChatButton`、`clickElement(chatButton)` 或 `GreetingService.sendCurrent`。
- 快照必须包含至少一个可靠强 ID；只有弱签名的岗位记录为不可投递快照。

## Phase 1 Compatibility Baseline

- 统一使用 `http://127.0.0.1:8765`，不得改为其它默认端口。
- 复用现有 `BrowserTask` 和 `JobSnapshot`；Alembic 新迁移编号为 `0002_browser_task_leasing`。
- 业务 ID 均为字符串；测试沿用可注入的 `session_factory` 和 `FileSecretStore`。
- 浏览器令牌已经存在于 `SecretStore`，HTTP API 不得回显；本阶段增加显式本机 CLI 供用户主动读取。
- Phase 1 的 16 项测试必须持续通过。

---

### Task 1: Implement Browser Task Leasing and Idempotency

**Files:**
- Create: `agent_app/application/browser_tasks.py`
- Create: `agent_app/api/routers/browser.py`
- Create: `agent_app/cli.py`
- Create: `alembic/versions/0002_browser_task_leasing.py`
- Create: `tests/unit/test_browser_task_leases.py`
- Create: `tests/unit/test_token_cli.py`
- Create: `tests/api/test_browser_tasks.py`
- Modify: `agent_app/domain/schemas.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Modify: `agent_app/main.py`

**Interfaces:**
- Consumes: browser-scoped token and `BrowserTaskCreate(type, payload, idempotency_key)`.
- Produces: `BrowserTaskService.create/take/ack/progress/resolve`, `/api/v1/browser/*` and `python -m agent_app.cli show-browser-token`.

- [x] **Step 1: Write failing lease tests**

```python
from datetime import timedelta


def test_expired_browser_task_can_be_released(clock, browser_task_service):
    task = browser_task_service.create(
        task_type="collect_batch",
        payload={"batch_id": "batch-1", "limit": 10},
        idempotency_key="collect:batch-1",
    )
    leased = browser_task_service.take("worker-1")
    assert leased.id == task.id
    clock.advance(timedelta(seconds=31))
    assert browser_task_service.take("worker-2").id == task.id


def test_duplicate_idempotency_key_returns_existing_task(browser_task_service):
    first = browser_task_service.create("pause", {}, "pause:batch-1")
    second = browser_task_service.create("pause", {}, "pause:batch-1")
    assert second.id == first.id
```

另外在 `tests/unit/test_token_cli.py` 写失败测试：显式 `show-browser-token` 只输出注入的浏览器令牌；未知命令非零退出；输出不得包含应用令牌或模型密钥。

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_browser_task_leases.py tests/unit/test_token_cli.py -v`

Expected: FAIL because `BrowserTaskService` does not exist.

- [x] **Step 3: Define browser task schemas**

```python
from typing import Literal

from pydantic import BaseModel, Field


BrowserTaskType = Literal["collect_batch", "execute_delivery", "pause"]


class BrowserTaskEnvelope(BaseModel):
    id: str
    type: BrowserTaskType
    payload: dict[str, object]
    lease_seconds: int = 30


class BrowserTaskProgress(BaseModel):
    sequence: int = Field(ge=0)
    status: str = Field(min_length=1, max_length=80)
    detail: dict[str, object] = Field(default_factory=dict)


class BrowserTaskResult(BaseModel):
    ok: bool
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
```

- [x] **Step 4: Implement leases and idempotent resolution**

迁移 `0002_browser_task_leasing` 只为现有 `browser_tasks` 增加 `leased_by`、`attempt_count`、`progress_sequence`、`acked_at` 和 `resolved_at`；不得重建或改名 Phase 1 表。`take(worker_id)` 使用带状态和租约条件的原子 `UPDATE` 领取最早 pending 或已过期任务，设置 `lease_expires_at = now + 30 seconds` 并增加 `attempt_count`；SQLite 竞争失败时重新查询，不依赖进程内锁。`ack` 只接受当前 worker，`progress` 忽略重复或更小序号，`resolve` 采用“首个终态结果获胜”的幂等规则。

`agent_app.cli` 只支持显式 `show-browser-token` 命令，从同一 `SecretStore` 读取浏览器令牌并输出到当前终端；不得提供 HTTP 令牌读取接口，不得输出应用令牌、模型 API Key 或其它密钥。CLI 测试注入 `FileSecretStore`，不访问系统 keyring。

- [x] **Step 5: Implement exact browser endpoints**

```text
POST /api/v1/browser/heartbeat
GET  /api/v1/browser/tasks/next?worker_id=<id>
POST /api/v1/browser/tasks/{task_id}/ack
POST /api/v1/browser/tasks/{task_id}/progress
POST /api/v1/browser/tasks/{task_id}/result
```

Return 204 when no task exists, 404 for unknown tasks, and 409 for wrong worker or invalid terminal state.

- [x] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\python.exe -m pytest tests/unit/test_browser_task_leases.py tests/unit/test_token_cli.py tests/api/test_browser_tasks.py -v
```

Expected: Alembic reports `0002 (head)`；lease expiry、条件领取、worker ownership、progress ordering、token scope、CLI secret isolation 和 idempotent result tests pass.

- [x] **Step 7: Commit**

```powershell
git add agent_app alembic/versions/0002_browser_task_leasing.py tests/unit/test_browser_task_leases.py tests/unit/test_token_cli.py tests/api/test_browser_tasks.py
git commit -m "feat: add leased browser task protocol"
```

### Task 2: Add Agent Mode Configuration Without Breaking Standalone Mode

**Files:**
- Modify: `zhipin-auto-greeting.user.js`
- Create: `tests/userscript/test_standalone_contract.py`
- Create: `tests/userscript/test_agent_bridge_contract.py`

**Interfaces:**
- Consumes: localStorage config fields `agentModeEnabled`, `agentBaseUrl`, `agentBrowserToken`.
- Produces: `AgentBridge.isEnabled/start/stop/heartbeat/pollOnce` and visible connection status.

- [x] **Step 1: Write failing static contract tests**

```python
from pathlib import Path


SCRIPT = Path("zhipin-auto-greeting.user.js")


def test_agent_mode_defaults_off_and_preserves_standalone_start():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "agentModeEnabled: false" in source
    assert "const StandaloneAutomation = Automation" in source
    assert "if (!config.agentModeEnabled)" in source


def test_browser_bridge_is_local_and_whitelisted():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "const AgentBridge =" in source
    assert "http://127.0.0.1:8765" in source
    assert "collect_batch" in source
    assert "execute_delivery" in source
    assert "eval(" not in source
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/userscript/test_standalone_contract.py tests/userscript/test_agent_bridge_contract.py -v`

Expected: FAIL because Agent configuration and bridge do not exist.

- [x] **Step 3: Extend config with disabled Agent defaults**

Add exact defaults:

```javascript
agentModeEnabled: false,
agentBaseUrl: 'http://127.0.0.1:8765',
agentBrowserToken: '',
agentWorkerId: '',
```

Add a small “本地 Agent” section with enable switch, service URL, browser token, connection indicator, and “检查连接”. 浏览器令牌由用户在本机显式运行 `.\.venv\Scripts\python.exe -m agent_app.cli show-browser-token` 后手工填入；不得从网页接口、日志或数据库读取明文。Keep the existing start button mapped to standalone automation when the switch is off.

- [x] **Step 4: Implement a whitelist-only AgentBridge**

```javascript
const ALLOWED_AGENT_TASK_TYPES = new Set(['collect_batch', 'execute_delivery', 'pause']);

const AgentBridge = {
  timer: null,
  inFlight: false,
  isEnabled() {
    return Boolean(config.agentModeEnabled && config.agentBrowserToken);
  },
  headers() {
    return {
      'Content-Type': 'application/json',
      'X-Agent-Token': config.agentBrowserToken,
    };
  },
  start() {
    if (!this.isEnabled() || this.timer) return;
    this.pollOnce();
    this.timer = setInterval(() => this.pollOnce(), 3000);
  },
  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  },
};
```

Use `GM_xmlhttpRequest` only for the configured loopback URL after validating hostname is `127.0.0.1` or `localhost` and port is `8765`. Reject every task type outside `ALLOWED_AGENT_TASK_TYPES` and report `unsupported_task_type` without executing it.

- [x] **Step 5: Route the UI start action by mode**

```javascript
if (config.agentModeEnabled) {
  AgentBridge.start();
  UI.setStatus('已启用本地 Agent，等待任务...', 'info');
} else {
  StandaloneAutomation.start();
}
```

Do not change the existing `Automation` implementation in this task; assign `const StandaloneAutomation = Automation` immediately after its definition.

- [x] **Step 6: Run contracts and JavaScript syntax check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/userscript/test_standalone_contract.py tests/userscript/test_agent_bridge_contract.py -v
node --check .\zhipin-auto-greeting.user.js
```

Expected: tests pass and Node exits 0.

- [x] **Step 7: Perform manual standalone smoke test**

With Agent mode off, reload the userscript and confirm: existing panel opens, existing config loads, “启动” enters the original list loop, and no request to port 8765 is made.

- [x] **Step 8: Commit**

```powershell
git add zhipin-auto-greeting.user.js tests/userscript
git commit -m "feat: add optional local agent bridge"
```

### Task 3: Persist Immutable Job Snapshots

**Files:**
- Create: `agent_app/application/snapshots.py`
- Create: `agent_app/api/routers/snapshots.py`
- Create: `tests/unit/test_job_identity.py`
- Create: `tests/api/test_job_snapshots.py`
- Create: `tests/fixtures/job_snapshot.json`
- Modify: `agent_app/domain/schemas.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Modify: `agent_app/main.py`

**Interfaces:**
- Consumes: `JobSnapshotCreate` from the browser.
- Produces: `make_job_identity_key`, `make_jd_fingerprint`, `POST /api/v1/browser/batches/{id}/snapshots`.

- [x] **Step 1: Write failing identity tests**

```python
def test_identity_prefers_reliable_ids():
    assert make_job_identity_key(
        encrypt_job_id="job-123", security_id="sec-1", lid="lid-1"
    ) == "job:job-123|security:sec-1|lid:lid-1"


def test_snapshot_requires_a_reliable_identity():
    with pytest.raises(ValueError, match="reliable job identity"):
        make_job_identity_key(encrypt_job_id="", security_id="", lid="")


def test_jd_fingerprint_ignores_whitespace():
    assert make_jd_fingerprint("职责一\n\n职责二") == make_jd_fingerprint("职责一 职责二")
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_job_identity.py -v`

Expected: FAIL because snapshot utilities do not exist.

- [x] **Step 3: Implement identity and JD fingerprint helpers**

```python
from hashlib import sha256
import re


def make_job_identity_key(*, encrypt_job_id: str, security_id: str, lid: str) -> str:
    parts = [
        ("job", encrypt_job_id.strip()),
        ("security", security_id.strip()),
        ("lid", lid.strip()),
    ]
    reliable = [(name, value) for name, value in parts if value]
    if not reliable:
        raise ValueError("reliable job identity is required")
    return "|".join(f"{name}:{value}" for name, value in reliable)


def make_jd_fingerprint(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description).strip()
    return sha256(normalized.encode("utf-8")).hexdigest()
```

- [x] **Step 4: Define `JobSnapshotCreate`**

Include strong IDs, title, company, salary, city, experience, degree, address, description, skills, Boss fields, company fields, source URL, expectation context, and `captured_at`. Reject missing title/company/description. The service computes identity and fingerprint; clients cannot provide trusted values for those fields.

- [x] **Step 5: Implement idempotent persistence**

On `(batch_id, job_identity_key)` conflict, return the existing snapshot ID and update neither the immutable payload nor its fingerprint. Record a duplicate audit event. Reject snapshots when the batch is not `collecting`.

- [x] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_job_identity.py tests/api/test_job_snapshots.py -v
```

Expected: identity, fingerprint, validation, duplicate, and wrong-batch-state tests pass.

- [x] **Step 7: Commit**

```powershell
git add agent_app tests/unit/test_job_identity.py tests/api/test_job_snapshots.py tests/fixtures/job_snapshot.json
git commit -m "feat: persist immutable job snapshots"
```

### Task 4: Implement BatchCollector in the Userscript

**Files:**
- Modify: `zhipin-auto-greeting.user.js`
- Create: `tests/userscript/test_batch_collector_contract.py`
- Modify: `tests/userscript/test_standalone_contract.py`

**Interfaces:**
- Consumes: `collect_batch` task payload `{batch_id, limit, source_url}`.
- Produces: progress events, snapshot POSTs, and terminal `{collected_count, exhausted}`.

- [x] **Step 1: Write the failing collector contract**

```python
def test_collector_uses_detail_repository_without_chat_send():
    source = Path("zhipin-auto-greeting.user.js").read_text(encoding="utf-8")
    start = source.index("const BatchCollector =")
    end = source.index("const ApprovedQueueRunner =", start)
    collector = source[start:end]
    assert "JobRepository.waitForJobDetail" in collector
    assert "postSnapshot" in collector
    assert "findChatButton" not in collector
    assert "GreetingService.sendCurrent" not in collector
    assert "clickElement(chatButton)" not in collector
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/userscript/test_batch_collector_contract.py -v`

Expected: FAIL because `BatchCollector` and `ApprovedQueueRunner` markers do not exist.

- [x] **Step 3: Add task dispatch with an empty ApprovedQueueRunner placeholder object**

```javascript
const ApprovedQueueRunner = {
  async run() {
    throw new Error('发送队列尚未实现');
  },
};

async function dispatchAgentTask(task) {
  if (!ALLOWED_AGENT_TASK_TYPES.has(task.type)) {
    throw new Error(`不支持的 Agent 任务：${task.type}`);
  }
  if (task.type === 'collect_batch') return BatchCollector.run(task);
  if (task.type === 'execute_delivery') return ApprovedQueueRunner.run(task);
  if (task.type === 'pause') return BatchCollector.pause(task);
  throw new Error(`未实现的 Agent 任务：${task.type}`);
}
```

- [x] **Step 4: Implement collection state isolated from RunState**

Store Agent task state under a new key `__zhipin_agent_task_state__`; do not reuse `APP.runKey`. Required fields: `taskId`, `batchId`, `phase`, `processedKeys`, `collectedCount`, `limit`, `sourceUrl`, `expectationContext`, and `updatedAt`.

- [x] **Step 5: Implement the collection loop**

For each unprocessed visible card: resolve its job through `JobRepository.syncCards`, click the card, wait for `waitForJobCommunicationDetail`, then call `JobRepository.waitForJobDetail(..., {includeHtml: true, forceApiFetch: true})`. Reject if no reliable key exists. Flatten the merged job into the backend schema and POST it. Mark processed only after the backend accepts or reports duplicate.

The loop ends when accepted snapshots reach `limit`, three scroll attempts show no progress, the user pauses, or a security page is detected. It must not call chat-button lookup or send services.

- [x] **Step 6: Run static contracts and syntax check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/userscript -v
node --check .\zhipin-auto-greeting.user.js
```

Expected: all userscript contracts pass and syntax check exits 0.

- [x] **Step 7: Commit**

```powershell
git add zhipin-auto-greeting.user.js tests/userscript
git commit -m "feat: collect agent job batches"
```

### Task 5: Close Collection Tasks and Advance Batch State

**Files:**
- Modify: `agent_app/application/browser_tasks.py`
- Modify: `agent_app/application/batches.py`
- Modify: `agent_app/api/routers/browser.py`
- Create: `tests/api/test_collection_flow.py`
- Create: `docs/manual-testing/phase-2-collection.md`

**Interfaces:**
- Consumes: successful `collect_batch` result.
- Produces: atomic browser-task completion and batch transition to `collected`.

- [x] **Step 1: Write the failing integration test**

```python
def test_collection_result_advances_batch(client, app_headers, browser_headers):
    batch = client.post(
        "/api/v1/batches",
        headers=app_headers,
        json={"limit": 2, "source_url": JOB_LIST_URL},
    ).json()
    client.post(f"/api/v1/batches/{batch['id']}/collect", headers=app_headers)
    task = client.get(
        "/api/v1/browser/tasks/next?worker_id=test-browser",
        headers=browser_headers,
    ).json()
    response = client.post(
        f"/api/v1/browser/tasks/{task['id']}/result",
        headers=browser_headers,
        json={"ok": True, "result": {"collected_count": 2, "exhausted": False}},
    )
    assert response.status_code == 200
    current = client.get(f"/api/v1/batches/{batch['id']}", headers=app_headers).json()
    assert current["status"] == "collected"
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/api/test_collection_flow.py -v`

Expected: FAIL because `/collect` or completion coordination is missing.

- [x] **Step 3: Implement atomic collection completion**

`POST /batches/{id}/collect` transitions `draft -> collecting` and creates one idempotent `collect_batch` task. Resolving that task successfully verifies snapshot count, records audit data, and transitions `collecting -> collected` in one SQLAlchemy transaction. Failed or security results transition to `failed` or `paused_security` without deleting snapshots.

- [x] **Step 4: Add the manual Phase 2 checklist**

Document exact steps: migrate to `0002`, start service on `127.0.0.1:8765`, use the explicit CLI to obtain the browser token, enable Agent mode, load a BOSS list, create a limit-2 batch, verify two cards are selected without opening chat, confirm SQLite contains two snapshots, disable Agent mode, stop the service, and confirm standalone start still works without any request to port 8765.

- [x] **Step 5: Run Phase 2 verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check .\zhipin-auto-greeting.user.js
git diff --check
```

Expected: no failures and syntax check exits 0.

- [x] **Step 6: Commit**

```powershell
git add agent_app tests/api/test_collection_flow.py docs/manual-testing/phase-2-collection.md
git commit -m "feat: complete browser collection batches"
```

## Phase 2 Exit Gate

Run the manual checklist with a two-job batch in the user's logged-in browser. Evidence must show: no chat navigation, no sent message, two immutable snapshots, correct batch state, and standalone mode still starts with the Agent service stopped. Before the Phase 2 completion commit, update this plan's checkboxes and implementation log, `docs/current-state-analysis.md`, `docs/roadmap.md`, `docs/new-session-handoff.md`, `docs/README.md`, and any affected README instructions; remove only superseded process files under the `AGENTS.md` documentation cleanup rules.

## Implementation Log

- `c72636b`：浏览器任务租约、worker 所有权、进度与幂等终态、浏览器鉴权路由和显式令牌 CLI。
- `34f90d8`：默认关闭的 Agent 模式、回环地址校验、白名单 `AgentBridge` 和独立模式入口保留。
- `a571ed1`：服务端强身份键、JD 指纹、不可变快照和重复审计。
- `e7d5038`：只采集不发送的 `BatchCollector`、独立恢复状态和安全暂停。
- `098aae5`：幂等 `/collect`、快照计数校验、原子批次终结与人工验证清单。
- `09a7f90`：修复 Agent 面板被功能区可见性逻辑隐藏的问题，并增加可见性契约。
- `c54a75f`：修复首次创建浏览器 worker 时意外清空内存配置的问题，并增加 worker 契约。
- `2556893`：允许已完成批次幂等接收既有快照的终态重复上报，仍拒绝新增身份。
- 自动化证据：48 项 pytest 通过，`agent_app` 覆盖率 93.12%，Alembic `0002 (head)`，Python `compileall`、Userscript `node --check` 和 `git diff --check` 通过。
- 非阻塞警告：FastAPI/Starlette `TestClient` 有一条既有第三方弃用警告。
- 人工门禁：2026-07-22 在用户本人 Chrome 完成两个岗位的只读采集，批次为 `collected`、快照数为 2；用户确认无聊天导航、无沟通点击、无消息发送，也未出现验证码或安全校验。终态重复回放保持快照数、原 payload、JD 指纹和时间戳不变，只追加重复审计。关闭 Agent、停止本地服务并确认 8765 端口释放后，独立模式正常进入原列表循环，并在实际沟通前人工停止。Phase 2 Exit Gate 已通过；Phase 3 未开始。
