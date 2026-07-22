# Analysis, Greeting, and Approval Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对已冻结的职位快照进行可关闭的双维度分析，生成不虚构事实的短问候语，并在简约本地工作台中形成不可变的人工批准队列。

**Architecture:** 应用层只依赖结构化模型接口和仓储接口；模型适配器负责 OpenAI-compatible HTTP 调用与 JSON 校验。分析结果、问候语草稿和最终批准文本分层保存，批准后复制为不可变队列项，后续模型调用不得覆盖。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy 2、HTTPX、原生 HTML/CSS/JavaScript、pytest。

**Prerequisite:** Phase 1 与 Phase 2 已完成、测试通过并分别提交。

**Compatibility baseline:** 复用 Phase 1 已建立的 `Analysis`、`Greeting`、`ApprovalVersion`、`DeliveryItem` 表和字符串 UUID；复用 Phase 2 的浏览器任务租约。Phase 3 的迁移编号从 `0003` 开始，不创建同义重复表。模型配置字段使用现有 `ModelConfig.model`，画像载荷复用 `ProfileService.model_context()` 的可见性规则。

---

## Task 1: 定义模型请求、结构化响应与脱敏边界

**Files:**
- Create: `agent_app/domain/llm_schemas.py`
- Create: `agent_app/infrastructure/llm.py`
- Modify: `agent_app/config.py`
- Test: `tests/unit/test_llm_payload.py`
- Test: `tests/unit/test_llm_client.py`

- [x] **Step 1: 写脱敏载荷失败测试**

```python
def test_profile_payload_omits_empty_and_private_fields():
    profile = {
        "education": "华南农业大学研究生",
        "skills": ["Python", "AI Agent"],
        "availability": "可实习3至6个月",
        "phone": "13800000000",
        "email": "private@example.com",
        "address": "private",
        "awards": "",
    }
    payload = build_model_profile(profile)
    assert payload == {
        "education": "华南农业大学研究生",
        "skills": ["Python", "AI Agent"],
        "availability": "可实习3至6个月",
    }
```

- [x] **Step 2: 写客户端契约失败测试**

使用 `httpx.MockTransport` 验证请求目标为 `{base_url}/chat/completions`，请求含 `Authorization: Bearer ...`，并且响应必须经 `AnalysisModelOutput` 或 `GreetingModelOutput` 校验；非 JSON、字段缺失、超时均转换为 `ModelCallError`，错误文本不得包含 API Key。

- [x] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_llm_payload.py tests/unit/test_llm_client.py -q
```

Expected: collection error，提示 `llm_schemas` 或 `llm` 尚不存在。

- [x] **Step 4: 实现稳定接口**

```python
class AnalysisModelOutput(BaseModel):
    target_score: int = Field(ge=0, le=100)
    personal_score: int = Field(ge=0, le=100)
    target_reasons: list[str] = Field(max_length=5)
    personal_matches: list[str] = Field(max_length=5)
    cautions: list[str] = Field(max_length=5)

class GreetingModelOutput(BaseModel):
    greeting: str = Field(min_length=20, max_length=500)
    used_facts: list[str] = Field(max_length=8)

class LlmClient(Protocol):
    async def analyze(self, payload: dict[str, object]) -> AnalysisModelOutput:
        raise NotImplementedError

    async def generate_greeting(self, payload: dict[str, object]) -> GreetingModelOutput:
        raise NotImplementedError
```

模型画像直接使用 `ProfileService.model_context()`，沿用 Phase 1 的字段可见性和空值剔除规则，禁止另建第二套白名单。`OpenAICompatibleClient` 使用单一共享 `httpx.AsyncClient`、30 秒超时，并通过现有配置字段 `model` 调用。网络错误、超时或非法 JSON 最多允许一次结构化重试；错误文本不得包含原始响应、API Key 或隐私字段。

- [x] **Step 5: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_llm_payload.py tests/unit/test_llm_client.py -q
git add agent_app/domain/llm_schemas.py agent_app/infrastructure/llm.py agent_app/config.py tests/unit/test_llm_payload.py tests/unit/test_llm_client.py
git commit -m "feat: add privacy-safe model adapter"
```

Expected: tests pass；提交只包含模型契约、适配器和测试。

## Task 2: 实现可关闭的岗位分析与确定性降级

**Files:**
- Create: `agent_app/application/analysis.py`
- Modify: `agent_app/domain/enums.py`
- Modify: `agent_app/domain/schemas.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Create: `tests/unit/test_analysis_service.py`
- Create: `alembic/versions/0003_analysis_approval_integrity.py`

- [x] **Step 1: 写业务规则失败测试**

覆盖以下精确行为：

```python
assert recommendation_for(29) == "deselect"
assert recommendation_for(30) == "cautious"
assert recommendation_for(59) == "cautious"
assert recommendation_for(60) == "recommend"
assert recommendation_for(100) == "recommend"
```

另外验证：`analysis_enabled=False` 时不调用模型、目标分为 `None` 且默认选中；个人分不改变 `selected_by_default`；地点和经验不进入目标方向提示词；简历未出现 JD 技能只进入 `cautions`，不得成为排除条件。模型失败时状态为 `analysis_failed`，该职位可见但不可选择、不可批准；用户必须成功重试，或显式关闭分析后重新执行确定性跳过，才能进入审批。

- [x] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_analysis_service.py -q
```

