# 전국 아파트 최근 7일 매매/전월세 실거래가 수집 및 대시보드 시스템 설계서

- **작성일**: 2026-09-30
- **상태**: 승인됨 (Approved)
- **대상**: 공공데이터포털(국토교통부) 아파트 매매 실거래가 및 전월세 실거래가 OpenAPI 기반 자동 수집 및 Streamlit 대시보드

---

## 1. 개요 (Overview)

### 1.1 프로젝트 목적
국토교통부 아파트 매매 실거래가 OpenAPI(`RTMSDataSvcAptTrade`) 및 전월세 실거래가 OpenAPI(`RTMSDataSvcAptRent`)를 활용하여 **전국 단위의 최근 7일간 매매 및 전월세 실거래 데이터**를 매일 자동으로 수집하고, 이를 직관적으로 탐색 및 분석할 수 있는 **Streamlit 대시보드**를 구축합니다.

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
[공공데이터포털 매매/전월세 OpenAPI]
       │
       ▼ (매일 한국시간 06:00 자동 실행)
[GitHub Actions Workflow] ────▶ [Collector (Python + uv)]
                                           │
                                           ▼ (UPSERT & 롤링 7일 이전 삭제)
                                 [SQLite DB: data/real_estate.db]
                                   - apt_trade (매매)
                                   - apt_rent (전월세)
                                           │
                                           ▼ (자동 Git Commit & Push)
                                 [GitHub Repository]
                                           │
                                           ▼ (WebHook / Polling)
                                 [Streamlit Community Cloud]
                                           │
                                           ▼
                                 [매매/전월세 인터랙티브 대시보드]
```

### 2.1 구성 요소 및 책임
1. **`src/collector.py`**:
   - 전국 250개 시군구 법정동 코드(`LAWD_CD`) 목록을 순회하며 매매 및 전월세 API 호출.
   - 당일 기준 최근 7일 치 거래 데이터 추출 및 정제.
   - SQLite DB(`apt_trade`, `apt_rent`)에 데이터 적재 및 7일 초과 데이터 정리 (`DELETE` & `VACUUM`).
   - 메타데이터(`data/meta.json`: 마지막 수집 시각, 매매/전월세 건수 등) 기록.
2. **`src/regions.py`**:
   - 전국 17개 시도 및 약 250개 시군구 코드(`LAWD_CD`) 매핑 테이블.
3. **`data/real_estate.db`**:
   - `apt_trade` (매매), `apt_rent` (전월세) 테이블 및 인덱스 포함.
4. **`app.py`**:
   - Streamlit 메인 대시보드 UI (매매 / 전월세 탭 뷰 제공).
   - 사이드바 필터링, KPI 메트릭 카드, Plotly 기반 시각화 차트, 상세 거래 테이블 및 CSV 다운로드 제공.
5. **`.github/workflows/daily_collector.yml`**:
   - 매일 새벽 6시(KST) cron 트리거 및 수동(`workflow_dispatch`) 실행 지원.
   - GitHub Secret(`DATA_GO_KR_API_KEY`)을 주입받아 데이터 수집 후 DB 변경분 푸시.

---

## 3. 데이터베이스 설계 (Database Schema)

### 3.1 매매 테이블: `apt_trade`
```sql
CREATE TABLE IF NOT EXISTS apt_trade (
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

CREATE INDEX IF NOT EXISTS idx_trade_date ON apt_trade(deal_date);
CREATE INDEX IF NOT EXISTS idx_trade_region ON apt_trade(sido, sgg);
CREATE INDEX IF NOT EXISTS idx_trade_apt ON apt_trade(apt_name);
```

### 3.2 전월세 테이블: `apt_rent`
```sql
CREATE TABLE IF NOT EXISTS apt_rent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_date TEXT NOT NULL,         -- 계약일자 (YYYY-MM-DD)
    sido TEXT NOT NULL,              -- 시/도 명
    sgg TEXT NOT NULL,               -- 시/군/구 명
    sgg_cd TEXT NOT NULL,            -- 법정동 시군구 5자리 코드
    umd TEXT NOT NULL,               -- 읍/면/동 명
    apt_name TEXT NOT NULL,          -- 아파트 단지명
    deposit INTEGER NOT NULL,        -- 보증금 (만원)
    monthly_rent INTEGER NOT NULL,   -- 월세 (만원, 0이면 전세)
    rent_type TEXT NOT NULL,         -- 구분 ('전세' 또는 '월세')
    exclusive_area REAL NOT NULL,    -- 전용면적 (㎡)
    pyeong REAL NOT NULL,            -- 평수
    floor INTEGER,                   -- 층수
    build_year INTEGER,              -- 건축년도
    contract_type TEXT,              -- 갱신/신규 구분
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sgg_cd, umd, apt_name, deal_date, deposit, monthly_rent, exclusive_area, floor)
);

