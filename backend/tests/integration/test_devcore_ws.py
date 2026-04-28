import pytest, json
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

def test_ws_rejects_without_auth():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/cluely/ws") as ws:
        # Send non-auth frame immediately
        ws.send_json({"type": "session_start", "session_id": "abc"})
        data = ws.receive_json()
        assert data.get("type") == "error"

def test_ws_accepts_valid_auth():
    client = TestClient(app)
    token = create_access_token("test-user-id")
    with client.websocket_connect("/api/v1/cluely/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        # Send session_end to close cleanly
        ws.send_json({"type": "session_end"})
        # Connection should have closed cleanly — no exception raised
