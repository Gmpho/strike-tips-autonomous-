"""Supabase client factory.

Two roles, never mixed:
- service client: Modal backend only (crons, settlement, imports).
  Built from SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY. Bypasses RLS.
- user client: bound to a caller's JWT (HUD / per-request). Built from
  SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY with the user's access token.
  RLS enforced.

supabase-py is imported lazily so hosts without the pinned dependency
(host CI, scratch scripts) can still import this package for tests.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("db-client")


def _require_env(name: str) -> str:
    val = os.getenv(name, "")
    if not val:
        raise RuntimeError(f"{name} is not set — cannot build Supabase client")
    return val


def _create(url: str, key: str):
    try:
        from supabase import create_client
    except ImportError as e:
        raise RuntimeError(
            "supabase-py is not installed (requirements.txt pins supabase==2.31.0)"
        ) from e
    return create_client(url, key)


def get_service_client():
    """Backend-only client (Modal secrets). NEVER ship to the HUD."""
    return _create(_require_env("SUPABASE_URL"), _require_env("SUPABASE_SERVICE_ROLE_KEY"))


def get_user_client(access_token: str):
    """RLS-enforced client for one user's JWT."""
    if not access_token:
        raise RuntimeError("access_token is required for a user client")
    try:
        from supabase import create_client
    except ImportError as e:
        raise RuntimeError(
            "supabase-py is not installed (requirements.txt pins supabase==2.31.0)"
        ) from e
    url = _require_env("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not key:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not set")
    client = create_client(url, key)
    client.postgrest.auth(access_token)
    return client
