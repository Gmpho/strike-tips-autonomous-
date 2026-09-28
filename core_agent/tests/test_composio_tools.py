"""Composio tools: mocked-executor tests (no network, no CLI needed)."""
from unittest.mock import MagicMock, patch

from core_agent.integrations import composio_client
from core_agent.integrations.composio_client import ComposioError, execute
from core_agent.tools import composio_tools
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY


def _ok_result():
    m = MagicMock()
    m.returncode = 0
    m.stdout = '{"successful": true, "data": {"updatedRange": "T!A1:B2"}}'
    m.stderr = ""
    return m


def test_allowlist_refuses_unknown_slug():
    try:
        execute("EVIL_DELETE_EVERYTHING", {})
        assert False, "must raise"
    except ComposioError as e:
        assert "allowlist" in str(e)


def test_execute_parses_success():
    with patch("subprocess.run", return_value=_ok_result()):
        with patch("shutil.which", return_value="/usr/bin/composio"):
            res = execute("GOOGLESHEETS_VALUES_UPDATE", {"a": 1})
    assert res["data"]["updatedRange"] == "T!A1:B2"


def test_execute_timeout_is_friendly():
    import subprocess

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("c", 1)):
        with patch("shutil.which", return_value="/usr/bin/composio"):
            try:
                execute("GOOGLESHEETS_VALUES_GET", {})
                assert False, "must raise"
            except ComposioError as e:
                assert "timed out" in str(e)


def test_no_vendor_slugs_in_registry():
    names = list(TOOL_REGISTRY)
    for wanted in ("create_analysis_sheet", "export_pnl_report", "publish_tip_post"):
        assert wanted in names
    for name in names:
        assert "GOOGLESHEETS" not in name and "COMPOSIO_" not in name


def test_publish_cap_blocks_sixth_post():
    uid = "u-cap-test"
    composio_tools._post_counts.pop(uid, None)
    for _ in range(5):
        r = composio_tools.publish_tip_post("Firealley R7 banker", uid)
        assert r["ok"] is True
        composio_tools._post_cap_hit(uid)
    r = composio_tools.publish_tip_post("one more", uid)
    assert r["ok"] is False and "cap" in r["error"].lower()


def test_publish_dry_run_by_default():
    r = composio_tools.publish_tip_post("Hello racecard", "u-dry")
    assert r == {"ok": True, "dry_run": True, "chars": 14}


def test_create_sheet_maps_failure_plainly():
    import core_agent.tools.composio_tools as ct

    with patch.object(ct, "execute", side_effect=ComposioError("nope")):
        r = ct.create_analysis_sheet("sid", "T", [["a"]])
    assert r["ok"] is False and r["error"] == "nope"
