# Agent Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可启动、可迁移、可测试的本地 FastAPI/SQLite 应用，并提供安全的画像、模型配置和批次基础 API。

**Architecture:** 使用应用工厂创建 FastAPI，SQLAlchemy Session 通过依赖注入按请求创建，Alembic 管理 SQLite schema。领域状态和 Pydantic schema 不依赖 FastAPI/ORM，API Key 通过 `SecretStore` 保存，普通配置和业务数据进入 SQLite。

**Tech Stack:** Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、keyring、pytest、HTTPX。

## Global Constraints

- 继承主计划 `2026-07-22-local-resume-delivery-agent.md` 的全部约束。
- 服务默认绑定 `127.0.0.1:8765`。
- 健康检查无需令牌；`/api/v1` 业务接口要求 `X-Agent-Token`。
- 测试使用临时 SQLite 文件，不共享生产数据库，也不依赖系统 keyring。
- 本阶段不修改油猴脚本，不调用模型，不实现发送。

---

### Task 1: Bootstrap the Local Application

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `agent_app/__init__.py`
- Create: `agent_app/config.py`
- Create: `agent_app/main.py`
- Create: `tests/conftest.py`
- Create: `tests/api/test_health.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: environment variables `BOSS_AGENT_DATA_DIR`, `BOSS_AGENT_HOST`, `BOSS_AGENT_PORT`.
- Produces: `agent_app.main.create_app(settings: Settings | None = None) -> FastAPI` and `GET /api/health`.

- [x] **Step 1: Add dependency manifests and runtime ignores**

`requirements.txt`:

```text
fastapi>=0.115,<1
uvicorn[standard]>=0.34,<1
pydantic>=2.10,<3
pydantic-settings>=2.7,<3
sqlalchemy>=2.0,<2.1
alembic>=1.15,<2
httpx>=0.28,<1
keyring>=25,<26
```

`requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8,<9
pytest-cov>=6,<7
```

Append to `.gitignore`:

```text
.venv/
data/
.pytest_cache/
.coverage
htmlcov/
*.db
*.sqlite3
.boss-agent-token
.boss-agent-secrets.json
```

- [x] **Step 2: Create the failing health test**

```python
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.main import create_app


def test_health_reports_local_service(tmp_path):
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "boss-resume-delivery-agent",
        "version": "0.1.0",
    }
```

- [x] **Step 3: Run the test and verify the expected failure**

Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/api/test_health.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'agent_app'`.

- [x] **Step 4: Implement settings and the app factory**

`agent_app/config.py`:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOSS_AGENT_")

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8765
    version: str = "0.1.0"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
```

`agent_app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved.ensure_directories()
        app.state.settings = resolved
        yield

    app = FastAPI(
        title="BOSS Resume Delivery Agent",
        version=resolved.version,
        lifespan=lifespan,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "boss-resume-delivery-agent",
            "version": resolved.version,
        }

    return app


app = create_app()
```

- [x] **Step 5: Run the focused and syntax tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_health.py -v
.\.venv\Scripts\python.exe -m compileall -q agent_app
```

Expected: health test passes and compileall exits 0.

- [x] **Step 6: Commit**

```powershell
git add .gitignore requirements.txt requirements-dev.txt agent_app tests
git commit -m "feat: bootstrap local agent service"
```

### Task 2: Add SQLite Models and Alembic Migration

**Files:**
- Create: `agent_app/domain/enums.py`
- Create: `agent_app/infrastructure/database.py`
- Create: `agent_app/infrastructure/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`
- Create: `tests/unit/test_database_schema.py`

**Interfaces:**
- Consumes: `Settings.data_dir`.
- Produces: `create_engine_and_session(settings) -> tuple[Engine, sessionmaker[Session]]`, ORM models, and migration revision `0001`.

- [x] **Step 1: Write the failing schema test**

