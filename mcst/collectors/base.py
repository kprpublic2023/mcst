"""수집기 베이스 클래스.

각 플랫폼 수집기는 다음을 따릅니다.
  1) API 키가 있으면 공식 API 경로 (`_fetch_api`)
  2) 없으면 공개 페이지 폴백 (`_fetch_public`)
  3) 둘 다 실패하면 status=missing 으로 빈 스냅샷
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

from ..config import Settings
from ..storage import Snapshot

log = logging.getLogger(__name__)


@dataclass
class CollectResult:
    snapshot: Snapshot
    ok: bool
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BaseCollector:
    platform: str = ""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.user_agent

    # ----- public ---------------------------------------------------------
    def collect(self, org: dict[str, Any]) -> CollectResult:
        handle = (org.get("accounts") or {}).get(self.platform, "") or ""
        snap = Snapshot(
            org_id=org["id"],
            category=org["category"],
            platform=self.platform,
            handle=handle,
        )
        if not handle:
            return CollectResult(snap, ok=False, error="no_handle")

        try:
            if self._has_api():
                snap = self._fetch_api(org, handle, snap)
                snap.source = "api"
            else:
                snap = self._fetch_public(org, handle, snap)
                snap.source = "scrape"
            return CollectResult(snap, ok=True)
        except NotImplementedError as e:
            return CollectResult(snap, ok=False, error=str(e))
        except Exception as e:  # pragma: no cover - 외부 IO
            log.warning("collect failed: %s/%s -> %s", self.platform, org["id"], e)
            return CollectResult(snap, ok=False, error=str(e))

    # ----- to override ----------------------------------------------------
    def _has_api(self) -> bool:
        return False

    def _fetch_api(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        raise NotImplementedError("api_not_configured")

    def _fetch_public(self, org: dict[str, Any], handle: str, snap: Snapshot) -> Snapshot:
        raise NotImplementedError("public_fallback_unavailable")

    # ----- helpers --------------------------------------------------------
    def _get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.settings.request_timeout)
        return self.session.get(url, **kwargs)
