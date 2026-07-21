# Analysis, Greeting, and Approval Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对已冻结的职位快照进行可关闭的双维度分析，生成不虚构事实的短问候语，并在简约本地工作台中形成不可变的人工批准队列。

**Architecture:** 应用层只依赖结构化模型接口和仓储接口；模型适配器负责 OpenAI-compatible HTTP 调用与 JSON 校验。分析结果、问候语草稿和最终批准文本分层保存，批准后复制为不可变队列项，后续模型调用不得覆盖。

**Tech Stack:** FastAPI、Pydantic 2、SQLAlchemy 2、HTTPX、原生 HTML/CSS/JavaScript、pytest。

**Prerequisite:** Phase 1 与 Phase 2 已完成、测试通过并分别提交。

---

## Task 1: 定义模型请求、结构化响应与脱敏边界

**Files:**
- Create: `agent_app/domain/llm_schemas.py`
- Create: `agent_app/infrastructure/llm.py`
- Modify: `agent_app/config.py`
- Test: `tests/unit/test_llm_payload.py`
- Test: `tests/unit/test_llm_client.py`

- [ ] **Step 1: 写脱敏载荷失败测试**

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

- [ ] **Step 2: 写客户端契约失败测试**

使用 `httpx.MockTransport` 验证请求目标为 `{base_url}/chat/completions`，请求含 `Authorization: Bearer ...`，并且响应必须经 `AnalysisModelOutput` 或 `GreetingModelOutput` 校验；非 JSON、字段缺失、超时均转换为 `ModelCallError`，错误文本不得包含 API Key。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_llm_payload.py tests/unit/test_llm_client.py -q
```

Expected: collection error，提示 `llm_schemas` 或 `llm` 尚不存在。

- [ ] **Step 4: 实现稳定接口**

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

`build_model_profile()` 仅允许 `education`、`target_roles`、`skills`、`projects`、`research`、`competitions`、`work_experience`、`availability`、`arrival_time`、`strengths`、`extra_model_context`；空字符串、空列表和 `None` 全部剔除。`OpenAICompatibleClient` 使用单一共享 `httpx.AsyncClient`、30 秒超时、一次请求不自动重试，并通过配置的 `model_name` 调用。

- [ ] **Step 5: 运行测试并提交**

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
- Create: `alembic/versions/0002_analysis_and_greetings.py`

- [ ] **Step 1: 写业务规则失败测试**

覆盖以下精确行为：

```python
assert recommendation_for(29) == "deselect"
assert recommendation_for(30) == "cautious"
assert recommendation_for(59) == "cautious"
assert recommendation_for(60) == "recommend"
assert recommendation_for(100) == "recommend"
```

另外验证：`analysis_enabled=False` 时不调用模型、目标分为 `None` 且默认选中；个人分不改变 `selected_by_default`；地点和经验不进入目标方向提示词；简历未出现 JD 技能只进入 `cautions`，不得成为排除条件；模型失败时状态为 `analysis_failed`、职位仍可人工选择。

- [ ] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_analysis_service.py -q
```

Expected: import error 或断言失败。

- [ ] **Step 3: 添加领域结构和数据库字段**

`JobSnapshot` 增加 `analysis_status`；新增 `JobAnalysis`，字段固定为 `id`、`job_snapshot_id`、`target_score`、`personal_score`、`recommendation`、`target_reasons_json`、`personal_matches_json`、`cautions_json`、`model_name`、`prompt_version`、`created_at`。迁移 `0002` 只新增表/列，不重写已有快照。

- [ ] **Step 4: 实现 AnalysisService**

```python
class AnalysisService:
    async def analyze_snapshot(
        self,
        snapshot_id: int,
        *,
        analysis_enabled: bool,
    ) -> JobAnalysisView:
        raise NotImplementedError
```

将 `raise NotImplementedError` 替换为最小实现：读取冻结快照和当前画像，构造不含隐私字段的载荷；关闭时返回跳过结果；开启时保存经校验的模型结果。`selected_by_default` 只按 `target_score >= 30` 计算。模型错误写入安全错误码，不保存原始响应和密钥。

- [ ] **Step 5: 迁移、测试并提交**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/unit/test_analysis_service.py -q
git add agent_app/application/analysis.py agent_app/domain/enums.py agent_app/domain/schemas.py agent_app/infrastructure/models.py agent_app/infrastructure/repositories.py alembic/versions/0002_analysis_and_greetings.py tests/unit/test_analysis_service.py
git commit -m "feat: analyze job fit with optional filtering"
```

Expected: migration succeeds and tests pass。

## Task 3: 生成轻量个性化问候语并执行事实校验

**Files:**
- Create: `agent_app/application/greetings.py`
- Modify: `agent_app/infrastructure/models.py`
- Modify: `agent_app/infrastructure/repositories.py`
- Create: `tests/unit/test_greeting_service.py`

- [ ] **Step 1: 写问候语约束失败测试**

固定基础模板为产品规格中的文本，验证：关闭模型或模型失败时返回基础模板；岗位要求技能、时间或经验且画像有对应事实时允许补充；画像没有事实时不得声称具备；输出去除电话、邮箱和地址；最终文本允许 20–500 字且不得为空。

```python
assert result.source in {"model", "base_template", "edited"}
assert "13800000000" not in result.text
assert result.approved_at is None
```

- [ ] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_greeting_service.py -q
```

