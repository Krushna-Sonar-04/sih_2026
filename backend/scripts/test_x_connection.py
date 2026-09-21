"""Explicit live X credential test.

    cd backend && python scripts/test_x_connection.py

Loads the server-side environment and performs one authenticated request
against the official X API v2 recent-search endpoint. The bearer token is never
printed - only a masked identifier. Normal `pytest` runs never perform live
network calls; this script is the deliberate way to do it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.registry import get_adapter  # noqa: E402
from app.adapters.x_adapter import XConnectionTester  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    adapter = get_adapter("X")
    assert adapter is not None

    print("DRISHTI - X connection test")
    print("-" * 46)

    if not settings.x_bearer_token:
        print("X configuration        : NOT CONFIGURED")
        print("Overall status         : NOT CONFIGURED")
        print("\nSet X_BEARER_TOKEN in backend/.env, then run this again.")
        print("Demo Mode remains fully available without any credentials.")
        return 1

    print("X configuration        : FOUND")
    result = XConnectionTester(adapter).test()
    print(f"Masked identifier      : {result.identifier}")
    print(f"Authentication         : {'SUCCESS' if result.authenticated else 'FAILED'}")
    print(f"API accessible         : {'YES' if result.source_reachable else 'NO'}")
    if result.source_name:
        print(f"Endpoint               : {result.source_name}")
    if result.account:
        print(f"Access detail          : {result.account}")

    ok = result.status == "Connected" and result.authenticated
    print(f"Overall status         : {'CONNECTED' if ok else result.status.upper()}")
    if result.error:
        print(f"Detail                 : {result.error}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
