## Context

No new dependencies allowed (stdlib logging + contextvars only). Modal log tailing is text-only, hence JSON-at-source. Telegram messages are the only cross-process artifact the user sees, hence the trailing token.

## Goals / Non-Goals

**Goals:** one-grep incidents; queryable prod logs; quiet routine paths.

**Non-Goals:** OpenTelemetry, dashboards, per-user metrics (later sprint, pending review).

## Decisions

* ContextVar (not thread-local): async-safe across the FastAPI/Modal runtimes.
* Empty-when-unbound: tests/REPL never break; call sites unconditional.
* `ref` as optional trailing param on Telegram sends (no signature breaks).
* ReactMarkdown + remark-gfm for assistant messages only; user bubbles stay plain.
