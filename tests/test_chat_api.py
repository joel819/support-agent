from app import service
from app.agent.base import AgentError


def test_chat_policy_route(client):
    r = client.post("/chat", json={"message": "What is your return policy?"}).json()
    assert r["route"] == "policy_search" and r["mode"] == "demo"
    assert "30 days" in r["answer"]
    assert r["sources"][0]["section"] == "Returns"


def test_chat_order_route(client):
    r = client.post("/chat", json={"message": "Where is order 1019?"}).json()
    assert r["route"] == "order_status"
    assert r["tool_calls"][0]["name"] == "get_order_status"
    assert r["tool_calls"][0]["arguments"] == {"order_id": "1019"}


def test_every_query_is_logged(client):
    for msg in ["Hi", "Where is order 1019?", "What is your return policy?"]:
        log_id = client.post("/chat", json={"message": msg}).json()["log_id"]
        assert log_id
    logs = client.get("/logs").json()
    assert [l["question"] for l in logs] == ["What is your return policy?", "Where is order 1019?", "Hi"]
    assert [l["route"] for l in logs] == ["policy_search", "order_status", "none"]


def test_llm_failure_falls_back_and_logs_error(client, monkeypatch):
    class Broken:
        name = "groq"

        def run(self, db, message, history):
            raise AgentError("rate limited")

    monkeypatch.setattr(service, "get_agent", lambda: Broken())
    r = client.post("/chat", json={"message": "Where is order 1019?"}).json()
    assert r["mode"] == "fallback" and r["route"] == "order_status"
    log = client.get("/logs").json()[0]
    assert log["mode"] == "fallback" and "rate limited" in log["error"]


def test_empty_message_rejected(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_orders_helper_and_health(client):
    orders = client.get("/orders").json()
    assert len(orders) == 25 and set(orders[0]) == {"order_id", "status"}
    h = client.get("/health").json()
    assert h["demo_mode"] is True and h["orders"] == 25 and h["policy_sections"] > 5


def test_index_page(client):
    assert "Kestrel Support Agent" in client.get("/").text
