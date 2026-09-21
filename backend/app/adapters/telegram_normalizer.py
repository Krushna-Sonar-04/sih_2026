"""CommonTelegramNormalizer.

Both the Bot API path and the MTProto path produce the same canonical DRISHTI
post through this single normalizer, so storage and analytics never need to
know which Telegram ingestion path produced a record.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .base import NormalizedPost

MENTION_RE = re.compile(r"@([A-Za-z0-9_]{3,})")
HASHTAG_RE = re.compile(r"#(\w+)")

PLATFORM = "Telegram"


def _aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


class CommonTelegramNormalizer:
    """Shared normalization for every Telegram ingestion path."""

    @staticmethod
    def from_bot_update(raw: dict[str, Any]) -> NormalizedPost:
        message = raw.get("message") or raw.get("channel_post") or raw.get("edited_message") or {}
        chat = message.get("chat", {}) or {}
        sender = message.get("from", {}) or {}
        username = sender.get("username") or chat.get("username") or str(chat.get("id", "telegram-channel"))
        display = chat.get("title") or sender.get("first_name") or username
        text = message.get("text") or message.get("caption") or ""
        event_time = _aware(message.get("date")) or datetime.now(timezone.utc)

        relationships: list[dict[str, Any]] = []
        forward = message.get("forward_from_chat") or message.get("forward_from")
        repost_of = None
        if forward:
            target = forward.get("username") or str(forward.get("id", ""))
            if target:
                relationships.append({"type": "forward", "target": f"@{str(target).lstrip('@')}"})
                repost_of = str(target)
        reply = (message.get("reply_to_message") or {}).get("message_id")
        if reply:
            relationships.append({"type": "reply", "target_post": str(reply)})

        mentions = [f"@{m}" for m in MENTION_RE.findall(text)]
        for mention in mentions:
            relationships.append({"type": "mention", "target": mention})

        message_id = message.get("message_id")
        source_url = None
        if chat.get("username") and message_id:
            source_url = f"https://t.me/{chat['username']}/{message_id}"

        return NormalizedPost(
            platform=PLATFORM,
            external_id=str(message_id or raw.get("update_id") or ""),
            account_username=f"@{str(username).lstrip('@')}",
            account_display_name=str(display),
            text=text,
            event_time=event_time,
            engagement=int(message.get("views") or 0),
            language=str(sender.get("language_code") or "en"),
            relationships=relationships,
            reply_to=str(reply) if reply else None,
            repost_of=repost_of,
            mentions=mentions,
            hashtags=[f"#{h}" for h in HASHTAG_RE.findall(text)],
            source_url=source_url,
            raw_reference=f"telegram:update:{raw.get('update_id', message_id)}",
        )

    @staticmethod
    def from_mtproto_message(raw: dict[str, Any]) -> NormalizedPost:
        """Normalize a Telethon-style message dict into the same canonical post."""
        channel = str(raw.get("channel") or raw.get("peer") or "telegram-channel").lstrip("@")
        text = str(raw.get("message") or raw.get("text") or "")
        event_time = _aware(raw.get("date")) or datetime.now(timezone.utc)
        mentions = [f"@{m}" for m in MENTION_RE.findall(text)]
        relationships = [{"type": "mention", "target": m} for m in mentions]
        fwd = raw.get("fwd_from")
        if fwd:
            relationships.append({"type": "forward", "target": f"@{str(fwd).lstrip('@')}"})
        message_id = raw.get("id")
        return NormalizedPost(
            platform=PLATFORM,
            external_id=str(message_id or ""),
            account_username=f"@{channel}",
            account_display_name=str(raw.get("channel_title") or channel),
            text=text,
            event_time=event_time,
            engagement=int(raw.get("views") or 0),
            language=str(raw.get("language") or "en"),
            relationships=relationships,
            reply_to=str(raw["reply_to"]) if raw.get("reply_to") else None,
            repost_of=str(fwd) if fwd else None,
            mentions=mentions,
            hashtags=[f"#{h}" for h in HASHTAG_RE.findall(text)],
            source_url=f"https://t.me/{channel}/{message_id}" if message_id else None,
            raw_reference=f"telegram:mtproto:{message_id}",
        )
