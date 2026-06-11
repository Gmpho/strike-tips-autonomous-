"""Prompt examples — CoT, one-shot, and few-shot per intent.

Embedded in system prompt string, activated by intent filter in context_builder.py.
Each family has:
  - CoT reasoning steps (step-by-step thinking)
  - One-shot (one ideal example)
  - Few-shot (2 good examples + 1 counter-example)
"""

COT_STEPS = {
    "evaluate_race": (
        "=== Chain of Thought — Race Evaluation ===\n"
        "Step 1 — Get odds snapshot for this race using get_odds_snapshot.\n"
        "Step 2 — Search form insights for each runner using search_past_races.\n"
        "Step 3 — Convert each runner's odds to implied probability: 1/decimal_odds.\n"
        "Step 4 — Estimate true probability from form: recent finishing positions, "
        "track suitability, jockey performance.\n"
        "Step 5 — Calculate edge = true_prob - implied_prob for each runner.\n"
        "Step 6 — Only recommend if edge > 5.5%. Show the math.\n"
        "Step 7 — If no runner has a positive edge, pass the race.\n"
    ),
    "calculate_probability_edge": (
        "=== Chain of Thought — Probability & Edge ===\n"
        "Step 1 — Convert fractional odds to decimal: a/b → (a+b)/a.\n"
        "Step 2 — Convert decimal to implied probability: 1/decimal.\n"
        "Step 3 — Estimate true probability from form, track, going, jockey.\n"
        "Step 4 — Edge = true_prob - implied_prob.\n"
        "Step 5 — Positive edge = value bet. Negative edge = pass.\n"
    ),
    "record_selection": (
        "=== Chain of Thought — Recording a Bet ===\n"
        "Step 1 — Verify the race still exists with verify_race_exists.\n"
        "Step 2 — Confirm current odds via get_odds_snapshot.\n"
        "Step 3 — Check bankroll via get_account_summary.\n"
        "Step 4 — Validate edge > min_edge (5.5%).\n"
        "Step 5 — Only then call record_selection.\n"
        "Step 6 — If odds changed or edge dropped, do NOT bet.\n"
    ),
    "run_daily_analysis": (
        "=== Chain of Thought — Daily Scan ===\n"
        "Step 1 — Get today's races via get_odds_snapshot with no arguments.\n"
        "Step 2 — Group races by region, then by course.\n"
        "Step 3 — For each region, scan the number of races and key runners.\n"
        "Step 4 — Note any high-profile races or standout horses.\n"
        "Step 5 — Present a structured summary by region/course.\n"
    ),
    "search_racing_data": (
        "=== Chain of Thought — Searching ===\n"
        "Step 1 — Determine the target: upcoming races, past results, or tips.\n"
        "Step 2 — Use search_past_races for historical vector memory lookups.\n"
        "Step 3 — Only call search_racing_data for external web information.\n"
        "Step 4 — Return relevant snippets with source labels.\n"
    ),
    "search_past_races": (
        "=== Chain of Thought — Past Race Search ===\n"
        "Step 1 — Craft a search query from the user's question.\n"
        "Step 2 — Call search_past_races with the query.\n"
        "Step 3 — Review results: official_tips, dreams, race cards, heartbeats.\n"
        "Step 4 — Synthesize findings into a clear answer.\n"
        "Step 5 — If results are empty, say so — do not fabricate.\n"
    ),
}

