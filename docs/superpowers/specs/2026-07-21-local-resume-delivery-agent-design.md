# 本地简历投递 Agent 设计规格

## 1. 设计目标

将现有 BOSS 直聘自动沟通油猴脚本扩展成双模式系统：

- 油猴独立模式保留原有功能。
- Agent 模式增加本地任务编排、岗位分析、个性化话术、批次审批和安全发送。
- 核心能力可通过稳定 API 被其他本地项目作为子 Agent 调用。

所有新增实现位于 `boss-auto-greeting` 仓库，不修改父目录原项目。

## 2. 设计原则

1. **兼容优先**：不破坏已有独立模式。
2. **审批优先**：自然语言和模型都不能绕过人工审批门禁。
3. **身份优先**：发送以岗位强 ID 和会话归属为依据，不以列表序号或旧 DOM 为依据。
4. **本地优先**：画像、批次、审批和投递记录保存在本机。
5. **隐私最小化**：只向模型提交用户授权字段。
6. **宽松筛选**：只默认取消求职方向明显偏离的岗位。
7. **接口优先**：UI 和内置 Agent 都是应用接口的客户端，便于未来复用。
8. **合规停止**：不绕过登录、验证码、安全校验和平台访问控制。

## 3. 总体架构

```text
BOSS 职位列表/聊天页面
          │
          ▼
Tampermonkey 浏览器执行层
  ├─ StandaloneAutomation
  ├─ AgentBridge
  ├─ BatchCollector
  └─ ApprovedQueueRunner
          │ localhost task protocol
          ▼
本地 FastAPI Agent 服务
  ├─ ProfileService
  ├─ BatchService
  ├─ AnalysisService
  ├─ GreetingService
  ├─ ApprovalService
  ├─ DeliveryService
  └─ CommandService
          │                    │
          ▼                    ▼
       SQLite          OpenAI-compatible API
          ▲
          │ /api/v1
          ├─ 本地网页工作台
          ├─ 内置自然语言 Agent
          └─ 未来上层项目/子 Agent
```

## 4. 仓库结构建议

首版建议保持油猴主脚本可直接安装，同时新增独立本地应用：

```text
boss-auto-greeting/
├─ zhipin-auto-greeting.user.js
├─ zhipin-devtools-unlock.user.js
├─ agent_app/
│  ├─ main.py
│  ├─ api/
│  ├─ application/
│  ├─ domain/
│  ├─ infrastructure/
│  ├─ llm/
│  └─ web/
├─ tests/
│  ├─ unit/
│  ├─ api/
│  ├─ contracts/
│  └─ userscript/
├─ data/                 # 运行时创建并忽略
├─ docs/
├─ requirements.txt
└─ README.md
```

首版不要求把油猴脚本拆成构建产物。新增逻辑应以清晰模块对象接入现有单文件，避免同时进行大规模重写和功能开发。等契约与测试稳定后，再评估源文件模块化构建。

## 5. 浏览器执行层

### 5.1 StandaloneAutomation

保留现有实时流程和配置。Agent 功能关闭或本地服务不可用时，独立模式不依赖后端。

### 5.2 AgentBridge

职责：

- 检测本地 Agent 是否连接。
- 使用本机令牌进行任务轮询。
- 领取 `collect_batch`、`execute_delivery`、`pause` 等有限任务类型。
- 定期续租并回报结构化结果。
- Agent 断开时暂停智能任务，但不影响独立模式。

桥接层不得执行后端返回的任意 JavaScript、CSS 选择器或 URL。所有任务必须符合固定 schema。

### 5.3 BatchCollector

批次采集只点击岗位卡片并等待当前详情稳定，不进入聊天。

每个快照至少包括：

- 本地 `snapshot_id` 和批次 ID。
- `encryptJobId`、`securityId`、`lid`。
- 岗位、公司、薪资、经验、学历、城市、地址。
- 完整 JD、技能、Boss 信息和公司信息。
- 来源 URL、采集时间、求职期望上下文。
- 规范化 JD 指纹。

采集达到数量、列表耗尽、用户停止或遇到安全校验时结束。

### 5.4 ApprovedQueueRunner

输入只能是后端生成的已批准队列项 ID，不能直接接受任意话术和岗位对象。

每个队列项流程：

```text
approved
  -> locating
  -> revalidating
  -> sending
  -> sent
```

异常终态：

- `already_contacted`
- `unavailable`
- `identity_mismatch`
- `send_failed`
- `cancelled`

遇到验证码、登录失效或安全校验时进入批次级 `paused_security`，不继续领取任务。

## 6. 本地应用层

### 6.1 ProfileService

管理求职目标、个人画像、时间信息、基础话术和字段模型可见性。空字段在构造模型上下文时直接删除。

### 6.2 BatchService

管理批次生命周期：

