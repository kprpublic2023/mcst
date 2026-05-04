"""data/known_handles.yaml 의 큐레이션 핸들을 gov_orgs.yaml 로 일괄 적용.

기본 동작은 dry-run. --apply 로 실제 반영.
기존 사람이 채운 값(공란이 아닌 항목)은 절대 덮어쓰지 않습니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcst.config import PLATFORMS, SEED_FILE  # noqa: E402

KNOWN_FILE = ROOT / "data" / "known_handles.yaml"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--min-confidence", choices=["low", "medium", "high"],
                   default="low",
                   help="이 신뢰도 이상만 반영 (기본 low = 전체)")
    args = p.parse_args()

    rank = {"low": 0, "medium": 1, "high": 2}
    threshold = rank[args.min_confidence]

    raw = yaml.safe_load(SEED_FILE.read_text(encoding="utf-8"))
    known = yaml.safe_load(KNOWN_FILE.read_text(encoding="utf-8"))

    changed = 0
    skipped = 0
    for entries in raw.values():
        for entry in entries or []:
            org_id = entry["id"]
            if org_id not in known:
                continue
            k = known[org_id]
            if rank.get(k.get("confidence", "low"), 0) < threshold:
                skipped += 1
                continue
            accounts = entry.setdefault("accounts", {})
            for platform in PLATFORMS:
                if accounts.get(platform):
                    continue  # 사람이 채운 값 보존
                v = (k.get("accounts") or {}).get(platform)
                if v:
                    accounts[platform] = v
                    changed += 1
                    print(f"  + {org_id}.{platform} = {v}")

    print(f"\n채울 항목: {changed}, 신뢰도로 스킵된 기관: {skipped}")
    if args.apply:
        SEED_FILE.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        print(f"YAML 갱신 -> {SEED_FILE}")
    else:
        print("(dry-run) --apply 로 실제 반영")


if __name__ == "__main__":
    main()
