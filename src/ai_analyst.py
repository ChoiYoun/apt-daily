"""Google Gemini API 기반 부동산 시장 일일 애널리스트 분석 리포트 모듈"""

import os
import json
import time
import logging
import requests
import pandas as pd
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

from src.dashboard_components import format_korean_currency, get_clean_region_label

logger = logging.getLogger(__name__)


def prepare_daily_context(trades_df: pd.DataFrame, rents_df: pd.DataFrame) -> Dict[str, Any]:
    """당일 실거래 데이터를 애널리스트 프롬프트에 주입하기 위한 핵심 요약 지표로 전처리"""
    ctx: Dict[str, Any] = {}

    # 1. 매매 데이터 전처리
    if trades_df is not None and not trades_df.empty:
        ctx["trade_count"] = len(trades_df)
        ctx["avg_trade_price"] = int(trades_df["deal_amount"].mean()) if "deal_amount" in trades_df else 0
        ctx["avg_trade_pyeong_price"] = int(trades_df["price_per_pyeong"].mean()) if "price_per_pyeong" in trades_df else 0

        # 최고가 거래 단지 TOP 3
        sorted_trades = trades_df.sort_values(by="deal_amount", ascending=False).head(3)
        top_trades = []
        for _, row in sorted_trades.iterrows():
            reg = get_clean_region_label(row.get("sido"), row.get("sgg"))
            top_trades.append({
                "apt_name": str(row.get("apt_name", "-")),
                "region": reg,
                "deal_amount": int(row.get("deal_amount", 0)),
                "deal_amount_str": format_korean_currency(row.get("deal_amount")),
                "area_str": f"{float(row.get('exclusive_area', 0)):.1f}㎡({row.get('floor', '-')}층)"
            })
        ctx["top_trades"] = top_trades

        # 최다 거래 지역 TOP 3
        if "sido" in trades_df and "sgg" in trades_df:
            reg_counts = trades_df.groupby(["sido", "sgg"]).size().sort_values(ascending=False).head(3)
            ctx["top_trade_regions"] = [
                (get_clean_region_label(idx[0], idx[1]), int(cnt)) for idx, cnt in reg_counts.items()
            ]
        else:
            ctx["top_trade_regions"] = []
    else:
        ctx["trade_count"] = 0
        ctx["avg_trade_price"] = 0
        ctx["avg_trade_pyeong_price"] = 0
        ctx["top_trades"] = []
        ctx["top_trade_regions"] = []

    # 2. 전월세 데이터 전처리
    if rents_df is not None and not rents_df.empty:
        ctx["rent_count"] = len(rents_df)
        jeonse_df = rents_df[rents_df["rent_type"] == "전세"]
        wolse_df = rents_df[rents_df["rent_type"] == "월세"]

        ctx["jeonse_count"] = len(jeonse_df)
        ctx["wolse_count"] = len(wolse_df)
        ctx["jeonse_ratio"] = round((len(jeonse_df) / len(rents_df)) * 100, 1) if len(rents_df) > 0 else 0.0

        ctx["avg_jeonse_deposit"] = int(jeonse_df["deposit"].mean()) if not jeonse_df.empty else 0
        ctx["avg_wolse_rent"] = int(wolse_df["monthly_rent"].mean()) if not wolse_df.empty else 0

        # 최고 보증금 단지 TOP 3
        sorted_rents = rents_df.sort_values(by="deposit", ascending=False).head(3)
        top_rents = []
        for _, row in sorted_rents.iterrows():
            reg = get_clean_region_label(row.get("sido"), row.get("sgg"))
            top_rents.append({
                "apt_name": str(row.get("apt_name", "-")),
                "region": reg,
                "deposit": int(row.get("deposit", 0)),
                "deposit_str": format_korean_currency(row.get("deposit")),
                "monthly_rent": int(row.get("monthly_rent", 0)),
                "rent_type": str(row.get("rent_type", "-"))
            })
        ctx["top_rents"] = top_rents
    else:
        ctx["rent_count"] = 0
        ctx["jeonse_count"] = 0
        ctx["wolse_count"] = 0
        ctx["jeonse_ratio"] = 0.0
        ctx["avg_jeonse_deposit"] = 0
        ctx["avg_wolse_rent"] = 0
        ctx["top_rents"] = []

    return ctx


