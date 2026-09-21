"""Adapter registry: the only place the application resolves a platform.

Adapter isolation is structural - each platform is resolved and executed
independently, so one failing connector never affects another.
"""
from __future__ import annotations

from .base import AdapterHealth, ConnectionTest, PlannedAdapter, PlatformAdapter
from .telegram_bot import TelegramBotAdapter
from .telegram_mtproto import TelegramMTProtoAdapter
from .x_adapter import XAdapter, XConnectionTester

_x = XAdapter()
_telegram = TelegramBotAdapter()
_telegram_mtproto = TelegramMTProtoAdapter()
_x_tester = XConnectionTester(_x)

ADAPTERS: dict[str, PlatformAdapter] = {
    "X": _x,
    "Telegram": _telegram,
    "Instagram": PlannedAdapter("Instagram"),
    "Facebook": PlannedAdapter("Facebook"),
    "Reddit": PlannedAdapter("Reddit"),
    "YouTube": PlannedAdapter("YouTube"),
}

PLATFORM_PRIORITY = ["Telegram", "X", "Instagram", "Facebook", "Reddit", "YouTube"]


def get_adapter(platform: str) -> PlatformAdapter | None:
    return ADAPTERS.get(platform)


def get_telegram_history_adapter() -> TelegramMTProtoAdapter:
    return _telegram_mtproto


def test_connection(platform: str) -> ConnectionTest:
    """Honest connector test - never fabricates a successful connection."""
    if platform == "X":
        return _x_tester.test()
    adapter = get_adapter(platform)
    if adapter is None:
        return ConnectionTest(platform=platform, status="Unavailable", error="No adapter registered.")
    return adapter.test_connection()


def adapter_health(demo_mode: bool = True) -> list[AdapterHealth]:
    results: list[AdapterHealth] = []
    for platform in PLATFORM_PRIORITY:
        adapter = ADAPTERS[platform]
        try:
            health = adapter.health()
        except Exception as exc:  # isolation: one adapter can never break the list
            health = AdapterHealth(platform=platform, status="Error", detail=str(exc)[:160])
        if demo_mode and health.status == "Not configured" and platform in ("X", "Telegram"):
            health.detail = f"{health.detail} Serving deterministic demo records for {platform}."
        results.append(health)
    results.append(_telegram_mtproto.health())
    return results
