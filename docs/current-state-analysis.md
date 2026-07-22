# 当前项目状态审计

更新时间：2026-07-22。本文描述 Phase 1 完成后的代码事实，不替代产品需求或设计规格。

## 1. 仓库与分支边界

`D:\Web\boss\boss-auto-greeting` 是独立 Git 仓库，位于另一个 Git 仓库 `D:\Web\boss` 内。所有实现、测试、迁移和文档只能修改本仓库；父项目文件不在任务范围内。

阶段开发采用独立分支和 Pull Request：阶段分支合并到 GitHub `main` 后，本地先同步 `main`，再创建下一阶段分支。不要从未合并阶段分支继续堆叠后续阶段。

## 2. Phase 1 已实现能力

### 2.1 本地应用

- `agent_app.main.create_app()` 提供 FastAPI 应用工厂。
- 默认配置为 `127.0.0.1:8765`，数据目录默认为 `data/`。
- `GET /api/health` 无需令牌；业务接口位于 `/api/v1` 并要求 `X-Agent-Token`。
- 应用令牌和浏览器令牌分离，使用常量时间比较；令牌只保存在 `SecretStore`。

### 2.2 密钥与配置

- 正式运行优先使用 Windows keyring，keyring 明确不可用时回退到 Git 忽略的 `.boss-agent-secrets.json`。
- 模型 API Key 只以固定引用出现在普通配置表，明文不进入 SQLite、接口响应或测试导出。
- 已提供画像和模型配置 API：`GET/PUT /api/v1/profiles/current`、`GET/PUT /api/v1/settings/model`。
- 模型上下文会剔除空字段；电话、邮箱和详细地址默认不可见，只有显式授权才允许进入后续模型上下文。

### 2.3 SQLite 与迁移

Alembic 当前 head 为 `0001`。初始迁移和 ORM 均定义以下 11 张业务表：

- `profiles`
- `base_greetings`
- `model_configs`
- `batches`
- `job_snapshots`
- `analyses`
- `greetings`
- `approval_versions`
- `delivery_items`
- `browser_tasks`
- `audit_events`

Phase 2–4 必须复用这些表，只有缺失字段、索引或约束时才新增迁移，不能重复创建同义表。

### 2.4 批次基础状态

- `POST /api/v1/batches` 创建默认 10 个岗位的 `draft` 批次。
- 来源 URL 只允许 HTTPS 的 `www.zhipin.com/web/geek/jobs`。
- `GET /api/v1/batches/{id}` 返回批次、计数和当前可用动作。
- 批次状态和转换集中在 `agent_app/domain/enums.py` 与 `transitions.py`；未批准状态不能执行。

## 3. 当前测试与验证证据

Phase 1 退出门禁结果：

- 16 项 pytest 全部通过。
- `agent_app` 总覆盖率 93%。
- Python `compileall`、`node --check zhipin-auto-greeting.user.js` 和 `git diff --check` 通过。
- Uvicorn 曾实际绑定 `127.0.0.1:8765`，健康检查返回 200，验证后进程已停止。
- 测试输出存在一条 FastAPI/Starlette `TestClient` 第三方弃用警告，不影响通过结果，后续依赖升级时再处理。

## 4. 油猴脚本现状

`zhipin-auto-greeting.user.js` 仍是接近九千行的单文件原生 JavaScript Userscript，Phase 1 没有修改它。现有独立模式继续负责列表遍历、详情合并、筛选、进入聊天、发送验证、返回列表、IndexedDB/localStorage 和导出。

尚未实现：

- Agent 模式开关和本机服务桥接。
- 浏览器任务租约、进度和幂等结果协议。
- 只采集不发送的 `BatchCollector`。
- 已批准队列执行器 `ApprovedQueueRunner`。
- Agent 模式的真实浏览器人工验证。

`zhipin-devtools-unlock.user.js` 仍只允许作为隔离调试辅助，不能成为正式依赖或用于绕过平台安全措施。

## 5. Phase 2 开始前必须对齐的实现事实

- `BrowserTask` 已有 `task_type`、`status`、`idempotency_key`、`payload`、`result` 和 `lease_expires_at`；Phase 2 迁移 `0002` 只补充租约所有者、尝试次数、进度序号和完成时间等缺失字段。
- `JobSnapshot` 已有不可变 payload、强身份键和 JD 指纹列，Phase 2 不再创建重复快照表。
- Userscript 需要浏览器令牌，但 HTTP API 不得回显令牌；Phase 2 必须提供显式本机 CLI 获取方式。
- Agent 模式默认关闭；采集期间不得进入聊天或调用任何发送服务。

## 6. 仍存在的主要风险

1. 油猴主脚本高度集中，Phase 2 只能做职责隔离和契约测试，不能借机整体重写。
2. BOSS 是 SPA，DOM、内部接口、BFCache 和列表恢复都需要可控夹具及本人登录环境下的小批量人工验证。
3. SQLite 在单浏览器场景下仍要使用条件更新保证租约原子性和结果幂等。
4. 后续模型、审批、自然语言和外部 API 必须继续消费同一应用服务，不能复制或绕过审批规则。
