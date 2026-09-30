"""대한민국 아파트 최근 7일 매매/전월세 실거래가 Streamlit 모니터링 대시보드"""

import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime

from src.db import DatabaseManager
from src.regions import get_sido_list, get_sgg_list_by_sido
from src.dashboard_components import (
    format_korean_currency,
    compute_trade_kpis,
    compute_rent_kpis,
    create_daily_trend_chart,
    create_top_regions_chart,
    create_price_distribution_chart,
    create_pyeong_distribution_chart,
)

# 1. 페이지 설정
st.set_page_config(
    page_title="대한민국 아파트 최근 7일 실거래가",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS 스타일링
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748B;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #3B82F6;
        margin-top: 2px;
    }
</style>
""", unsafe_allow_html=True)


# 2. DB 및 메타데이터 로드
@st.cache_resource
def get_db():
    db = DatabaseManager("data/real_estate.db")
    db.init_db()
    return db


def get_meta():
    meta_path = "data/meta.json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


db = get_db()
meta = get_meta()

# 3. 상단 헤더
st.markdown('<div class="main-title">🏢 대한민국 아파트 최근 7일 실거래가 모니터링</div>', unsafe_allow_html=True)

sync_info = "동기화 정보 없음"
if meta and "last_updated" in meta:
    try:
        updated_dt = datetime.fromisoformat(meta["last_updated"])
        sync_info = f"최근 수집: {updated_dt.strftime('%Y년 %m월 %d일 %H:%M')} (기준 윈도우: {meta.get('cutoff_date')} ~ {meta.get('target_date')})"
    except Exception:
        sync_info = f"최근 수집: {meta.get('last_updated')}"

st.markdown(f'<div class="sub-title">국토교통부 공공데이터포털 실시간 실거래가 연동 &bull; {sync_info}</div>', unsafe_allow_html=True)

# 4. 사이드바 필터링
st.sidebar.header("🔍 검색 및 필터 옵션")

# 4.1 거래 유형 탭 라디오
mode = st.sidebar.radio(
    "거래 유형 선택",
    ["📈 매매 실거래가", "🏠 전월세 실거래가"],
    index=0
)
is_trade = "매매" in mode

# 4.2 지역 필터
sido_options = ["전체"] + get_sido_list()
selected_sido = st.sidebar.selectbox("시/도 선택", sido_options, index=0)

selected_sggs = []
if selected_sido != "전체":
    available_sgg_objs = get_sgg_list_by_sido(selected_sido)
    sgg_names = [item["sgg"] for item in available_sgg_objs]
    selected_sggs = st.sidebar.multiselect("시/군/구 선택 (복수 선택 가능)", sgg_names)

# 4.3 단지명 검색
search_apt = st.sidebar.text_input("아파트 단지명 검색", placeholder="예: 자이, 래미안, 현대")

# 4.4 전월세 전용 구분 필터
rent_type_filter = "전체"
if not is_trade:
    rent_type_filter = st.sidebar.selectbox("임대 구분", ["전체", "전세", "월세"], index=0)

# 4.5 금액 슬라이더
if is_trade:
    price_range = st.sidebar.slider(
        "매매 가격 범위 (억원)",
        min_value=0.0,
        max_value=100.0,
        value=(0.0, 100.0),
        step=0.5
    )
    min_amount = int(price_range[0] * 10000)
    max_amount = int(price_range[1] * 10000)
else:
    deposit_range = st.sidebar.slider(
        "보증금 범위 (억원)",
        min_value=0.0,
        max_value=50.0,
        value=(0.0, 50.0),
        step=0.5
    )
    min_amount = int(deposit_range[0] * 10000)
    max_amount = int(deposit_range[1] * 10000)

# 5. 데이터 조회
@st.cache_data(ttl=60)
def load_trade_data(sido, sgg_tuple, min_p, max_p, apt_name):
    df = db.query_trades(
        sido=sido if sido != "전체" else None,
        min_price=min_p,
        max_price=max_p if max_p < 1000000 else None,
        apt_name=apt_name if apt_name else None
    )
    if sgg_tuple and not df.empty and "sgg" in df:
        df = df[df["sgg"].isin(sgg_tuple)]
    return df


@st.cache_data(ttl=60)
def load_rent_data(sido, sgg_tuple, r_type, min_d, max_d, apt_name):
    df = db.query_rents(
        sido=sido if sido != "전체" else None,
        rent_type=r_type if r_type != "전체" else None,
        min_deposit=min_d,
        max_deposit=max_d if max_d < 500000 else None,
        apt_name=apt_name if apt_name else None
    )
    if sgg_tuple and not df.empty and "sgg" in df:
        df = df[df["sgg"].isin(sgg_tuple)]
    return df


sgg_tuple = tuple(selected_sggs) if selected_sggs else None

if is_trade:
    df = load_trade_data(selected_sido, sgg_tuple, min_amount, max_amount, search_apt)
else:
    df = load_rent_data(selected_sido, sgg_tuple, rent_type_filter, min_amount, max_amount, search_apt)

# 6. 대시보드 뷰 렌더링
if df.empty:
    st.info("💡 조건에 부합하는 최근 7일간의 실거래 데이터가 없습니다. 사이드바 필터를 변경하거나 데이터 수집 상태를 확인하세요.")
else:
    # 6.1 1단: 핵심 메트릭 (KPI Cards)
    if is_trade:
        kpis = compute_trade_kpis(df)
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">총 매매 거래량</div>
                <div class="metric-value">{kpis['total_deals']:,} <span style="font-size:1rem;font-weight:normal;">건</span></div>
                <div class="metric-sub">최근 7일 기준</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            max_d = kpis['max_deal']
            max_title = f"{max_d['apt_name']} ({format_korean_currency(max_d['deal_amount'])})" if max_d else "-"
            max_sub = f"{max_d['sgg']} · {max_d['pyeong']:.1f}평({max_d['exclusive_area']:.1f}㎡) · {max_d['floor']}층" if max_d else "-"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">최고가 거래 단지</div>
                <div class="metric-value" style="font-size:1.25rem;">{max_title}</div>
                <div class="metric-sub">{max_sub}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">평균 매매 가격</div>
                <div class="metric-value">{format_korean_currency(kpis['avg_price'])}</div>
                <div class="metric-sub">평균 평당 {kpis['avg_pyeong_price']:,}만원</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">최다 거래 지역</div>
                <div class="metric-value">{kpis['top_sgg']}</div>
                <div class="metric-sub">검색 조건 내 1위</div>
            </div>
            """, unsafe_allow_html=True)

    else:
        kpis = compute_rent_kpis(df)
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">총 전월세 거래량</div>
                <div class="metric-value">{kpis['total_deals']:,} <span style="font-size:1rem;font-weight:normal;">건</span></div>
                <div class="metric-sub">전세 {kpis['jeonse_count']}건 / 월세 {kpis['wolse_count']}건</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            max_d = kpis['max_deposit']
            max_title = f"{max_d['apt_name']} ({format_korean_currency(max_d['deposit'])})" if max_d else "-"
            max_sub = f"{max_d['sgg']} · {max_d['rent_type']} · {max_d['exclusive_area']:.1f}㎡" if max_d else "-"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">최고 보증금 단지</div>
                <div class="metric-value" style="font-size:1.25rem;">{max_title}</div>
                <div class="metric-sub">{max_sub}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">평균 전세 보증금</div>
                <div class="metric-value">{format_korean_currency(kpis['avg_jeonse_deposit'])}</div>
                <div class="metric-sub">평균 월세: {kpis['avg_wolse_rent']:,}만원</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">최다 임대 지역</div>
                <div class="metric-value">{kpis['top_sgg']}</div>
                <div class="metric-sub">검색 조건 내 1위</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 6.2 2단: 인터랙티브 차트 (Plotly)
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.plotly_chart(create_daily_trend_chart(df), width="stretch")

    with chart_col2:
        st.plotly_chart(create_top_regions_chart(df, top_n=10), width="stretch")

    # 6.3 3단: 분포 차트
    dist_col1, dist_col2 = st.columns(2)

    with dist_col1:
        if is_trade:
            st.plotly_chart(create_price_distribution_chart(df, "deal_amount", "매매가 분포"), width="stretch")
        else:
            st.plotly_chart(create_price_distribution_chart(df, "deposit", "보증금 분포"), width="stretch")

    with dist_col2:
        st.plotly_chart(create_pyeong_distribution_chart(df), width="stretch")

    # 6.4 4단: 상세 실거래가 데이터 테이블 & 다운로드
    st.subheader(f"📋 실거래 상세 내역 (총 {len(df):,}건)")

    display_df = df.copy()

    if is_trade:
        display_df["거래금액(표기)"] = display_df["deal_amount"].apply(format_korean_currency)
        display_df["평당가(만원)"] = display_df["price_per_pyeong"].apply(lambda x: f"{x:,}만원" if pd.notna(x) else "-")
        display_df["전용면적(㎡)"] = display_df["exclusive_area"].apply(lambda x: f"{x:.2f}㎡ ({x/3.30578:.1f}평)")
        show_cols = [
            "deal_date", "sido", "sgg", "umd", "apt_name",
            "floor", "전용면적(㎡)", "거래금액(표기)", "평당가(만원)",
            "build_year", "dealing_gbn"
        ]
        rename_cols = {
            "deal_date": "계약일자",
            "sido": "시도",
            "sgg": "시군구",
            "umd": "읍면동",
            "apt_name": "아파트 단지명",
            "floor": "층수",
            "build_year": "건축년도",
            "dealing_gbn": "거래유형"
        }
    else:
        display_df["보증금(표기)"] = display_df["deposit"].apply(format_korean_currency)
        display_df["월세(만원)"] = display_df["monthly_rent"].apply(lambda x: f"{x:,}만원" if x > 0 else "전세")
        display_df["전용면적(㎡)"] = display_df["exclusive_area"].apply(lambda x: f"{x:.2f}㎡ ({x/3.30578:.1f}평)")
        show_cols = [
            "deal_date", "sido", "sgg", "umd", "apt_name",
            "rent_type", "floor", "전용면적(㎡)", "보증금(표기)", "월세(만원)",
            "build_year", "contract_type"
        ]
        rename_cols = {
            "deal_date": "계약일자",
            "sido": "시도",
            "sgg": "시군구",
            "umd": "읍면동",
            "apt_name": "아파트 단지명",
            "rent_type": "구분",
            "floor": "층수",
            "build_year": "건축년도",
            "contract_type": "계약구분"
        }

    valid_show_cols = [c for c in show_cols if c in display_df.columns]
    table_df = display_df[valid_show_cols].rename(columns=rename_cols)

    st.dataframe(
        table_df,
        width="stretch",
        hide_index=True,
        height=400
    )

    # CSV 다운로드
    csv_bytes = table_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 필터링된 실거래 데이터 CSV 다운로드",
        data=csv_bytes,
        file_name=f"apt_real_estate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
