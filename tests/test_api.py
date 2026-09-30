import os
import pytest
from src.api import ApiClient

def test_api_client_initialization():
    client = ApiClient(service_key="test_key")
    assert client.service_key == "test_key"
    assert "RTMSDataSvcAptTrade" in client.trade_url
    assert "RTMSDataSvcAptRent" in client.rent_url

def test_api_client_real_fetch():
    api_key = os.environ.get("DATA_GO_KR_API_KEY")
    if not api_key:
        pytest.skip("No DATA_GO_KR_API_KEY found")

    client = ApiClient(service_key=api_key)
    # 종로구 (11110) 2024년 9월 매매 조회
    trade_xml = client.fetch_trades(lawd_cd="11110", deal_ymd="202409", num_of_rows=5)
    assert "<resultCode>000</resultCode>" in trade_xml
    assert "<aptNm>" in trade_xml

    # 종로구 (11110) 2024년 9월 전월세 조회
    rent_xml = client.fetch_rents(lawd_cd="11110", deal_ymd="202409", num_of_rows=5)
    assert "<resultCode>000</resultCode>" in rent_xml
    assert "<deposit>" in rent_xml
