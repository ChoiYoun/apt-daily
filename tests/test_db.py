import os
import pytest
import pandas as pd
from src.db import DatabaseManager

@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_real_estate.db")
    manager = DatabaseManager(db_file)
    manager.init_db()
    return manager

def test_insert_and_cleanup_trades(temp_db):
    sample_trade = {
        "deal_date": "2026-09-28",
        "sido": "서울특별시",
        "sgg": "강남구",
        "sgg_cd": "11680",
        "umd": "개포동",
        "apt_name": "개포자이",
        "deal_amount": 250000,
        "exclusive_area": 84.5,
        "pyeong": 25.56,
        "price_per_pyeong": 9780,
        "floor": 10,
        "build_year": 2020,
        "buyer_gbn": "개인",
        "dealing_gbn": "중개거래"
    }
    inserted = temp_db.insert_trades([sample_trade])
    assert inserted == 1

    # 중복 삽입 시 무시 검증 (UNIQUE 제약)
    assert temp_db.insert_trades([sample_trade]) == 0

    # 조회 검증
    df = temp_db.query_trades(sido="서울특별시", sgg="강남구")
    assert len(df) == 1
    assert df.iloc[0]["apt_name"] == "개포자이"
    assert df.iloc[0]["deal_amount"] == 250000

    # 롤링 7일 삭제 검증
    del_trades, _ = temp_db.cleanup_old_data(cutoff_date="2026-09-29")
    assert del_trades == 1
    assert len(temp_db.query_trades()) == 0

def test_insert_and_cleanup_rents(temp_db):
    sample_rent = {
        "deal_date": "2026-09-28",
        "sido": "서울특별시",
        "sgg": "서초구",
        "sgg_cd": "11650",
        "umd": "반포동",
        "apt_name": "래미안원베일리",
        "deposit": 150000,
        "monthly_rent": 0,
        "rent_type": "전세",
        "exclusive_area": 84.9,
        "pyeong": 25.68,
        "floor": 15,
        "build_year": 2023,
        "contract_type": "신규"
    }
    inserted = temp_db.insert_rents([sample_rent])
    assert inserted == 1

    # 전세 필터 조회
    df = temp_db.query_rents(rent_type="전세")
    assert len(df) == 1
    assert df.iloc[0]["deposit"] == 150000

    # 월세 필터 조회 (0건)
    assert len(temp_db.query_rents(rent_type="월세")) == 0

    # 롤링 삭제
    _, del_rents = temp_db.cleanup_old_data(cutoff_date="2026-09-29")
    assert del_rents == 1
    assert len(temp_db.query_rents()) == 0
