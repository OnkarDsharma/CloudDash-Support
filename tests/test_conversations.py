from fastapi.testclient import TestClient

from main import app


def test_start_conversation() -> None:
    client = TestClient(app)

    response = client.post("/conversations", json={"customer_id": "cust_123"})

    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"]
    assert body["trace_id"]
    assert body["active_agent"] == "triage"
    assert body["status"] == "active"


def test_get_conversation() -> None:
    client = TestClient(app)
    created = client.post("/conversations", json={"customer_id": "cust_456"}).json()

    response = client.get(f"/conversations/{created['conversation_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == created["conversation_id"]
    assert body["trace_id"] == created["trace_id"]
    assert body["customer_id"] == "cust_456"
    assert body["messages"] == []


def test_send_message_appends_customer_and_assistant_messages() -> None:
    client = TestClient(app)
    created = client.post("/conversations", json={}).json()

    response = client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "My alerts stopped firing after I updated AWS credentials."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == created["conversation_id"]
    assert body["active_agent"] == "technical"
    assert body["customer_message"]["role"] == "customer"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["agent"] == "technical"
    assert body["assistant_message"]["citations"]
    assert len(body["state"]["messages"]) == 2
    assert body["state"]["retrieved_sources"]


def test_unknown_conversation_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/conversations/does-not-exist")

    assert response.status_code == 404


def test_duplicate_charge_message_escalates() -> None:
    client = TestClient(app)
    created = client.post("/conversations", json={"customer_id": "cust_billing"}).json()

    response = client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "I've been charged twice for April. I need an immediate refund and a manager."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["active_agent"] == "escalation"
    assert body["assistant_message"]["agent"] == "escalation"
    assert body["state"]["status"] == "escalated"
    assert body["state"]["escalation_ticket"]["priority"] == "high"
