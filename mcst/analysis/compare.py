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


def org_overview(df: pd.DataFrame) -> pd.DataFrame:
    """기관별 통합 점수 (전 플랫폼 합산/평균)."""
    if df.empty:
        return df
    g = df.groupby(["org_id", "name_ko", "category_label"], dropna=False).agg(
        platforms_active=("followers", lambda s: int(s.notna().sum())),
        total_followers=("followers", "sum"),
        avg_activity=("activity_score", "mean"),
        avg_efficiency=("efficiency", "mean"),
        avg_engagement=("engagement_rate", "mean"),
    ).reset_index()
    g["composite_score"] = (
        g["avg_activity"].fillna(0) * 0.5
        + g["platforms_active"] / 5 * 100 * 0.3
        + (g["avg_engagement"].fillna(0) * 100).clip(upper=100) * 0.2
    ).round(1)
    return g.sort_values("composite_score", ascending=False).reset_index(drop=True)


def tier_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """플랫폼별 성과 등급(휴면/저조/보통/우수) 분포."""
    if df.empty or "tier" not in df.columns:
        return pd.DataFrame()
    out = df.groupby(["platform", "tier"], observed=False).size().unstack(fill_value=0)
    return out.reset_index()


def coverage_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """기관 × 플랫폼 운영 여부 매트릭스 (1=운영, 0=미운영)."""
    if df.empty:
        return df
    df2 = df.assign(operating=df["followers"].notna().astype(int))
    pivot = df2.pivot_table(index=["category_label", "name_ko"],
                             columns="platform", values="operating",
                             aggfunc="max", fill_value=0)
    pivot["total"] = pivot.sum(axis=1)
    return pivot.reset_index()


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
