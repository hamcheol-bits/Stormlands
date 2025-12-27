"""
금융 AI 모델 통합 관리
"""
from enum import Enum
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """AI 모델 유형"""
    GENERAL = "general"  # Llama3 - 범용 추론, 쿼리 파싱
    FINANCIAL = "financial"  # FinGPT - 금융 특화 분석
    SENTIMENT = "sentiment"  # FinBERT - 감성 분석


class FinancialAIEngine:
    """
    금융 AI 엔진 통합

    여러 AI 모델을 조합하여 최적의 분석 결과 제공:
    1. Llama3: 자연어 이해, 쿼리 파싱
    2. FinGPT: 종목 분석, 투자 의견 생성
    3. FinBERT: 뉴스/리포트 감성 분석
    """

    def __init__(self):
        self.llama3 = None  # 범용 추론
        self.fingpt = None  # 금융 특화
        self.finbert = None  # 감성 분석
        self._initialized = False

    async def initialize(self):
        """모든 AI 모델 초기화"""
        if self._initialized:
            return

        from app.core.llm_client import get_llm_client
        from app.config.config import get_settings

        settings = get_settings()

        # 1. Llama3 (필수)
        self.llama3 = get_llm_client()
        logger.info("✓ Llama3 initialized")

        # 2. FinGPT (선택)
        if settings.FINGPT_ENABLED:
            try:
                from app.core.fingpt_client import get_fingpt_client
                self.fingpt = get_fingpt_client()
                logger.info("✓ FinGPT initialized")
            except Exception as e:
                logger.warning(f"FinGPT initialization failed: {e}")
                logger.warning("Falling back to Llama3 for financial analysis")

        # 3. FinBERT (선택)
        if settings.FINBERT_ENABLED:
            try:
                from app.core.finbert_client import get_finbert_client
                self.finbert = get_finbert_client()
                logger.info("✓ FinBERT initialized")
            except Exception as e:
                logger.warning(f"FinBERT initialization failed: {e}")
                logger.warning("Falling back to Llama3 for sentiment analysis")

        self._initialized = True
        logger.info("All AI models ready")

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        자연어 쿼리 분석

        Args:
            query: 사용자 질문
                예: "KOSPI에서 저평가되고 영업이익률이 상승중인 3개만 추천해줘"

        Returns:
            {
                "market": "KOSPI" | "KOSDAQ" | "ALL",
                "sector": "반도체" | None,
                "financial_conditions": {
                    "valuation": "undervalued" | "fair" | "overvalued",
                    "profitability": "improving" | "stable" | "declining",
                    "min_roe": 10.0,
                    "max_debt_ratio": 150.0,
                    ...
                },
                "sort_by": [
                    {"field": "roe", "direction": "desc"},
                    {"field": "sales_growth", "direction": "desc"}
                ],
                "count": 3,
                "analysis_type": "value" | "growth" | "dividend" | "general"
            }
        """
        if not self._initialized:
            await self.initialize()

        # Llama3로 쿼리 파싱
        system_prompt = """당신은 금융 데이터 분석 전문가입니다.
사용자의 자연어 질문을 분석하여 다음 정보를 JSON 형식으로 추출하세요:

1. market: 시장 구분 (KOSPI/KOSDAQ/ALL)
2. sector: 섹터/업종 (반도체, 바이오, 금융 등)
3. financial_conditions: 재무 조건
   - valuation: 밸류에이션 (undervalued/fair/overvalued)
   - profitability: 수익성 추세 (improving/stable/declining)
   - growth: 성장성 (high/medium/low)
   - safety: 안정성 (safe/moderate/risky)
   - 구체적 수치 조건 (min_roe, max_debt_ratio 등)
4. sort_by: 정렬 기준 배열
   - field: roe, sales_growth, dividend_yield 등
   - direction: asc 또는 desc
5. count: 결과 개수
6. analysis_type: 분석 유형 (value/growth/dividend/general)

예시:
질문: "저평가된 반도체 종목 3개 추천해줘"
응답:
{
  "market": "ALL",
  "sector": "반도체",
  "financial_conditions": {
    "valuation": "undervalued"
  },
  "sort_by": [
    {"field": "pbr", "direction": "asc"}
  ],
  "count": 3,
  "analysis_type": "value"
}

