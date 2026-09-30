"""최근 7일 전국 아파트 매매 및 전월세 실거래가 수집 파이프라인 모듈"""

import os
import json
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Tuple
from dotenv import load_dotenv

from src.regions import REGIONS
from src.db import DatabaseManager
from src.api import ApiClient
from src.parser import parse_trade_xml, parse_rent_xml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Collector:
    """전국 250개 시군구 매매 및 전월세 실거래가 수집 오케스트레이터"""

    def __init__(self, api_key: str, db_path: str = "data/real_estate.db", max_workers: int = 5):
        if not api_key:
            raise ValueError("API 키가 제공되지 않았습니다.")
        self.api_key = api_key
        self.db_path = db_path
        self.max_workers = max_workers
        self.api_client = ApiClient(service_key=api_key)
        self.db_manager = DatabaseManager(db_path=db_path)

    @classmethod
    def from_env(cls, db_path: str = "data/real_estate.db", max_workers: int = 5) -> "Collector":
        """환경변수(.env)에서 API 키를 읽어 인스턴스 생성"""
        load_dotenv()
        key = os.environ.get("DATA_GO_KR_API_KEY")
        if not key:
            raise ValueError("환경변수 DATA_GO_KR_API_KEY를 찾을 수 없습니다.")
        return cls(api_key=key, db_path=db_path, max_workers=max_workers)

    def get_target_months(self, target_date: Optional[datetime.date] = None) -> List[str]:
        """최근 7일 기간이 걸쳐 있는 YYYYMM 목록 계산 (월 경계 대응)"""
        end_date = target_date or datetime.date.today()
        start_date = end_date - datetime.timedelta(days=6)

        months = set()
        current = start_date
        while current <= end_date:
            months.add(f"{current.year:04d}{current.month:02d}")
            current += datetime.timedelta(days=1)

        return sorted(list(months))

    def get_cutoff_date(self, target_date: Optional[datetime.date] = None) -> str:
        """최근 7일 윈도우의 시작일 (YYYY-MM-DD) 반환"""
        end_date = target_date or datetime.date.today()
        start_date = end_date - datetime.timedelta(days=6)
        return start_date.strftime("%Y-%m-%d")

    def collect_region(
        self,
        region: Dict[str, str],
        months: List[str],
        cutoff_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """1개 시군구에 대해 매매 및 전월세 데이터 조회 및 7일 필터링"""
        trades = []
        rents = []
        code = region["code"]

        for month in months:
            # 1. 매매 수집
            try:
                trade_xml = self.api_client.fetch_trades(lawd_cd=code, deal_ymd=month)
                parsed_trades = parse_trade_xml(trade_xml, region)
                for t in parsed_trades:
                    if cutoff_date and t["deal_date"] < cutoff_date:
                        continue
                    if max_date and t["deal_date"] > max_date:
                        continue
                    trades.append(t)
            except Exception as e:
                logger.warning(f"[{region['sido']} {region['sgg']}][매매] 수집 실패 ({month}): {e}")

            # 2. 전월세 수집
            try:
                rent_xml = self.api_client.fetch_rents(lawd_cd=code, deal_ymd=month)
                parsed_rents = parse_rent_xml(rent_xml, region)
                for r in parsed_rents:
                    if cutoff_date and r["deal_date"] < cutoff_date:
                        continue
                    if max_date and r["deal_date"] > max_date:
                        continue
                    rents.append(r)
            except Exception as e:
                logger.warning(f"[{region['sido']} {region['sgg']}][전월세] 수집 실패 ({month}): {e}")

        return trades, rents

    def run(
        self,
        target_date: Optional[datetime.date] = None,
        regions: Optional[List[Dict[str, str]]] = None
    ) -> Dict:
        """전체 수집 프로세스 실행 및 DB 갱신"""
        target = target_date or datetime.date.today()
        months = self.get_target_months(target)
        cutoff_date = self.get_cutoff_date(target)
        max_date = target.strftime("%Y-%m-%d")
        target_regions = regions or REGIONS

        logger.info(f"=== 실거래가 수집 시작 ===")
        logger.info(f"수집 기준일: {max_date} (최근 7일 윈도우: {cutoff_date} ~ {max_date})")
        logger.info(f"조회 대상 월: {months}, 대상 지역 수: {len(target_regions)}개 시군구")

        # 1. DB 초기화
        self.db_manager.init_db()

        # 2. 병렬 수집
        all_trades = []
        all_rents = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_region = {
                executor.submit(self.collect_region, reg, months, cutoff_date, max_date): reg
                for reg in target_regions
            }

            for future in as_completed(future_to_region):
                reg = future_to_region[future]
                try:
                    t_list, r_list = future.result()
                    all_trades.extend(t_list)
                    all_rents.extend(r_list)
                except Exception as e:
                    logger.error(f"지역 {reg['sgg']} 처리 중 예외 발생: {e}")

        logger.info(f"수집 완료: 매매 {len(all_trades)}건, 전월세 {len(all_rents)}건")

        # 3. DB 적재
        inserted_trades = self.db_manager.insert_trades(all_trades)
        inserted_rents = self.db_manager.insert_rents(all_rents)
        logger.info(f"DB 신규 삽입: 매매 {inserted_trades}건, 전월세 {inserted_rents}건")

        # 4. 과거 롤링 데이터 정리
        del_trades, del_rents = self.db_manager.cleanup_old_data(cutoff_date)
        logger.info(f"과거 롤링 데이터 정리: 매매 {del_trades}건 삭제, 전월세 {del_rents}건 삭제")

        # 5. 메타데이터 저장
        db_summary = self.db_manager.get_summary()
        meta_data = {
            "last_updated": datetime.datetime.now().isoformat(),
            "target_date": max_date,
            "cutoff_date": cutoff_date,
            "trades_collected": len(all_trades),
            "rents_collected": len(all_rents),
            "trades_inserted": inserted_trades,
            "rents_inserted": inserted_rents,
            "db_summary": db_summary,
        }

        meta_path = os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)

        logger.info(f"메타데이터 저장 완료: {meta_path}")
        return meta_data


if __name__ == "__main__":
    collector = Collector.from_env()
    collector.run()
