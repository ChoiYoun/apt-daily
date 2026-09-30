"""공공데이터포털 국토교통부 아파트 매매 및 전월세 OpenAPI 클라이언트 모듈"""

import time
import requests
from typing import Optional


class ApiClient:
    """국토교통부 아파트 실거래가 OpenAPI 통신 클라이언트"""

    TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

    def __init__(self, service_key: str, max_retries: int = 3, timeout: int = 15):
        self.service_key = service_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.trade_url = self.TRADE_URL
        self.rent_url = self.RENT_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _fetch(self, url: str, lawd_cd: str, deal_ymd: str, page_no: int = 1, num_of_rows: int = 1000) -> str:
        """API 호출 공통 메서드 (지수 백오프 재시도 포함)"""
        params = {
            "serviceKey": self.service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
        }

        last_error = None
        last_resp_text = ""
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.encoding = "utf-8"
                last_resp_text = resp.text

                if resp.status_code == 200:
                    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS_PER_SECOND" in resp.text:
                        time.sleep(1.2 * (attempt + 1))
                        continue
                    return resp.text
                elif resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.2 * (2 ** attempt))
                    continue
                else:
                    return resp.text
            except (requests.RequestException, TimeoutError) as e:
                last_error = e
                time.sleep(1.2 * (2 ** attempt))

        if last_error:
            raise last_error
        return last_resp_text

    def fetch_trades(self, lawd_cd: str, deal_ymd: str, page_no: int = 1, num_of_rows: int = 1000) -> str:
        """아파트 매매 실거래가 원본 XML 조회"""
        return self._fetch(self.trade_url, lawd_cd, deal_ymd, page_no, num_of_rows)

    def fetch_rents(self, lawd_cd: str, deal_ymd: str, page_no: int = 1, num_of_rows: int = 1000) -> str:
        """아파트 전월세 실거래가 원본 XML 조회"""
        return self._fetch(self.rent_url, lawd_cd, deal_ymd, page_no, num_of_rows)
