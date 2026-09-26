def _ask(client, *msgs):
    for m in msgs:
        client.post("/chat", json={"message": m})


def test_filter_by_route(client):
    _ask(client, "Hi", "Where is order 1019?", "Where is order 1020?", "Do you accept Klarna?")
    logs = client.get("/logs", params={"route": "order_status"}).json()
    assert len(logs) == 2 and all(l["route"] == "order_status" for l in logs)


def test_invalid_filter_rejected(client):
    assert client.get("/logs", params={"route": "bogus"}).status_code == 422


def test_stats(client):
    _ask(client, "Hi", "Where is order 1019?", "Order 1010 arrived damaged, what can I do?", "Do you accept Klarna?")
    s = client.get("/logs/stats").json()
    assert s["total"] == 4
    assert s["by_route"] == {"policy_search": 1, "order_status": 1, "both": 1, "none": 1}
    assert s["by_mode"] == {"demo": 4}
    assert s["llm_errors"] == 0


def test_log_records_tool_arguments(client):
    _ask(client, "Where is order 1019?")
    call = client.get("/logs").json()[0]["tool_calls"][0]
    assert call == {"name": "get_order_status", "arguments": {"order_id": "1019"}, "ok": True}