def build_analyst_prompt(context: Dict[str, Any], deal_date: str) -> str:
    """부동산 시장 수석 애널리스트 페르소나 및 정제된 데이터를 결합하여 프롬프트 생성"""
    trade_count = context.get("trade_count", 0)
    avg_price_str = format_korean_currency(context.get("avg_trade_price", 0))
    avg_pyeong_str = f"{context.get('avg_trade_pyeong_price', 0):,}만원"

    top_trades_text = "\n".join([
        f"- {t['apt_name']} ({t['region']}): {t['deal_amount_str']} / {t['area_str']}"
        for t in context.get("top_trades", [])
    ]) or "해당 없음"

    top_regions_text = ", ".join([
        f"{r[0]} ({r[1]}건)" for r in context.get("top_trade_regions", [])
    ]) or "해당 없음"

    rent_count = context.get("rent_count", 0)
    jeonse_cnt = context.get("jeonse_count", 0)
    wolse_cnt = context.get("wolse_count", 0)
    jeonse_ratio = context.get("jeonse_ratio", 0.0)
    avg_deposit_str = format_korean_currency(context.get("avg_jeonse_deposit", 0))
    avg_wolse_rent_str = f"{context.get('avg_wolse_rent', 0):,}만원"

    top_rents_text = "\n".join([
        f"- {r['apt_name']} ({r['region']}): 보증금 {r['deposit_str']} ({r['rent_type']})"
        for r in context.get("top_rents", [])
    ]) or "해당 없음"

    prompt = f"""
당신은 15년 경력의 대한민국 부동산 수석 시장 애널리스트입니다.
아래에 제공된 {deal_date} 하루 동안 신고된 전국 아파트 실거래 데이터 요약 지표를 면밀히 분석하여, 투자자와 실수요자가 당일 시장의 흐름과 특징을 명확히 이해할 수 있는 전문적이고 객관적인 '데일리 마켓 브리핑 리포트'를 작성해 주세요.

[기준 일자]
- 계약 일자: {deal_date}

[당일 매매 시장 팩트 데이터]
- 총 매매 건수: {trade_count:,}건
- 평균 거래 금액: {avg_price_str} (평균 평당 {avg_pyeong_str})
- 거래량 상위 집중 지역: {top_regions_text}
- 당일 주요 최고가 거래 단지 TOP 3:
{top_trades_text}

[당일 전월세 시장 팩트 데이터]
- 총 전월세 거래량: {rent_count:,}건 (전세 {jeonse_cnt}건, 월세 {wolse_cnt}건, 전세 비중 {jeonse_ratio}%)
- 평균 전세 보증금: {avg_deposit_str} / 평균 월세액: {avg_wolse_rent_str}
- 당일 최고 보증금 단지 TOP 3:
{top_rents_text}

[작성 및 출력 가이드라인]
1. 반드시 첫 번째 줄은 `# [한줄 마켓 헤드라인]` 형태로 전체 시장을 관통하는 간결하고 핵심적인 1줄 요약 제목을 작성하세요. (따옴표나 다른 부가 텍스트 없이)
2. 헤드라인 다음 줄부터 아래 4개 항목을 포함한 구조화된 마크다운 본문을 작성하세요:
   - ### 1. 📊 시장 유동성 및 거래 온도: 당일 거래량 수준과 평균 가격대를 통한 시장 심리 평가
   - ### 2. 🏢 매매 시장 특징 & 주요 단지: 최고가 거래 단지의 상징성과 거래가 활발했던 지역의 시사점
   - ### 3. 🔑 전월세 동향 & 임대 시장 흐름: 전세 vs 월세 비중, 보증금 수준을 통한 임대차 시장 특징
   - ### 4. 💡 애널리스트 총평 & 관전 포인트: 실수요자와 투자자 관점에서 주목해야 할 향후 체크포인트
3. 감정적이거나 막연한 추측은 배제하고, 제공된 수치(건수, 억/만원, 단지명)를 적극 인용하여 신뢰도 높은 전문가적 어조로 작성하세요.
""".strip()

    return prompt


DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
FALLBACK_GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]