ONE_SHOT = {
    "evaluate_race": (
        "=== Example — Race Evaluation ===\n"
        "User: Analyse race 4 at Turffontein\n"
        "Agent: \"Let me evaluate race 4 at Turffontein.\"\n"
        "[calls get_odds_snapshot for race_id='turffontein-4']\n"
        "[gets: Winter Mountain 2/1, Storm Surge 5/2, Gold Trip 4/1]\n"
        "[calls search_past_races for each runner]\n"
        "\"I found Turffontein race 4 (1600m, good going):\n"
        "• Winter Mountain (2/1 → 33% implied) — Won last 2 on good, loves 1600m.\n"
        "  True prob ~40%. Edge = +7%. RECOMMENDED.\n"
        "• Storm Surge (5/2 → 29% implied) — 3rd last time, unproven at trip.\n"
        "  True prob ~25%. Edge = -4%. Pass.\n"
        "• Gold Trip (4/1 → 20% implied) — 7th and 5th recently.\n"
        "  True prob ~15%. Edge = -5%. Pass.\n"
        "Edge analysis: Winter Mountain shows +7% positive edge. Consider backing.\""
    ),
    "calculate_probability_edge": (
        "=== Example — Edge Calculation ===\n"
        "User: What's the edge on a horse priced at 3/1 with a 30% true chance?\n"
        "Agent: \"3/1 fractional = 4.0 decimal.\n"
        "Implied probability = 1 / 4.0 = 25%.\n"
        "True probability = 30%.\n"
        "Edge = 30% - 25% = +5%.\n"
        "This is below our 5.5% threshold — pass on this bet.\""
    ),
    "record_selection": (
        "=== Example — Bet Recording ===\n"
        "User: Back Winter Mountain in race 4 Turffontein\n"
        "Agent: \"Let me verify before recording.\"\n"
        "[verify_race_exists → race 4 at Turffontein is confirmed]\n"
        "[get_odds_snapshot → Winter Mountain still at 2/1]\n"
        "[get_account_summary → R857.38 paper bankroll]\n"
        "[Edge pre-calculated at +7% > 5.5% threshold — OK]\n"
        "\"All checks passed. Recording selection: Winter Mountain, Turffontein R4, 2/1.\""
    ),
    "run_daily_analysis": (
        "=== Example — Daily Scan ===\n"
        "User: Scan today's races\n"
        "Agent: \"Running daily scan...\"\n"
        "[get_odds_snapshot with no args → 4 regions, 12 races]\n"
        "\"Today's racing (scan results):\n"
        "🇿🇦 South Africa — 6 races\n"
        "  • Turffontein (3 races) — R2: 1400m, R4: 1600m feature, R6: 1200m\n"
        "  • Vaal (3 races) — R1: 1000m, R3: 1800m, R5: 2000m\n"
        "🇬🇧 UK — 4 races\n"
        "  • Kempton (4 races) — All-weather, standard\n"
        "🇦🇪 Dubai — 2 races at Meydan\n"
        "Notable: Turffontein R4 looks competitive with 8 runners.\""
    ),
    "search_past_races": (
        "=== Example — Past Race Search ===\n"
        "User: What do we know about Kenilworth form?\n"
        "Agent: \"Searching past insights on Kenilworth...\"\n"
        "[search_past_races('Kenilworth form')]\n"
        "\"From vector memory, Kenilworth insights:\n"
        "• [RACE CARD] Kenilworth 4 Jan: going good, 1600m inside track bias.\n"
        "• [OFFICIAL TIP] Kenilworth R3: Silver Storm tipped 3/1.\n"
        "• [HEARTBEAT] Kenilworth winter track tends to favour front-runners.\""
    ),
}

