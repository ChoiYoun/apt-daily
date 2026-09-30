# 🏢 대한민국 아파트 최근 7일 매매/전월세 실거래가 모니터링 시스템

국토교통부 공공데이터포털의 **아파트 매매 실거래가(`RTMSDataSvcAptTrade`)** 및 **아파트 전월세 실거래가(`RTMSDataSvcAptRent`)** OpenAPI를 기반으로, 전국 단위의 최근 7일 실거래 데이터를 매일 자동 수집하고 시각화하는 인터랙티브 **Streamlit 대시보드**입니다.

GitHub Actions와 Streamlit Community Cloud를 연동하여 **서버 비용 0원(100% 무료)**으로 운영됩니다.

---

## 🌟 주요 기능

1. **전국 250개 시군구 일일 자동 수집**:
   - 매일 한국 시간 새벽 6시(KST) GitHub Actions가 자동으로 실행되어 최근 7일간의 전국 실거래가를 수집합니다.
2. **롤링 7일(Rolling 7-Day) 경량 데이터 보관**:
   - SQLite DB(`data/real_estate.db`)에 중복 없이 UPSERT 적재되며, 7일이 지난 과거 데이터는 자동 삭제 및 `VACUUM` 처리되어 저장소 크기가 항상 가볍게 유지됩니다.
3. **매매 / 전월세 통합 대시보드 (`app.py`)**:
   - **탭 뷰**: 매매 실거래가와 전월세(전세/월세) 데이터를 분리하여 최적화된 시각화 제공.
   - **동적 필터**: 시도 ➔ 시군구 연동 멀티선택, 계약기간, 금액대/보증금 슬라이더, 아파트 단지명 검색.
   - **핵심 KPI 메트릭**: 총 거래량, 최고가/최고보증금 거래 단지, 평균 거래금액, 평당 가격, 최다 거래 지역.
   - **Plotly 인터랙티브 차트**: 일자별 거래량 추이, 시군구 거래량 TOP 10, 금액대별 분포, 평형대별 거래 비중.
   - **상세 거래 테이블 & CSV 내보내기**: 한글 금액 표기(`15억 5,000만원`), 컬럼 정렬, 필터링된 데이터 CSV 다운로드.

---

## 🏗️ 시스템 아키텍처

```text
[공공데이터포털 매매/전월세 OpenAPI]
       │
       ▼ (매일 한국시간 06:00 자동 실행 / workflow_dispatch)
[GitHub Actions Workflow] ────▶ [Collector (Python + uv)]
                                           │
                                           ▼ (UPSERT & 7일 이전 자동 삭제)
                                 [SQLite DB: data/real_estate.db]
                                   - apt_trade (매매)
                                   - apt_rent (전월세)
                                           │
                                           ▼ (자동 Git Commit & Push)
                                 [GitHub Repository]
                                           │
                                           ▼ (자동 반영)
                                 [Streamlit Community Cloud]
                                           │
                                           ▼
                                 [사용자 인터랙티브 대시보드]
```

---

## 🚀 빠른 시작 가이드 (로컬 개발)

본 프로젝트는 초고속 패키지 관리자인 **`uv`**를 기반으로 동작합니다.

### 1. 가상환경 및 의존성 설치
```bash
uv sync
```

### 2. 환경 변수 설정
`.env` 파일에 발급받은 공공데이터포털 일반 인증키를 등록합니다:
```bash
cp .env.example .env
```
`.env` 내용:
```env
DATA_GO_KR_API_KEY=your_public_data_portal_api_key_here
```

### 3. 데이터 수집 실행
```bash
# 전체 전국 수집 실행
uv run python src/collector.py
```

### 4. Streamlit 대시보드 실행
```bash
uv run streamlit run app.py
```
브라우저에서 `http://localhost:8501`로 접속하여 대시보드를 확인합니다.

---

## 🧪 테스트 실행

모든 단위/통합 테스트는 `pytest`를 통해 실행할 수 있습니다:
```bash
uv run pytest -v
```

---

## ☁️ 무료 자동 배포 가이드

### 1단계: GitHub 저장소 푸시 및 Secrets 등록
1. 본 프로젝트를 본인의 GitHub 리포지토리에 푸시합니다:
   ```bash
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git branch -M main
   git push -u origin main
   ```
2. GitHub 저장소의 **Settings > Secrets and variables > Actions**로 이동합니다.
3. **New repository secret**을 클릭하고 아래와 같이 등록합니다:
   - Name: `DATA_GO_KR_API_KEY`
   - Secret: 공공데이터포털 인증키 입력
4. **Actions** 탭에서 **Daily Real Estate Data Collector** 워크플로를 수동 실행(`Run workflow`)하여 정상 동작을 확인합니다.

### 2단계: Streamlit Community Cloud 무료 배포
1. [share.streamlit.io](https://share.streamlit.io)에 접속하여 GitHub 계정으로 로그인합니다.
2. **Create app** 버튼을 클릭합니다.
3. 배포 설정:
   - **Repository**: 생성한 GitHub 저장소 선택
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Deploy!** 버튼을 클릭하면 약 1분 내에 전 세계 어디서나 접근 가능한 무료 대시보드가 배포됩니다.
5. 이후 GitHub Actions가 매일 새벽 데이터를 갱신하여 푸시하면, Streamlit 앱이 자동으로 최신 DB를 조회하여 화면에 반영합니다.

---

## 📁 디렉터리 구조

```text
apt-daily/
├── .github/
│   └── workflows/
│       └── daily_collector.yml    # 매일 한국시간 06:00 자동 수집 워크플로
├── data/
│   ├── real_estate.db             # 롤링 7일 실거래가 SQLite DB
│   └── meta.json                  # 마지막 수집 시각 및 통계 메타데이터
├── docs/
│   └── superpowers/
│       ├── specs/                 # 기획/설계 문서
│       └── plans/                 # 상세 구현 계획 문서
├── src/
│   ├── __init__.py
│   ├── api.py                     # 공공데이터포털 OpenAPI 클라이언트
│   ├── collector.py               # 7일 롤링 수집 오케스트레이터
│   ├── dashboard_components.py    # 한글 금액 포맷, KPI 계산, Plotly 차트
│   ├── db.py                      # SQLite 스키마 및 쿼리 매니저
│   ├── parser.py                  # 매매 및 전월세 XML 응답 파서
│   └── regions.py                 # 전국 250개 시군구 법정동 코드 매핑
├── tests/                         # 단위 및 통합 테스트 슈트 (16개 테스트)
├── .env.example                   # 환경 변수 예시 파일
├── .gitignore
├── app.py                         # Streamlit 메인 대시보드
├── pyproject.toml                 # uv 프로젝트 의존성 설정
└── README.md
```