class GeminiAnalystClient:
    """Google Gemini REST API 클라이언트 및 분석 리포트 캐싱 오케스트레이터"""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_GEMINI_MODEL):
        load_dotenv()
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = model

    def call_gemini(self, prompt: str) -> Tuple[str, str]:
        """Google Gemini REST API를 호출하여 헤드라인과 본문 마크다운을 반환 (모델 대체 폴백 지원)"""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

        models_to_try = [self.model] + [m for m in FALLBACK_GEMINI_MODELS if m != self.model]
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
            }
        }

        last_err = None

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            
            # 모델당 최대 2회 시도
            for attempt in range(1, 3):
                try:
                    res = requests.post(url, headers=headers, json=payload, timeout=35)
                    # 404(모델 미지원)나 503(서버 일시 과부하)일 경우 다음 모델로 폴백
                    if res.status_code in (404, 503):
                        logger.warning(f"Gemini 모델 '{model_name}' 응답 코드 {res.status_code}. 다음 후보 모델로 시도합니다.")
                        last_err = requests.HTTPError(f"{res.status_code} Error for model {model_name}: {res.text[:120]}", response=res)
                        break

                    res.raise_for_status()
                    data = res.json()

                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError(f"Gemini API 응답에 후보(candidates)가 없습니다: {data}")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        raise ValueError(f"Gemini API 응답에 내용(parts)이 없습니다: {candidates[0]}")

                    full_text = parts[0].get("text", "").strip()
                    if not full_text:
                        raise ValueError("Gemini API가 빈 텍스트를 반환했습니다.")

                    # 첫 번째 줄을 헤드라인으로 추출, 나머지를 본문으로 파싱
                    lines = full_text.splitlines()
                    headline = ""
                    content_lines = []
                    found_headline = False

                    for line in lines:
                        stripped = line.strip()
                        if not found_headline and stripped:
                            headline = stripped
                            found_headline = True
                        elif found_headline:
                            content_lines.append(line)

                    summary_markdown = "\n".join(content_lines).strip()
                    self.model = model_name
                    return headline, summary_markdown

                except requests.RequestException as e:
                    last_err = e
                    logger.warning(f"Gemini API 호출 ({model_name}) {attempt}회차 실패: {e}")
                    if attempt < 2:
                        time.sleep(1.5)

        raise RuntimeError(f"Gemini API 호출에 최종 실패했습니다: {last_err}")

    def get_or_create_daily_analysis(
        self,
        db_manager: Any,
        deal_date: str,
        trades_df: pd.DataFrame,
        rents_df: pd.DataFrame,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """DB 캐시를 우선 조회하고, 없거나 force_refresh 시 Gemini를 호출하여 DB에 캐싱 후 반환"""
        # 1. 캐시 우선 확인 (force_refresh가 아닐 때)
        if not force_refresh:
            cached = db_manager.get_daily_analysis(deal_date)
            if cached is not None:
                cached["cached"] = True
                return cached

        # 2. API 키 유효성 확인
        if not self.api_key:
            # 캐시가 이미 있다면 키가 없어도 캐시 반환
            cached = db_manager.get_daily_analysis(deal_date)
            if cached is not None:
                cached["cached"] = True
                return cached
            return {
                "error": "NO_API_KEY",
                "message": "GEMINI_API_KEY가 설정되지 않아 AI 마켓 브리핑을 생성할 수 없습니다. .env 파일에 키를 등록해 주세요."
            }

        # 3. 신규 리포트 생성 및 DB 저장
        try:
            ctx = prepare_daily_context(trades_df, rents_df)
            prompt = build_analyst_prompt(ctx, deal_date)
            headline, summary_markdown = self.call_gemini(prompt)

            trade_count = len(trades_df) if trades_df is not None and not trades_df.empty else 0
            rent_count = len(rents_df) if rents_df is not None and not rents_df.empty else 0

            db_manager.save_daily_analysis(
                deal_date=deal_date,
                headline=headline,
                summary_markdown=summary_markdown,
                model_name=self.model,
                trade_count=trade_count,
                rent_count=rent_count
            )

            return {
                "deal_date": deal_date,
                "headline": headline,
                "summary_markdown": summary_markdown,
                "model_name": self.model,
                "cached": False
            }
        except Exception as e:
            logger.error(f"Gemini 일일 분석 생성 중 오류 발생: {e}", exc_info=True)
            # 폴백: 기존 캐시가 있다면 경고와 함께 반환
            cached = db_manager.get_daily_analysis(deal_date)
            if cached is not None:
                cached["cached"] = True
                cached["warning"] = f"새 리포트 생성에 실패하여 기존 저장된 리포트를 표시합니다. ({str(e)})"
                return cached
            return {
                "error": "API_ERROR",
                "message": f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}"
            }
