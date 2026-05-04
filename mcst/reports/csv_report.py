"""CSV 리포트 묶음 출력."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..analysis import (
    build_dataframe,
    platform_summary,
    category_summary,
    ranking,
    growth_table,
)


def write_csv_bundle(latest_snapshots: list[dict], history: list[dict],
                     out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_dataframe(latest_snapshots)
    hist = pd.DataFrame(history) if history else pd.DataFrame()

    paths: dict[str, Path] = {}
    paths["latest"] = out_dir / "latest_snapshots.csv"
    df.to_csv(paths["latest"], index=False, encoding="utf-8-sig")

    paths["platform_summary"] = out_dir / "platform_summary.csv"
    platform_summary(df).to_csv(paths["platform_summary"], index=False, encoding="utf-8-sig")

    paths["category_summary"] = out_dir / "category_summary.csv"
    category_summary(df).to_csv(paths["category_summary"], index=False, encoding="utf-8-sig")

    paths["ranking_activity"] = out_dir / "ranking_activity.csv"
    ranking(df, by="activity_score", top_n=50).to_csv(
        paths["ranking_activity"], index=False, encoding="utf-8-sig")

    paths["ranking_followers"] = out_dir / "ranking_followers.csv"
    ranking(df, by="followers", top_n=50).to_csv(
        paths["ranking_followers"], index=False, encoding="utf-8-sig")

    if not hist.empty:
        paths["growth_30d"] = out_dir / "growth_30d.csv"
        growth_table(hist, window_days=30).to_csv(
            paths["growth_30d"], index=False, encoding="utf-8-sig")

    return paths
