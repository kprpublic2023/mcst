"""기관 홈페이지에서 SNS 링크를 자동 탐색해 시드 YAML을 채워주는 스크립트.

동작:
  1) data/gov_orgs.yaml 의 각 기관 homepage URL을 가져옴
  2) 페이지 HTML에서 youtube.com / instagram.com / twitter.com / x.com /
     facebook.com / blog.naver.com / tistory.com 링크를 추출
  3) 핸들 정규화 후 빈 항목만 채워 넣음 (기존 값 보존)
  4) 자동 탐색된 항목은 verified=false 로 유지

사용:
  python scripts/discover_handles.py            # dry-run (변경 없이 보기)
  python scripts/discover_handles.py --apply    # YAML에 반영
  python scripts/discover_handles.py --apply --org moef --org moe   # 일부만
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcst.config import PLATFORMS, SEED_FILE  # noqa: E402

log = logging.getLogger("discover")

UA = "MCST-SNS-Analyzer/0.1 (+homepage discovery)"
TIMEOUT = 12

PATTERNS = {
    "youtube": [
        re.compile(r"youtube\.com/(@[\w.\-]+)"),
        re.compile(r"youtube\.com/channel/(UC[\w\-]{22})"),
        re.compile(r"youtube\.com/user/([\w.\-]+)"),
        re.compile(r"youtube\.com/c/([\w.\-]+)"),
    ],
    "instagram": [
        re.compile(r"instagram\.com/([\w.\-]+)/?", re.I),
    ],
    "x": [
        re.compile(r"(?:twitter|x)\.com/([\w.\-]+)/?", re.I),
    ],
    "facebook": [
        re.compile(r"facebook\.com/([\w.\-]+)/?", re.I),
    ],
    "blog": [
        re.compile(r"(blog\.naver\.com/[\w.\-]+)", re.I),
        re.compile(r"([\w\-]+\.tistory\.com)", re.I),
        re.compile(r"(brunch\.co\.kr/@[\w.\-]+)", re.I),
    ],
}

# 기관 사이트가 외부 SNS로 안내할 때 자주 거치는 인터스티셜 도메인은 무시
IGNORED_HANDLES = {
    "instagram": {"explore", "accounts", "directory", "p", "reel", "stories"},
    "x": {"home", "search", "i", "intent", "share", "settings"},
    "facebook": {"sharer", "tr", "dialog", "login", "policies", "help",
                 "privacy", "terms", "pages", "groups", "watch"},
    "youtube": {"watch", "results", "playlist", "embed"},
}


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko"},
                         timeout=TIMEOUT, allow_redirects=True)
        if r.ok and "text/html" in r.headers.get("Content-Type", ""):
            return r.text
    except requests.RequestException as e:
        log.warning("fetch failed: %s -> %s", url, e)
    return None


def discover(html: str) -> dict[str, str]:
    """HTML 한 페이지에서 플랫폼별 첫 매칭값을 반환."""
    found: dict[str, str] = {}
    soup = BeautifulSoup(html, "html.parser")
    hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
    # iframe/script 안에 들어있는 경우도 종종 있어 raw HTML도 함께 검사
    blob = " ".join(hrefs) + " " + html

    for platform, patterns in PATTERNS.items():
        for pat in patterns:
            for m in pat.finditer(blob):
                handle = m.group(1).strip().rstrip(".")
                base = handle.split("/")[-1].lstrip("@")
                if base.lower() in IGNORED_HANDLES.get(platform, set()):
                    continue
                if platform == "blog":
                    found[platform] = "https://" + handle if not handle.startswith("http") else handle
                elif platform == "youtube" and m.re.pattern.startswith(r"youtube\.com/(@"):
                    found[platform] = handle  # @handle
                elif platform == "youtube" and "channel/" in pat.pattern:
                    found[platform] = handle  # UCxxxx
                else:
                    found[platform] = handle
                break
            if platform in found:
                break
    return found


def crawl_org(org: dict[str, Any]) -> dict[str, str]:
    homepage = (org.get("homepage") or "").strip()
    if not homepage:
        return {}
    html = fetch(homepage)
    if not html:
        return {}
    found = discover(html)
    # 자주 SNS 모음 페이지가 별도 URL인 경우(/sns, /share 등) 한번 더 시도
    if len(found) < 3:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() or "").strip().lower()
            if any(k in href.lower() or k in text for k in ("sns", "소셜", "social")):
                from urllib.parse import urljoin
                child_url = urljoin(homepage, href)
                child = fetch(child_url)
                if child:
                    extra = discover(child)
                    for k, v in extra.items():
                        found.setdefault(k, v)
                break
    return found


def merge_into_seed(updates: dict[str, dict[str, str]], apply: bool) -> int:
    raw = yaml.safe_load(SEED_FILE.read_text(encoding="utf-8"))
    changed = 0
    for category, entries in raw.items():
        for entry in entries or []:
            org_id = entry["id"]
            if org_id not in updates:
                continue
            accounts = entry.setdefault("accounts", {})
            for platform in PLATFORMS:
                if accounts.get(platform):
                    continue  # 사람이 채운 값은 보존
                if platform in updates[org_id]:
                    accounts[platform] = updates[org_id][platform]
                    changed += 1
    if apply:
        # 보기 좋게 dump
        SEED_FILE.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
    return changed


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="YAML에 실제로 기록")
    p.add_argument("--org", action="append", default=[],
                   help="특정 기관 ID만 처리 (반복 지정 가능)")
    p.add_argument("--delay", type=float, default=1.0, help="요청 간격(초)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    raw = yaml.safe_load(SEED_FILE.read_text(encoding="utf-8"))
    targets = []
    for entries in raw.values():
        for entry in entries or []:
            if args.org and entry["id"] not in args.org:
                continue
            targets.append(entry)

    log.info("대상 기관: %d", len(targets))
    updates: dict[str, dict[str, str]] = {}
    for i, org in enumerate(targets, 1):
        found = crawl_org(org)
        log.info("[%2d/%d] %-30s %s", i, len(targets), org["name_ko"],
                 ", ".join(f"{k}={v}" for k, v in found.items()) or "(없음)")
        if found:
            updates[org["id"]] = found
        time.sleep(args.delay)

    n = merge_into_seed(updates, apply=args.apply)
    if args.apply:
        log.info("\nYAML 업데이트: %d개 항목 채움 -> %s", n, SEED_FILE)
    else:
        log.info("\n(dry-run) 채워질 항목 수: %d. --apply 로 실제 반영하세요.", n)


if __name__ == "__main__":
    main()
