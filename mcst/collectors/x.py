"""X(Twitter) 수집기.

- API: v2 (Bearer Token 필요, 유료 등급)
- 폴백: nitter 미러를 시도 (가용성 변동 큼)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import BaseCollector, Snapshot

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
]


class XCollector(BaseCollector):
    platform = "x"

    def _has_api(self) -> bool:
        return bool(self.settings.x_bearer_token)

    def _fetch_api(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        token = self.settings.x_bearer_token
        username = handle.lstrip("@")
        headers = {"Authorization": f"Bearer {token}"}
        r = self._get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            params={"user.fields": "public_metrics,created_at"},
            headers=headers,
        )
        r.raise_for_status()
        u = r.json().get("data") or {}
        if not u:
            raise RuntimeError("user_not_found")
        m = u.get("public_metrics", {})
        snap.followers = m.get("followers_count")
        snap.posts_total = m.get("tweet_count")

        r2 = self._get(
            f"https://api.twitter.com/2/users/{u['id']}/tweets",
            params={"max_results": 100,
                    "tweet.fields": "created_at,public_metrics"},
            headers=headers,
        )
        if r2.ok:
            tweets = r2.json().get("data") or []
            self._fill_recent(snap, tweets)
        snap.raw = {"user": u}
        return snap

    def _fill_recent(self, snap: Snapshot, tweets: list[dict[str, Any]]):
        if not tweets:
            return
        now = datetime.now(timezone.utc)
        d30 = now - timedelta(days=30)
        d90 = now - timedelta(days=90)
        last = None
        cnt30 = cnt90 = 0
        likes = retweets = replies = 0
        n = 0
        for t in tweets:
            ct = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
            if last is None or ct > last:
                last = ct
            if ct >= d30:
                cnt30 += 1
            if ct >= d90:
                cnt90 += 1
            pm = t.get("public_metrics", {})
            likes += pm.get("like_count", 0)
            retweets += pm.get("retweet_count", 0)
            replies += pm.get("reply_count", 0)
            n += 1
        snap.posts_30d = cnt30
        snap.posts_90d = cnt90
        snap.last_post_at = last.isoformat() if last else None
        snap.avg_likes = likes / n
        snap.avg_comments = replies / n
        snap.avg_views = retweets / n  # X는 view보다 retweet을 인게이지 신호로 채택
        if snap.followers:
            snap.engagement_rate = (likes + retweets + replies) / n / snap.followers

    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        username = handle.lstrip("@")
        last_err: Exception | None = None
        for base in NITTER_INSTANCES:
            try:
                r = self._get(f"{base}/{username}")
                if not r.ok:
                    continue
                html = r.text
                fol = re.search(r"Followers</span>\s*<span[^>]*>([\d,\.]+)", html)
                tweets = re.search(r"Tweets</span>\s*<span[^>]*>([\d,\.]+)", html)
                if fol:
                    snap.followers = int(fol.group(1).replace(",", "").replace(".", ""))
                if tweets:
                    snap.posts_total = int(tweets.group(1).replace(",", "").replace(".", ""))
                snap.raw = {"url": f"{base}/{username}"}
                return snap
            except Exception as e:  # pragma: no cover
                last_err = e
        raise RuntimeError(f"nitter_unavailable: {last_err}")
