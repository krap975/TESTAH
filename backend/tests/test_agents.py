import json
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from app.core.config import Settings
from app.main import create_app
from app.models.agent import Agent

VALID = {"name": "ShopBot", "description": "Independent candidate", "endpoint_url": "https://agents.example.com/agent"}

def create(client, **changes):
    return client.post("/api/agents", json={**VALID, **changes})

def test_registration_read_and_persistence(agent_client):
    response = create(agent_client)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["id"] and record["created_at"].endswith("Z")
    assert record["last_test_status"] == "not_tested" and record["last_test_at"] is None
    assert "authentication" not in record and "auth_secret_key" not in record
    assert agent_client.get("/api/agents/" + record["id"]).json() == record
    assert agent_client.get("/api/agents").json() == [record]
    with TestClient(create_app(agent_client.app.state.settings)) as other:
        assert other.get("/api/agents/" + record["id"]).json()["name"] == "ShopBot"

@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "   "}, {"name": "a" * 101}, {"name": 123},
    {"description": "a" * 4001}, {"endpoint_url": "not a url"},
    {"endpoint_url": "http://agents.example.com/agent"},
    {"endpoint_url": "https://localhost/agent"}, {"endpoint_url": "https://127.0.0.1/agent"},
    {"endpoint_url": "https://10.0.0.1/agent"}, {"endpoint_url": "https://169.254.169.254/"},
    {"endpoint_url": "https://[::1]/"}, {"endpoint_url": "https://[::ffff:8.8.8.8]/"},
    {"endpoint_url": "https://224.0.0.1/"}, {"endpoint_url": "https://168.63.129.16/"},
    {"endpoint_url": "https://user:secret@agents.example.com/"},
    {"endpoint_url": "https://agents.example.com:8443/"},
    {"endpoint_url": "https://agents.example.com/?token=private"},
    {"endpoint_url": "https://agents.example.com/#fragment"},
    {"endpoint_url": "https://127%2e0%2e0%2e1/"},
    {"authentication": {"header_name": "Host", "secret_key": "KEY"}},
    {"authentication": {"header_name": "Authorization", "secret_key": "KEY", "value": "private"}},
    {"unknown": True},
])
def test_invalid_registration(agent_client, changes):
    response = create(agent_client, **changes)
    assert response.status_code == 422, response.text
    assert "private" not in response.text

def test_duplicate_update_delete(agent_client):
    first = create(agent_client).json()
    assert create(agent_client, name=" shopbot ").status_code == 409
    second = create(agent_client, name="OtherBot").json()
    assert agent_client.patch("/api/agents/" + second["id"], json={"name": "SHOPBOT"}).status_code == 409
    response = agent_client.patch("/api/agents/" + first["id"], json={"name": "Revised", "description": "Updated"})
    assert response.status_code == 200 and response.json()["description"] == "Updated"
    assert response.json()["created_at"] == first["created_at"]
    assert agent_client.patch("/api/agents/" + first["id"], json={"name": None}).status_code == 422
    assert agent_client.patch("/api/agents/" + first["id"], json={"endpoint_url": "http://localhost/"}).status_code == 422
    assert agent_client.delete("/api/agents/" + first["id"]).status_code == 204
    assert agent_client.get("/api/agents/" + first["id"]).status_code == 404
    assert agent_client.delete("/api/agents/" + first["id"]).status_code == 404
    assert agent_client.post("/api/agents/missing/test").status_code == 404

def test_secret_reference_and_removal(agent_client):
    secret = "Bearer private-credential"
    agent_client.app.state.settings.agent_secrets = {"KEY": SecretStr(secret)}
    response = create(agent_client, authentication={"header_name": "Authorization", "secret_key": "KEY"})
    assert response.status_code == 201
    assert response.json()["authentication_configured"] is True
    assert secret not in response.text and "secret_key" not in response.text
    agent_id = response.json()["id"]
    assert agent_client.patch("/api/agents/" + agent_id, json={"description": "changed"}).json()["authentication_configured"] is True
    assert agent_client.patch("/api/agents/" + agent_id, json={"authentication": None}).json()["authentication_configured"] is False
    assert create(agent_client, name="Missing", authentication={"header_name": "Authorization", "secret_key": "MISSING"}).status_code == 400
    with agent_client.app.state.session_factory() as session:
        saved = session.scalar(select(Agent).where(Agent.id == agent_id))
        assert saved.auth_secret_key is None
        assert secret not in str(saved.__dict__)

def test_development_sample_is_separate_and_explicit(agent_client):
    local = {"endpoint_url": "http://127.0.0.1:9001/agent", "connection_mode": "local_sample"}
    assert create(agent_client, **local).status_code == 400
    agent_client.app.state.settings.allow_local_sample = True
    assert create(agent_client, **local).status_code == 201
    assert create(agent_client, name="External local", endpoint_url=local["endpoint_url"]).status_code == 422
    assert create(agent_client, name="Other port", connection_mode="local_sample", endpoint_url="http://127.0.0.1:8000/agent").status_code == 422
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", allow_local_sample=True)

def test_list_pagination_and_bounds(agent_client):
    create(agent_client)
    assert agent_client.get("/api/agents?offset=1").json() == []
    assert agent_client.get("/api/agents?limit=101").status_code == 422


def test_validation_messages_are_useful_without_echoing_values(agent_client):
    response = create(agent_client, endpoint_url="https://127.0.0.1/")
    assert "public destination" in response.json()["error"]["message"]
    assert "127.0.0.1" not in response.text
    response = create(agent_client, name="")
    assert "name" in response.json()["error"]["message"]
