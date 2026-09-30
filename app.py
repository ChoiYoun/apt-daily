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
from src.ai_analyst import GeminiAnalystClient

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
    .ai-header-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #1E293B 100%);
        border-radius: 12px;
        padding: 22px 26px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
    }
    .ai-meta {
        color: #93C5FD;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 8px;
    }
    .ai-headline {
        font-size: 1.45rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.4;
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

# 4. 사이드바 메인 뷰 선택
st.sidebar.markdown("### 📌 메뉴 선택")
view_mode = st.sidebar.radio(
    "화면 모드 선택",
    ["📊 전국 종합 대시보드", "📅 일자별 AI 상세 리포트"],
    index=0
)

# ==============================================================================
# VIEW 1: 전국 종합 대시보드
# ==============================================================================
if view_mode == "📊 전국 종합 대시보드":
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 검색 및 필터 옵션")

    # 1. 거래 유형 탭 라디오
    mode = st.sidebar.radio(
        "거래 유형 선택",
        ["📈 매매 실거래가", "🏠 전월세 실거래가"],
        index=0
    )
    is_trade = "매매" in mode

    # 2. 지역 필터
    sido_options = ["전체"] + get_sido_list()
    selected_sido = st.sidebar.selectbox("시/도 선택", sido_options, index=0)

    selected_sggs = []
    if selected_sido != "전체":
        available_sgg_objs = get_sgg_list_by_sido(selected_sido)
        sgg_names = [item["sgg"] for item in available_sgg_objs]
        selected_sggs = st.sidebar.multiselect("시/군/구 선택 (복수 선택 가능)", sgg_names)

    # 3. 단지명 검색
    search_apt = st.sidebar.text_input("아파트 단지명 검색", placeholder="예: 자이, 래미안, 현대")

    # 4. 전월세 전용 구분 필터
    rent_type_filter = "전체"
    if not is_trade:
        rent_type_filter = st.sidebar.selectbox("임대 구분", ["전체", "전세", "월세"], index=0)

    # 5. 금액 슬라이더
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

    # 데이터 로드
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

    if df.empty:
        st.info("💡 조건에 부합하는 최근 7일간의 실거래 데이터가 없습니다. 사이드바 필터를 변경하거나 데이터 수집 상태를 확인하세요.")
    else:
        # KPI Cards
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
                region_str = max_d.get('region_label', max_d.get('sgg', '-')) if max_d else "-"
                max_sub = f"{region_str} · {max_d['pyeong']:.1f}평({max_d['exclusive_area']:.1f}㎡) · {max_d['floor']}층" if max_d else "-"
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
                deal_cnt = kpis.get('top_sgg_count', 0)
                sub_txt = f"최근 7일 {deal_cnt:,}건 거래" if deal_cnt > 0 else "검색 조건 내 1위"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">최다 거래 지역</div>
                    <div class="metric-value">{kpis['top_sgg']}</div>
                    <div class="metric-sub">{sub_txt}</div>
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
                region_str = max_d.get('region_label', max_d.get('sgg', '-')) if max_d else "-"
                max_sub = f"{region_str} · {max_d['rent_type']} · {max_d['exclusive_area']:.1f}㎡" if max_d else "-"
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
                deal_cnt = kpis.get('top_sgg_count', 0)
                sub_txt = f"최근 7일 {deal_cnt:,}건 거래" if deal_cnt > 0 else "검색 조건 내 1위"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">최다 임대 지역</div>
                    <div class="metric-value">{kpis['top_sgg']}</div>
                    <div class="metric-sub">{sub_txt}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Plotly 차트
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(create_daily_trend_chart(df), width="stretch")
        with chart_col2:
            st.plotly_chart(create_top_regions_chart(df, top_n=10), width="stretch")

        dist_col1, dist_col2 = st.columns(2)
        with dist_col1:
            if is_trade:
                st.plotly_chart(create_price_distribution_chart(df, "deal_amount", "매매가 분포"), width="stretch")
            else:
                st.plotly_chart(create_price_distribution_chart(df, "deposit", "보증금 분포"), width="stretch")
        with dist_col2:
            st.plotly_chart(create_pyeong_distribution_chart(df), width="stretch")

        # 테이블 및 CSV 다운로드
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

        csv_bytes = table_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 필터링된 실거래 데이터 CSV 다운로드",
            data=csv_bytes,
            file_name=f"apt_real_estate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

# ==============================================================================
# VIEW 2: 일자별 AI 상세 리포트
# ==============================================================================
else:
    st.sidebar.markdown("---")
    st.sidebar.header("📅 일자별 분석 설정")

    available_dates = db.get_available_dates()

    if not available_dates:
        st.warning("⚠️ 현재 데이터베이스에 저장된 실거래 일자가 없습니다. 먼저 데이터 수집을 실행해 주세요.")
    else:
        selected_date = st.sidebar.selectbox(
            "분석 기준 일자 선택",
            available_dates,
            index=0,
            help="분석 및 조회를 원하는 계약일자를 선택하세요."
        )

        force_refresh = st.sidebar.button(
            "🔄 AI 리포트 강제 재생성",
            help="기존 캐시된 분석을 무시하고 Google Gemini를 호출하여 리포트를 새로 생성합니다."
        )

        # 데이터 로드 (특정 일자)
        daily_trades = db.query_trades(start_date=selected_date, end_date=selected_date)
        daily_rents = db.query_rents(start_date=selected_date, end_date=selected_date)

        # 메인 제목
        st.markdown(f"### 📅 {selected_date} 아파트 실거래 마켓 브리핑")

        # 당일 4대 KPI 카드
        trade_kpis = compute_trade_kpis(daily_trades)
        rent_kpis = compute_rent_kpis(daily_rents)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">당일 매매 거래량</div>
                <div class="metric-value">{trade_kpis['total_deals']:,} <span style="font-size:1rem;font-weight:normal;">건</span></div>
                <div class="metric-sub">평균 {format_korean_currency(trade_kpis['avg_price'])}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            max_t = trade_kpis['max_deal']
            t_name = f"{max_t['apt_name']} ({format_korean_currency(max_t['deal_amount'])})" if max_t else "거래 없음"
            t_sub = f"{max_t.get('region_label', '-')} · {max_t.get('pyeong', 0):.1f}평({max_t.get('floor', '-')}층)" if max_t else "-"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">당일 매매 최고가 단지</div>
                <div class="metric-value" style="font-size:1.25rem;">{t_name}</div>
                <div class="metric-sub">{t_sub}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">당일 전월세 거래량</div>
                <div class="metric-value">{rent_kpis['total_deals']:,} <span style="font-size:1rem;font-weight:normal;">건</span></div>
                <div class="metric-sub">전세 {rent_kpis['jeonse_count']}건 / 월세 {rent_kpis['wolse_count']}건</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            max_r = rent_kpis['max_deposit']
            r_name = f"{max_r['apt_name']} ({format_korean_currency(max_r['deposit'])})" if max_r else "거래 없음"
            r_sub = f"{max_r.get('region_label', '-')} · {max_r.get('rent_type', '-')} · {max_r.get('exclusive_area', 0):.1f}㎡" if max_r else "-"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">당일 최고 보증금 단지</div>
                <div class="metric-value" style="font-size:1.25rem;">{r_name}</div>
                <div class="metric-sub">{r_sub}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # AI 마켓 브리핑 리포트 섹션
        client = GeminiAnalystClient()

        with st.spinner("🤖 AI 수석 애널리스트가 당일 시장 데이터를 분석 중입니다..."):
            report = client.get_or_create_daily_analysis(
                db_manager=db,
                deal_date=selected_date,
                trades_df=daily_trades,
                rents_df=daily_rents,
                force_refresh=force_refresh
            )

        if report.get("error") == "NO_API_KEY":
            st.markdown("""
            <div style="background:#FFFBEB; border:1px solid #FCD34D; border-radius:10px; padding:18px 22px; margin: 15px 0;">
                <h4 style="color:#B45309; margin:0 0 8px 0; font-size:1.05rem;">🤖 AI 마켓 브리핑 비활성화 안내</h4>
                <p style="color:#92400E; margin:0; font-size:0.92rem; line-height:1.5;">
                    <code>GEMINI_API_KEY</code> 환경변수가 설정되지 않아 AI 요약 리포트를 생성할 수 없습니다.<br>
                    <a href="https://aistudio.google.com/" target="_blank" style="color:#B45309; font-weight:700; text-decoration:underline;">Google AI Studio</a>에서 무료 API 키를 발급받아 <code>.env</code> 파일에 등록하시면, 매일 실시간 부동산 수석 애널리스트 브리핑이 자동 생성됩니다.
                </p>
            </div>
            """, unsafe_allow_html=True)
        elif report.get("error") == "API_ERROR":
            st.error(f"⚠️ AI 리포트 생성 중 오류가 발생했습니다: {report.get('message')}")
        else:
            # 정상 또는 캐시 로드된 리포트
            headline = report.get("headline", "")
            summary_markdown = report.get("summary_markdown", "")
            model_name = report.get("model_name", "gemini-flash-lite-latest")
            is_cached = report.get("cached", False)
            created_at = report.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
            cache_label = "💾 캐시 로드 (0.01s)" if is_cached else "⚡ 신규 실시간 생성"

            # 헤드라인 텍스트 전처리 (마크다운 기호 및 메타 태그 정제)
            clean_headline = headline.lstrip("#").strip()
            for prefix in ["[한줄 마켓 헤드라인]", "[마켓 헤드라인]", "[데일리 마켓 브리핑]", "[데일리 브리핑]", "[한줄 헤드라인]"]:
                if clean_headline.startswith(prefix):
                    clean_headline = clean_headline[len(prefix):].strip()

            with st.container(border=True):
                # 헤더 카드
                st.markdown(f"""
                <div class="ai-header-card">
                    <div class="ai-meta">
                        🤖 부동산 수석 애널리스트 마켓 브리핑 &bull; 모델: {model_name} &bull; {cache_label} &bull; {created_at}
                    </div>
                    <div class="ai-headline">{clean_headline}</div>
                </div>
                """, unsafe_allow_html=True)

                # 본문 마크다운
                st.markdown(summary_markdown)

                if report.get("warning"):
                    st.warning(report["warning"])

        st.markdown("<br>", unsafe_allow_html=True)

        # 당일 실거래 상세 내역 탭
        tab_trade, tab_rent = st.tabs([
            f"📈 당일 매매 실거래 내역 ({len(daily_trades):,}건)",
            f"🏠 당일 전월세 실거래 내역 ({len(daily_rents):,}건)"
        ])

        with tab_trade:
            if daily_trades.empty:
                st.info(f"{selected_date}에 등록된 매매 실거래 내역이 없습니다.")
            else:
                trade_display = daily_trades.copy()
                trade_display["거래금액(표기)"] = trade_display["deal_amount"].apply(format_korean_currency)
                trade_display["평당가(만원)"] = trade_display["price_per_pyeong"].apply(
                    lambda x: f"{x:,}만원" if pd.notna(x) else "-"
                )
                trade_display["전용면적(㎡)"] = trade_display["exclusive_area"].apply(
                    lambda x: f"{x:.2f}㎡ ({x/3.30578:.1f}평)"
                )
                t_cols = [
                    "deal_date", "sido", "sgg", "umd", "apt_name",
                    "floor", "전용면적(㎡)", "거래금액(표기)", "평당가(만원)",
                    "build_year", "dealing_gbn"
                ]
                t_rename = {
                    "deal_date": "계약일자", "sido": "시도", "sgg": "시군구", "umd": "읍면동",
                    "apt_name": "아파트 단지명", "floor": "층수", "build_year": "건축년도",
                    "dealing_gbn": "거래유형"
                }
                valid_t_cols = [c for c in t_cols if c in trade_display.columns]
                t_table = trade_display[valid_t_cols].rename(columns=t_rename)

                st.dataframe(t_table, width="stretch", hide_index=True, height=350)

                t_csv = t_table.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label=f"📥 {selected_date} 매매 실거래 CSV 다운로드",
                    data=t_csv,
                    file_name=f"apt_trades_{selected_date}.csv",
                    mime="text/csv",
                    key="daily_trade_csv"
                )

        with tab_rent:
            if daily_rents.empty:
                st.info(f"{selected_date}에 등록된 전월세 실거래 내역이 없습니다.")
            else:
                rent_display = daily_rents.copy()
                rent_display["보증금(표기)"] = rent_display["deposit"].apply(format_korean_currency)
                rent_display["월세(만원)"] = rent_display["monthly_rent"].apply(
                    lambda x: f"{x:,}만원" if x > 0 else "전세"
                )
                rent_display["전용면적(㎡)"] = rent_display["exclusive_area"].apply(
                    lambda x: f"{x:.2f}㎡ ({x/3.30578:.1f}평)"
                )
                r_cols = [
                    "deal_date", "sido", "sgg", "umd", "apt_name",
                    "rent_type", "floor", "전용면적(㎡)", "보증금(표기)", "월세(만원)",
                    "build_year", "contract_type"
                ]
                r_rename = {
                    "deal_date": "계약일자", "sido": "시도", "sgg": "시군구", "umd": "읍면동",
                    "apt_name": "아파트 단지명", "rent_type": "구분", "floor": "층수",
                    "build_year": "건축년도", "contract_type": "계약구분"
                }
                valid_r_cols = [c for c in r_cols if c in rent_display.columns]
                r_table = rent_display[valid_r_cols].rename(columns=r_rename)

                st.dataframe(r_table, width="stretch", hide_index=True, height=350)

                r_csv = r_table.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label=f"📥 {selected_date} 전월세 실거래 CSV 다운로드",
                    data=r_csv,
                    file_name=f"apt_rents_{selected_date}.csv",
                    mime="text/csv",
                    key="daily_rent_csv"
                )
