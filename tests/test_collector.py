import datetime
import pytest
from src.collector import Collector

def test_get_target_months_month_boundary():
    collector = Collector(api_key="mock_key")
    # 월초 (예: 10월 3일): 당월 202610 + 전월 202609
    target = datetime.date(2026, 10, 3)
    months = collector.get_target_months(target_date=target)
    assert "202610" in months
    assert "202609" in months
    assert len(months) == 2

    # 월말 (예: 10월 25일): 당월 202610만 해당
    target_mid = datetime.date(2026, 10, 25)
    months_mid = collector.get_target_months(target_date=target_mid)
    assert months_mid == ["202610"]

    # 연초 (예: 2027년 1월 2일): 당월 202701 + 전월 202612
    target_year = datetime.date(2027, 1, 2)
    months_year = collector.get_target_months(target_date=target_year)
    assert "202701" in months_year
    assert "202612" in months_year


def test_cutoff_date_calculation():
    collector = Collector(api_key="mock_key")
    target = datetime.date(2026, 10, 7)
    # 최근 7일(10월 1일 ~ 10월 7일) -> cutoff_date는 10월 1일
    cutoff = collector.get_cutoff_date(target_date=target)
    assert cutoff == "2026-10-01"


def test_collector_mock_run(tmp_path, monkeypatch):
    db_file = str(tmp_path / "mock.db")
    collector = Collector(api_key="mock_key", db_path=db_file)

    sample_trades = [{
        "deal_date": "2026-10-05", "sido": "서울특별시", "sgg": "종로구",
        "sgg_cd": "11110", "umd": "청운동", "apt_name": "테스트아파트",
        "deal_amount": 100000, "exclusive_area": 84.0, "pyeong": 25.4,
        "price_per_pyeong": 3937, "floor": 5, "build_year": 2015,
        "buyer_gbn": "개인", "dealing_gbn": "중개거래"
    }]
    sample_rents = [{
        "deal_date": "2026-10-05", "sido": "서울특별시", "sgg": "종로구",
        "sgg_cd": "11110", "umd": "청운동", "apt_name": "테스트아파트",
        "deposit": 50000, "monthly_rent": 0, "rent_type": "전세",
        "exclusive_area": 84.0, "pyeong": 25.4, "floor": 5,
        "build_year": 2015, "contract_type": "신규"
    }]

    # Mock collect_region with matching signature
    monkeypatch.setattr(collector, "collect_region", lambda reg, months, cutoff=None, max_date=None: (sample_trades, sample_rents))

    test_region = [{"sido": "서울특별시", "sgg": "종로구", "code": "11110"}]
    summary = collector.run(target_date=datetime.date(2026, 10, 7), regions=test_region)

    assert summary["trades_collected"] == 1
    assert summary["rents_collected"] == 1
    assert summary["db_summary"]["trade_count"] == 1
    assert summary["db_summary"]["rent_count"] == 1