Expected: import error 或断言失败。

- [x] **Step 3: 添加领域结构和数据库字段**

复用现有 `Analysis.payload` 保存经 Pydantic 校验的目标分、个人分、推荐档位、原因、风险、模型名和提示词版本；复用其 `status` 表达完成、跳过或失败。迁移 `0003` 只补充审批所需的唯一约束和索引（至少保证 `approval_versions(batch_id, version)` 唯一），不创建 `JobAnalysis`、`GreetingDraft`、`Approval` 或 `ApprovedDeliveryItem` 等同义表，也不重写已有数据。

- [x] **Step 4: 实现 AnalysisService**

```python
class AnalysisService:
    async def analyze_snapshot(
        self,
        snapshot_id: str,
        *,
        analysis_enabled: bool,
    ) -> AnalysisView:
        raise NotImplementedError
```

将 `raise NotImplementedError` 替换为最小实现：读取冻结快照和当前画像，构造不含隐私字段的载荷；关闭时返回跳过结果；开启时保存经校验的模型结果。`selected_by_default` 只按 `target_score >= 30` 计算。模型错误写入安全错误码，不保存原始响应和密钥。

- [x] **Step 5: 迁移、测试并提交**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/unit/test_analysis_service.py -q
git add agent_app/application/analysis.py agent_app/domain/enums.py agent_app/domain/schemas.py agent_app/infrastructure/models.py agent_app/infrastructure/repositories.py alembic/versions/0003_analysis_approval_integrity.py tests/unit/test_analysis_service.py
git commit -m "feat: analyze job fit with optional filtering"
```

Expected: migration succeeds and tests pass。

## Task 3: 生成轻量个性化问候语并执行事实校验

**Files:**
- Create: `agent_app/application/greetings.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Create: `tests/unit/test_greeting_service.py`

- [x] **Step 1: 写问候语约束失败测试**

固定基础模板为产品规格中的文本，验证：关闭问候语模型时返回基础模板；模型开启但最终失败时标记 `generation_failed` 且不可批准；用户可显式关闭问候语模型后重新生成基础模板。岗位要求技能、时间或经验且画像有对应事实时允许补充；画像没有事实时不得声称具备；输出去除电话、邮箱和地址；最终文本允许 20–500 字且不得为空。

```python
assert result.source in {"model", "base_template", "edited"}
assert "13800000000" not in result.text
assert result.approved_at is None
```

- [x] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_greeting_service.py -q
```

Expected: `GreetingService` 尚不存在。

- [x] **Step 3: 实现生成和事实白名单校验**

`GreetingService.generate(snapshot_id: str)` 的模型输入仅含基础模板、JD 摘要、岗位名称、公司名称、非空画像和已保存分析。系统指令要求模仿模板自然、直接、礼貌的中文风格，优先补充技能/时间/经验的真实匹配点，不虚构、不拉长。模型返回的 `used_facts` 必须逐项存在于画像白名单；任一事实无法验证时标记 `generation_failed`，不得静默回退并进入审批。

- [x] **Step 4: 保存可编辑草稿**

复用现有 `Greeting`：模型原文写入 `generated_text`，用户编辑结果写入 `final_text`，来源、事实引用、错误码和时间写入 `payload`。编辑只更新未批准记录；批准由下一任务复制文本，禁止原地改变批准内容。

- [x] **Step 5: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_greeting_service.py -q
git add agent_app/application/greetings.py agent_app/infrastructure/models.py agent_app/infrastructure/repositories.py tests/unit/test_greeting_service.py
git commit -m "feat: generate fact-checked greetings"
```

Expected: tests pass。

## Task 4: 编排整批分析、生成和人工批准

**Files:**
- Create: `agent_app/application/approvals.py`
- Create: `agent_app/api/routers/analysis.py`
- Create: `agent_app/api/routers/approvals.py`
- Modify: `agent_app/main.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Create: `tests/api/test_analysis_and_approval_api.py`

- [x] **Step 1: 写 API 失败测试**

覆盖：

```text
POST /api/v1/batches/{id}/analyze              -> 202
GET  /api/v1/batches/{id}/review               -> 200
PATCH /api/v1/batches/{id}/drafts/{snapshotId} -> 200
POST /api/v1/batches/{id}/approve              -> 200
```

批准请求体为 `{"items":[{"snapshot_id":"<uuid>","selected":true,"greeting":"..."}]}`。验证未分析完成、`analysis_failed` 或 `generation_failed` 返回 409；空选择允许批准并形成空完成队列；重复批准返回同一个 `approval_version_id`；批准后编辑返回 409；未批准批次不得创建可领取发送任务。

- [x] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_analysis_and_approval_api.py -q
```

Expected: routes return 404。

- [x] **Step 3: 实现批处理编排**

