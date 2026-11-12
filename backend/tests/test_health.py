from fastapi import Query
from sqlalchemy.exc import OperationalError
from app.database.session import get_session

def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Testah API", "database": "connected"}

def test_database_failure_is_unavailable(client):
    class BrokenSession:
        def execute(self, _statement):
            raise OperationalError("SELECT 1", {}, Exception("private database details"))
    client.app.dependency_overrides[get_session] = lambda: BrokenSession()
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "http_503", "message": "Database unavailable."}}
    assert "private" not in response.text

def test_cors_allowed_and_disallowed(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers

def test_not_found_uses_error_envelope(client):
    response = client.get("/api/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_404"

def test_validation_does_not_echo_input(client):
    @client.app.get("/test-validation")
    def validation_route(value: int = Query()):
        return value
    response = client.get("/test-validation?value=private-secret")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "private-secret" not in response.text

def test_unexpected_error_is_sanitized(client):
    @client.app.get("/test-error")
    def error_route():
        raise RuntimeError("private-secret")
    response = client.get("/test-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private-secret" not in response.text

