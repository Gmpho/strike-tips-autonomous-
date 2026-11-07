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


def _first_env(*names: str) -> str:
    """First non-empty env var from a list of accepted names.

    The same Supabase project is configured under different names depending on
    the runtime: Modal secrets use SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY,
    while the repo's .env (shared with the Vite HUD) only defines the VITE_*
    aliases. Without the fallbacks, every JWT lookup fails inside Docker and
    the API answers "sign in" to a punter who is already signed in.
    """
    for name in names:
        val = os.getenv(name, "")
        if val:
            return val
    raise RuntimeError(
        f"none of {', '.join(names)} is set — cannot build Supabase client"
    )


def _require_env(name: str) -> str:
    val = os.getenv(name, "")
    if not val:
        raise RuntimeError(f"{name} is not set — cannot build Supabase client")
    return val


_URL_VARS = ("SUPABASE_URL", "VITE_SUPABASE_URL", "SUPABASE_PROJECT_URL")
_ANON_VARS = (
    "SUPABASE_PUBLISHABLE_KEY",
    "VITE_SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
    "VITE_SUPABASE_ANON_KEY",
)


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
    return _create(_first_env(*_URL_VARS), _require_env("SUPABASE_SERVICE_ROLE_KEY"))


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
    url = _first_env(*_URL_VARS)
    key = _first_env(*_ANON_VARS)
    client = create_client(url, key)
    client.postgrest.auth(access_token)
    return client