반드시 JSON만 출력하세요."""

        try:
            response = await self.llama3.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ])

            parsed = self._parse_json_response(response)

            # 기본값 설정
            if not parsed.get("market"):
                parsed["market"] = "ALL"
            if not parsed.get("count"):
                parsed["count"] = 5
            if not parsed.get("analysis_type"):
                parsed["analysis_type"] = "general"

            return parsed

        except Exception as e:
            logger.error(f"Query analysis failed: {e}")

            # 폴백: 기본 응답
            return {
                "market": "ALL",
                "count": 5,
                "analysis_type": "general",
                "error": str(e)
            }

    async def analyze_stock(
            self,
            ticker: str,
            name: str,
            financial_data: Dict[str, Any],
            price_data: Optional[Dict[str, Any]] = None,
            news_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        종목 상세 분석 (FinGPT 우선, 폴백: Llama3)

        Args:
            ticker: 종목코드
            name: 회사명
            financial_data: 재무 데이터
            price_data: 주가 데이터 (선택)
            news_summary: 뉴스 요약 (선택)

        Returns:
            {
                "analysis": "분석 내용",
                "recommendation": "buy" | "hold" | "sell",
                "target_price": 예상 적정가,
                "risks": ["리스크1", "리스크2"],
                "opportunities": ["기회1", "기회2"]
            }
        """
        if not self._initialized:
            await self.initialize()

        # FinGPT 사용 가능하면 우선 사용
        if self.fingpt:
            try:
                analysis = await self.fingpt.analyze_stock(
                    ticker, name, financial_data, news_summary
                )

                return {
                    "analysis": analysis,
                    "model": "FinGPT",
                    "confidence": "high"
                }
            except Exception as e:
                logger.warning(f"FinGPT analysis failed, falling back to Llama3: {e}")

        # 폴백: Llama3
        prompt = self._build_stock_analysis_prompt(
            ticker, name, financial_data, price_data, news_summary
        )

        response = await self.llama3.generate(
            prompt,
            system_prompt="당신은 전문 증권 애널리스트입니다. 종목을 분석하고 투자 의견을 제시하세요."
        )

        return {
            "analysis": response,
            "model": "Llama3",
            "confidence": "medium"
        }

    async def analyze_sentiment(
            self,
            texts: List[str],
            aggregate: bool = True
    ) -> Dict[str, Any]:
        """
        뉴스/리포트 감성 분석 (FinBERT 우선, 폴백: Llama3)

        Args:
            texts: 분석할 텍스트 리스트
            aggregate: 집계 여부

        Returns:
            {
                "label": "positive" | "neutral" | "negative",
                "score": 0.95,
                "scores": {"positive": 0.95, "neutral": 0.03, "negative": 0.02}
            }
        """
        if not self._initialized:
            await self.initialize()

        # FinBERT 사용 가능하면 우선 사용
        if self.finbert:
            try:
                if aggregate:
                    return self.finbert.aggregate_sentiment(texts)
                else:
                    return self.finbert.analyze_batch(texts)
            except Exception as e:
                logger.warning(f"FinBERT analysis failed, falling back to Llama3: {e}")

        # 폴백: Llama3
        combined_text = "\n\n".join(texts[:5])  # 최대 5개

        prompt = f"""다음 텍스트의 투자 감성을 분석하세요:

{combined_text}

감성 분류:
- positive: 긍정적 (주가 상승 기대)
- neutral: 중립적
- negative: 부정적 (주가 하락 우려)

JSON 형식으로 응답:
{{
  "label": "positive/neutral/negative",
  "score": 0.0~1.0,
  "reason": "이유"
}}"""

        response = await self.llama3.generate(prompt)
        parsed = self._parse_json_response(response)

        return {
            "label": parsed.get("label", "neutral"),
            "score": parsed.get("score", 0.5),
            "reason": parsed.get("reason", ""),
            "model": "Llama3"
        }

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출"""
        import json

        try:
            # 마크다운 코드블록 제거
            clean = response.strip()

            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            # JSON 파싱
            return json.loads(clean)

        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Response: {response}")
            return {}

    def _build_stock_analysis_prompt(
            self,
            ticker: str,
            name: str,
            financial_data: Dict[str, Any],
            price_data: Optional[Dict[str, Any]],
            news_summary: Optional[str]
    ) -> str:
        """종목 분석 프롬프트 생성"""

        prompt = f"""종목 분석 요청:

회사: {name} ({ticker})

재무 데이터:
- 매출액: {financial_data.get('sale_account', 'N/A'):,} 원
- 영업이익: {financial_data.get('bsop_prti', 'N/A'):,} 원
- 당기순이익: {financial_data.get('thtr_ntin', 'N/A'):,} 원
- ROE: {financial_data.get('roe_val', 'N/A')}%
- 부채비율: {financial_data.get('lblt_rate', 'N/A')}%
- EPS: {financial_data.get('eps', 'N/A'):,} 원
- BPS: {financial_data.get('bps', 'N/A'):,} 원
- 매출성장률: {financial_data.get('grs', 'N/A')}%
"""

        if price_data:
            prompt += f"\n주가 정보:\n"
            prompt += f"- 현재가: {price_data.get('current_price', 'N/A'):,} 원\n"
            prompt += f"- 52주 최고/최저: {price_data.get('high_52w', 'N/A')} / {price_data.get('low_52w', 'N/A')}\n"

        if news_summary:
            prompt += f"\n최근 뉴스:\n{news_summary}\n"

        prompt += """
다음 항목을 포함하여 분석하세요:
1. 재무 건전성 평가
2. 성장 가능성
3. 밸류에이션 (저평가/적정/고평가)
4. 투자 의견 (매수/보유/매도)
5. 리스크 요인
6. 투자 포인트
"""

        return prompt


# 싱글톤 인스턴스
_ai_engine: Optional[FinancialAIEngine] = None


def get_ai_engine() -> FinancialAIEngine:
    """AI 엔진 싱글톤 반환"""
    global _ai_engine

    if _ai_engine is None:
        _ai_engine = FinancialAIEngine()

    return _ai_engine