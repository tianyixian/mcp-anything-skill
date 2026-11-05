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
