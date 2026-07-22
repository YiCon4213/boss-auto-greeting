import pytest
from fastapi.testclient import TestClient

from agent_app.config import Settings
from agent_app.infrastructure.database import create_engine_and_session
from agent_app.infrastructure.models import Base
from agent_app.infrastructure.secrets import FileSecretStore
from agent_app.main import create_app


@pytest.fixture
def workbench_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine, session_factory = create_engine_and_session(settings)
    Base.metadata.create_all(engine)
    app = create_app(
        settings,
        secret_store=FileSecretStore(tmp_path / "secrets.json"),
        session_factory=session_factory,
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_workbench_root_serves_approval_layout_and_local_assets(workbench_client):
    response = workbench_client.get("/")

    assert response.status_code == 200
    assert "本地简历投递 Agent" in response.text
    assert "当前批次" in response.text
    assert "分析与话术" in response.text
    assert "批准本批次" in response.text
    assert "/assets/styles.css" in response.text
    assert "/assets/app.js" in response.text
    assert workbench_client.get("/assets/styles.css").status_code == 200
    assert workbench_client.get("/assets/app.js").status_code == 200


def test_workbench_cookie_authenticates_same_origin_without_exposing_token(workbench_client):
    response = workbench_client.get("/")

    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert workbench_client.get("/api/v1/auth-check").status_code == 200
    assert workbench_client.app.state.app_token not in response.text
