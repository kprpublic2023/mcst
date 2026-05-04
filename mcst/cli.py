"""CLI: 수집 / 리포트 생성 / 데모 시드.

사용 예:
  python -m mcst.cli collect             # 시드의 모든 기관·플랫폼 수집
  python -m mcst.cli collect --platform youtube
  python -m mcst.cli report --out reports/output
  python -m mcst.cli demo --weeks 8      # 8주치 데모 트렌드 데이터 시드
"""
from __future__ import annotations

import argparse
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings, load_orgs, PLATFORMS
from .collectors import REGISTRY
from .reports import render_html, render_pdf, write_csv_bundle
from .storage import Snapshot, SnapshotStore

log = logging.getLogger("mcst")


def cmd_collect(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    store = SnapshotStore(settings.db_path)
    orgs = load_orgs()
    platforms = [args.platform] if args.platform else list(PLATFORMS)

    snapshots: list[Snapshot] = []
    summary = {p: {"ok": 0, "fail": 0, "skip": 0} for p in platforms}
    for p in platforms:
        coll = REGISTRY[p](settings)
        for org in orgs:
            res = coll.collect(org)
            if res.ok:
                snapshots.append(res.snapshot)
                summary[p]["ok"] += 1
            elif res.error == "no_handle":
                summary[p]["skip"] += 1
            else:
                summary[p]["fail"] += 1
                log.info("[%s/%s] failed: %s", p, org["id"], res.error)
    n = store.insert_many(snapshots)
    print(f"saved {n} snapshots")
    for p, s in summary.items():
        print(f"  {p:>9}: ok={s['ok']} fail={s['fail']} skip={s['skip']}")


def cmd_report(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    store = SnapshotStore(settings.db_path)
    latest = store.latest()
    history = store.all()
    if not latest:
        print("스냅샷이 없습니다. 먼저 `python -m mcst.cli collect` 또는 `demo`를 실행해 주세요.")
        return
    out = Path(args.out)
    paths = write_csv_bundle(latest, history, out)
    html = render_html(latest, history)
    html_path = out / "report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"CSV bundle: {out}")
    for k, v in paths.items():
        print(f"  - {k}: {v.name}")
    print(f"HTML: {html_path}")
    if args.pdf:
        try:
            pdf_path = render_pdf(html, out / "report.pdf")
            print(f"PDF: {pdf_path}")
        except Exception as e:
            print(f"PDF 생성 실패: {e}")


def cmd_demo(args: argparse.Namespace) -> None:
    """실 API 키 없이 대시보드를 점검할 수 있도록 가상의 트렌드 데이터를 시드."""
    settings = Settings.from_env()
    store = SnapshotStore(settings.db_path)
    orgs = load_orgs()
    rng = random.Random(args.seed)

    weeks = args.weeks
    end = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    snaps: list[Snapshot] = []
    for org in orgs:
        # 시드 YAML에 등록된(=비어있지 않은) 핸들만 데모 대상
        accounts = org.get("accounts") or {}
        registered = [p for p in PLATFORMS if (accounts.get(p) or "").strip()]
        if not registered:
            continue
        base_followers = {p: rng.randint(500, 200_000) for p in registered}
        growth = {p: rng.uniform(-0.005, 0.02) for p in registered}  # 주 단위
        for w in range(weeks):
            captured = end - timedelta(weeks=(weeks - 1 - w))
            for p in registered:
                followers = int(base_followers[p] * ((1 + growth[p]) ** w))
                posts_30d = max(0, int(rng.gauss(8, 4)))
                posts_90d = posts_30d + max(0, int(rng.gauss(20, 8)))
                avg_likes = max(0, rng.gauss(40, 20))
                avg_comments = max(0, rng.gauss(5, 3))
                er = (avg_likes + avg_comments) / max(followers, 1)
                last_post = captured - timedelta(days=rng.randint(0, 21))
                snaps.append(Snapshot(
                    org_id=org["id"], category=org["category"], platform=p,
                    handle=accounts[p],
                    captured_at=captured.isoformat(timespec="seconds"),
                    followers=followers,
                    posts_total=posts_90d * 5 + rng.randint(0, 200),
                    posts_30d=posts_30d, posts_90d=posts_90d,
                    last_post_at=last_post.isoformat(timespec="seconds"),
                    avg_views=rng.uniform(100, 5000),
                    avg_likes=avg_likes,
                    avg_comments=avg_comments,
                    engagement_rate=er,
                    source="demo",
                    raw={"demo": True},
                ))
    n = store.insert_many(snaps)
    print(f"demo: {n} snapshots seeded across {weeks} weeks for {len(orgs)} orgs")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("mcst")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("collect", help="시드 기준으로 수집 1회 실행")
    pc.add_argument("--platform", choices=PLATFORMS)
    pc.set_defaults(func=cmd_collect)

    pr = sub.add_parser("report", help="CSV/HTML(/PDF) 리포트 생성")
    pr.add_argument("--out", default="reports/output")
    pr.add_argument("--pdf", action="store_true")
    pr.set_defaults(func=cmd_report)

    pd_ = sub.add_parser("demo", help="API 키 없이 대시보드 동작 확인용 데모 데이터 시드")
    pd_.add_argument("--weeks", type=int, default=8)
    pd_.add_argument("--seed", type=int, default=42)
    pd_.set_defaults(func=cmd_demo)

    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