CREATE INDEX IF NOT EXISTS idx_rent_date ON apt_rent(deal_date);
CREATE INDEX IF NOT EXISTS idx_rent_region ON apt_rent(sido, sgg);
CREATE INDEX IF NOT EXISTS idx_rent_apt ON apt_rent(apt_name);
```

### 3.3 롤링 7일 데이터 보관 로직
데이터 적재 후, 수집 기준일로부터 7일 이전의 데이터는 자동 정리합니다.
```sql
DELETE FROM apt_trade WHERE deal_date < DATE(:cutoff_date);
DELETE FROM apt_rent WHERE deal_date < DATE(:cutoff_date);
VACUUM;
```

---

## 4. 데이터 수집 파이프라인 (Collector Implementation Details)

### 4.1 OpenAPI 연동 규격
- **매매 API**: `https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade`
- **전월세 API**: `https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent`
- **주요 파라미터**:
  - `serviceKey`: 발급받은 공공데이터포털 인증키
  - `LAWD_CD`: 법정동 5자리 코드
  - `DEAL_YMD`: 계약년월 6자리 (`YYYYMM`)
  - `pageNo`: 1
  - `numOfRows`: 1000
- **최근 7일 처리 기준**:
  - 기준일이 월초인 경우, 당월과 전월 2개 월을 조회하여 최근 7일 치 거래 데이터 누락 방지.
- **안정성 및 속도 최적화**:
  - `requests.Session` 및 `ThreadPoolExecutor`(최대 5개 워커)로 병렬 요청.
  - 지수 백오프 기반 재시도(3회).

---

## 5. Streamlit 대시보드 설계 (Dashboard UI/UX)

### 5.1 상단 구성 및 거래 유형 탭
- 상단 타이틀: `🏢 대한민국 아파트 최근 7일 실거래가 모니터링`
- 탭 선택: **📈 매매 실거래가** / **🏠 전월세 실거래가**
- 상태 배지: 마지막 동기화 일시 및 각 탭별 최근 7일 수집 건수.

### 5.2 사이드바 인터랙티브 필터
- 기간 선택 (최근 7일 내 날짜 슬라이더).
- 지역 선택 (시/도 선택 ➔ 시군구 멀티선택).
- 가격/보증금 필터 (금액 범위 슬라이더).
- 면적/평형 필터 (소형, 중형, 대형).
- 단지명 검색.

### 5.3 1단 KPI 메트릭 (매매 / 전월세 맞춤)
- **매매**: 총 매매 거래량, 최고 매매가 단지, 평균 매매가, 평균 평당가.
- **전월세**: 총 전월세 거래량(전세 N건 / 월세 M건), 최고 전세보증금 단지, 평균 전세가, 평균 월세액.

### 5.4 2단 Plotly 시각화 차트
- 일자별 거래량 추이 (매매 vs 전세 vs 월세).
- 지역별(시군구) 거래량 상위 TOP 10.
- 가격대별/평형별 분포 히스토그램 및 파이 차트.

### 5.5 3단 실거래 상세 테이블 및 다운로드
- 필터링된 결과 데이터프레임 (한글 금액 서식 포맷팅).
- CSV 다운로드 기능.

---

## 6. 배포 및 자동화 구성 (Deployment & CI/CD)

### 6.1 GitHub Actions Workflow (`.github/workflows/daily_collector.yml`)
- 매일 한국 시간 06:00 (UTC 21:00) 자동 실행 및 수동(`workflow_dispatch`) 실행 지원.
- `DATA_GO_KR_API_KEY` 시크릿 주입.
- 매매 및 전월세 데이터 수집 후 `data/real_estate.db`, `data/meta.json` 자동 커밋 & 푸시.

### 6.2 Streamlit Community Cloud 배포
- GitHub 리포지토리 연동, 무료 자동 배포.
- GitHub Actions 커밋 푸시 시 자동 최신 데이터 반영.
