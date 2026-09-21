from fastapi.testclient import TestClient

from agent_hub_api.main import app


def test_health_returns_safe_liveness_payload() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AgentHub API",
        "environment": "local",
    }
    assert "database" not in response.text.lower()
