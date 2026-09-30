import os
import sqlite3
import pytest
from src.db import DatabaseManager

def test_daily_analysis_crud(tmp_path):
    db_file = str(tmp_path / "test_analysis.db")
    db = DatabaseManager(db_path=db_file)
    db.init_db()

    # 1. 초기 상태 조회 (없음)
    assert db.get_daily_analysis("2026-09-30") is None

    # 2. 신규 저장
    db.save_daily_analysis(
        deal_date="2026-09-30",
        headline="서울 강남권 신고가 행진 속 지방 완만한 회복세",
        summary_markdown="### 1. 개요\n오늘 총 120건의 실거래가 집계되었습니다.",
        model_name="gemini-1.5-flash",
        trade_count=50,
        rent_count=70
    )

    # 3. 조회 검증
    res = db.get_daily_analysis("2026-09-30")
    assert res is not None
    assert res["deal_date"] == "2026-09-30"
    assert res["headline"] == "서울 강남권 신고가 행진 속 지방 완만한 회복세"
    assert "총 120건" in res["summary_markdown"]
    assert res["model_name"] == "gemini-1.5-flash"
    assert res["trade_count"] == 50
    assert res["rent_count"] == 70

    # 4. 덮어쓰기 (재생성 시 업데이트)
    db.save_daily_analysis(
        deal_date="2026-09-30",
        headline="업데이트된 헤드라인",
        summary_markdown="업데이트된 마크다운 내용",
        model_name="gemini-1.5-flash",
        trade_count=55,
        rent_count=75
    )

    updated = db.get_daily_analysis("2026-09-30")
    assert updated["headline"] == "업데이트된 헤드라인"
    assert updated["summary_markdown"] == "업데이트된 마크다운 내용"
    assert updated["trade_count"] == 55


def test_get_available_dates(tmp_path):
    db_file = str(tmp_path / "test_dates.db")
    db = DatabaseManager(db_path=db_file)
    db.init_db()

    # 빈 DB
    assert db.get_available_dates() == []

    # 거래 데이터 삽입
    sample_trades = [
        {"deal_date": "2026-09-28", "sido": "서울", "sgg": "강남구", "sgg_cd": "11680", "umd": "역삼동", "apt_name": "A", "deal_amount": 100000, "exclusive_area": 84.0, "pyeong": 25.4, "price_per_pyeong": 3937, "floor": 5, "build_year": 2020, "buyer_gbn": "-", "dealing_gbn": "-"},
        {"deal_date": "2026-09-30", "sido": "서울", "sgg": "서초구", "sgg_cd": "11650", "umd": "반포동", "apt_name": "B", "deal_amount": 200000, "exclusive_area": 84.0, "pyeong": 25.4, "price_per_pyeong": 7874, "floor": 10, "build_year": 2021, "buyer_gbn": "-", "dealing_gbn": "-"},
    ]
    sample_rents = [
        {"deal_date": "2026-09-29", "sido": "서울", "sgg": "송파구", "sgg_cd": "11710", "umd": "잠실동", "apt_name": "C", "deposit": 80000, "monthly_rent": 0, "rent_type": "전세", "exclusive_area": 84.0, "pyeong": 25.4, "floor": 7, "build_year": 2019, "contract_type": "-"}
    ]

    db.insert_trades(sample_trades)
    db.insert_rents(sample_rents)

    # 날짜 목록 최신순 정렬 확인 (2026-09-30, 2026-09-29, 2026-09-28)
    dates = db.get_available_dates()
    assert dates == ["2026-09-30", "2026-09-29", "2026-09-28"]