Expected: `GreetingService` 尚不存在。

- [ ] **Step 3: 实现生成和事实白名单校验**

`GreetingService.generate(snapshot_id)` 的模型输入仅含基础模板、JD 摘要、岗位名称、公司名称、非空画像和已保存分析。系统指令要求模仿模板自然、直接、礼貌的中文风格，优先补充技能/时间/经验的真实匹配点，不虚构、不拉长。模型返回的 `used_facts` 必须逐项存在于画像白名单；任一事实无法验证时丢弃模型文本并回退基础模板。

- [ ] **Step 4: 保存可编辑草稿**

新增 `GreetingDraft`：`id`、`job_snapshot_id`、`text`、`source`、`used_facts_json`、`edited_at`、`approved_at`、`created_at`。编辑只更新未批准草稿；批准由下一任务复制文本，禁止原地改变批准内容。

- [ ] **Step 5: 运行测试并提交**

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

- [ ] **Step 1: 写 API 失败测试**

覆盖：

```text
POST /api/v1/batches/{id}/analyze              -> 202
GET  /api/v1/batches/{id}/review               -> 200
PATCH /api/v1/batches/{id}/drafts/{snapshotId} -> 200
POST /api/v1/batches/{id}/approve              -> 200
```

批准请求体为 `{"items":[{"snapshot_id":1,"selected":true,"greeting":"..."}]}`。验证未分析完成返回 409；空选择允许批准并形成空完成队列；重复批准返回同一个 `approval_id`；批准后编辑返回 409；未批准批次不得创建可领取发送任务。

- [ ] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_analysis_and_approval_api.py -q
```

Expected: routes return 404。

- [ ] **Step 3: 实现批处理编排**

`POST analyze` 在本地后台任务中按快照顺序执行，单项模型失败记录后继续。批次状态依次为 `collected -> analyzing -> awaiting_approval`。同一批次已有进行中的分析时返回原作业，不并发启动第二次。

- [ ] **Step 4: 实现不可变批准队列**

新增 `Approval` 和 `ApprovedDeliveryItem`。在一个数据库事务中锁定批次、复制每个被选中的强 ID、职位快照摘要、最终问候语、顺序号和批准时间；批准完成后状态为 `approved`。发送层只能读取 `ApprovedDeliveryItem`，不能读取后来变化的草稿生成发送文本。

- [ ] **Step 5: 运行 API 与回归测试并提交**

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

- [ ] **Step 1: 写静态页面与安全契约失败测试**

验证 `/` 返回工作台，包含批次状态、分析开关、左侧职位列表、右侧 JD/匹配原因/风险/问候语编辑区以及“批准并开始发送”按钮；脚本不得包含 `innerHTML =`、远程 CDN 或 API Key；批准按钮仅在批次 `awaiting_approval` 时启用。

- [ ] **Step 2: 运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_workbench.py tests/contracts/test_workbench_assets.py -q
```

Expected: `/` returns 404 或资源不存在。

- [ ] **Step 3: 实现无构建工具工作台**

使用语义化 HTML、CSS 变量和原生模块脚本。列表卡片显示公司、岗位、两个分数、推荐档位和选中状态；右栏允许查看冻结 JD、编辑问候语、手动勾选/取消。所有用户内容通过 `textContent` 或表单 `value` 渲染。

- [ ] **Step 4: 接入任务轮询和审批 API**

页面每 2 秒轮询当前批次；离开审批状态后停止轮询。点击批准时禁用按钮，提交当前选择和文本；成功后进入发送进度视图，失败时恢复按钮并显示可读错误，不自动重复提交。

- [ ] **Step 5: 测试、全阶段验证并提交**

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

- [ ] 分析关闭时仍能生成基础问候语并进入审批。
- [ ] 个人匹配分不导致自动取消；目标分阈值边界测试通过。
- [ ] 空画像字段和隐私字段不进入模型请求。
- [ ] 批准后文本与强 ID 不可变，任何发送入口都尚不能绕过批准。
- [ ] 工作台在窄屏可用，所有动态内容安全渲染。
- [ ] `git status --short` 为空，然后进入 Phase 4。
