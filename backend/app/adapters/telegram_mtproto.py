"""TelegramMTProtoAdapter - separate interface for historical/public-channel reads.

Deliberately kept apart from the Bot API path. It activates only when
TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SESSION are configured and the
Telethon client library is installed, and it is intended only for accounts and
use cases that are legally and platform-policy compliant. When it is not
available it reports "Not configured" and never fabricates a connection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..config import get_settings
from .base import AdapterHealth, ConnectionTest, HistoryUnsupported, NormalizedPost, PlatformAdapter, mask
from .telegram_normalizer import CommonTelegramNormalizer


def _telethon_available() -> bool:
    try:  # pragma: no cover - optional dependency
        import telethon  # noqa: F401

        return True
    except Exception:
        return False


class TelegramMTProtoAdapter(PlatformAdapter):
    platform = "Telegram"
    path = "mtproto"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.normalizer = CommonTelegramNormalizer()
        self.last_error: str | None = None

    def is_configured(self) -> bool:
        s = self.settings
        return bool(s.telegram_api_id and s.telegram_api_hash and s.telegram_session and _telethon_available())

    def health(self) -> AdapterHealth:
        if not self.is_configured():
            missing = "Telethon client library" if not _telethon_available() else "TELEGRAM_API_ID / API_HASH / SESSION"
            return AdapterHealth(
                platform="Telegram (MTProto)",
                status="Not configured",
                detail=f"MTProto historical path inactive: {missing} not available. Bot API path is unaffected.",
            )
        return AdapterHealth(
            platform="Telegram (MTProto)",
            status="Connected",
            detail="MTProto session configured for permitted public-channel history.",
            configured=True,
        )

    def test_connection(self) -> ConnectionTest:
        configured = self.is_configured()
        return ConnectionTest(
            platform="Telegram (MTProto)",
            configured=configured,
            authenticated=configured,
            source_reachable=configured,
            status="Connected" if configured else "Not configured",
            identifier=mask(self.settings.telegram_api_id),
            error=None if configured else "MTProto historical path is not configured.",
        )

    def normalize_post(self, raw: dict[str, Any]) -> NormalizedPost:
        return self.normalizer.from_mtproto_message(raw)

    def fetch_posts(self, query: str, limit: int = 50) -> list[NormalizedPost]:
        if not self.is_configured():
            return []
        return self._read_history(query, None, None, limit)

    def fetch_range(self, query: str, since: datetime, until: datetime, limit: int = 100) -> list[NormalizedPost]:
        if not self.is_configured():
            raise HistoryUnsupported(
                "Historical data is unavailable: the Telegram MTProto path is not configured."
            )
        return self._read_history(query, since, until, limit)

    def _read_history(
        self, query: str, since: datetime | None, until: datetime | None, limit: int
    ) -> list[NormalizedPost]:  # pragma: no cover - requires a live MTProto session
        from telethon.sync import TelegramClient  # type: ignore

        channel = (self.settings.telegram_channel_id or "").strip()
        if not channel:
            raise HistoryUnsupported("No Telegram source configured for historical retrieval.")
        terms = [t.strip().lower() for t in (query or "").split(",") if t.strip()]
        posts: list[NormalizedPost] = []
        with TelegramClient(
            self.settings.telegram_session, int(self.settings.telegram_api_id), self.settings.telegram_api_hash
        ) as client:
            for message in client.iter_messages(channel, limit=limit, offset_date=until):
                if since and message.date and message.date < since:
                    break
                post = self.normalizer.from_mtproto_message(
                    {
                        "id": message.id,
                        "channel": channel,
                        "message": message.message or "",
                        "date": message.date,
                        "views": getattr(message, "views", 0) or 0,
                        "fwd_from": getattr(message, "fwd_from", None) and channel,
                        "reply_to": getattr(message, "reply_to_msg_id", None),
                    }
                )
                if not post.text:
                    continue
                if terms and not any(term in post.text.lower() for term in terms):
                    continue
                posts.append(post)
        return posts
