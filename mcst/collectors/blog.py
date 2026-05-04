"""블로그 수집기 (네이버/티스토리/자체 블로그 RSS 기반).

- 입력: 블로그 홈 URL (예: https://blog.naver.com/<id> 또는 https://<id>.tistory.com)
- 동작: RSS 피드 위치를 추정하여 feedparser로 게시 빈도/최근 글 시점을 산출.
- 팔로워/구독자: 블로그 종류에 따라 미공개. 운영 활성도 위주로 측정.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import BaseCollector, Snapshot


class BlogCollector(BaseCollector):
    platform = "blog"

    def _has_api(self) -> bool:
        return False  # 공통 RSS 폴백만 사용 (네이버 검색 API는 별도)

    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        try:
            import feedparser  # 지연 임포트 — 시스템에 따라 선택 설치
        except ImportError as e:  # pragma: no cover
            raise NotImplementedError(
                "feedparser 미설치. `pip install feedparser` 후 다시 시도해 주세요."
            ) from e
        feed_url = self._guess_feed_url(handle)
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            # blog 홈 자체를 RSS로 가정해 한번 더 시도
            feed = feedparser.parse(handle)
            if not feed.entries:
                raise RuntimeError(f"feed_unavailable: {feed_url}")

        entries = feed.entries[:50]
        snap.posts_total = len(entries)
        now = datetime.now(timezone.utc)
        d30 = now - timedelta(days=30)
        d90 = now - timedelta(days=90)
        last = None
        cnt30 = cnt90 = 0
        for e in entries:
            tm = e.get("published_parsed") or e.get("updated_parsed")
            if not tm:
                continue
            t = datetime(*tm[:6], tzinfo=timezone.utc)
            if last is None or t > last:
                last = t
            if t >= d30:
                cnt30 += 1
            if t >= d90:
                cnt90 += 1
        snap.posts_30d = cnt30
        snap.posts_90d = cnt90
        snap.last_post_at = last.isoformat() if last else None
        snap.raw = {"feed_url": feed_url, "title": getattr(feed.feed, "title", "")}
        return snap

    @staticmethod
    def _guess_feed_url(url: str) -> str:
        url = url.rstrip("/")
        if "blog.naver.com" in url:
            blog_id = url.rsplit("/", 1)[-1]
            return f"https://rss.blog.naver.com/{blog_id}.xml"
        if "tistory.com" in url:
            return f"{url}/rss"
        if "brunch.co.kr" in url:
            user = url.rsplit("/", 1)[-1].lstrip("@")
            return f"https://brunch.co.kr/api/feeds/@{user}.rss"
        # 기본: /rss, /feed 차례로 시도하지 않고 단일 추정만 반환
        return f"{url}/rss"
