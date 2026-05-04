"""Streamlit 대시보드.

실행:  streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from mcst.analysis import (
    build_dataframe,
    platform_summary,
    category_summary,
    ranking,
    growth_table,
    org_overview,
    tier_distribution,
    coverage_matrix,
)
from mcst.config import PLATFORMS, Settings, load_orgs
from mcst.reports import render_html, render_pdf
from mcst.storage import SnapshotStore

st.set_page_config(
    page_title="정부조직 SNS 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=60)
def load_data():
    settings = Settings.from_env()
    store = SnapshotStore(settings.db_path)
    latest = store.latest()
    history = store.all()
    df = build_dataframe(latest)
    hist_df = pd.DataFrame(history) if history else pd.DataFrame()
    if not hist_df.empty:
        hist_df["captured_at"] = pd.to_datetime(hist_df["captured_at"], utc=True)
    return df, hist_df


def fmt_int(v):
    if pd.isna(v):
        return "-"
    return f"{int(v):,}"


def fmt_pct(v):
    if pd.isna(v):
        return "-"
    return f"{v * 100:.2f}%"


# ---------- Sidebar ---------------------------------------------------------
st.sidebar.title("정부조직 SNS 분석")
st.sidebar.caption("19부 6처 19청 6위원회 · YouTube · Instagram · X · Facebook · 블로그")

df, hist_df = load_data()

if df.empty:
    st.warning(
        "수집된 스냅샷이 없습니다.\n\n"
        "터미널에서 다음을 실행해 주세요.\n"
        "```bash\n"
        "python -m mcst.cli demo          # API 키 없이 데모 데이터 시드\n"
        "python -m mcst.cli collect       # 실수집 (시드 핸들·API 키 필요)\n"
        "```"
    )
    st.stop()

categories = sorted(df["category_label"].dropna().unique().tolist())
sel_cats = st.sidebar.multiselect("분류", categories, default=categories)
sel_platforms = st.sidebar.multiselect("플랫폼", list(PLATFORMS), default=list(PLATFORMS))
search = st.sidebar.text_input("기관명 검색", "")

mask = df["category_label"].isin(sel_cats) & df["platform"].isin(sel_platforms)
if search:
    mask &= df["name_ko"].str.contains(search, na=False)
fdf = df[mask].copy()

# ---------- Header KPIs -----------------------------------------------------
st.title("정부조직 SNS 운영현황·성과 대시보드")
all_orgs = load_orgs()
total_orgs = len({o["id"] for o in all_orgs})

col1, col2, col3, col4 = st.columns(4)
col1.metric("대상 기관", f"{total_orgs}")
col2.metric("운영 중인 계정 수", f"{int(fdf['followers'].notna().sum())}")
col3.metric("총 팔로워(필터)", fmt_int(fdf["followers"].sum()))
col4.metric("평균 활성도", f"{fdf['activity_score'].mean():.1f}" if not fdf.empty else "-")

# ---------- Tabs ------------------------------------------------------------
(tab_overview, tab_platform, tab_org, tab_compare,
 tab_coverage, tab_trend, tab_report) = st.tabs(
    ["개요", "플랫폼별", "기관별", "비교/랭킹", "운영 매트릭스", "트렌드", "리포트"]
)

with tab_overview:
    st.subheader("플랫폼별 운영현황 요약")
    psum = platform_summary(fdf)
    st.dataframe(psum, use_container_width=True, hide_index=True)
    if not psum.empty:
        fig = px.bar(psum, x="platform", y="operating_orgs",
                     title="플랫폼별 운영 기관 수", text="operating_orgs")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("기관 분류 × 플랫폼 매트릭스 (활성도 평균)")
    csum = category_summary(fdf)
    if not csum.empty:
        pivot = csum.pivot(index="category_label", columns="platform",
                           values="avg_activity")
        st.dataframe(pivot.style.background_gradient(cmap="Blues", axis=None),
                     use_container_width=True)

with tab_platform:
    plat = st.selectbox("플랫폼 선택", sel_platforms or list(PLATFORMS))
    pdf_ = fdf[fdf["platform"] == plat].copy()
    st.subheader(f"{plat.upper()} 운영현황")
    cols = ["name_ko", "category_label", "handle", "followers", "posts_30d",
            "posts_90d", "last_post_at", "engagement_rate", "activity_score"]
    show = pdf_[cols].sort_values("activity_score", ascending=False)
    st.dataframe(show, use_container_width=True, hide_index=True)

    if not pdf_.empty:
        fig = px.scatter(pdf_, x="followers", y="engagement_rate",
                         size="posts_30d", color="category_label",
                         hover_name="name_ko", log_x=True,
                         title=f"{plat.upper()} 팔로워 vs 인게이지율")
        st.plotly_chart(fig, use_container_width=True)

with tab_org:
    orgs_avail = sorted(fdf["name_ko"].dropna().unique().tolist())
    if not orgs_avail:
        st.info("표시할 기관이 없습니다.")
    else:
        org = st.selectbox("기관 선택", orgs_avail)
        org_df = fdf[fdf["name_ko"] == org].copy()
        st.subheader(f"{org} - 플랫폼별 현황")
        st.dataframe(org_df[["platform", "handle", "followers", "posts_30d",
                              "last_post_at", "engagement_rate", "activity_score"]],
                     use_container_width=True, hide_index=True)
        if not org_df.empty:
            fig = px.bar(org_df, x="platform", y="activity_score",
                         color="platform", text="activity_score",
                         title=f"{org} 플랫폼별 활성도")
            st.plotly_chart(fig, use_container_width=True)

with tab_compare:
    st.subheader("기관 종합 점수 (전 플랫폼 통합)")
    st.caption("종합점수 = 평균활성도×0.5 + 멀티플랫폼 가중치×0.3 + 인게이지율×0.2")
    overview = org_overview(fdf)
    st.dataframe(overview, use_container_width=True, hide_index=True)
    if not overview.empty:
        fig = px.bar(overview.head(20), x="name_ko", y="composite_score",
                     color="category_label", title="종합점수 상위 20")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("플랫폼별 성과 등급 분포")
    td = tier_distribution(fdf)
    if not td.empty:
        st.dataframe(td, use_container_width=True, hide_index=True)

    st.subheader("랭킹 (지표 선택)")
    metric = st.selectbox(
        "정렬 기준",
        ["activity_score", "followers", "engagement_rate",
         "efficiency", "posts_30d", "multi_platform_score"],
    )
    st.dataframe(ranking(fdf, metric, 30),
                 use_container_width=True, hide_index=True)

with tab_coverage:
    st.subheader("기관 × 플랫폼 운영 매트릭스")
    st.caption("1 = 해당 플랫폼 운영, 0 = 미운영. total 은 운영 플랫폼 수.")
    cov = coverage_matrix(fdf)
    if cov.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.dataframe(cov, use_container_width=True, hide_index=True)
        st.subheader("플랫폼별 운영률")
        rate = (cov[list(PLATFORMS)].mean() * 100).round(1).reset_index()
        rate.columns = ["platform", "operation_rate(%)"]
        fig = px.bar(rate, x="platform", y="operation_rate(%)",
                     text="operation_rate(%)", title="필터 대상 기관 중 플랫폼별 운영률")
        st.plotly_chart(fig, use_container_width=True)

with tab_trend:
    if hist_df.empty:
        st.info("트렌드를 보려면 시간차를 둔 수집이 필요합니다. (또는 `demo` 명령으로 시드)")
    else:
        org_choices = (
            hist_df.merge(pd.DataFrame(load_orgs())[["id", "name_ko"]],
                          left_on="org_id", right_on="id")
            ["name_ko"].dropna().unique().tolist()
        )
        sel_org = st.selectbox("기관", sorted(org_choices))
        sel_plat = st.selectbox("플랫폼", list(PLATFORMS))
        org_id = next((o["id"] for o in load_orgs() if o["name_ko"] == sel_org), None)
        sub = hist_df[(hist_df["org_id"] == org_id) & (hist_df["platform"] == sel_plat)]
        if sub.empty:
            st.warning("해당 조합의 데이터가 없습니다.")
        else:
            sub = sub.sort_values("captured_at")
            fig = px.line(sub, x="captured_at", y="followers",
                          title=f"{sel_org} · {sel_plat.upper()} 팔로워 추이",
                          markers=True)
            st.plotly_chart(fig, use_container_width=True)
            fig2 = px.line(sub, x="captured_at", y="posts_30d",
                           title="30일 게시 수 추이", markers=True)
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("최근 30일 팔로워 성장률 (전 기관)")
        gt = growth_table(hist_df, 30)
        if gt.empty:
            st.info("성장률 산출 가능한 이력이 부족합니다.")
        else:
            st.dataframe(gt.sort_values("growth_pct", ascending=False),
                         use_container_width=True, hide_index=True)

with tab_report:
    st.subheader("리포트 다운로드")
    st.caption("현재 화면의 필터를 무시하고 전체 데이터로 리포트를 생성합니다.")
    settings = Settings.from_env()
    store = SnapshotStore(settings.db_path)
    latest = store.latest()
    history = store.all()
    html = render_html(latest, history)

    st.download_button(
        "📄 HTML 리포트 다운로드", data=html.encode("utf-8"),
        file_name="sns_report.html", mime="text/html",
    )

    # CSV bundle (zip)
    import io
    import zipfile
    from mcst.reports import write_csv_bundle
    import tempfile

    if st.button("📦 CSV 묶음 생성"):
        with tempfile.TemporaryDirectory() as td:
            paths = write_csv_bundle(latest, history, Path(td))
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in paths.values():
                    z.write(p, arcname=p.name)
            st.download_button("⬇️ CSV.zip 다운로드", data=buf.getvalue(),
                               file_name="sns_csv_bundle.zip", mime="application/zip")

    if st.button("🧾 PDF 리포트 생성"):
        try:
            tmp = ROOT / "reports" / "output" / "report.pdf"
            render_pdf(html, tmp)
            with open(tmp, "rb") as f:
                st.download_button("⬇️ PDF 다운로드", data=f.read(),
                                   file_name="sns_report.pdf",
                                   mime="application/pdf")
        except Exception as e:
            st.error(f"PDF 생성 실패: {e}\nWeasyPrint 시스템 의존성(libpango/cairo)을 확인해 주세요.")

    st.markdown("---")
    st.markdown(
        "**페이지 공유**: 이 대시보드는 `streamlit run` 으로 호스팅하면 사내 네트워크에서 URL로 공유 가능합니다.\n"
        "정적 공유가 필요하면 위 HTML 리포트 파일을 그대로 배포하세요."
    )
