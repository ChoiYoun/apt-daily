# 전국 아파트 최근 7일 실거래가 수집 및 대시보드 시스템 설계서

- **작성일**: 2026-09-30
- **상태**: 승인됨 (Approved)
- **대상**: 공공데이터포털(국토교통부) 아파트 매매 실거래가 OpenAPI 기반 자동 수집 및 Streamlit 대시보드

---

## 1. 개요 (Overview)

### 1.1 프로젝트 목적
국토교통부 아파트 매매 실거래 상세 자료 OpenAPI([15126469](https://www.data.go.kr/data/15126469/openapi.do))를 활용하여 **전국 단위의 최근 7일간 실거래가 데이터**를 매일 자동으로 수집하고, 이를 직관적으로 탐색 및 분석할 수 있는 **Streamlit 대시보드**를 구축합니다.

### 1.2 핵심 제약 및 배포 환경
- **서버 비용 0원 (100% 무료 티어)**:
  - **데이터 수집 자동화**: GitHub Actions (일일 cron 스케줄러)
  - **대시보드 호스팅**: Streamlit Community Cloud (GitHub 연동 무료 배포)
- **데이터 보관 정책**:
  - 저장소 용량 및 로딩 성능 최적화를 위해 **최근 7일 치 데이터만 유지하는 롤링 윈도우(Rolling Window)** 정책 적용
- **데이터베이스**: 경량 파일 기반의 **SQLite DB** (`data/real_estate.db`) 활용

---

## 2. 시스템 아키텍처 (Architecture)

```text
[공공데이터포털 OpenAPI]
       │
       ▼ (매일 한국시간 06:00 자동 실행)
[GitHub Actions Workflow] ────▶ [Collector (Python + uv)]
                                           │
                                           ▼ (UPSERT & 롤링 7일 이전 삭제)
                                 [SQLite DB: data/real_estate.db]
                                           │
                                           ▼ (자동 Git Commit & Push)
                                 [GitHub Repository]
                                           │
                                           ▼ (WebHook / Polling)
                                 [Streamlit Community Cloud]
                                           │
                                           ▼
                                 [사용자 인터랙티브 대시보드]
```

### 2.1 구성 요소 및 책임
1. **`src/collector.py`**:
   - 전국 250개 시군구 법정동 코드(`LAWD_CD`) 목록을 순회하며 국토교통부 API 호출.
   - 당일 기준 최근 7일 치 거래 데이터 추출 및 정제.
   - SQLite DB에 데이터 적재 및 7일 초과 데이터 정리 (`DELETE` & `VACUUM`).
   - 메타데이터(`data/meta.json`: 마지막 수집 시각, 총 건수 등) 기록.
2. **`src/regions.py` (또는 `src/regions.json`)**:
   - 전국 17개 시도 및 약 250개 시군구 코드(`LAWD_CD`) 매핑 테이블.
3. **`data/real_estate.db`**:
   - 실거래 데이터 테이블 및 인덱스가 포함된 SQLite 데이터베이스 파일.
4. **`app.py`**:
   - Streamlit 메인 대시보드 UI.
   - 사이드바 필터링, KPI 메트릭 카드, Plotly 기반 시각화 차트, 상세 거래 테이블 및 CSV 다운로드 제공.
5. **`.github/workflows/daily_collector.yml`**:
   - 매일 새벽 6시(KST) cron 트리거 및 수동(`workflow_dispatch`) 실행 지원.
   - GitHub Secret(`DATA_GO_KR_API_KEY`)을 주입받아 데이터 수집 후 DB 변경분 푸시.

---

## 3. 데이터베이스 설계 (Database Schema)

### 3.1 테이블: `apt_deals`
```sql
CREATE TABLE IF NOT EXISTS apt_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_date TEXT NOT NULL,         -- 계약일자 (YYYY-MM-DD)
    sido TEXT NOT NULL,              -- 시/도 명 (예: 서울특별시, 경기도)
    sgg TEXT NOT NULL,               -- 시/군/구 명 (예: 강남구, 분당구)
    sgg_cd TEXT NOT NULL,            -- 법정동 시군구 5자리 코드 (예: 11680)
    umd TEXT NOT NULL,               -- 읍/면/동 명 (예: 개포동)
    apt_name TEXT NOT NULL,          -- 아파트 단지명
    deal_amount INTEGER NOT NULL,    -- 거래금액 (만원 단위 정수, 예: 155000 -> 15억 5천만원)
    exclusive_area REAL NOT NULL,    -- 전용면적 (㎡, 소수점 2자리)
    pyeong REAL NOT NULL,            -- 평수 (전용면적 / 3.30578)
    price_per_pyeong INTEGER NOT NULL,-- 평당 가격 (deal_amount / pyeong, 만원/평)
    floor INTEGER,                   -- 층수
    build_year INTEGER,              -- 건축년도
    buyer_gbn TEXT,                  -- 매수자 구분 (개인, 법인 등)
    dealing_gbn TEXT,                -- 거래 유형 (중개거래, 직거래)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sgg_cd, umd, apt_name, deal_date, deal_amount, exclusive_area, floor)
);

-- 검색 및 필터링 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_apt_deals_date ON apt_deals(deal_date);
CREATE INDEX IF NOT EXISTS idx_apt_deals_region ON apt_deals(sido, sgg);
CREATE INDEX IF NOT EXISTS idx_apt_deals_apt ON apt_deals(apt_name);
```

### 3.2 롤링 7일 데이터 보관 로직
데이터 삽입 완료 후, 수집 기준일(`target_date`)로부터 7일 이전의 데이터는 자동 정리합니다.
```sql
DELETE FROM apt_deals 
WHERE deal_date < DATE(:cutoff_date);

VACUUM;
```

---

## 4. 데이터 수집 파이프라인 (Collector Implementation Details)

### 4.1 OpenAPI 연동 규격
- **엔드포인트**: `http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev`
- **주요 파라미터**:
  - `serviceKey`: 발급받은 공공데이터포털 디코딩/인코딩 키
  - `LAWD_CD`: 법정동 5자리 코드
  - `DEAL_YMD`: 계약년월 6자리 (`YYYYMM`)
  - `pageNo`: 1
  - `numOfRows`: 1000 (시군구당 월별 거래량 수용)
- **최근 7일 처리 기준**:
  - 기준일이 월초(예: 10월 3일)인 경우, 당월(`202610`)과 전월(`202609`)을 함께 조회하여 최근 7일(09-27 ~ 10-03) 누락 방지.
- **안정성 및 속도 최적화**:
  - `requests.Session` 재사용.
  - 최대 5개 워커의 스레드 풀(`ThreadPoolExecutor`)을 적용하여 250개 시군구를 약 30~50초 내에 수집 완료.
  - 네트워크 일시 장애에 대비한 지수 백오프 재시도(3회).

---

## 5. Streamlit 대시보드 설계 (Dashboard UI/UX)

### 5.1 상단 헤더 및 상태 바
- 타이틀: `🏢 대한민국 아파트 최근 7일 실거래가 모니터링`
- 상태 정보: 마지막 데이터 동기화 시간 및 최근 7일 수집 건수 표기.

### 5.2 사이드바 인터랙티브 필터
- **기간 선택**: 최근 7일 내 날짜 슬라이더 또는 시작일/종료일 선택.
- **지역 선택**: 시/도 드롭다운 (전체, 서울, 경기, 부산 등) ➔ 선택된 시/도의 시군구 멀티선택.
- **가격 필터**: 거래 금액 범위 슬라이더 (단위: 억원 또는 만원).
- **면적 필터**: 전용면적/평형대 필터링 (소형, 중형, 대형 등).
- **검색창**: 아파트 단지명 키워드 검색.

### 5.3 1단: 핵심 메트릭 (KPI Cards)
1. **총 거래량**: 필터 조건 내 최근 7일 총 거래 건수 (전국 기준 및 선택 지역 기준).
2. **최고가 거래 단지**: 최근 7일간 최고가로 거래된 단지명, 금액, 전용면적.
3. **평균 거래금액**: 선택 조건의 평균 거래가격 및 평균 평당가.
4. **핫플레이스**: 최근 7일간 거래량이 가장 많았던 시군구 지역.

### 5.4 2단: 인터랙티브 차트 (Plotly Charts)
- **일자별 거래량 추이**: 최근 7일간의 일자별 거래 건수 막대 차트 + 추세선.
- **지역별 거래량 상위 TOP 10**: 시군구별 거래량 순위 가로 막대 차트.
- **가격 및 평형 분포**:
  - 탭 1: 평당 거래가격 분포 히스토그램.
  - 탭 2: 가격대별(3억 이하, 3~6억, 6~9억, 9~15억, 15억 초과) 비중 파이 차트.

### 5.5 3단: 실거래 상세 목록 및 내보내기
- 필터링된 거래 내역 테이블 (계약일자, 지역, 아파트명, 층수, 전용면적, 평수, 거래금액, 평당가, 거래유형).
- 금액/평당가 등 숫자 서식 한글 표기 (`15억 5,000만원`).
- 검색 결과 CSV 다운로드 버튼 제공.

---

## 6. 배포 및 자동화 구성 (Deployment & CI/CD)

### 6.1 GitHub Actions Workflow (`.github/workflows/daily_collector.yml`)
```yaml
name: Daily Real Estate Data Collector

on:
  schedule:
    # 매일 UTC 21:00 (한국 시간 오전 06:00)
    - cron: '0 21 * * *'
  workflow_dispatch: # 수동 즉시 실행 지원

jobs:
  collect-and-commit:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install 3.12

      - name: Install Dependencies
        run: uv sync

      - name: Run Collector
        env:
          DATA_GO_KR_API_KEY: ${{ secrets.DATA_GO_KR_API_KEY }}
        run: uv run python src/collector.py

      - name: Commit and Push DB Changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add data/real_estate.db data/meta.json
          git commit -m "chore(data): auto-update 7-day apartment sales data [skip ci]" || echo "No changes to commit"
          git push
```

### 6.2 Streamlit Community Cloud 배포 절차
1. GitHub 리포지토리 생성 후 프로젝트 푸시.
2. [share.streamlit.io](https://share.streamlit.io) 로그인 및 새 앱 생성.
3. 리포지토리 및 브랜치(`main`), 실행 파일(`app.py`) 선택 후 배포 클릭.
4. 이후 GitHub Actions가 매일 새벽 DB를 업데이트하여 커밋하면, Streamlit 앱이 자동으로 최신 DB를 조회하여 반영.

---

## 7. 검증 및 테스트 계획 (Verification Plan)

### 7.1 단위 및 통합 테스트
1. **API 파서 테스트 (`tests/test_parser.py`)**:
   - 샘플 XML/JSON 응답에 대한 데이터 파싱, 금액 쉼표 제거, 평당가 계산 정확도 검증.
2. **데이터베이스 롤링 테스트 (`tests/test_database.py`)**:
   - 데이터 UPSERT 시 중복 방지 동작 검증.
   - 7일 이전 데이터 삭제 쿼리 및 잔여 데이터 범위 검증.
3. **수집기 E2E 테스트 (`tests/test_collector.py`)**:
   - 1개 시군구(예: 서울 종로구 `11110`)를 대상으로 실제 API 통신 및 DB 적재 확인.

### 7.2 대시보드 로컬 동작 검증
- `uv run streamlit run app.py`로 로컬 서버 실행 후 브라우저 서빙, 사이드바 필터링, 차트 인터랙션, CSV 다운로드 정상 동작 확인.
