"""기관·플랫폼 간 비교/랭킹/성장률 산출."""
from __future__ import annotations

import pandas as pd


def platform_summary(df: pd.DataFrame) -> pd.DataFrame:
    """플랫폼별 운영현황 요약."""
    if df.empty:
        return df
    g = df.groupby("platform").agg(
        operating_orgs=("followers", lambda s: s.notna().sum()),
        total_orgs=("org_id", "nunique"),
        total_followers=("followers", "sum"),
        median_followers=("followers", "median"),
        avg_posts_30d=("posts_30d", "mean"),
        avg_engagement_rate=("engagement_rate", "mean"),
        avg_activity=("activity_score", "mean"),
    ).reset_index()
    g["operation_rate"] = (g["operating_orgs"] / g["total_orgs"]).round(3)
    return g


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """기관 분류(부/처/청/위원회)별 요약."""
    if df.empty:
        return df
    g = df.groupby(["category_label", "platform"]).agg(
        operating_orgs=("followers", lambda s: s.notna().sum()),
        total_followers=("followers", "sum"),
        avg_posts_30d=("posts_30d", "mean"),
        avg_activity=("activity_score", "mean"),
    ).reset_index()
    return g


def ranking(df: pd.DataFrame, by: str = "activity_score", top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return df
    cols = ["name_ko", "category_label", "platform", "handle",
            "followers", "posts_30d", "engagement_rate", "activity_score"]
    out = df[cols].sort_values(by, ascending=False).head(top_n)
    return out.reset_index(drop=True)


def growth_table(history: pd.DataFrame, window_days: int = 30) -> pd.DataFrame:
    """과거 스냅샷 대비 팔로워 성장률 계산."""
    if history.empty:
        return history
    history = history.copy()
    history["captured_at"] = pd.to_datetime(history["captured_at"], utc=True)
    history = history.sort_values("captured_at")

    rows = []
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=window_days)
    for (org_id, platform), grp in history.groupby(["org_id", "platform"]):
        latest = grp.iloc[-1]
        past = grp[grp["captured_at"] <= cutoff]
        if past.empty:
            continue
        before = past.iloc[-1]
        if not before["followers"] or not latest["followers"]:
            continue
        delta = latest["followers"] - before["followers"]
        pct = delta / before["followers"] if before["followers"] else 0
        rows.append({
            "org_id": org_id,
            "platform": platform,
            "followers_before": before["followers"],
            "followers_now": latest["followers"],
            "delta": delta,
            "growth_pct": round(pct * 100, 2),
            "window_days": window_days,
        })
    return pd.DataFrame(rows)