```python
from sqlalchemy import inspect

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base


def test_initial_schema_contains_agent_tables(tmp_path):
    engine, _ = create_engine_and_session(Settings(data_dir=tmp_path))
    Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == {
        "profiles",
        "base_greetings",
        "model_configs",
        "batches",
        "job_snapshots",
        "analyses",
        "greetings",
        "approval_versions",
        "delivery_items",
        "browser_tasks",
        "audit_events",
    }
```

- [x] **Step 2: Run the test and verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_database_schema.py -v`

Expected: FAIL because `agent_app.infrastructure.database` does not exist.

- [x] **Step 3: Define domain enums**

`agent_app/domain/enums.py`:

```python
from enum import StrEnum


class BatchStatus(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PAUSED = "paused"
    PAUSED_SECURITY = "paused_security"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    APPROVED = "approved"
    LOCATING = "locating"
    REVALIDATING = "revalidating"
    SENDING = "sending"
    SENT = "sent"
    ALREADY_CONTACTED = "already_contacted"
    UNAVAILABLE = "unavailable"
    IDENTITY_MISMATCH = "identity_mismatch"
    SEND_FAILED = "send_failed"
    CANCELLED = "cancelled"
```

- [x] **Step 4: Implement database creation and the initial models**

`agent_app/infrastructure/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from agent_app.config import Settings


def create_engine_and_session(
    settings: Settings,
) -> tuple[Engine, sessionmaker[Session]]:
    settings.ensure_directories()
    database_path = (settings.data_dir / "boss_agent.sqlite3").resolve()
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
```

Implement `agent_app/infrastructure/models.py` with SQLAlchemy 2 typed mappings. Every table listed in the failing test must have a string UUID primary key, `created_at`, and `updated_at`. Use JSON columns for versioned payloads and explicit foreign keys for batch-owned rows. The minimum relationships are:

```python
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
```

Required unique constraints: `job_snapshots(batch_id, job_identity_key)`, `delivery_items(approval_version_id, job_snapshot_id)`, and `browser_tasks.idempotency_key`.

- [x] **Step 5: Configure Alembic and write revision 0001**

Set `target_metadata = Base.metadata` in `alembic/env.py`. In `0001_initial_schema.py`, create exactly the eleven tables and constraints asserted by the test. `downgrade()` drops them in reverse foreign-key order.

- [x] **Step 6: Run schema and migration verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_database_schema.py -v
$env:BOSS_AGENT_DATA_DIR=(Resolve-Path .).Path + '\data\migration-check'
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
Remove-Item Env:BOSS_AGENT_DATA_DIR
```

Expected: test passes; Alembic reports revision `0001` as head.

- [x] **Step 7: Commit**

```powershell
git add agent_app/domain agent_app/infrastructure alembic alembic.ini tests/unit/test_database_schema.py
git commit -m "feat: add agent database schema"
```

### Task 3: Add Local Tokens and Secret Storage

**Files:**
- Create: `agent_app/infrastructure/secrets.py`
- Create: `agent_app/api/dependencies.py`
- Create: `tests/unit/test_secrets.py`
- Create: `tests/api/test_auth.py`
- Modify: `agent_app/main.py`
- Modify: `agent_app/config.py`

**Interfaces:**
- Consumes: `Settings.data_dir`, request header `X-Agent-Token`.
- Produces: `SecretStore.get/set/delete`, `require_app_token`, and `require_browser_token`.

- [x] **Step 1: Write failing secret and authorization tests**

```python
def test_file_secret_store_never_returns_other_keys(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    store.set("openai_api_key", "secret-value")
    assert store.get("openai_api_key") == "secret-value"
    assert store.get("missing") is None


def test_business_api_rejects_missing_token(client):
    response = client.get("/api/v1/auth-check")
    assert response.status_code == 401
```

- [x] **Step 2: Run tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_secrets.py tests/api/test_auth.py -v`

Expected: FAIL because secret and auth modules do not exist.

- [x] **Step 3: Implement the secret interface and file fallback**

```python
from pathlib import Path
from typing import Protocol
import json
import os


class SecretStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class FileSecretStore:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def set(self, key: str, value: str) -> None:
        values = self._read()
        values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(values), encoding="utf-8")
        os.chmod(self.path, 0o600)

    def get(self, key: str) -> str | None:
        return self._read().get(key)

    def delete(self, key: str) -> None:
        values = self._read()
        values.pop(key, None)
        self.path.write_text(json.dumps(values), encoding="utf-8")
