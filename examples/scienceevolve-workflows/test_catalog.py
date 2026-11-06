import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent


def test_public_catalog_points_to_sanitized_workflow_recipes():
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["kind"] == "mcp-anything-workflow-catalog"
    assert len(catalog["entries"]) == 3
    for entry in catalog["entries"]:
        recipe = ROOT / entry["recipe"]
        assert recipe.is_file()
        workflow = json.loads(recipe.read_text(encoding="utf-8"))
        assert "agents" in workflow
        assert all(agent.get("mcpServers") == [] for agent in workflow["agents"].values())
        assert len(workflow["agents"]) == 7


def test_public_catalog_has_no_local_deployment_or_secret_material():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.name != "test_catalog.py"
        and path.suffix in {".json", ".md", ".py", ".csv"}
    )
    forbidden = ("/inspire/", "127.0.0.1", "feishu.cn", "api_key", "password", "secret")
    assert not any(marker.lower() in text.lower() for marker in forbidden)


def test_all_public_json_is_well_formed():
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_catalog_capability_references_resolve():
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    capabilities = {item["id"] for item in catalog["capabilities"]}
    for entry in catalog["entries"]:
        assert set(entry["mcp_capabilities"]) <= capabilities


def test_official_evidence_matches_current_public_workflows():
    report = json.loads((ROOT / "validation/official-sdk-validation.json").read_text(encoding="utf-8"))
    expected = {"workflows/pvdf.workflow.json", "workflows/pi.workflow.json", "workflows/binder.workflow.json"}
    assert report["passed"] is True
    assert {item["file"] for item in report["workflows"]} == expected
    for item in report["workflows"]:
        assert item["sha256"] == hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
        assert item["passed"] is True
        assert item["agent_instructions_preserved"] is True
        assert item["skill_definitions_preserved"] is True
        assert item["invalid_agent_rejected"] is True
        assert item["empty_mcp_connections"] is True
