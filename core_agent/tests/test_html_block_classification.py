"""The 403 page names the layer that refused us — it must be read correctly.

Betway and ``*.workers.dev`` are both fronted by Cloudflare, so the same block
page can mean two completely different things. The logs blamed Betway for
5,437 calls that Cloudflare refused before the Worker even ran.
"""

from core_agent.skills.parsers.betway_api import BetwayAPI, _classify_html_block

BLOCK_PAGE = (
    '<!DOCTYPE html><html class="no-js ie6 oldie"><head>'
    "<title>Attention Required! | Cloudflare</title></head><body>Sorry…</body></html>"
)
CHALLENGE_PAGE = "<html><head><title>Just a moment...</title></head></html>"


def test_cloudflare_block_page_is_named():
    assert _classify_html_block(BLOCK_PAGE) == "Cloudflare WAF block page"


def test_cloudflare_js_challenge_is_named():
    assert _classify_html_block(CHALLENGE_PAGE) == "Cloudflare JS challenge"


def test_origin_error_is_not_called_a_block():
    """A 520 is Cloudflare failing to reach Betway — the opposite of a refusal."""
    assert "not a block" in _classify_html_block("error code: 520")


def test_unknown_html_still_reports_its_title():
    assert "502 Bad Gateway" in _classify_html_block(
        "<html><head><title>502 Bad Gateway</title></head></html>"
    )


def test_empty_body_is_safe():
    assert _classify_html_block("") == "HTML error page"


def test_edge_block_is_logged_once_per_cycle(caplog):
    """One accurate line, not one per GetEvent call."""
    api = BetwayAPI()
    api.start_cycle()
    caplog.clear()

    import logging

    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            # Mirror what _http_get does when the Worker returns a block page.
            api._edge_blocked_calls += 1
            if not api._edge_block_logged:
                api._edge_block_logged = True
                logging.getLogger("betway-api").warning("Worker edge refused this cycle (403)")

    refused = [r for r in caplog.records if "Worker edge refused" in r.getMessage()]
    assert len(refused) == 1
    assert api._edge_blocked_calls == 5

    # A new cycle may report again — the block can lift between cycles.
    api.start_cycle()
    assert api._edge_block_logged is False
    assert api._edge_blocked_calls == 0
