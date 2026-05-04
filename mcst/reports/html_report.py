"""HTML 리포트 렌더러 (공유/뷰 + PDF 변환의 원본)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..analysis import (
    build_dataframe,
    platform_summary,
    category_summary,
    ranking,
    growth_table,
)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _to_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p class='muted'>데이터 없음</p>"
    return df.to_html(index=False, classes="data", border=0, na_rep="-",
                      float_format=lambda v: f"{v:,.2f}" if abs(v) < 100 else f"{v:,.0f}")


def render_html(latest_snapshots: list[dict], history: list[dict] | None = None,
                title: str = "정부조직 SNS 운영현황·성과 리포트") -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR),
                      autoescape=select_autoescape(["html"]))
    tpl = env.get_template("report.html.j2")
    df = build_dataframe(latest_snapshots)
    hist_df = pd.DataFrame(history) if history else pd.DataFrame()
    growth = growth_table(hist_df) if not hist_df.empty else pd.DataFrame()

    return tpl.render(
        title=title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        org_count=df["org_id"].nunique() if not df.empty else 0,
        platform_table=_to_html(platform_summary(df)),
        category_table=_to_html(category_summary(df)),
        ranking_activity=_to_html(ranking(df, "activity_score", 20)),
        ranking_followers=_to_html(ranking(df, "followers", 20)),
        growth_table=_to_html(growth) if not growth.empty else "",
        growth_window=30,
    )
