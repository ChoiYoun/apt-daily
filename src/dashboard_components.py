"""Streamlit 대시보드 지표 계산, 통화 서식 및 Plotly 시각화 컴포넌트 모듈"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Dict, Any


def format_korean_currency(amount_in_manwon: Optional[int]) -> str:
    """만원 단위 숫자를 'X억 Y,YYY만원' 형태의 직관적인 한글 표기로 변환"""
    if amount_in_manwon is None or pd.isna(amount_in_manwon):
        return "-"
    if amount_in_manwon == 0:
        return "0원"

    amount = int(amount_in_manwon)
    eok = amount // 10000
    man = amount % 10000

    if eok > 0 and man > 0:
        return f"{eok}억 {man:,}만원"
    elif eok > 0 and man == 0:
        return f"{eok}억원"
    else:
        return f"{man:,}만원"


def compute_trade_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """매매 데이터프레임으로부터 상단 KPI 지표 요약 산출"""
    if df.empty:
        return {
            "total_deals": 0,
            "avg_price": 0,
            "avg_pyeong_price": 0,
            "max_deal": None,
            "top_sgg": "-",
        }

    total_deals = len(df)
    avg_price = int(df["deal_amount"].mean())
    avg_pyeong_price = int(df["price_per_pyeong"].mean()) if "price_per_pyeong" in df else 0

    max_idx = df["deal_amount"].idxmax()
    max_row = df.loc[max_idx]
    max_deal = {
        "apt_name": max_row.get("apt_name", "-"),
        "deal_amount": int(max_row.get("deal_amount", 0)),
        "exclusive_area": float(max_row.get("exclusive_area", 0.0)),
        "pyeong": float(max_row.get("pyeong", 0.0)),
        "floor": max_row.get("floor", "-"),
        "deal_date": max_row.get("deal_date", "-"),
        "sgg": max_row.get("sgg", "-"),
    }

    top_sgg = df["sgg"].value_counts().index[0] if "sgg" in df and not df["sgg"].empty else "-"

    return {
        "total_deals": total_deals,
        "avg_price": avg_price,
        "avg_pyeong_price": avg_pyeong_price,
        "max_deal": max_deal,
        "top_sgg": top_sgg,
    }


def compute_rent_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """전월세 데이터프레임으로부터 상단 KPI 지표 요약 산출"""
    if df.empty:
        return {
            "total_deals": 0,
            "jeonse_count": 0,
            "wolse_count": 0,
            "avg_jeonse_deposit": 0,
            "avg_wolse_rent": 0,
            "max_deposit": None,
            "top_sgg": "-",
        }

    total_deals = len(df)
    jeonse_df = df[df["rent_type"] == "전세"]
    wolse_df = df[df["rent_type"] == "월세"]

    jeonse_count = len(jeonse_df)
    wolse_count = len(wolse_df)

    avg_jeonse_deposit = int(jeonse_df["deposit"].mean()) if not jeonse_df.empty else 0
    avg_wolse_rent = int(wolse_df["monthly_rent"].mean()) if not wolse_df.empty else 0

    max_idx = df["deposit"].idxmax()
    max_row = df.loc[max_idx]
    max_deposit = {
        "apt_name": max_row.get("apt_name", "-"),
        "deposit": int(max_row.get("deposit", 0)),
        "monthly_rent": int(max_row.get("monthly_rent", 0)),
        "rent_type": max_row.get("rent_type", "-"),
        "exclusive_area": float(max_row.get("exclusive_area", 0.0)),
        "deal_date": max_row.get("deal_date", "-"),
        "sgg": max_row.get("sgg", "-"),
    }

    top_sgg = df["sgg"].value_counts().index[0] if "sgg" in df and not df["sgg"].empty else "-"

    return {
        "total_deals": total_deals,
        "jeonse_count": jeonse_count,
        "wolse_count": wolse_count,
        "avg_jeonse_deposit": avg_jeonse_deposit,
        "avg_wolse_rent": avg_wolse_rent,
        "max_deposit": max_deposit,
        "top_sgg": top_sgg,
    }


def create_daily_trend_chart(df: pd.DataFrame, date_col: str = "deal_date") -> go.Figure:
    """최근 7일간 일자별 거래량 막대 차트 및 추세선"""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="거래 데이터가 없습니다.")
        return fig

    daily_counts = df.groupby(date_col).size().reset_index(name="count")
    daily_counts = daily_counts.sort_values(by=date_col)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily_counts[date_col],
        y=daily_counts["count"],
        name="일일 거래량",
        marker_color="#2563EB",
        text=daily_counts["count"],
        textposition="auto",
    ))
    fig.add_trace(go.Scatter(
        x=daily_counts[date_col],
        y=daily_counts["count"],
        mode="lines+markers",
        name="추세",
        line=dict(color="#EF4444", width=2),
    ))

    fig.update_layout(
        title="📅 최근 일자별 거래량 추이",
        xaxis_title="계약일자",
        yaxis_title="거래 건수 (건)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def create_top_regions_chart(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """시군구별 거래량 상위 TOP N 가로 막대 차트"""
    if df.empty or "sgg" not in df:
        fig = go.Figure()
        fig.update_layout(title="지역 데이터가 없습니다.")
        return fig

    top_regions = df.groupby(["sido", "sgg"]).size().reset_index(name="count")
    top_regions["region_label"] = top_regions["sido"] + " " + top_regions["sgg"]
    top_regions = top_regions.sort_values(by="count", ascending=True).tail(top_n)

    fig = go.Figure(go.Bar(
        x=top_regions["count"],
        y=top_regions["region_label"],
        orientation="h",
        marker_color="#10B981",
        text=top_regions["count"],
        textposition="auto",
    ))

    fig.update_layout(
        title=f"🏆 시군구별 거래량 TOP {top_n}",
        xaxis_title="거래 건수 (건)",
        yaxis_title="지역",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_price_distribution_chart(df: pd.DataFrame, price_col: str = "deal_amount", title: str = "거래금액 분포") -> go.Figure:
    """거래 금액대별 분포 히스토그램"""
    if df.empty or price_col not in df:
        fig = go.Figure()
        fig.update_layout(title="금액 데이터가 없습니다.")
        return fig

    # 억원 단위로 환산하여 표현
    eok_series = df[price_col] / 10000.0

    fig = px.histogram(
        x=eok_series,
        nbins=25,
        title=f"📊 {title} (억원 단위)",
        labels={"x": "금액 (억원)", "y": "건수"},
        color_discrete_sequence=["#8B5CF6"]
    )
    fig.update_layout(
        xaxis_title="금액 (억원)",
        yaxis_title="건수 (건)",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def create_pyeong_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """평형대별 비중 파이 차트"""
    if df.empty or "pyeong" not in df:
        fig = go.Figure()
        fig.update_layout(title="면적 데이터가 없습니다.")
        return fig

    def get_pyeong_group(p):
        if p < 20:
            return "소형 (<20평)"
        elif p < 30:
            return "중소형 (20~29평)"
        elif p < 40:
            return "중형 (30~39평)"
        elif p < 50:
            return "중대형 (40~49평)"
        else:
            return "대형 (50평+)"

    pyeong_groups = df["pyeong"].apply(get_pyeong_group).value_counts().reset_index()
    pyeong_groups.columns = ["group", "count"]

    fig = px.pie(
        pyeong_groups,
        names="group",
        values="count",
        title="📐 평형대별 거래 비중",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    return fig
