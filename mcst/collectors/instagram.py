"""Instagram 수집기.

- API: Meta Graph API (Instagram Business Account 연결 토큰 필요)
- 폴백: 공개 프로필 페이지 og:description 파싱 (게시물·팔로워 수)
        ※ Instagram은 비로그인 접근을 점차 차단 중이라 실패할 수 있습니다.
"""
from __future__ import annotations

import re
from typing import Any

from .base import BaseCollector, Snapshot


class InstagramCollector(BaseCollector):
    platform = "instagram"

    def _has_api(self) -> bool:
        return bool(self.settings.meta_graph_token)

    def _fetch_api(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        # 사용자가 Business Account ID 매핑 테이블을 별도로 제공해야 정확합니다.
        # 여기서는 username으로 비즈니스 발견(business_discovery)을 시도합니다.
        token = self.settings.meta_graph_token
        username = handle.lstrip("@")
        # business_discovery는 페이지 owner의 IG Business User ID 가 필요합니다.
        # 토큰 owner의 ig_user_id를 환경변수 META_IG_USER_ID 로 전달하거나,
        # 그렇지 않다면 NotImplemented 처리.
        import os
        ig_user_id = os.getenv("META_IG_USER_ID", "")
        if not ig_user_id:
            raise NotImplementedError("META_IG_USER_ID is required for business_discovery")
        url = f"https://graph.facebook.com/v19.0/{ig_user_id}"
        fields = (
            f"business_discovery.username({username})"
            "{followers_count,media_count,media.limit(25){like_count,comments_count,timestamp}}"
        )
        r = self._get(url, params={"fields": fields, "access_token": token})
        r.raise_for_status()
        data = r.json().get("business_discovery") or {}
        snap.followers = data.get("followers_count")
        snap.posts_total = data.get("media_count")
        media = (data.get("media") or {}).get("data") or []
        if media:
            likes = sum(m.get("like_count", 0) for m in media)
            comments = sum(m.get("comments_count", 0) for m in media)
            n = len(media)
            snap.avg_likes = likes / n
            snap.avg_comments = comments / n
            if snap.followers:
                snap.engagement_rate = (likes + comments) / n / snap.followers
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            d30 = now - timedelta(days=30)
            d90 = now - timedelta(days=90)
            cnt30 = cnt90 = 0
            last = None
            for m in media:
                t = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                if last is None or t > last:
                    last = t
                if t >= d30:
                    cnt30 += 1
                if t >= d90:
                    cnt90 += 1
            snap.posts_30d = cnt30
            snap.posts_90d = cnt90
            snap.last_post_at = last.isoformat() if last else None
        snap.raw = data
        return snap

    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        username = handle.lstrip("@")
        url = f"https://www.instagram.com/{username}/"
        r = self._get(url)
        r.raise_for_status()
        html = r.text
        # og:description: "1,234 Followers, 56 Following, 78 Posts - ..."
        m = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if m:
            text = m.group(1)
            mf = re.search(r"([\d,\.]+)\s*Followers", text)
            mp = re.search(r"([\d,\.]+)\s*Posts", text)
            if mf:
                snap.followers = int(mf.group(1).replace(",", "").replace(".", ""))
            if mp:
                snap.posts_total = int(mp.group(1).replace(",", "").replace(".", ""))
        snap.raw = {"url": url}
        return snap
