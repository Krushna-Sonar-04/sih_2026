"""Explicit live Telegram credential test.

    cd backend && python scripts/test_telegram_connection.py

Loads the server-side environment, calls the official Bot API (getMe, then
getChat for the configured source) and prints a safe status. The bot token is
never printed - only a masked identifier. Normal `pytest` runs never perform
live network calls; this script is the deliberate way to do it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.registry import get_adapter  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    adapter = get_adapter("Telegram")
    assert adapter is not None

    print("DRISHTI - Telegram connection test")
    print("-" * 46)

    if not settings.telegram_bot_token:
        print("Telegram configuration : NOT CONFIGURED")
        print("Overall status         : NOT CONFIGURED")
        print("\nSet TELEGRAM_BOT_TOKEN (and TELEGRAM_CHANNEL_ID) in backend/.env, then run this again.")
        print("Demo Mode remains fully available without any credentials.")
        return 1

    print("Telegram configuration : FOUND")
    result = adapter.test_connection()
    print(f"Masked identifier      : {result.identifier}")
    print(f"Bot authentication     : {'SUCCESS' if result.authenticated else 'FAILED'}")
    if result.account:
        print(f"Bot account            : {result.account}")
    source_state = (
        "ACCESSIBLE" if result.source_reachable
        else "NOT CONFIGURED" if not settings.telegram_channel_id
        else "NOT ACCESSIBLE"
    )
    print(f"Configured source      : {source_state}")
    if result.source_name:
        print(f"Source name            : {result.source_name}")
    if result.last_message_time:
        print(f"Last message time      : {result.last_message_time.isoformat()}")

    ok = result.status == "Connected" and result.authenticated and result.source_reachable
    print(f"Overall status         : {'CONNECTED' if ok else result.status.upper()}")
    if result.error:
        print(f"Detail                 : {result.error}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
