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
