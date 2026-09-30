"""SQLite 데이터베이스 스키마 정의 및 트랜잭션 관리 모듈"""

import os
import sqlite3
import pandas as pd
from typing import Optional, List, Dict, Tuple


class DatabaseManager:
    """아파트 매매 및 전월세 실거래가 SQLite 데이터베이스 관리 클래스"""

    def __init__(self, db_path: str = "data/real_estate.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """테이블 스키마 및 인덱스 초기화"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 매매 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS apt_trade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_date TEXT NOT NULL,
                sido TEXT NOT NULL,
                sgg TEXT NOT NULL,
                sgg_cd TEXT NOT NULL,
                umd TEXT NOT NULL,
                apt_name TEXT NOT NULL,
                deal_amount INTEGER NOT NULL,
                exclusive_area REAL NOT NULL,
                pyeong REAL NOT NULL,
                price_per_pyeong INTEGER NOT NULL,
                floor INTEGER,
                build_year INTEGER,
                buyer_gbn TEXT,
                dealing_gbn TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sgg_cd, umd, apt_name, deal_date, deal_amount, exclusive_area, floor)
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_date ON apt_trade(deal_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_region ON apt_trade(sido, sgg);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_apt ON apt_trade(apt_name);")

            # 2. 전월세 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS apt_rent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_date TEXT NOT NULL,
                sido TEXT NOT NULL,
                sgg TEXT NOT NULL,
                sgg_cd TEXT NOT NULL,
                umd TEXT NOT NULL,
                apt_name TEXT NOT NULL,
                deposit INTEGER NOT NULL,
                monthly_rent INTEGER NOT NULL,
                rent_type TEXT NOT NULL,
                exclusive_area REAL NOT NULL,
                pyeong REAL NOT NULL,
                floor INTEGER,
                build_year INTEGER,
                contract_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sgg_cd, umd, apt_name, deal_date, deposit, monthly_rent, exclusive_area, floor)
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rent_date ON apt_rent(deal_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rent_region ON apt_rent(sido, sgg);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rent_apt ON apt_rent(apt_name);")

            # 3. 일자별 AI 애널리스트 분석 캐시 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_analysis (
                deal_date TEXT PRIMARY KEY,
                headline TEXT NOT NULL,
                summary_markdown TEXT NOT NULL,
                model_name TEXT NOT NULL,
                trade_count INTEGER NOT NULL,
                rent_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_date ON daily_analysis(deal_date);")

            conn.commit()

    def insert_trades(self, trades: List[Dict]) -> int:
        """매매 실거래 데이터 일괄 삽입 (중복 무시)"""
        if not trades:
            return 0

        sql = """
        INSERT OR IGNORE INTO apt_trade (
            deal_date, sido, sgg, sgg_cd, umd, apt_name,
            deal_amount, exclusive_area, pyeong, price_per_pyeong,
            floor, build_year, buyer_gbn, dealing_gbn
        ) VALUES (
            :deal_date, :sido, :sgg, :sgg_cd, :umd, :apt_name,
            :deal_amount, :exclusive_area, :pyeong, :price_per_pyeong,
            :floor, :build_year, :buyer_gbn, :dealing_gbn
        )
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, trades)
            inserted_count = cursor.rowcount
            conn.commit()
            return inserted_count

    def insert_rents(self, rents: List[Dict]) -> int:
        """전월세 실거래 데이터 일괄 삽입 (중복 무시)"""
        if not rents:
            return 0

        sql = """
        INSERT OR IGNORE INTO apt_rent (
            deal_date, sido, sgg, sgg_cd, umd, apt_name,
            deposit, monthly_rent, rent_type, exclusive_area, pyeong,
            floor, build_year, contract_type
        ) VALUES (
            :deal_date, :sido, :sgg, :sgg_cd, :umd, :apt_name,
            :deposit, :monthly_rent, :rent_type, :exclusive_area, :pyeong,
            :floor, :build_year, :contract_type
        )
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, rents)
            inserted_count = cursor.rowcount
            conn.commit()
            return inserted_count

    def cleanup_old_data(self, cutoff_date: str) -> Tuple[int, int]:
        """지정된 기준일(cutoff_date) 이전의 과거 데이터 삭제 및 VACUUM 실행"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 매매 삭제
            cursor.execute("DELETE FROM apt_trade WHERE deal_date < ?", (cutoff_date,))
            del_trades = cursor.rowcount

            # 전월세 삭제
            cursor.execute("DELETE FROM apt_rent WHERE deal_date < ?", (cutoff_date,))
            del_rents = cursor.rowcount

            conn.commit()

        # VACUUM은 트랜잭션 밖에서 실행
        with self._get_connection() as conn:
            conn.execute("VACUUM;")

        return del_trades, del_rents

    def get_summary(self) -> Dict:
        """현재 DB에 보관된 요약 통계 정보 반환"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*), MIN(deal_date), MAX(deal_date) FROM apt_trade")
            trade_count, min_trade_date, max_trade_date = cursor.fetchone()

            cursor.execute("SELECT COUNT(*), MIN(deal_date), MAX(deal_date) FROM apt_rent")
            rent_count, min_rent_date, max_rent_date = cursor.fetchone()

            return {
                "trade_count": trade_count or 0,
                "rent_count": rent_count or 0,
                "trade_date_range": (min_trade_date, max_trade_date),
                "rent_date_range": (min_rent_date, max_rent_date),
            }

    def query_trades(
        self,
        sido: Optional[str] = None,
        sgg: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        apt_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """조건별 매매 실거래가 검색 쿼리"""
        conditions = ["1=1"]
        params = []

        if sido and sido != "전체":
            conditions.append("sido = ?")
            params.append(sido)
        if sgg and sgg != "전체":
            conditions.append("sgg = ?")
            params.append(sgg)
        if start_date:
            conditions.append("deal_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("deal_date <= ?")
            params.append(end_date)
        if min_price is not None:
            conditions.append("deal_amount >= ?")
            params.append(min_price)
        if max_price is not None:
            conditions.append("deal_amount <= ?")
            params.append(max_price)
        if apt_name:
            conditions.append("apt_name LIKE ?")
            params.append(f"%{apt_name}%")

        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM apt_trade WHERE {where_clause} ORDER BY deal_date DESC, deal_amount DESC"

        with self._get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def query_rents(
        self,
        sido: Optional[str] = None,
        sgg: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        rent_type: Optional[str] = None,
        min_deposit: Optional[int] = None,
        max_deposit: Optional[int] = None,
        apt_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """조건별 전월세 실거래가 검색 쿼리"""
        conditions = ["1=1"]
        params = []

        if sido and sido != "전체":
            conditions.append("sido = ?")
            params.append(sido)
        if sgg and sgg != "전체":
            conditions.append("sgg = ?")
            params.append(sgg)
        if start_date:
            conditions.append("deal_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("deal_date <= ?")
            params.append(end_date)
        if rent_type and rent_type != "전체":
            conditions.append("rent_type = ?")
            params.append(rent_type)
        if min_deposit is not None:
            conditions.append("deposit >= ?")
            params.append(min_deposit)
        if max_deposit is not None:
            conditions.append("deposit <= ?")
            params.append(max_deposit)
        if apt_name:
            conditions.append("apt_name LIKE ?")
            params.append(f"%{apt_name}%")

        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM apt_rent WHERE {where_clause} ORDER BY deal_date DESC, deposit DESC"

        with self._get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def get_daily_analysis(self, deal_date: str) -> Optional[Dict]:
        """지정된 계약일자의 AI 애널리스트 분석 캐시 조회"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT deal_date, headline, summary_markdown, model_name, trade_count, rent_count, created_at, updated_at FROM daily_analysis WHERE deal_date = ?",
                (deal_date,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def save_daily_analysis(
        self,
        deal_date: str,
        headline: str,
        summary_markdown: str,
        model_name: str,
        trade_count: int,
        rent_count: int
    ) -> None:
        """일자별 AI 애널리스트 분석 결과 저장 또는 갱신"""
        sql = """
        INSERT INTO daily_analysis (
            deal_date, headline, summary_markdown, model_name, trade_count, rent_count, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(deal_date) DO UPDATE SET
            headline=excluded.headline,
            summary_markdown=excluded.summary_markdown,
            model_name=excluded.model_name,
            trade_count=excluded.trade_count,
            rent_count=excluded.rent_count,
            updated_at=CURRENT_TIMESTAMP;
        """
        with self._get_connection() as conn:
            conn.execute(sql, (deal_date, headline, summary_markdown, model_name, trade_count, rent_count))
            conn.commit()

    def get_available_dates(self) -> List[str]:
        """DB에 존재하는 계약일자 목록을 최신순으로 반환"""
        sql = """
        SELECT DISTINCT deal_date FROM apt_trade
        UNION
        SELECT DISTINCT deal_date FROM apt_rent
        ORDER BY deal_date DESC;
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [r[0] for r in rows if r[0]]

