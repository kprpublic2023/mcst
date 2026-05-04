"""스냅샷을 분석용 DataFrame으로 변환 및 파생지표 계산."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from ..config import CATEGORY_LABELS, load_orgs


def build_dataframe(snapshots: list[dict[str, Any]]) -> pd.DataFrame:
    """스냅샷 리스트 -> DataFrame (기관 메타 결합)."""
    if not snapshots:
        return pd.DataFrame()
    df = pd.DataFrame(snapshots)
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    df["last_post_at"] = pd.to_datetime(df["last_post_at"], utc=True, errors="coerce")

    # 기관 메타데이터 결합
    orgs = pd.DataFrame(load_orgs())[["id", "name_ko", "name_en", "category"]]
    orgs = orgs.rename(columns={"id": "org_id", "category": "category_meta"})
    df = df.merge(orgs, on="org_id", how="left")
    df["category"] = df["category"].fillna(df["category_meta"])
    df["category_label"] = df["category"].map(CATEGORY_LABELS).fillna(df["category"])

    df["activity_score"] = df.apply(activity_score, axis=1)
    df["days_since_last_post"] = (
        pd.Timestamp.now(tz="UTC") - df["last_post_at"]
    ).dt.days

    # 효율성: 팔로워 1만 명당 인게이지 (좋아요+댓글)
    eng_per_post = (df["avg_likes"].fillna(0) + df["avg_comments"].fillna(0))
    df["efficiency"] = np.where(
        df["followers"].fillna(0) > 0,
        eng_per_post / df["followers"].replace({0: np.nan}) * 10_000,
        np.nan,
    )

    # 성과 등급 (활성도 점수 기반)
    df["tier"] = pd.cut(
        df["activity_score"],
        bins=[-0.01, 20, 50, 75, 100.01],
        labels=["휴면", "저조", "보통", "우수"],
    )

    # 기관별 멀티플랫폼 점수 (운영 중인 플랫폼 수)
    operating = df[df["followers"].notna()].groupby("org_id")["platform"].nunique()
    df["multi_platform_count"] = df["org_id"].map(operating).fillna(0).astype(int)
    df["multi_platform_score"] = (df["multi_platform_count"] / len(df["platform"].unique()) * 100).round(1)

    return df


def activity_score(row: pd.Series) -> float:
    """0~100 활성도 점수.

    구성: 최근 30일 게시(40) + 최근 90일 게시(20) + 마지막 게시 신선도(20) + 인게이지율(20)
    """
    p30 = row.get("posts_30d") or 0
    p90 = row.get("posts_90d") or 0
    last = row.get("last_post_at")
    er = row.get("engagement_rate") or 0

    s_30 = min(p30 / 12, 1.0) * 40       # 30일에 12건 이상이면 만점
    s_90 = min(p90 / 30, 1.0) * 20       # 90일에 30건 이상이면 만점

    if isinstance(last, str):
        last_dt = pd.to_datetime(last, utc=True, errors="coerce")
    else:
        last_dt = last
    if pd.isna(last_dt):
        s_fresh = 0.0
    else:
        days = (datetime.now(timezone.utc) - last_dt.to_pydatetime()).days
        s_fresh = max(0.0, 1.0 - days / 60) * 20  # 60일 지나면 0

    s_eng = min(er / 0.05, 1.0) * 20  # 5% 인게이지율이면 만점

    return round(s_30 + s_90 + s_fresh + s_eng, 1)
