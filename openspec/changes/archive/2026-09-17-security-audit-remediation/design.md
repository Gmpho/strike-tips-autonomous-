## Context

Audit snapshot predates the Pages migration (cites `middleware.ts`, ratio 2.0). Verified each claim live: VULN-01 relocated to the Pages Function, VULN-02 confirmed minus the `/agent/memory` false positive, VULN-04 confirmed in `modal_app.py`, Chroma bug reproduced from the user's docker log.

## Goals / Non-Goals

**Goals:** close paid-compute abuse, close write proxy, lock PINs, stop Groq waste.

**Non-Goals:** user auth system (no identity layer exists — key-per-IP + rate limits are the proportionate control); Redis token bucket (no Redis server on Modal); WAF rules (blocked on custom domain).

## Decisions

* Key `/v1/*` rather than proxy-only: direct Modal URLs are enumerable, defense must live at the backend.
* HUD safety comes from the proxy injecting the key — verified 200s on reads, chat, and health post-change.
* WS key via query param (browsers can't set WS headers); 4401 close code.
* PIN state on volume JSON (shared across containers); fail-open on I/O so a corrupt file can't lock out the owner.
* Chroma fix at the single offending call site (audit found no siblings).
