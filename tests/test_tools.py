from app.knowledge.loader import load_policy, load_sections
from app.tools import route_for, run_tool
from app.tools.get_order_status import normalise_order_id


def test_order_found(db):
    r = run_tool(db, "get_order_status", {"order_id": "1019"})
    assert r.ok
    assert r.result["status"] == "shipped"
    assert r.result["tracking_number"]
    assert r.result["items"]


def test_order_result_has_no_personal_data(db):
    result = run_tool(db, "get_order_status", {"order_id": 1019}).result
    assert "email" not in result and "customer_name" not in result


def test_order_not_found(db):
    r = run_tool(db, "get_order_status", {"order_id": "9999"})
    assert not r.ok and r.result["error"] == "order_not_found"


def test_invalid_order_id(db):
    r = run_tool(db, "get_order_status", {"order_id": "abc"})
    assert r.result["error"] == "invalid_order_id"


def test_order_id_formats():
    assert normalise_order_id("#1042") == normalise_order_id("ORD-1042") == normalise_order_id(1042) == 1042


def test_missing_argument_and_unknown_tool_do_not_raise(db):
    assert run_tool(db, "get_order_status", {}).result["error"] == "missing_argument"
    assert run_tool(db, "delete_everything", {}).result["error"] == "unknown_tool"


def test_policy_search_finds_right_section(db):
    r = run_tool(db, "search_policy", {"query": "refund to my card how many business days"})
    assert r.ok
    assert r.result["results"][0]["section"] == "Refunds"


def test_policy_loader_splits_by_heading():
    titles = [s.title for s in load_policy()]
    assert "Returns" in titles and "Warranty" in titles
    assert len(titles) == len(set(s.id for s in load_policy()))


def test_long_section_is_split_but_keeps_title():
    md = "## Big\n\n" + "\n\n".join("word " * 120 for _ in range(4))
    parts = load_sections(md)
    assert len(parts) > 1 and all(p.title == "Big" for p in parts)


def test_route_is_derived_from_calls(db):
    order = run_tool(db, "get_order_status", {"order_id": "1019"})
    policy = run_tool(db, "search_policy", {"query": "returns"})
    assert route_for([]) == "none"
    assert route_for([order]) == "order_status"
    assert route_for([policy]) == "policy_search"
    assert route_for([order, policy]) == "both"
