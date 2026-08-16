import time

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.helpers import navisworks_html


def test_report_chat_stream_and_persistence(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
        inference_provider="mock",
    )
    with TestClient(create_app(settings)) as client:
        conversation = client.post("/api/conversations", json={"title": "Test chat"}).json()
        upload = client.post(
            "/api/uploads",
            files={"file": ("report.html", navisworks_html(), "text/html")},
        )
        assert upload.status_code == 201, upload.text
        report = client.post("/api/reports", json={"upload_id": upload.json()["id"]})
        assert report.status_code == 201, report.text
        assert report.json()["clash_count"] == 1
        clash = client.get(f"/api/reports/{report.json()['id']}/clashes").json()[0]
        message = client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"content": "Analyze this clash", "attachment_ids": []},
        ).json()
        run = client.post(
            "/api/inference-runs",
            json={
                "conversation_id": conversation["id"],
                "user_message_id": message["id"],
                "clash_item_id": clash["id"],
            },
        )
        assert run.status_code == 202, run.text

        deadline = time.monotonic() + 5
        state = run.json()
        while state["status"] in {"pending", "running"} and time.monotonic() < deadline:
            time.sleep(0.01)
            state = client.get(f"/api/inference-runs/{state['id']}").json()

        assert state["status"] == "completed", state
        assert state["result"]["normalized"]["clash_name"] == "cd-test-001"
        conversation_state = client.get(f"/api/conversations/{conversation['id']}").json()
        assert [item["role"] for item in conversation_state["messages"]] == ["user", "assistant"]
        assert "trusted" not in conversation_state["messages"][1]["content"].lower()


def test_health_and_readiness(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/ready").json() == {
            "status": "ok",
            "checks": {"database": True, "storage": True},
        }
