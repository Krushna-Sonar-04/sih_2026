"""TelegramBotAdapter - official Bot API ingestion path.

Credentials come from the environment only (TELEGRAM_BOT_TOKEN,
TELEGRAM_CHANNEL_ID). Only updates the bot is permitted to receive are
processed; nothing is scraped and no platform restriction is bypassed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import get_settings
from .base import (
    AdapterHealth,
    ConnectionTest,
    HistoryUnsupported,
    NormalizedPost,
    PermanentAuthError,
    PlatformAdapter,
    RateLimitError,
    mask,
    with_retries,
)
from .telegram_normalizer import CommonTelegramNormalizer

API_ROOT = "https://api.telegram.org"

logger = logging.getLogger("drishti.telegram")


class TelegramBotAdapter(PlatformAdapter):
    platform = "Telegram"
    path = "bot-api"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.normalizer = CommonTelegramNormalizer()
        self.offset: int | None = None  # safe offset so updates are never re-ingested
        self.last_fetch_at: datetime | None = None
        self.last_success: datetime | None = None
        self.last_message_time: datetime | None = None
        self.records_last_fetch = 0
        self.skipped_updates = 0
        self.last_error: str | None = None

    # ------------------------------------------------------------------ state
    def is_configured(self) -> bool:
        return bool(self.settings.telegram_bot_token)

    def _call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> dict:
        def _do() -> dict:
            with httpx.Client(timeout=timeout) as client:
                res = client.get(
                    f"{API_ROOT}/bot{self.settings.telegram_bot_token}/{method}", params=params or {}
                )
            if res.status_code in (401, 403):
                raise PermanentAuthError(f"Telegram rejected the bot token (HTTP {res.status_code}).")
            if res.status_code == 429:
                raise RateLimitError("Telegram rate limit reached. Retrying later.")
            res.raise_for_status()
            return res.json()

        return with_retries(_do, attempts=self.settings.adapter_max_retries)

    def health(self) -> AdapterHealth:
        if not self.is_configured():
            return AdapterHealth(
                platform=self.platform,
                status="Not configured",
                detail="TELEGRAM_BOT_TOKEN is not set. Demo Mode remains available.",
            )
        if self.last_error:
            return AdapterHealth(
                platform=self.platform, status="Error", detail=self.last_error,
                configured=True, last_fetch_at=self.last_fetch_at,
            )
        try:
            payload = self._call("getMe", timeout=8.0)
            if payload.get("ok"):
                name = (payload.get("result") or {}).get("username", "bot")
                return AdapterHealth(
                    platform=self.platform, status="Connected", detail=f"Bot @{name} authorized.",
                    configured=True, last_fetch_at=self.last_fetch_at,
                    records_last_fetch=self.records_last_fetch,
                )
            return AdapterHealth(
                platform=self.platform, status="Unavailable",
                detail="Telegram did not confirm the bot identity.", configured=True,
            )
        except PermanentAuthError as exc:
            return AdapterHealth(platform=self.platform, status="Unauthorized", detail=str(exc), configured=True)
        except RateLimitError as exc:
            return AdapterHealth(platform=self.platform, status="Rate limited", detail=str(exc), configured=True)
        except Exception as exc:
            return AdapterHealth(
                platform=self.platform, status="Unavailable",
                detail=f"Telegram API unreachable: {str(exc)[:120]}", configured=True,
            )

    # ------------------------------------------------------------ connection test
    def test_connection(self) -> ConnectionTest:
        result = ConnectionTest(
            platform=self.platform,
            configured=self.is_configured(),
            identifier=mask(self.settings.telegram_bot_token),
            last_success=self.last_success,
        )
        if not result.configured:
            result.status = "Not configured"
            result.error = "TELEGRAM_BOT_TOKEN is not set in the backend environment."
            return result
        try:
            me = self._call("getMe", timeout=8.0)
            result.authenticated = bool(me.get("ok"))
            result.account = f"@{(me.get('result') or {}).get('username', '')}".rstrip("@")
        except PermanentAuthError as exc:
            result.status = "Invalid credentials"  # type: ignore[assignment]
            result.error = str(exc)
            return result
        except Exception as exc:
            result.status = "Unavailable"
            result.error = f"Telegram API unreachable: {str(exc)[:140]}"
            return result

        channel = (self.settings.telegram_channel_id or "").strip()
        if not channel:
            result.status = "Connected"
            result.source_reachable = False
            result.error = "Bot authenticated. TELEGRAM_CHANNEL_ID is not set, so no source is bound yet."
            return result
        try:
            chat = self._call("getChat", {"chat_id": channel}, timeout=8.0)
            if chat.get("ok"):
                info = chat.get("result") or {}
                result.source_reachable = True
                result.status = "Connected"
                result.source_name = str(info.get("title") or info.get("username") or channel)
                result.last_message_time = self.last_message_time
            else:
                result.status = "No accessible source"  # type: ignore[assignment]
                result.error = "Telegram is configured but the bot cannot access this source."
        except Exception as exc:
            result.status = "No accessible source"  # type: ignore[assignment]
            result.error = f"Telegram is configured but the bot cannot access this source: {str(exc)[:120]}"
        return result

    # ----------------------------------------------------------------- ingestion
    def normalize_post(self, raw: dict[str, Any]) -> NormalizedPost:
        return self.normalizer.from_bot_update(raw)

    def _matches(self, post: NormalizedPost, query: str) -> bool:
        channel = (self.settings.telegram_channel_id or "").strip()
        if channel and channel not in (post.account_username, post.account_display_name, channel):
            if channel.lstrip("@").lower() not in post.account_username.lstrip("@").lower():
                return False
        terms = [t.strip().lower() for t in (query or "").split(",") if t.strip()]
        if terms and not any(term in post.text.lower() for term in terms):
            return False
        return True

    def fetch_posts(self, query: str, limit: int = 50) -> list[NormalizedPost]:
        """Poll getUpdates with safe offset handling so updates are read once."""
        if not self.is_configured():
            return []
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "allowed_updates": '["message","channel_post"]',
            "timeout": 0,
        }
        if self.offset is not None:
            params["offset"] = self.offset
        try:
            updates = self._call("getUpdates", params).get("result", [])
            self.last_error = None
        except PermanentAuthError as exc:
            self.last_error = str(exc)
            raise
        except RateLimitError as exc:
            self.last_error = str(exc)
            raise
        except Exception as exc:
            self.last_error = f"Telegram fetch failed: {str(exc)[:140]}"
            return []

        posts: list[NormalizedPost] = []
        self.skipped_updates = 0
        for raw in updates:
            update_id = raw.get("update_id")
            # The offset advances for every update that was read, even when the
            # individual message fails: one bad message never replays a batch.
            if isinstance(update_id, int):
                self.offset = max(self.offset or 0, update_id + 1)
            try:
                post = self.normalize_post(raw)
            except Exception as exc:
                self.skipped_updates += 1
                logger.warning("Telegram update %s could not be normalized: %s", update_id, str(exc)[:160])
                continue
            if not post.text or not self._matches(post, query):
                continue
            posts.append(post)
            self.last_message_time = max(self.last_message_time or post.event_time, post.event_time)

        self.last_fetch_at = datetime.now(timezone.utc)
        self.last_success = self.last_fetch_at
        self.records_last_fetch = len(posts)
        return posts

    def fetch_range(self, query: str, since: datetime, until: datetime, limit: int = 100):
        raise HistoryUnsupported(
            "Historical data is unavailable through the Telegram Bot API. "
            "Bot updates only cover recent deliveries; configure the MTProto path for archive access."
        )
