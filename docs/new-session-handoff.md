# 新会话交接说明

更新时间：2026-07-22。本文是唯一的新会话交接文件；不要再创建按日期复制的交接文档。

## 当前状态

Phase 1“本地服务与数据基础”已经完成并通过退出门禁，下一项工作是 Phase 2“油猴桥接与批次采集”。Phase 1 的实现包括 FastAPI、SQLite/Alembic `0001`、双令牌、画像与模型设置、批次基础 API 和 16 项自动化测试。

开始 Phase 2 前应确保 Phase 1 Pull Request 已合并到 GitHub `main`，然后在本地执行：

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/phase-2-browser-bridge-collection
```

不要直接从 `codex/phase-1-agent-foundation` 创建 Phase 2 分支，否则后续 PR 会形成不必要的堆叠依赖。

## 必读顺序

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/current-state-analysis.md`
4. `docs/product-requirements.md`
5. `docs/superpowers/specs/2026-07-21-local-resume-delivery-agent-design.md`
6. `docs/roadmap.md`
7. `docs/superpowers/plans/2026-07-22-local-resume-delivery-agent.md`
8. `docs/superpowers/plans/2026-07-22-browser-bridge-collection.md`

然后检查 Git 状态、最近提交、当前分支、Alembic head 和现有未提交改动。

## Phase 2 已对齐的前置事实

- 服务地址统一为 `http://127.0.0.1:8765`。
- Phase 1 已创建 `browser_tasks` 和 `job_snapshots`，Phase 2 通过迁移 `0002_browser_task_leasing` 补字段，不创建重复表。
- Phase 1 的 `create_app()` 支持注入临时 `session_factory` 和 `SecretStore`，测试应继续使用临时 SQLite 与文件密钥库。
- 浏览器令牌不得通过 API 返回；Phase 2 计划增加显式本机 CLI，只在用户主动运行时显示浏览器令牌。
- Agent 模式默认关闭；连接失败不得影响独立模式。
- Phase 2 只采集详情，不进入聊天、不发送消息；`execute_delivery` 在 Phase 4 前只能返回“尚未实现”。

## 安全与验证边界

- 只处理用户本人已登录后有权查看的职位。
- 不自动登录、不导出 Cookie、不自动处理验证码，不绕过登录、安全校验、频率限制和访问控制。
- 后端只下发固定 schema 和白名单任务类型，不下发任意 JavaScript、选择器、SQL 或 URL。
- 每个任务遵循测试先行，并在提交前检查自动化测试、Userscript 语法、独立模式回归、文档一致性和 Git 状态。
- Phase 2 退出门禁必须由用户在本人登录环境中完成两岗位采集验证；出现验证码或安全校验时只确认暂停，不尝试处理或绕过。

## 新会话执行指令

```text
请在 D:\Web\boss\boss-auto-greeting 中继续“本地简历投递 Agent”。只修改该子项目。先完整阅读 AGENTS.md、docs/README.md、docs/current-state-analysis.md、产品需求、设计规格、路线图、总计划和 Phase 2 计划；检查 Git 状态并保留已有改动。确认 Phase 1 已在 main 中后，从 Phase 2 第一个未完成复选框开始，使用 superpowers:executing-plans 和测试驱动方式执行。只完成 Phase 2 并通过退出门禁后汇报；保留油猴独立模式，不得绕过人工审批、验证码、登录或安全校验。
```
