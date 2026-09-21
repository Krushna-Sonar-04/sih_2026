"""Common platform adapter interface.

Every adapter returns the same normalized post structure so that ingestion,
storage and analytics are identical for every platform.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal, TypeVar

AdapterStatus = Literal[
    "Connected",
    "Not configured",
    "Demo",
    "Planned",
    "Unavailable",
    "Unauthorized",
    "Rate limited",
    "Error",
]


@dataclass
class NormalizedPost:
    """The canonical DRISHTI post. Demo and live records share this shape."""

    platform: str
    external_id: str
    account_username: str
    account_display_name: str
    text: str
    event_time: datetime
    engagement: int = 0
    language: str = "en"
    topic: str = ""
    relationships: list[dict[str, Any]] = field(default_factory=list)
    source_mode: str = "live"
    reply_to: str | None = None
    repost_of: str | None = None
    mentions: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    source_url: str | None = None
    raw_reference: str | None = None


@dataclass
class AdapterHealth:
    platform: str
    status: AdapterStatus
    detail: str
    configured: bool = False
    last_fetch_at: datetime | None = None
    records_last_fetch: int = 0


@dataclass
class ConnectionTest:
    """Result of an explicit connector test. Never fabricates success."""

    platform: str
    configured: bool = False
    authenticated: bool = False
    source_reachable: bool = False
    status: AdapterStatus = "Not configured"
    last_message_time: datetime | None = None
    last_success: datetime | None = None
    identifier: str = ""  # masked identifier only - never a secret
    source_name: str = ""  # public channel/source name, never a credential
    account: str = ""  # provider-side account/app label where available
    error: str | None = None


def mask(value: str, keep: int = 4) -> str:
    """Mask a credential-derived identifier so it can be shown safely."""
    if not value:
        return ""
    tail = value[-keep:] if len(value) > keep else value
    return f"{'*' * 6}{tail}"


T = TypeVar("T")


def with_retries(call: Callable[[], T], attempts: int = 2, base_delay: float = 0.6) -> T:
    """Bounded retries with exponential backoff for transient failures only."""
    last: Exception | None = None
    for index in range(max(1, attempts)):
        try:
            return call()
        except PermanentAuthError:
            raise
        except Exception as exc:  # transient network/timeout failure
            last = exc
            if index + 1 < attempts:
                time.sleep(base_delay * (2**index))
    raise last if last else RuntimeError("Adapter call failed")


class PermanentAuthError(RuntimeError):
    """Authentication failures are never retried."""


class RateLimitError(RuntimeError):
    """Provider signalled a rate limit; the caller should back off, not retry hard."""


class PlatformAdapter(ABC):
    platform: str = "unknown"

    @abstractmethod
    def is_configured(self) -> bool:
        """True only when real credentials are present server-side."""

    @abstractmethod
    def health(self) -> AdapterHealth:
        """Never raises. Reports Connected / Not configured / Planned / Error."""

    @abstractmethod
    def fetch_posts(self, query: str, limit: int = 50) -> list[NormalizedPost]:
        """Fetch permitted recent posts. Returns [] when not configured."""

    def test_connection(self) -> ConnectionTest:
        health = self.health()
        return ConnectionTest(
            platform=self.platform,
            configured=self.is_configured(),
            authenticated=health.status == "Connected",
            source_reachable=health.status == "Connected",
            status=health.status,
            error=None if health.status == "Connected" else health.detail,
        )

    def fetch_range(self, query: str, since: datetime, until: datetime, limit: int = 100) -> list[NormalizedPost]:
        """Historical backfill. Adapters that cannot honour history must raise."""
        raise HistoryUnsupported(
            f"Historical data is unavailable for the {self.platform} connector with the configured access."
        )

    def normalize_post(self, raw: dict[str, Any]) -> NormalizedPost:  # pragma: no cover - overridden
        raise NotImplementedError


class HistoryUnsupported(RuntimeError):
    """Raised when a platform/access level cannot serve a historical window."""


class PlannedAdapter(PlatformAdapter):
    """Interface placeholder for platforms that are not implemented yet."""

    def __init__(self, platform: str) -> None:
        self.platform = platform

    def is_configured(self) -> bool:
        return False

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            platform=self.platform,
            status="Planned",
            detail=f"{self.platform} adapter interface reserved. Integration not implemented in this prototype.",
        )

    def fetch_posts(self, query: str, limit: int = 50) -> list[NormalizedPost]:
        return []

    def test_connection(self) -> ConnectionTest:
        return ConnectionTest(
            platform=self.platform,
            status="Planned",
            error=f"{self.platform} integration is planned. No connection is attempted.",
        )