```text
draft -> collecting -> collected -> analyzing -> awaiting_approval
      -> approved -> executing -> completed
```

可中断状态：`paused`、`failed`、`cancelled`。

### 6.3 AnalysisService

为每个职位生成结构化分析：

```json
{
  "target_match_score": 0,
  "personal_match_score": 0,
  "overall_score": 0,
  "recommendation": "recommended|cautious|off_target",
  "target_reasons": [],
  "personal_matches": [],
  "information_gaps": [],
  "summary": ""
}
```

约束：

- 自动默认取消只取决于 `target_match_score < 30`。
- `personal_match_score` 不得触发淘汰。
- 画像未提及的信息放入 `information_gaps`，不得表述为用户不会或不具备。
- 地点和工作经验不参与求职方向筛选。
- 分析关闭时不调用模型，所有岗位默认进入审批列表。

### 6.4 GreetingService

输入：职位快照、授权画像字段、基础话术和分析结果。

输出：

```json
{
  "greeting": "...",
  "used_profile_fields": [],
  "matched_requirements": [],
  "warnings": []
}
```

服务端需要进行：

- 最大长度和非空校验。
- 禁止出现画像中无法追溯的个人事实。
- 敏感字段泄露检查。
- 保留用户人工终稿，不在执行前重新生成。

### 6.5 ApprovalService

- 维护每个批次项的勾选状态和人工终稿。
- 低于 30 分仅默认取消，不删除。
- 批准时验证所有选中项均有合法终稿。
- 批准操作创建不可变发送队列；后续修改必须产生新的审批版本或撤销未执行队列。

### 6.6 DeliveryService

- 向浏览器执行层发布已批准任务。
- 保存状态转换、时间、错误和身份校验结果。
- 单项失败后继续下一项。
- 安全类错误暂停整个批次。
- 提供失败项重新执行入口，重新执行仍经过身份校验。

### 6.7 CommandService

把自然语言转换为有限命令对象，例如：

```json
{
  "command": "create_batch",
  "arguments": { "limit": 10, "analysis_enabled": true }
}
```

命令解析结果必须通过白名单 schema。涉及配置变更时保存结构化参数；涉及发送时只允许打开审批或执行已经批准的批次。

## 7. 数据模型

### 7.1 主要表

- `profiles`：画像版本和授权字段。
- `base_greetings`：基础话术版本。
- `model_configs`：非敏感模型配置；API Key 只保存引用。
- `batches`：批次配置、状态和统计。
- `job_snapshots`：不可变职位快照和 JD 指纹。
- `analyses`：模型、提示词版本、结构化结果和状态。
- `greetings`：生成稿、人工终稿和使用字段。
- `approval_versions`：审批版本、批准时间和项目集合。
- `delivery_items`：不可变发送队列和执行状态。
- `audit_events`：关键状态变化，不保存 API Key 和完整敏感上下文。

### 7.2 幂等与去重

- 以强岗位身份集合生成稳定 `job_identity_key`。
- 同一岗位同一批次只保留一个快照。
- 已成功发送岗位在默认设置下不能再次进入发送队列。
- 任务结果提交使用任务 ID 幂等处理。
- 租约超时允许任务重新领取，但重复结果不会产生重复发送记录。

## 8. API 设计

统一前缀 `/api/v1`。

### 8.1 工作台和外部调用

- `GET/PUT /profiles/current`
- `GET/PUT /settings/model`
- `POST /commands`
- `POST /batches`
- `GET /batches/{batch_id}`
- `POST /batches/{batch_id}/analyze`
- `GET /batches/{batch_id}/approval`
- `PUT /batches/{batch_id}/items/{item_id}`
- `POST /batches/{batch_id}/approve`
- `POST /batches/{batch_id}/execute`
- `POST /batches/{batch_id}/pause`
- `GET /batches/{batch_id}/report`

### 8.2 浏览器桥接

- `POST /browser/heartbeat`
- `GET /browser/tasks/next`
- `POST /browser/tasks/{task_id}/ack`
- `POST /browser/tasks/{task_id}/progress`
- `POST /browser/tasks/{task_id}/result`

浏览器桥接应使用短期租约、本机令牌和任务类型白名单。

### 8.3 子 Agent 扩展性

外部项目通过 `/api/v1` 创建和查询批次。返回值包含状态、下一步可用动作和本地审批 URL。外部项目可以触发分析和打开审批，但不能伪造批准状态或直接下发浏览器发送任务。

## 9. 本地网页工作台

首版导航：

- Agent 对话。
- 当前批次。
- 审批工作台。
- 个人画像。
- 基础话术。
- 投递记录。
- 模型与系统设置。

审批页使用简约左右分栏：

- 左侧显示岗位、公司、分数、建议和勾选状态。
- 右侧显示 JD 摘要、匹配依据、信息差距和可编辑话术。
- 不展示无助于审批的原始接口字段和复杂图表。
- 提供保存、重新生成、恢复低分岗位和批准本批次。