```

Add `KeyringSecretStore` with service name `boss-resume-delivery-agent`; select keyring first and fall back to the file store only when keyring raises `NoKeyringError` or `KeyringError`.

- [x] **Step 4: Implement scoped token dependencies**

Generate separate app and browser tokens on first startup using `secrets.token_urlsafe(32)`. Save only in the `SecretStore`. `require_app_token` compares `X-Agent-Token` with `hmac.compare_digest`; `require_browser_token` performs the same check against the browser token.

Add a temporary protected `GET /api/v1/auth-check` returning `{"ok": true}` for the contract test. Do not expose tokens through any endpoint.

- [x] **Step 5: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_secrets.py tests/api/test_auth.py -v`

Expected: all tests pass; missing/wrong token returns 401 and correct app token returns 200.

- [x] **Step 6: Commit**

```powershell
git add agent_app tests/unit/test_secrets.py tests/api/test_auth.py
git commit -m "feat: secure local agent endpoints"
```

### Task 4: Implement Profile and Model Configuration APIs

**Files:**
- Create: `agent_app/domain/schemas.py`
- Create: `agent_app/application/profiles.py`
- Create: `agent_app/infrastructure/repositories.py`
- Create: `agent_app/api/routers/profiles.py`
- Create: `agent_app/api/routers/settings.py`
- Create: `tests/unit/test_profile_context.py`
- Create: `tests/api/test_profiles.py`
- Modify: `agent_app/main.py`

**Interfaces:**
- Consumes: authorized profile/model payloads.
- Produces: `ProfileService.model_context(profile) -> dict[str, object]`, `GET/PUT /api/v1/profiles/current`, and `GET/PUT /api/v1/settings/model`.

- [x] **Step 1: Write failing profile visibility tests**

```python
def test_model_context_removes_empty_and_private_fields():
    profile = ProfileUpdate(
        target_roles=["AI 应用工程师"],
        skills=["Python", "FastAPI"],
        email="private@example.com",
        field_visibility={"target_roles": True, "skills": True, "email": False},
    )
    assert ProfileService.model_context(profile) == {
        "target_roles": ["AI 应用工程师"],
        "skills": ["Python", "FastAPI"],
    }
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_profile_context.py -v`

Expected: FAIL because `ProfileUpdate` and `ProfileService` do not exist.

- [x] **Step 3: Define exact schemas**

Create `ProfileUpdate` with optional fields for target roles/directions, desired work, focus skills, excluded directions, summary, education, skills, projects, employment, research, competitions, open source, strengths, availability, email, phone, address, and `field_visibility: dict[str, bool]`.

Create `ModelConfigUpdate`:

```python
class ModelConfigUpdate(BaseModel):
    base_url: HttpUrl
    model: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    temperature: float = Field(default=0.2, ge=0, le=1)
    api_key: SecretStr | None = None
```

- [x] **Step 4: Implement repository, service, and routers**

`ProfileService.model_context` must iterate model fields, include only visible non-empty values, and always exclude `email`, `phone`, and `address` unless visibility is explicitly `True`. Model config GET returns `api_key_configured: bool`, never the key. PUT stores the key through `SecretStore` and stores only `base_url`, `model`, timeout, and temperature in SQLite.