`POST analyze` 在本地后台任务中按快照顺序执行，单项模型失败记录后继续。批次状态依次为 `collected -> analyzing -> awaiting_approval`。同一批次已有进行中的分析时返回原作业，不并发启动第二次。

- [x] **Step 4: 实现不可变批准队列**

复用现有 `ApprovalVersion` 和 `DeliveryItem`。在一个数据库事务中锁定批次、递增版本，并把每个被选中的强 ID、职位快照摘要、最终问候语、顺序号和批准时间复制到不可变的批准版本及队列项；批准完成后状态为 `approved`。发送层只能读取对应 `approval_version_id` 的 `DeliveryItem.final_greeting`，不能读取后来变化的 `Greeting` 生成发送文本。

- [x] **Step 5: 运行 API 与回归测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_analysis_and_approval_api.py tests/unit/test_analysis_service.py tests/unit/test_greeting_service.py -q
git add agent_app/application/approvals.py agent_app/api/routers/analysis.py agent_app/api/routers/approvals.py agent_app/main.py agent_app/infrastructure/models.py agent_app/infrastructure/repositories.py tests/api/test_analysis_and_approval_api.py
git commit -m "feat: freeze human-approved delivery queues"
```

Expected: tests pass。

## Task 5: 构建简约双栏审批工作台

**Files:**
- Create: `agent_app/web/index.html`
- Create: `agent_app/web/app.js`
- Create: `agent_app/web/styles.css`
- Modify: `agent_app/main.py`
- Create: `tests/api/test_workbench.py`
- Create: `tests/contracts/test_workbench_assets.py`

- [x] **Step 1: 写静态页面与安全契约失败测试**

验证 `/` 返回工作台，包含批次状态、分析开关、左侧职位列表、右侧 JD/匹配原因/风险/问候语编辑区以及“批准本批次”按钮；脚本不得包含 `innerHTML =`、远程 CDN 或 API Key；批准按钮仅在批次 `awaiting_approval` 且所有选中项均可批准时启用。Phase 3 不提供执行发送按钮。

- [x] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_workbench.py tests/contracts/test_workbench_assets.py -q
```

Expected: `/` returns 404 或资源不存在。

- [x] **Step 3: 实现无构建工具工作台**

使用语义化 HTML、CSS 变量和原生模块脚本。列表卡片显示公司、岗位、两个分数、推荐档位和选中状态；右栏允许查看冻结 JD、编辑问候语、手动勾选/取消。所有用户内容通过 `textContent` 或表单 `value` 渲染。

- [x] **Step 4: 接入任务轮询和审批 API**

页面每 2 秒轮询当前批次；离开审批状态后停止轮询。点击批准时禁用按钮，提交当前选择和文本；成功后显示“已批准，等待用户在 Phase 4 显式开始执行”，失败时恢复按钮并显示可读错误，不自动重复提交。

- [x] **Step 5: 测试、全阶段验证并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_workbench.py tests/contracts/test_workbench_assets.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check .\agent_app\web\app.js
node --check .\zhipin-auto-greeting.user.js
git diff --check
git add agent_app/web/index.html agent_app/web/app.js agent_app/web/styles.css agent_app/main.py tests/api/test_workbench.py tests/contracts/test_workbench_assets.py
git commit -m "feat: add minimal approval workbench"
```

Expected: all tests pass；两个 JavaScript 文件语法检查成功；`git diff --check` 无输出。

## Phase 3 Exit Gate

- [x] 分析关闭时仍能生成基础问候语并进入审批。
- [x] 个人匹配分不导致自动取消；目标分阈值边界测试通过。
- [x] 空画像字段和隐私字段不进入模型请求。
- [x] 批准后文本与强 ID 不可变，任何发送入口都尚不能绕过批准。
- [x] 工作台在窄屏可用，所有动态内容安全渲染。
- [x] 按 `AGENTS.md` 检查并更新当前状态、路线图、计划索引、交接文档，安全清理完全过时且无独有证据的过程文件。
- [ ] `git status --short` 为空，然后进入 Phase 4。

## 实施记录

- `935b182`：隐私安全的 OpenAI-compatible 模型适配与结构化输出契约。
- `115b617`：可关闭双评分分析、阈值边界、失败隔离与 Alembic `0003`。
- `eff29e8`：基础模板、事实白名单与敏感输出清理。
- `36de0e8`：分析/审阅/编辑/批准 API 与不可变人工批准队列。
- `af17ffa`：无构建工具的本地双栏工作台与 HttpOnly 会话 cookie。
- 自动化门禁：81 项 pytest 通过，`agent_app` 覆盖率 92.42%；Python 编译、工作台和原油猴脚本语法检查、空库迁移与差异检查通过。
- 本机浏览器门禁：桌面双栏和 390x844 单栏布局通过，无横向溢出；验证期间没有访问 BOSS、调用真实模型或执行发送。
- 安全边界：批准只冻结队列，不创建 `execute_delivery` 任务；`ApprovedQueueRunner` 继续保持未实现占位，油猴独立模式未改变。
