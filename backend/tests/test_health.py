from __future__ import annotations


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["airgap"] is True


def test_models_hide_remote_in_airgap(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()["models"]
    assert models, "registry should expose local models"
    assert all(not model["remote"] for model in models)


def test_egress_status(client):
    response = client.get("/api/health/egress")
    assert response.status_code == 200
    assert response.json()["airgap"] is True


def test_unmatched_routes_and_validation_use_error_envelope(client):
    assert client.get("/api/missing").json()["error"]["code"] == "http_404"
    assert client.post("/api/tasks", json={}).json()["error"]["code"] == "validation_error"