## 10. 模型适配

使用 OpenAI 兼容客户端抽象：

- `base_url`
- `model`
- `api_key_ref`
- `timeout`
- 可控生成参数

分析与话术使用独立提示词、独立结构化 schema 和版本号。首版按岗位调用，限制低并发，优先可观察性和错误隔离，不使用一次请求分析整个批次。

失败策略：

- 网络错误和超时允许有限重试。
- 无效 JSON 可执行一次结构修复重试。
- 最终失败将岗位标记为 `analysis_failed` 或 `generation_failed`，不进入自动发送。

## 11. 安全和隐私

- 服务只绑定 `127.0.0.1`。
- 生成本机访问令牌，油猴桥接和外部本地调用使用不同权限范围。
- CORS 只允许本地工作台来源。
- API Key 使用操作系统秘密存储；若环境不支持，使用权限受限且被 Git 忽略的本地文件。
- 前端 API 永不返回完整 API Key。
- 日志不记录模型请求头、完整个人画像、Cookie、浏览器凭据或安全参数。
- 导出默认排除个人画像、API Key、原始模型请求和链接安全参数。
- 不自动登录，不读取或导出 Cookie，不绕过验证码和访问控制。

## 12. 列表刷新与快照一致性

采集阶段职位快照不可变。审批引用快照 ID 和指纹。

发送阶段只将快照作为“要寻找哪个岗位”和“发送什么终稿”的依据，必须重新读取当前页面确认身份。允许同一强 ID 下 JD 更新后继续使用审批终稿，但：

- 下线或找不到则 `unavailable`。
- 已沟通则 `already_contacted`。
- 强 ID 或会话归属不同则 `identity_mismatch`。
- 所有三种情况都不发送，并继续队列。

列表位置、卡片序号、DOM 节点和岗位名称不能单独作为发送身份依据。

## 13. 错误处理

| 错误类型 | 处理 |
| --- | --- |
| 单项定位失败 | 记录并继续 |
| 单项发送失败 | 记录并继续 |
| 模型分析/生成失败 | 不进入发送，允许人工重试 |
| 本地 Agent 断开 | 智能批次暂停 |
| 登录失效/验证码/安全校验 | 整批暂停，等待人工处理 |
| 岗位或会话身份不一致 | 禁止发送，记录并继续 |
| SQLite/存储错误 | 暂停当前批次，避免丢失审计状态 |

## 14. 测试策略

### 14.1 单元测试

- 空画像字段不进入提示词。
- 敏感字段默认排除。
- 目标分阈值和默认勾选规则。
- 个人匹配分不淘汰岗位。
- 状态机合法/非法转换。
- 岗位身份键、指纹和去重。
- 人工终稿不会被覆盖。

### 14.2 API 测试

- 画像和模型设置。
- 创建、采集、分析、审批、执行和报告。
- 未批准批次不能执行。
- 外部子 Agent 不能绕过审批。
- 浏览器任务租约、重复结果和权限隔离。

### 14.3 模型契约测试

- 有效结构化分析。
- 无效 JSON、字段缺失、超时和有限重试。
- 缺失画像信息不会被描述成能力不足。
- 话术不虚构事实、不泄露敏感字段、保持基础风格。

### 14.4 油猴回归测试

- Agent 未启动时独立模式仍能启动。
- Agent 模式只采集不发送。
- 返回列表刷新后按强 ID 重新定位。
- 身份不一致时不点击沟通或发送。
- 发送验证成功后才写 `sent`。
- 安全校验出现时暂停。

### 14.5 人工端到端验证

在本人登录且可正常手动浏览的环境中，小批量验证：采集、审批、列表刷新后发送、失败继续、验证码暂停和独立模式回归。

## 15. 首版范围与后续扩展

首版包含：

- 单用户、本机 FastAPI 和 SQLite。
- 简单自然语言命令。
- 一个活动 BOSS 标签页和一个执行批次。
- OpenAI 兼容模型。
- 简约审批工作台。
- 稳定 `/api/v1` 和浏览器桥接协议。

首版不包含：

- 云端部署或多用户账户。
- 多浏览器并发执行。
- 自动绕过验证码或安全验证。
- 完整通用 Agent 平台。
- 将油猴脚本整体迁移为 Chrome 扩展。
- 复杂工作流编辑器、插件市场和自主长期规划。

后续可在不改变核心服务接口的前提下增加：

- 上层求职管理项目调用。
- 更丰富的命令 Agent。
- 多画像和不同求职方向预设。
- 模型质量评估与提示词版本对比。
- 油猴源代码模块化构建或 Chrome 扩展执行适配器。

## 16. 完成定义

满足 `product-requirements.md` 第 13 节全部验收标准，自动化测试通过，并完成人工小批量浏览器验证，方可认为首版完成。
