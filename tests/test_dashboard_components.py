import pytest
import pandas as pd
from src.dashboard_components import (
    format_korean_currency,
    compute_trade_kpis,
    compute_rent_kpis
)

def test_format_korean_currency():
    assert format_korean_currency(125000) == "12억 5,000만원"
    assert format_korean_currency(200000) == "20억원"
    assert format_korean_currency(7500) == "7,500만원"
    assert format_korean_currency(0) == "0원"
    assert format_korean_currency(None) == "-"

def test_compute_trade_kpis():
    df = pd.DataFrame([
        {
            "deal_amount": 100000,
            "price_per_pyeong": 4000,
            "apt_name": "A아파트",
            "exclusive_area": 84.0,
            "floor": 5,
            "sgg": "강남구"
        },
        {
            "deal_amount": 250000,
            "price_per_pyeong": 8000,
            "apt_name": "B아파트",
            "exclusive_area": 114.0,
            "floor": 15,
            "sgg": "서초구"
        }
    ])
    kpis = compute_trade_kpis(df)
    assert kpis["total_deals"] == 2
    assert kpis["avg_price"] == 175000
    assert kpis["avg_pyeong_price"] == 6000
    assert kpis["max_deal"]["apt_name"] == "B아파트"
    assert kpis["max_deal"]["deal_amount"] == 250000

def test_compute_rent_kpis():
    df = pd.DataFrame([
        {
            "deposit": 100000,
            "monthly_rent": 0,
            "rent_type": "전세",
            "apt_name": "A아파트",
            "exclusive_area": 84.0,
            "floor": 5,
            "sgg": "강남구"
        },
        {
            "deposit": 20000,
            "monthly_rent": 250,
            "rent_type": "월세",
            "apt_name": "B아파트",
            "exclusive_area": 59.0,
            "floor": 10,
            "sgg": "강남구"
        }
    ])
    kpis = compute_rent_kpis(df)
    assert kpis["total_deals"] == 2
    assert kpis["jeonse_count"] == 1
    assert kpis["wolse_count"] == 1
    assert kpis["avg_jeonse_deposit"] == 100000
    assert kpis["avg_wolse_rent"] == 250


def test_top_region_differentiation_by_sido():
    """동명이구(북구)가 여러 시도에 존재할 때 합산되지 않고 시도별로 올바르게 1위가 산출되는지 검증"""
    df = pd.DataFrame([
        {"sido": "부산광역시", "sgg": "북구", "deal_amount": 30000},
        {"sido": "부산광역시", "sgg": "북구", "deal_amount": 31000},
        {"sido": "대구광역시", "sgg": "북구", "deal_amount": 25000},
        {"sido": "대구광역시", "sgg": "북구", "deal_amount": 26000},
        {"sido": "대구광역시", "sgg": "북구", "deal_amount": 27000},
        {"sido": "서울특별시", "sgg": "강남구", "deal_amount": 150000},
        {"sido": "서울특별시", "sgg": "강남구", "deal_amount": 160000},
        {"sido": "서울특별시", "sgg": "강남구", "deal_amount": 170000},
        {"sido": "서울특별시", "sgg": "강남구", "deal_amount": 180000},
    ])
    kpis = compute_trade_kpis(df)
    # 기존 버그: 북구(2+3=5건)로 강남구(4건)를 제치고 북구가 1위로 오집계
    # 정상 동작: 서울 강남구가 4건으로 1위
    assert kpis["top_sgg"] == "서울 강남구"
    assert kpis["top_sgg_count"] == 4