- [x] **Step 5: Run focused API and unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_profile_context.py tests/api/test_profiles.py -v
```

Expected: profile round trip passes; private and empty fields are absent; model config response contains no API key.

- [x] **Step 6: Commit**

```powershell
git add agent_app tests/unit/test_profile_context.py tests/api/test_profiles.py
git commit -m "feat: manage local candidate profile"
```

### Task 5: Implement Batch State and Base APIs

**Files:**
- Create: `agent_app/domain/transitions.py`
- Create: `agent_app/application/batches.py`
- Create: `agent_app/api/routers/batches.py`
- Create: `tests/unit/test_batch_transitions.py`
- Create: `tests/api/test_batches.py`
- Modify: `agent_app/main.py`

**Interfaces:**
- Consumes: `BatchCreate(limit, analysis_enabled, greeting_enabled, source_url)`.
- Produces: `BatchService.create/get/transition`, `POST /api/v1/batches`, `GET /api/v1/batches/{id}`.

- [x] **Step 1: Write failing transition tests**

```python
import pytest


def test_batch_allows_collection_path():
    assert next_batch_status(BatchStatus.DRAFT, "start_collection") is BatchStatus.COLLECTING
    assert next_batch_status(BatchStatus.COLLECTING, "collection_complete") is BatchStatus.COLLECTED


def test_batch_rejects_execution_before_approval():
    with pytest.raises(InvalidBatchTransition):
        next_batch_status(BatchStatus.COLLECTED, "execute")
```

- [x] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_batch_transitions.py -v`

Expected: FAIL because transition symbols do not exist.

- [x] **Step 3: Implement the transition table**

```python
TRANSITIONS = {
    (BatchStatus.DRAFT, "start_collection"): BatchStatus.COLLECTING,
    (BatchStatus.COLLECTING, "collection_complete"): BatchStatus.COLLECTED,
    (BatchStatus.COLLECTED, "start_analysis"): BatchStatus.ANALYZING,
    (BatchStatus.ANALYZING, "analysis_complete"): BatchStatus.AWAITING_APPROVAL,
    (BatchStatus.COLLECTED, "skip_analysis"): BatchStatus.AWAITING_APPROVAL,
    (BatchStatus.AWAITING_APPROVAL, "approve"): BatchStatus.APPROVED,
    (BatchStatus.APPROVED, "execute"): BatchStatus.EXECUTING,
    (BatchStatus.EXECUTING, "complete"): BatchStatus.COMPLETED,
}
```

Add explicit pause, security pause, resume, fail, and cancel transitions. Every invalid pair raises `InvalidBatchTransition(current, event)`.

- [x] **Step 4: Implement batch schemas, service, and routes**

`BatchCreate.limit` defaults to 10 and is constrained to 1-50. `source_url` must use HTTPS and host `www.zhipin.com` with path `/web/geek/jobs`. `POST /batches` persists `draft`; `GET` returns counts and `available_actions` derived from current status.

- [x] **Step 5: Run focused tests and full Phase 1 suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_batch_transitions.py tests/api/test_batches.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: focused and full suites pass.

- [x] **Step 6: Verify startup and local binding**

Run: `.\.venv\Scripts\python.exe -m uvicorn agent_app.main:app --host 127.0.0.1 --port 8765`

Expected: server starts on `http://127.0.0.1:8765`; `/api/health` returns 200. Stop with Ctrl+C.

- [x] **Step 7: Commit**

```powershell
git add agent_app tests
git commit -m "feat: add batch lifecycle API"
```

## Phase 1 Exit Gate

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=agent_app --cov-report=term-missing
.\.venv\Scripts\python.exe -m compileall -q agent_app
node --check .\zhipin-auto-greeting.user.js
git diff --check
```

Expected: no failures; service/data code has meaningful branch coverage; userscript syntax remains valid. Record the exact test count in the implementation log before starting Phase 2.

## Implementation Log

- 2026-07-22 Phase 1 exit gate: 16 tests passed; `agent_app` coverage 93%; Python compile, userscript syntax, and `git diff --check` passed. Uvicorn bound to `127.0.0.1:8765`, `/api/health` returned 200, and the process was stopped after verification.
