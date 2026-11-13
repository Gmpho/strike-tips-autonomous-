"""Region resolution — the Gulf, and the venues that must not change.

Nov-2026: the Betfair exchange feed carries the Bahrain meeting (group
"BAH") and ATR's results cover Abu Dhabi, but neither venue was in any
region map. Every Gulf race resolved to "OTHER" and was dropped by the
region filters before it could reach the card.
"""
from core_agent.skills.league.regions import region_label, region_of


# ── the Gulf ────────────────────────────────────────────────────────────────

def test_uae_venues_resolve_to_uae():
    assert region_of("Abu Dhabi") == "UAE"
    assert region_of("Abu Dhabi (UAE)") == "UAE"
    assert region_of("Dubai") == "UAE"
    assert region_of("Meydan") == "UAE"
    assert region_of("Jebel Ali") == "UAE"
    assert region_of("Al Ain") == "UAE"


def test_bahrain_venues_resolve_to_bahrain():
    assert region_of("Bahrain") == "BHR"
    assert region_of("Sakhir") == "BHR"
    assert region_of("Bahrain (BHR)") == "BHR"
    assert region_of("Sakhir (BHR)") == "BHR"


def test_gulf_regions_have_labels():
    assert region_label("UAE") == "United Arab Emirates"
    assert region_label("BHR") == "Bahrain"


# ── the venues that already worked must keep working ───────────────────────

def test_existing_venues_are_unaffected():
    assert region_of("Turffontein") == "SA"
    assert region_of("Greyville") == "SA"
    assert region_of("Kenilworth") == "SA"
    assert region_of("Fairview") == "SA"
    assert region_of("Churchill Downs") == "USA"
    assert region_of("Horseshoe Indianapolis") == "USA"
    assert region_of("Mahoning Valley") == "USA"
    assert region_of("Woodbine") == "CAN"
    assert region_of("Happy Valley") == "HK"
    assert region_of("Randwick") == "AUS"
    assert region_of("Ayr") == "UK_IE"
    assert region_of("Naas") == "UK_IE"
    assert region_of("Meydan") == "UAE"


def test_unknown_courses_stay_other():
    """Unknown courses are grouped, never hidden — and never guessed."""
    assert region_of("Some Unknown Track") == "OTHER"
    assert region_of("") == "OTHER"
    assert region_of(None) == "OTHER"
