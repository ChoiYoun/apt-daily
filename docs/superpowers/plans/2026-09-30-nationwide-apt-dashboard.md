# 전국 아파트 최근 7일 매매/전월세 실거래가 수집 및 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 국토교통부 아파트 매매 및 전월세 실거래가 OpenAPI로부터 최근 7일간의 전국 실거래 데이터를 자동 수집하고, SQLite DB 롤링 보관 및 GitHub Actions 자동화, Streamlit 대시보드로 시각화하는 시스템 구축.

**Architecture:** 전국 250개 시군구 법정동 코드(`LAWD_CD`)를 스레드 풀 기반으로 조회하여 최근 7일 치 거래를 SQLite(`apt_trade`, `apt_rent`)에 UPSERT하고 7일 이전 데이터를 롤링 삭제합니다. GitHub Actions가 매일 한국시간 06:00에 수집 후 DB를 자동 커밋/푸시하며, Streamlit Community Cloud를 통해 100% 무료 서버 비용으로 실시간 탐색 대시보드를 제공합니다.

**Tech Stack:** Python 3.12, `uv`, `sqlite3`, `requests`, `pandas`, `streamlit`, `plotly`, `pytest`, GitHub Actions

**Spec:** [docs/superpowers/specs/2026-09-30-nationwide-apt-dashboard-design.md](file:///c:/Users/student/Downloads/apt-daily/docs/superpowers/specs/2026-09-30-nationwide-apt-dashboard-design.md)

---

## Global Constraints

- **가상환경 도구**: Python 패키지 관리 및 실행은 항상 `uv`만을 사용 (`uv sync`, `uv run pytest`, `uv run streamlit run app.py`).
- **상대경로 준수**: 프로젝트 내 코드 및 설정은 특별한 경우를 제외하고 항상 상대경로를 사용.
- **인증키 보안**: `DATA_GO_KR_API_KEY`는 `.env` 및 GitHub Secrets로 주입하며 저장소 커밋 파일에 직접 하드코딩 금지.
- **롤링 7일 데이터 보관**: SQLite DB 내 데이터는 수집 기준일(`deal_date >= cutoff_date`) 기준 최근 7일만 보관하고 이전 데이터는 매 실행마다 삭제 후 `VACUUM`.
- **배포 및 서버 비용**: GitHub Actions(무료 티어 월 2,000분 중 60분 미만 사용) + Streamlit Community Cloud(무료 배포)로 서버 비용 0원 유지.

---

## Review Focus

1. **월초(1~7일) 수집 시 월 경계 누락**: 오늘이 10월 3일이면 최근 7일(9월 27일~10월 3일)을 확보하기 위해 당월(`202610`)과 전월(`202609`)을 모두 조회해야 함.
2. **API 응답 포맷 예외 처리**: 데이터가 없는 시군구의 빈 `<items/>` 태그, 일시적인 네트워크 지연, 쉼표 포함 거래금액(`"15,000"`), 공백 층수/건축년도에 대한 방어 로직.
3. **복합 고유키 기반 중복 방지**: 동일 거래 건이 재수집되더라도 DB에 중복 저장되지 않도록 `UNIQUE` 제약 및 `INSERT OR IGNORE` 처리.
4. **전세 vs 월세 구분**: 전월세 API에서 `monthlyRent == 0`은 '전세', `monthlyRent > 0`은 '월세'로 명확히 라벨링.
5. **Streamlit 캐싱 및 메모리 보호**: 대시보드 로딩 시 `@st.cache_resource` 및 `@st.cache_data`로 SQLite 연결 및 쿼리 캐시를 적용하여 새로고침 시 즉각 응답 보장.

---

## Task Decomposition

### Task 1: 프로젝트 기반 환경 및 의존성 설정

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: `uv` 기반 Python 패키지 환경 및 테스트 픽스처

- [ ] **Step 1: Write `pyproject.toml` and `.gitignore`**
  - 의존성: `requests`, `pandas`, `streamlit`, `plotly`, `python-dotenv`, `pytest`
  - `.gitignore`에 `.env`, `*.db-journal`, `__pycache__`, `.venv`, `.pytest_cache` 추가

- [ ] **Step 2: Sync environment using uv**
  - Run: `uv sync`
  - Expected: PASS and creates lockfile

- [ ] **Step 3: Write test in `tests/test_env.py` to verify imports and environment**
  ```python
  def test_required_packages_imported():
      import requests
      import pandas
      import streamlit
      import plotly
      import dotenv
      assert True
  ```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_env.py -v`
  - Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add pyproject.toml uv.lock .gitignore .env.example tests/
  git commit -m "chore: setup project dependencies and environment"
  ```

---

### Task 2: 전국 시도 및 시군구 법정동 코드 모듈 (`src/regions.py`)

**Files:**
- Create: `src/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `REGIONS: list[dict[str, str]]` (전국 약 250개 시군구 매핑 `[{"sido": "서울특별시", "sgg": "종로구", "code": "11110"}, ...]`)
  - `get_sido_list() -> list[str]`
  - `get_sgg_list_by_sido(sido: str) -> list[dict[str, str]]`
  - `get_region_by_code(code: str) -> dict[str, str] | None`

- [ ] **Step 1: Write failing test in `tests/test_regions.py`**
  ```python
  from src.regions import get_sido_list, get_sgg_list_by_sido, get_region_by_code, REGIONS

  def test_regions_data_integrity():
      assert len(REGIONS) >= 200
      sidos = get_sido_list()
      assert "서울특별시" in sidos
      assert "경기도" in sidos
      
      seoul_sggs = get_sgg_list_by_sido("서울특별시")
      assert any(r["sgg"] == "강남구" and r["code"] == "11680" for r in seoul_sggs)
      
      region = get_region_by_code("11110")
      assert region is not None
      assert region["sgg"] == "종로구"
  ```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `uv run pytest tests/test_regions.py -v`
  - Expected: FAIL with ModuleNotFoundError: No module named 'src.regions'

- [ ] **Step 3: Implement `src/regions.py`**
  - 대한민국 17개 광역시·도 및 하위 250개 시군구 법정동 앞 5자리 코드 내장 데이터 및 조회 유틸리티 구현.

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_regions.py -v`
  - Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/regions.py tests/test_regions.py
  git commit -m "feat: add nationwide region codes mapping module"
  ```

---

### Task 3: SQLite 데이터베이스 스키마 및 관리자 (`src/db.py`)

**Files:**
- Create: `src/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `DatabaseManager(db_path: str = "data/real_estate.db")`:
    - `init_db() -> None`
    - `insert_trades(trades: list[dict]) -> int`
    - `insert_rents(rents: list[dict]) -> int`
    - `cleanup_old_data(cutoff_date: str) -> tuple[int, int]` (trades_deleted, rents_deleted)
    - `get_summary() -> dict`
    - `query_trades(sido: str = None, sgg: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame`
    - `query_rents(sido: str = None, sgg: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame`

- [ ] **Step 1: Write failing test in `tests/test_db.py`**
  ```python
  import os
  import pytest
  from src.db import DatabaseManager

  @pytest.fixture
  def temp_db(tmp_path):
      db_file = str(tmp_path / "test.db")
      manager = DatabaseManager(db_file)
      manager.init_db()
      return manager

  def test_insert_and_cleanup_trades(temp_db):
      sample_trade = {
          "deal_date": "2026-09-28", "sido": "서울특별시", "sgg": "강남구",
          "sgg_cd": "11680", "umd": "개포동", "apt_name": "개포자이",
          "deal_amount": 250000, "exclusive_area": 84.5, "pyeong": 25.56,
          "price_per_pyeong": 9780, "floor": 10, "build_year": 2020,
          "buyer_gbn": "개인", "dealing_gbn": "중개거래"
      }
      inserted = temp_db.insert_trades([sample_trade])
      assert inserted == 1

      # 중복 삽입 시 무시 검증
      assert temp_db.insert_trades([sample_trade]) == 0

      # 롤링 삭제 검증
      deleted_trades, _ = temp_db.cleanup_old_data(cutoff_date="2026-09-29")
      assert deleted_trades == 1
  ```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `uv run pytest tests/test_db.py -v`
  - Expected: FAIL with ModuleNotFoundError: No module named 'src.db'

- [ ] **Step 3: Implement `src/db.py`**
  - `apt_trade` 및 `apt_rent` 테이블 스키마 생성 및 인덱스 설정
  - `executemany` 기반의 일괄 삽입 및 `INSERT OR IGNORE` 처리
  - 날짜 기준 롤링 데이터 삭제 및 `VACUUM` 실행
  - pandas DataFrame 반환 쿼리 메서드 구현

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_db.py -v`
  - Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/db.py tests/test_db.py
  git commit -m "feat: add SQLite database schema and manager module"
  ```

---

### Task 4: OpenAPI 클라이언트 및 응답 파서 (`src/api.py`, `src/parser.py`)

**Files:**
- Create: `src/parser.py`
- Create: `src/api.py`
- Test: `tests/test_parser.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `src.regions`
- Produces:
  - `parse_trade_xml(xml_content: str, region_info: dict) -> list[dict]`
  - `parse_rent_xml(xml_content: str, region_info: dict) -> list[dict]`
  - `ApiClient(service_key: str)`:
    - `fetch_trades(lawd_cd: str, deal_ymd: str) -> str`
    - `fetch_rents(lawd_cd: str, deal_ymd: str) -> str`

- [ ] **Step 1: Write failing test for XML parser in `tests/test_parser.py`**
  ```python
  from src.parser import parse_trade_xml, parse_rent_xml

  SAMPLE_TRADE_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
  <response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
  <body><items><item>
  <aptDong>101</aptDong><aptNm>현대아파트</aptNm><buildYear>2010</buildYear>
  <buyerGbn>개인</buyerGbn><dealAmount> 125,000 </dealAmount><dealDay>25</dealDay>
  <dealMonth>9</dealMonth><dealYear>2026</dealYear><dealingGbn>중개거래</dealingGbn>
  <excluUseAr>84.95</excluUseAr><floor>15</floor><sggCd>11110</sggCd><umdNm>청운동</umdNm>
  </item></items></body></response>"""

  def test_parse_trade_xml():
      region = {"sido": "서울특별시", "sgg": "종로구", "code": "11110"}
      trades = parse_trade_xml(SAMPLE_TRADE_XML, region)
      assert len(trades) == 1
      t = trades[0]
      assert t["deal_date"] == "2026-09-25"
      assert t["deal_amount"] == 125000
      assert t["apt_name"] == "현대아파트"
      assert t["floor"] == 15
      assert round(t["pyeong"], 1) == 25.7
      assert t["price_per_pyeong"] > 0
  ```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `uv run pytest tests/test_parser.py -v`
  - Expected: FAIL

- [ ] **Step 3: Implement `src/parser.py` and `src/api.py`**
  - `parse_trade_xml`: 쉼표 제거(`125,000` -> `125000`), 날짜 조합(`2026-09-25`), 평수 및 평당가 산출.
  - `parse_rent_xml`: 전세/월세 라벨링(`monthlyRent == 0` -> '전세', else '월세').
  - `ApiClient`: 재시도(지수 백오프), 세션 풀, 에러 핸들링.

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_parser.py tests/test_api.py -v`
  - Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/parser.py src/api.py tests/test_parser.py tests/test_api.py
  git commit -m "feat: add OpenAPI client and XML response parsers"
  ```

---

### Task 5: 최근 7일 롤링 데이터 수집 파이프라인 통합 (`src/collector.py`)

**Files:**
- Create: `src/collector.py`
- Test: `tests/test_collector.py`

**Interfaces:**
- Consumes: `src.regions`, `src.db`, `src.api`, `src.parser`
- Produces:
  - `Collector(api_key: str, db_path: str = "data/real_estate.db", max_workers: int = 5)`:
    - `get_target_months(target_date: datetime.date = None) -> list[str]` (최근 7일에 걸친 YYYYMM 목록)
    - `collect_region(region: dict, months: list[str]) -> tuple[list[dict], list[dict]]`
    - `run(target_date: datetime.date = None) -> dict` (수집 결과 요약 반환)

- [ ] **Step 1: Write failing test in `tests/test_collector.py`**
  ```python
  import datetime
  from src.collector import Collector

  def test_get_target_months_month_boundary():
      collector = Collector(api_key="mock_key")
      # 월초(10월 3일)인 경우 10월과 9월 2개 월이 대상이 되어야 함
      months = collector.get_target_months(target_date=datetime.date(2026, 10, 3))
      assert months == ["202609", "202610"]

      # 월말(10월 25일)인 경우 10월 1개 월만 대상
      months_mid = collector.get_target_months(target_date=datetime.date(2026, 10, 25))
      assert months_mid == ["202610"]
  ```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `uv run pytest tests/test_collector.py -v`
  - Expected: FAIL

- [ ] **Step 3: Implement `src/collector.py`**
  - 날짜 윈도우 계산 로직 (기준일 ~ 6일 전, 총 7일)
  - `ThreadPoolExecutor` 기반 병렬 수집
  - 최근 7일 필터링 후 DB 적재 및 과거 데이터 롤링 삭제
  - `data/meta.json` 생성 (마지막 수집 일시, 매매 건수, 전월세 건수 기록)
  - CLI 엔트리포인트 (`if __name__ == "__main__": Collector.from_env().run()`)

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_collector.py -v`
  - Expected: PASS

- [ ] **Step 5: Run real smoke test with 1-2 regions using user API key**
  - Run: `uv run python -c "from src.collector import Collector; c = Collector.from_env(); print('COLLECTOR READY')"`
  - Expected: SUCCESS

- [ ] **Step 6: Commit**
  ```bash
  git add src/collector.py tests/test_collector.py
  git commit -m "feat: implement 7-day rolling data collection pipeline"
  ```

---

### Task 6: Streamlit 반응형 실거래가 대시보드 (`app.py`, `src/dashboard_components.py`)

**Files:**
- Create: `src/dashboard_components.py`
- Create: `app.py`
- Test: `tests/test_dashboard_components.py`

**Interfaces:**
- Consumes: `src.db`, `data/real_estate.db`
- Produces:
  - Streamlit Web Application

- [ ] **Step 1: Write failing test in `tests/test_dashboard_components.py`**
  ```python
  import pandas as pd
  from src.dashboard_components import format_korean_currency, compute_kpis

  def test_format_korean_currency():
      assert format_korean_currency(125000) == "12억 5,000만원"
      assert format_korean_currency(7500) == "7,500만원"

  def test_compute_kpis():
      df = pd.DataFrame([
          {"deal_amount": 100000, "price_per_pyeong": 4000, "apt_name": "A아파트", "sgg": "강남구"},
          {"deal_amount": 200000, "price_per_pyeong": 6000, "apt_name": "B아파트", "sgg": "서초구"}
      ])
      kpis = compute_kpis(df, mode="trade")
      assert kpis["total_deals"] == 2
      assert kpis["avg_price"] == 150000
      assert kpis["max_deal_apt"] == "B아파트"
  ```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `uv run pytest tests/test_dashboard_components.py -v`
  - Expected: FAIL

- [ ] **Step 3: Implement `src/dashboard_components.py` and `app.py`**
  - KPI 계산 및 한글 금액 포맷터 유틸리티.
  - Plotly 인터랙티브 차트 함수 (일자별 거래량 막대그래프, 시군구 TOP 10, 평당가 히스토그램, 가격대별 파이차트).
  - `app.py` 구축:
    - 매매 / 전월세 탭 뷰.
    - 사이드바 필터 (날짜 범위, 시도 ➔ 시군구 동적 필터, 가격/면적 슬라이더, 단지명 검색).
    - 상단 KPI 메트릭 카드 4종.
    - Plotly 시각화 섹션.
    - 실거래 상세 데이터프레임 및 CSV 다운로드 버튼.
    - 데이터베이스 연결 캐싱 (`@st.cache_resource`).

- [ ] **Step 4: Run test to verify it passes**
  - Run: `uv run pytest tests/test_dashboard_components.py -v`
  - Expected: PASS

- [ ] **Step 5: Verify Streamlit app runs without syntax/runtime errors**
  - Run: `uv run streamlit run app.py --server.headless true --server.port 8501` (smoke test and terminate)

- [ ] **Step 6: Commit**
  ```bash
  git add src/dashboard_components.py app.py tests/test_dashboard_components.py
  git commit -m "feat: implement Streamlit real estate transaction dashboard"
  ```

---

### Task 7: GitHub Actions 자동 수집 스케줄러 및 배포 가이드 문서화

**Files:**
- Create: `.github/workflows/daily_collector.yml`
- Create: `README.md`

**Interfaces:**
- Produces:
  - GitHub Actions 자동 일일 수집 워크플로
  - GitHub & Streamlit Community Cloud 배포 가이드

- [ ] **Step 1: Write `.github/workflows/daily_collector.yml`**
  - 스케줄: `cron: '0 21 * * *'` (매일 한국시간 06:00)
  - `workflow_dispatch` 지원
  - `astral-sh/setup-uv@v5` 및 `uv sync`
  - `uv run python -m src.collector`
  - Git commit & push (`git diff --quiet || git commit -m ... && git push`)

- [ ] **Step 2: Write comprehensive `README.md`**
  - 프로젝트 소개 및 아키텍처 다이어그램
  - 로컬 실행 가이드 (`uv sync`, `.env` 설정, `uv run streamlit run app.py`)
  - GitHub Actions Secret 등록 방법 (`DATA_GO_KR_API_KEY`)
  - Streamlit Community Cloud 무료 배포 절차 (클릭 3번으로 연동)

- [ ] **Step 3: Run all unit & integration tests to verify 100% pass**
  - Run: `uv run pytest -v`
  - Expected: All tests PASS

- [ ] **Step 4: Commit**
  ```bash
  git add .github/workflows/daily_collector.yml README.md
  git commit -m "ci: add daily collector workflow and deployment documentation"
  ```
