"""Facebook Page 수집기.

- API: Graph API (페이지 액세스 토큰 필요. 페이지 owner/admin 권한)
- 폴백: 페이지 og:title/about 페이지 일부 파싱 (제한적)
"""
from __future__ import annotations

import re
from typing import Any

from .base import BaseCollector, Snapshot


class FacebookCollector(BaseCollector):
    platform = "facebook"

    def _has_api(self) -> bool:
        return bool(self.settings.meta_graph_token)

    def _fetch_api(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        token = self.settings.meta_graph_token
        page = handle.lstrip("/")
        url = f"https://graph.facebook.com/v19.0/{page}"
        fields = "fan_count,followers_count,name,posts.limit(25){created_time,reactions.summary(total_count),comments.summary(total_count),shares}"
        r = self._get(url, params={"fields": fields, "access_token": token})
        r.raise_for_status()
        data = r.json()
        snap.followers = data.get("followers_count") or data.get("fan_count")
        posts = (data.get("posts") or {}).get("data") or []
        if posts:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            d30 = now - timedelta(days=30)
            d90 = now - timedelta(days=90)
            last = None
            cnt30 = cnt90 = 0
            reacts = comments = shares = 0
            n = 0
            for p in posts:
                t = datetime.fromisoformat(p["created_time"].replace("+0000", "+00:00"))
                if last is None or t > last:
                    last = t
                if t >= d30:
                    cnt30 += 1
                if t >= d90:
                    cnt90 += 1
                reacts += (p.get("reactions") or {}).get("summary", {}).get("total_count", 0)
                comments += (p.get("comments") or {}).get("summary", {}).get("total_count", 0)
                shares += (p.get("shares") or {}).get("count", 0)
                n += 1
            snap.posts_30d = cnt30
            snap.posts_90d = cnt90
            snap.posts_total = n
            snap.last_post_at = last.isoformat() if last else None
            snap.avg_likes = reacts / n
            snap.avg_comments = comments / n
            snap.avg_views = shares / n
            if snap.followers:
                snap.engagement_rate = (reacts + comments + shares) / n / snap.followers
        snap.raw = data
        return snap

    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        page = handle.lstrip("/")
        url = f"https://www.facebook.com/{page}/"
        r = self._get(url)
        r.raise_for_status()
        html = r.text
        # 비로그인 차단 페이지가 자주 반환됩니다. 가능한 신호만 추출.
        m = re.search(r'"follower_count":(\d+)', html)
        if m:
            snap.followers = int(m.group(1))
        snap.raw = {"url": url}
        return snap
