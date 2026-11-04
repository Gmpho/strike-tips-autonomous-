"""Strike Tips — Supabase/Postgres repository layer (Oct-2026).

Clean-room package for the supabase-ledger-auth change. The bankroll
governor (`skills/bankroll_manager/governor.py`) is a PROTECTED path and
is NOT imported or edited here — it gains a dual-write call behind a flag
in a later, separately-approved change.

Transport: supabase-py (PostgREST). No prepared statements, so it is safe
on the Supavisor transaction-mode pooler that Modal serverless requires.
Each method is one short REST round-trip (lock-short-transactions).
"""
from core_agent.db.client import get_service_client, get_user_client
from core_agent.db.repository import LedgerRepository

__all__ = ["get_service_client", "get_user_client", "LedgerRepository"]
