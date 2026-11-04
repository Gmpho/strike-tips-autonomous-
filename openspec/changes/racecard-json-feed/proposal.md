# Proposal: Racecard JSON Feed (retire the Computaform PDF parse)

## Why
We already talk to 4Racing's `phumelelaV4` content service in JSON — but only
to list PDFs:

- `pdf_discovery.py:9` → `.../get/Content/4RACINGWEB_TAB?sub_action=getComputaform&tag=ComputaformSA&date=...`
- `tab_content.py:15` → same base with `sub_action=getComputaform` for
  `ComputaformSA/UK/IRE/EX` plus `cards` and `tips` tag groups

Then we download the PDF from an Azure blob and re-parse a rendered document
(`tab_pdf_mapper.py`). The PDF is a print view: the same service almost
certainly exposes the structured card (race → runner → draw/weight/jockey/form)
that the PDF was generated from. Reading fields beats reconstructing columns.

## What changes (discovery first, then code)
1. **Discovery (REA / HAR):** load a tab4racing racecard for a live SA meeting
   with DevTools Network open; capture the `phumelelaV4` requests. Identify the
   sub-action returning runners (candidate names: `getRaceCard`,
   `getRacingInfo`, `getMeetings`). Record method, params, auth, and a sample
   response shape.
2. **Parser:** add `racecard_api.py` (or extend `tab_content.py`) returning the
   existing `ScrapedRace` / `ScrapedRunner` dataclasses so downstream code is
   untouched.
3. **Fallback:** keep `tab_pdf_mapper` for meetings where only the PDF exists
   (scanned/unstructured cards).

## Guardrails
- Honest client only: `user_agent()`, per-host pacing from `compliance.py`.
- No bot-protection evasion. If the endpoint is gated, stop and report — do not
  escalate to a stealth browser.
- 4Racing/TAB terms still apply; this is interoperability on data we already
  consume as a customer, not a licence.

## Blocked on
- REA install (after the user's Docker verification) and a **live SA meeting**
  to capture real traffic.
