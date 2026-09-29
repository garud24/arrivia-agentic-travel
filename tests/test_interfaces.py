import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from app.main import app
from app.mcp_server import mcp

client = TestClient(app)


def test_recommendations_endpoint_enforces_partner_rules():
    response = client.get("/api/recommendations/member_001")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 3
    assert "cruise" not in {r["category"] for r in body["recommendations"]}


def test_unknown_member_returns_404():
    response = client.get("/api/recommendations/no_such_member")

    assert response.status_code == 404


def test_missing_partner_config_returns_503():
    response = client.get("/api/recommendations/member_003")

    assert response.status_code == 503


def test_mcp_exposes_both_tools():
    tools = anyio.run(mcp.list_tools)

    assert {tool.name for tool in tools} == {
        "get_member_profile",
        "get_travel_recommendations",
    }


def test_mcp_tool_error_is_visible_to_agent():
    with pytest.raises(ToolError, match="Member no_such_member not found"):
        anyio.run(
            mcp.call_tool,
            "get_travel_recommendations",
            {"member_id": "no_such_member"},
        )
