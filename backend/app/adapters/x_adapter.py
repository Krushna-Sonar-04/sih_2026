"""X (Twitter) ingestion adapter.

Uses the official X API v2 with a server-side bearer token. No scraping and no
platform-restriction bypass. Credentials are read from the environment only and
are never exposed to the frontend.

Architecture: XNormalizer (canonical post), XAdapter (retrieval),
XConnectionTester (honest connection state).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
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

API_ROOT = "https://api.x.com/2"
HASHTAG_RE = re.compile(r"#(\w+)")


class XNormalizer:
    """Turns an X API v2 tweet object into the canonical DRISHTI post."""

    platform = "X"

    def normalize(self, raw: dict[str, Any], users: dict[str, dict] | None = None) -> NormalizedPost:
        users = users or {}
        author = users.get(str(raw.get("author_id")), {})
        metrics = raw.get("public_metrics", {}) or {}
        try:
            event_time = datetime.fromisoformat(str(raw.get("created_at")).replace("Z", "+00:00"))
        except Exception:
            event_time = datetime.now(timezone.utc)

        relationships: list[dict[str, Any]] = []
        reply_to = repost_of = None
        for ref in raw.get("referenced_tweets", []) or []:
            kind = {"replied_to": "reply", "retweeted": "repost", "quoted": "mention"}.get(
                ref.get("type", ""), "mention"
            )
            relationships.append({"type": kind, "target_post": ref.get("id")})
            if kind == "reply":
                reply_to = str(ref.get("id"))
            if kind == "repost":
                repost_of = str(ref.get("id"))

        entities = raw.get("entities", {}) or {}
        mentions = [f"@{m.get('username')}" for m in entities.get("mentions", []) or [] if m.get("username")]
        for mention in mentions:
            relationships.append({"type": "mention", "target": mention})
        text = raw.get("text", "")
        hashtags = [f"#{t.get('tag')}" for t in entities.get("hashtags", []) or [] if t.get("tag")] or [
            f"#{h}" for h in HASHTAG_RE.findall(text)
        ]

        username = author.get("username", "unknown")
        tweet_id = str(raw.get("id", ""))
        return NormalizedPost(
            platform=self.platform,
            external_id=tweet_id,
            account_username=f"@{username}",
            account_display_name=author.get("name", username),
            text=text,
            event_time=event_time,
            engagement=int(
                metrics.get("like_count", 0)
                + metrics.get("retweet_count", 0)
                + metrics.get("reply_count", 0)
                + metrics.get("quote_count", 0)
            ),
            language=raw.get("lang", "en"),
            relationships=relationships,
            reply_to=reply_to,
            repost_of=repost_of,
            mentions=mentions,
            hashtags=hashtags,
            source_url=f"https://x.com/{username}/status/{tweet_id}" if tweet_id and username != "unknown" else None,
            raw_reference=f"x:tweet:{tweet_id}",
        )


class XAdapter(PlatformAdapter):
    platform = "X"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.normalizer = XNormalizer()
        self.last_fetch_at: datetime | None = None
        self.last_success: datetime | None = None
        self.records_last_fetch = 0
        self.last_error: str | None = None
        self.rate_limited_until: datetime | None = None

    def is_configured(self) -> bool:
        return bool(self.settings.x_bearer_token)

    def health(self) -> AdapterHealth:
        if not self.is_configured():
            return AdapterHealth(
                platform=self.platform, status="Not configured",
                detail="X connection not configured. Set X_BEARER_TOKEN to enable live retrieval.",
            )
        if self.rate_limited_until and self.rate_limited_until > datetime.now(timezone.utc):
            return AdapterHealth(
                platform=self.platform, status="Rate limited",
                detail="Rate limit reached. Retrying later.", configured=True,
                last_fetch_at=self.last_fetch_at,
            )
        if self.last_error:
            return AdapterHealth(
                platform=self.platform, status="Error", detail=self.last_error,
                configured=True, last_fetch_at=self.last_fetch_at,
            )
        return AdapterHealth(
            platform=self.platform, status="Connected",
            detail="Bearer token configured for X API v2 recent search.",
            configured=True, last_fetch_at=self.last_fetch_at, records_last_fetch=self.records_last_fetch,
        )

    def normalize_post(self, raw: dict[str, Any], users: dict[str, dict] | None = None) -> NormalizedPost:
        return self.normalizer.normalize(raw, users)

    # ----------------------------------------------------------------- requests
    def _search(self, params: dict[str, Any]) -> dict:
        def _do() -> dict:
            with httpx.Client(timeout=20.0) as client:
                res = client.get(
                    f"{API_ROOT}/tweets/search/recent",
                    headers={"Authorization": f"Bearer {self.settings.x_bearer_token}"},
                    params=params,
                )
            if res.status_code in (401, 403):
                raise PermanentAuthError("X authentication failed.")
            if res.status_code == 429:
                raise RateLimitError("Rate limit reached. Retrying later.")
            res.raise_for_status()
            return res.json()

        return with_retries(_do, attempts=self.settings.adapter_max_retries)

    def _query(self, query: str) -> str:
        terms = [t.strip() for t in (query or "").split(",") if t.strip()] or ["AI regulation"]
        return " OR ".join(f'"{t}"' for t in terms[:5]) + " -is:retweet"

    def _params(self, query: str, limit: int) -> dict[str, Any]:
        return {
            "query": self._query(query),
            "max_results": max(10, min(limit, 100)),
            "tweet.fields": "created_at,public_metrics,lang,entities,referenced_tweets,author_id",
            "expansions": "author_id",
            "user.fields": "username,name",
        }

    def fetch_posts(self, query: str, limit: int = 50) -> list[NormalizedPost]:
        if not self.is_configured():
            return []
        try:
            payload = self._search(self._params(query, limit))
            self.last_error = None
            self.rate_limited_until = None
        except RateLimitError as exc:
            self.rate_limited_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            self.last_error = str(exc)
            raise
        except PermanentAuthError as exc:
            self.last_error = str(exc)
            raise
        except Exception as exc:
            self.last_error = f"X fetch failed: {str(exc)[:140]}"
            return []

        users = {u["id"]: u for u in (payload.get("includes", {}) or {}).get("users", [])}
        posts = [self.normalizer.normalize(raw, users) for raw in payload.get("data", [])]
        self.last_fetch_at = datetime.now(timezone.utc)
        self.last_success = self.last_fetch_at
        self.records_last_fetch = len(posts)
        return posts

    def fetch_range(self, query: str, since: datetime, until: datetime, limit: int = 100) -> list[NormalizedPost]:
        """Recent search covers roughly the last seven days for standard access."""
        if not self.is_configured():
            raise HistoryUnsupported("Historical data is unavailable: X is not configured.")
        age_days = (datetime.now(timezone.utc) - since).days
        if age_days > 7:
            raise HistoryUnsupported(
                "Historical data is unavailable for this connector: X recent search covers about seven days "
                "with the configured access level."
            )
        params = self._params(query, limit)
        params["start_time"] = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        params["end_time"] = until.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = self._search(params)
        users = {u["id"]: u for u in (payload.get("includes", {}) or {}).get("users", [])}
        return [self.normalizer.normalize(raw, users) for raw in payload.get("data", [])]


class XConnectionTester:
    """Explicit connection test. Performs a real request only when configured."""

    def __init__(self, adapter: XAdapter) -> None:
        self.adapter = adapter

    def test(self) -> ConnectionTest:
        settings = self.adapter.settings
        result = ConnectionTest(
            platform="X",
            configured=self.adapter.is_configured(),
            identifier=mask(settings.x_bearer_token),
            last_success=self.adapter.last_success,
        )
        if not result.configured:
            result.status = "Not configured"
            result.error = "X_BEARER_TOKEN is not set in the backend environment."
            return result
        try:
            payload = self.adapter._search(self.adapter._params("AI regulation", 10))
            result.authenticated = True
            result.source_reachable = "data" in payload or "meta" in payload
            result.status = "Connected"
            result.source_name = "X API v2 recent search"
            returned = len(payload.get("data", []) or [])
            result.account = f"app-only access · {returned} record(s) returned"
        except PermanentAuthError as exc:
            result.status = "Unauthorized"
            result.error = str(exc)
        except RateLimitError as exc:
            result.authenticated = True
            result.status = "Rate limited"
            result.error = str(exc)
        except Exception as exc:
            result.status = "Unavailable"
            result.error = f"X API unreachable: {str(exc)[:140]}"
        return result
