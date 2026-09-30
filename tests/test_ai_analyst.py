import pytest
import pandas as pd
from src.ai_analyst import prepare_daily_context, build_analyst_prompt

def test_prepare_daily_context_normal():
    trades = pd.DataFrame([
        {
            "deal_date": "2026-09-30", "sido": "서울특별시", "sgg": "강남구",
            "apt_name": "압구정현대", "deal_amount": 450000, "exclusive_area": 114.0,
            "pyeong": 34.5, "price_per_pyeong": 13043, "floor": 10
        },
        {
            "deal_date": "2026-09-30", "sido": "경기도", "sgg": "화성시",
            "apt_name": "동탄역롯데", "deal_amount": 120000, "exclusive_area": 84.0,
            "pyeong": 25.4, "price_per_pyeong": 4724, "floor": 20
        },
    ])

    rents = pd.DataFrame([
        {
            "deal_date": "2026-09-30", "sido": "서울특별시", "sgg": "서초구",
            "apt_name": "반포자이", "deposit": 180000, "monthly_rent": 0, "rent_type": "전세",
            "exclusive_area": 84.0, "pyeong": 25.4, "floor": 12
        },
        {
            "deal_date": "2026-09-30", "sido": "경기도", "sgg": "수원시 영통구",
            "apt_name": "광교호수마을", "deposit": 30000, "monthly_rent": 120, "rent_type": "월세",
            "exclusive_area": 84.0, "pyeong": 25.4, "floor": 8
        },
    ])

    ctx = prepare_daily_context(trades, rents)

    # 매매 검증
    assert ctx["trade_count"] == 2
    assert ctx["avg_trade_price"] == 285000
    assert len(ctx["top_trades"]) == 2
    assert ctx["top_trades"][0]["apt_name"] == "압구정현대"
    assert ctx["top_trades"][0]["deal_amount"] == 450000

    # 전월세 검증
    assert ctx["rent_count"] == 2
    assert ctx["jeonse_count"] == 1
    assert ctx["wolse_count"] == 1
    assert ctx["avg_jeonse_deposit"] == 180000
    assert ctx["avg_wolse_rent"] == 120
    assert len(ctx["top_rents"]) == 2
    assert ctx["top_rents"][0]["apt_name"] == "반포자이"


def test_prepare_daily_context_empty():
    empty_trades = pd.DataFrame()
    empty_rents = pd.DataFrame()

    ctx = prepare_daily_context(empty_trades, empty_rents)
    assert ctx["trade_count"] == 0
    assert ctx["avg_trade_price"] == 0
    assert ctx["top_trades"] == []
    assert ctx["rent_count"] == 0
    assert ctx["jeonse_count"] == 0
    assert ctx["wolse_count"] == 0


def test_build_analyst_prompt():
    ctx = {
        "trade_count": 25,
        "avg_trade_price": 65000,
        "avg_trade_pyeong_price": 2500,
        "top_trades": [
            {"apt_name": "압구정현대", "region": "서울 강남구", "deal_amount_str": "45억원", "area_str": "114.0㎡(10층)"}
        ],
        "top_trade_regions": [("경기 화성시", 8), ("서울 송파구", 5)],
        "rent_count": 40,
        "jeonse_count": 28,
        "wolse_count": 12,
        "jeonse_ratio": 70.0,
        "avg_jeonse_deposit": 35000,
        "avg_wolse_rent": 85,
        "top_rents": [
            {"apt_name": "반포자이", "region": "서울 서초구", "deposit_str": "18억원", "monthly_rent": 0, "rent_type": "전세"}
        ],
    }

    prompt = build_analyst_prompt(ctx, deal_date="2026-09-30")

    assert "2026-09-30" in prompt
    assert "부동산 수석 시장 애널리스트" in prompt
    assert "압구정현대" in prompt
    assert "45억원" in prompt
    assert "반포자이" in prompt
    assert "한줄 마켓 헤드라인" in prompt
    assert "관전 포인트" in prompt
