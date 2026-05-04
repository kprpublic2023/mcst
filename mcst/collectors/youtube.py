"""YouTube 수집기.

- API 모드: YouTube Data API v3
    채널 통계: subscriberCount, viewCount, videoCount
    최근 영상: search.list -> videos.list 통계
- 폴백 모드: 채널 페이지 메타태그 파싱 (불안정 — 구독자 수만 추정)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import BaseCollector, Snapshot


class YouTubeCollector(BaseCollector):
    platform = "youtube"

    API = "https://www.googleapis.com/youtube/v3"

    def _has_api(self) -> bool:
        return bool(self.settings.youtube_api_key)

    # -------- API ---------
    def _fetch_api(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        key = self.settings.youtube_api_key
        params: dict[str, Any] = {"part": "snippet,statistics,contentDetails", "key": key}
        if handle.startswith("@"):
            params["forHandle"] = handle
        elif handle.startswith("UC") and len(handle) == 24:
            params["id"] = handle
        else:
            params["forUsername"] = handle.lstrip("@")

        r = self._get(f"{self.API}/channels", params=params)
        r.raise_for_status()
        items = r.json().get("items") or []
        if not items:
            raise RuntimeError("channel_not_found")
        ch = items[0]
        stats = ch.get("statistics", {})
        snap.followers = int(stats.get("subscriberCount") or 0) or None
        snap.posts_total = int(stats.get("videoCount") or 0) or None

        uploads = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        recent: list[dict[str, Any]] = []
        if uploads:
            r2 = self._get(
                f"{self.API}/playlistItems",
                params={"part": "contentDetails,snippet", "playlistId": uploads,
                        "maxResults": 50, "key": key},
            )
            if r2.ok:
                recent = r2.json().get("items") or []

        if recent:
            video_ids = [it["contentDetails"]["videoId"] for it in recent]
            r3 = self._get(
                f"{self.API}/videos",
                params={"part": "statistics,snippet", "id": ",".join(video_ids), "key": key},
            )
            videos = r3.json().get("items") or [] if r3.ok else []
            self._fill_recent(snap, videos)

        snap.raw = {"channel": ch}
        return snap

    def _fill_recent(self, snap: Snapshot, videos: list[dict[str, Any]]) -> None:
        if not videos:
            return
        now = datetime.now(timezone.utc)
        d30 = now - timedelta(days=30)
        d90 = now - timedelta(days=90)
        last = None
        cnt30 = cnt90 = 0
        views = likes = comments = 0
        n = 0
        for v in videos:
            published = v["snippet"]["publishedAt"]
            t = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if last is None or t > last:
                last = t
            if t >= d30:
                cnt30 += 1
            if t >= d90:
                cnt90 += 1
            s = v.get("statistics", {})
            views += int(s.get("viewCount") or 0)
            likes += int(s.get("likeCount") or 0)
            comments += int(s.get("commentCount") or 0)
            n += 1
        snap.posts_30d = cnt30
        snap.posts_90d = cnt90
        snap.last_post_at = last.isoformat() if last else None
        if n:
            snap.avg_views = views / n
            snap.avg_likes = likes / n
            snap.avg_comments = comments / n
            if snap.followers:
                snap.engagement_rate = (likes + comments) / n / snap.followers

    # -------- public fallback ---------
    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        url = self._channel_url(handle)
        r = self._get(url, headers={"Accept-Language": "ko"})
        r.raise_for_status()
        html = r.text

        m = re.search(r'"subscriberCountText":\s*\{"simpleText":"([^"]+)"\}', html)
        if m:
            snap.followers = self._parse_count_kr(m.group(1))
        m2 = re.search(r'"videosCountText":\s*\{"runs":\[\{"text":"([^"]+)"\}', html)
        if m2:
            snap.posts_total = self._parse_count_kr(m2.group(1))
        snap.raw = {"url": url}
        return snap

    def _channel_url(self, handle: str) -> str:
        if handle.startswith("@"):
            return f"https://www.youtube.com/{handle}"
        if handle.startswith("UC"):
            return f"https://www.youtube.com/channel/{handle}"
        return f"https://www.youtube.com/@{handle.lstrip('@')}"

    @staticmethod
    def _parse_count_kr(s: str) -> int | None:
        s = s.replace(",", "").strip()
        m = re.match(r"([\d.]+)\s*(만|천|억|K|M|B)?", s)
        if not m:
            return None
        num = float(m.group(1))
        unit = m.group(2) or ""
        mult = {"": 1, "천": 1_000, "만": 10_000, "억": 100_000_000,
                "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        return int(num * mult.get(unit, 1))
