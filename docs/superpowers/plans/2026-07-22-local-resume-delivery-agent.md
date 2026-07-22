# Local Resume Delivery Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏油猴独立模式的前提下，构建本机 FastAPI + SQLite 简历投递 Agent，完成批次采集、宽松匹配分析、个性化话术、人工审批、安全发送和外部子 Agent API。

**Architecture:** `zhipin-auto-greeting.user.js` 继续作为可独立运行的浏览器执行层；新增 `agent_app` 本地服务承载领域逻辑、SQLite、模型适配和网页工作台。浏览器通过受限任务协议领取采集/发送任务，网页和未来上层项目统一调用 `/api/v1`，任何发送都必须消费不可变的已批准队列。

**Tech Stack:** Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、HTTPX、keyring、pytest、原生 JavaScript/HTML/CSS、Tampermonkey。

## Global Constraints

- 只修改 `D:\Web\boss\boss-auto-greeting`，不得修改父目录原项目。
- `zhipin-auto-greeting.user.js` 必须继续可直接安装，Agent 默认关闭且本地服务不是独立模式依赖。
- 默认批次大小为 10；采集阶段不得进入聊天或发送。
- `0-29` 默认取消、`30-59` 谨慎、`60-100` 推荐；只有求职目标分影响默认勾选。
- 画像空字段不参与模型上下文，联系方式和证件信息默认排除。
- 未批准批次不得执行；人工终稿批准后不得被重新生成或覆盖。
- 发送前使用 `encryptJobId`、`securityId`、`lid` 等强 ID 重新定位并确认会话。
- 单项普通失败继续，验证码、登录失效和安全校验暂停整批。
- 本地服务只监听 `127.0.0.1`；API Key 不进入 SQLite 普通表、前端响应、日志或导出。
- 不使用反调试脚本绕过平台安全措施。
- 每个任务执行红-绿测试循环并独立提交；每阶段结束验证油猴独立模式。

## Plan Set and Execution Order

该规格包含四个可独立验收的子系统，必须按顺序执行：

- [x] [Phase 1：本地服务与数据基础](2026-07-22-agent-foundation.md)（16 项测试，93% 覆盖率）
- [ ] [Phase 2：油猴桥接与批次采集](2026-07-22-browser-bridge-collection.md)（实现与 45 项自动化测试完成，真实浏览器退出门禁待验证）
- [ ] [Phase 3：分析、话术与审批工作台](2026-07-22-analysis-approval-workbench.md)
- [ ] [Phase 4：安全发送、自然语言与外部调用](2026-07-22-delivery-command-integration.md)

不要跨阶段并行修改共享状态机。只有当前阶段的最终验收通过并提交后，才进入下一阶段。

## Phase 1 Locked Baseline

- 服务端口统一为 `127.0.0.1:8765`；后续计划不得引入第二个默认端口。
- Alembic `0001` 已创建 11 张基础表；Phase 2 从 `0002` 开始，后续阶段复用已有 `analyses`、`greetings`、`approval_versions` 和 `delivery_items`。
- 所有业务 ID 为 32 位字符串 UUID，不使用整数 ID 假设。
- `create_app()` 已支持注入 `session_factory` 和 `SecretStore`；测试继续使用临时 SQLite 和文件密钥库。
- 应用令牌与浏览器令牌已经分离；任何 HTTP API 都不得返回明文令牌。

## Locked File Structure

```text
boss-auto-greeting/
├─ zhipin-auto-greeting.user.js
├─ agent_app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ domain/
│  │  ├─ enums.py
│  │  ├─ schemas.py
│  │  └─ transitions.py
│  ├─ application/
│  │  ├─ profiles.py
│  │  ├─ batches.py
│  │  ├─ analysis.py
│  │  ├─ greetings.py
│  │  ├─ approvals.py
│  │  ├─ deliveries.py
│  │  └─ commands.py
│  ├─ infrastructure/
│  │  ├─ database.py
│  │  ├─ models.py
│  │  ├─ repositories.py
│  │  ├─ secrets.py
│  │  └─ llm.py
│  ├─ api/
│  │  ├─ dependencies.py
│  │  └─ routers/
│  └─ web/
│     ├─ index.html
│     ├─ app.js
│     └─ styles.css
├─ alembic/
├─ tests/
│  ├─ unit/
│  ├─ api/
│  ├─ contracts/
│  ├─ userscript/
│  └─ fixtures/
├─ data/                 # runtime, ignored
├─ requirements.txt
├─ requirements-dev.txt
└─ alembic.ini
```

## Cross-Phase Verification

每个阶段最后运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check .\zhipin-auto-greeting.user.js
git diff --check
git status --short
```

Expected: pytest 无失败；Node 退出码 0；`git diff --check` 无输出；状态只包含当前任务预期文件。

最终还必须按 `docs/superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md` 第 14 节完成本人登录环境的小批量人工验证。

## Official Implementation References

- FastAPI 测试依赖覆盖：https://fastapi.tiangolo.com/advanced/testing-dependencies/
- FastAPI lifespan 测试：https://fastapi.tiangolo.com/advanced/testing-events/
- SQLAlchemy Session：https://docs.sqlalchemy.org/en/20/orm/session.html
- SQLAlchemy SQLite URL：https://docs.sqlalchemy.org/en/20/core/engines.html#sqlite
- Alembic 教程：https://alembic.sqlalchemy.org/en/latest/tutorial.html
- HTTPX AsyncClient：https://www.python-httpx.org/async/

## Completion Gate

四份阶段计划全部完成、全量测试通过、独立模式回归通过、真实浏览器小批量验证通过、用户文档更新完成后，首版才可以标记完成。