FEW_SHOT = {
    "evaluate_race": (
        "=== Good Example 1 — Full Edge Analysis ===\n"
        "User: Assess race 7 at Greyville\n"
        "Agent: \"Evaluating Greyville race 7...\"\n"
        "[odds snapshot → 6 runners, all 3/1 to 12/1]\n"
        "\"Runner-by-runner analysis:\n"
        "• Fast Dawn (7/2 → 22%) — 2 wins from last 3, loves poly. True 30%. Edge +8%. ✅\n"
        "• Storm King (4/1 → 20%) — Place only, not winning recently. True 15%. Edge -5%.\n"
        "• Lion Heart (6/1 → 14%) — First time poly, unknown. True 10%. Edge -4%.\n"
        "• rest: no positive edges.\n"
        "Conclusion: Fast Dawn is the only value bet with +8% edge.\"\n\n"
        "=== Good Example 2 — Passing a Weak Race ===\n"
        "User: Analyse race 2 at Vaal\n"
        "Agent: \"Checking Vaal race 2...\"\n"
        "[odds snapshot → 10 runners, favourite at 2/1]\n"
        "\"6 of 10 runners have no form data. Favourite (2/1) is 50% implied but\n"
        "true probability estimated at 48% based on limited form. Edge = -2%.\n"
        "No other runner shows positive edge. This race has low confidence — pass.\"\n\n"
        "=== Counter-Example — What NOT to Do ===\n"
        "User: Analyse race 3 at Kenilworth\n"
        "Agent: \"I think Winter Mountain will win.\"\n"
        "❌ Fabricated a horse name without checking odds.\n"
        "❌ Did not call get_odds_snapshot or search_past_races.\n"
        "❌ No edge calculation.\n"
        "❌ No implied probability shown.\n"
        "❌ No form evidence.\n"
        "CORRECT: Call get_odds_snapshot first, then search form, then compute edge."
    ),
    "record_selection": (
        "=== Good Example 1 — Full Verification ===\n"
        "User: Place a bet on Winter Mountain\n"
        "Agent: \"Verifying before placing...\"\n"
        "[verify_race_exists → race confirmed]\n"
        "[get_odds_snapshot → odds confirmed at 2/1]\n"
        "[get_account_summary → R857.38 available]\n"
        "[edge +7% > 5.5% → OK]\n"
        "\"All conditions met. Recording: Winter Mountain, Turffontein R4, 2/1.\"\n\n"
        "=== Good Example 2 — Declining a Bet ===\n"
        "User: Back Storm Surge at 5/2\n"
        "Agent: \"Verifying...\"\n"
        "[verify_race_exists → confirmed]\n"
        "[get_odds_snapshot → Storm Surge drifted to 3/1 (33% implied)]\n"
        "[true probability from form: ~30%, edge = -3%]\n"
        "\"Not backing. Edge has turned negative at -3%. Passing.\"\n\n"
        "=== Counter-Example — What NOT to Do ===\n"
        "User: Back Fast Dawn at 7/2\n"
        "Agent: \"Selection recorded: Fast Dawn.\"\n"
        "❌ Skipped verify_race_exists — race may be off.\n"
        "❌ Did not re-check odds — price may have changed.\n"
        "❌ Did not check bankroll — may exceed position limit.\n"
        "❌ Did not validate edge > threshold.\n"
        "CORRECT: Run all four verification steps before recording."
    ),
    "run_daily_analysis": (
        "=== Good Example 1 — Full Regional Breakdown ===\n"
        "User: What's racing today?\n"
        "Agent: \"Running full scan...\"\n"
        "[get_odds_snapshot → 4 regions, 15 races]\n"
        "\"Today's card:\n"
        "🇿🇦 South Africa: Turffontein (3), Vaal (2), Greyville (2) — 7 races\n"
        "🇬🇧 UK: Kempton (4), Lingfield (2) — 6 races\n"
        "🇦🇪 Dubai: Meydan (2) — 2 races\n"
        "🇮🇪 Ireland: Naas (1) — 1 race\n"
        "Standout: Vaal R5 is a feature handicap with 14 runners.\"\n\n"
        "=== Good Example 2 — Quiet Day ===\n"
        "User: What's running?\n"
        "Agent: \"Today is quiet — only 3 races at Fairview.\"\n"
        "[get_odds_snapshot → 3 races all at Fairview]\n"
        "\"Fairview hosts 3 races today (all poly, standard):\n"
        "R1: 1200m, R2: 1600m, R3: 2000m.\n"
        "R2 has the biggest field (10 runners).\"\n\n"
        "=== Counter-Example ===\n"
        "User: Scan today\n"
        "Agent: \"No races found.\"\n"
        "❌ Did not call get_odds_snapshot.\n"
        "❌ Did not group by region/course.\n"
        "❌ Returned zero information.\n"
        "CORRECT: Call get_odds_snapshot first, then structure results by region."
    ),
    "search_past_races": (
        "=== Good Example 1 — Found Results ===\n"
        "User: What do we have on Turffontein?\n"
        "Agent: \"Searching past Turffontein data...\"\n"
        "[search_past_races('Turffontein tips')]\n"
        "\"Found these records:\n"
        "• [OFFICIAL TIP] 15 Jan: Winter Mountain tipped in R4 (won at 2/1).\n"
        "• [RACE CARD] 22 Jan: Turffontein R3 1400m, good going.\n"
        "• [HEARTBEAT] Turffontein inside barrier advantage at 1400m.\"\n\n"
        "=== Good Example 2 — Empty Results ===\n"
        "User: Any info on Durbanville?\n"
        "Agent: \"Searching Durbanville records...\"\n"
        "[search_past_races('Durbanville form')]\n"
        "\"No past records found for Durbanville in vector memory.\"\n"
        "Honest answer — no fabrication.\n\n"
        "=== Counter-Example ===\n"
        "User: Greyville form?\n"
        "Agent: \"Greyville has strong form. Fast Dawn won there recently.\"\n"
        "❌ Fabricated a specific claim not backed by search results.\n"
        "❌ Did not cite source type ([OFFICIAL TIP], [HEARTBEAT], etc.).\n"
        "CORRECT: Call search_past_races and report only what is returned."
    ),
}
