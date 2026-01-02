"""
하이브리드 분석 서비스
전통적 밸류에이션 + AI 모델 융합

전략:
- Layer 1: 전통 모델이 정량적 기준선 제공 (DCF, Graham, Magic, 상대가치)
- Layer 2: AI가 정성적 맥락 해석 및 검증 (FinGPT, FinBERT, Llama3)
- Layer 3: 이중 검증으로 최종 판단 (상호 보완 구조)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.valuation import ComprehensiveValuation
from app.core.ai_models import get_ai_engine
from app.models.stock import Stock
from app.models.financial_statement import FinancialStatement
from app.models.investment_opinion import InvestmentOpinion
from app.models.stock_price import StockPrice

logger = logging.getLogger(__name__)


class HybridAnalysisService:
    """
    하이브리드 분석 서비스

    전통적 밸류에이션 모델과 AI 모델을 융합하여
    더 정확하고 신뢰할 수 있는 투자 분석 제공
    """

    def __init__(self, db: Session):
        self.db = db
        self.ai_engine = get_ai_engine()

    async def analyze_stock(
        self,
        ticker: str,
        include_ai_adjustment: bool = True,
        include_sentiment: bool = True,
        explain_differences: bool = True
    ) -> Dict[str, Any]:
        """
        종목 하이브리드 분석

        Args:
            ticker: 종목코드
            include_ai_adjustment: AI 조정 포함 여부
            include_sentiment: 감성 분석 포함 여부
            explain_differences: 차이 설명 포함 여부

        Returns:
            3-Layer 분석 결과
        """
        logger.info(f"🔍 Starting hybrid analysis for {ticker}")

        # 기본 데이터 로드
        stock = self._load_stock(ticker)
        if not stock:
            return {"error": "Stock not found", "ticker": ticker}

        # ============================================================
        # Layer 1: 전통적 밸류에이션 (정량 기준선)
        # ============================================================
        logger.info("📊 Layer 1: Traditional valuation models")

        traditional_result = await self._run_traditional_valuation(ticker)

        if "error" in traditional_result:
            return {
                "ticker": ticker,
                "stock_name": stock.hts_kor_isnm,
                "error": traditional_result["error"],
                "layer_completed": "none"
            }

        # ============================================================
        # Layer 2: AI 분석 (정성 맥락 해석)
        # ============================================================
        ai_result = {}

        if include_ai_adjustment:
            logger.info("🤖 Layer 2: AI contextual analysis")

            # 재무 품질 검증 (FinGPT)
            financial_data = self._prepare_financial_data(ticker)
            ai_result["financial_quality_check"] = await self._ai_financial_quality_check(
                ticker, stock.hts_kor_isnm, financial_data, traditional_result
            )

            # 감성 분석 (FinBERT)
            if include_sentiment:
                ai_result["sentiment_analysis"] = await self._ai_sentiment_analysis(ticker)

            # 이상 패턴 탐지
            ai_result["anomaly_detection"] = await self._ai_anomaly_detection(
                ticker, financial_data
            )

        # ============================================================
        # Layer 3: 하이브리드 통합 (AI 기반 조정)
        # ============================================================
        logger.info("⚖️  Layer 3: Hybrid integration")

        hybrid_result = await self._integrate_results(
            traditional_result,
            ai_result,
            explain_differences
        )

        # ============================================================
        # 최종 해석 생성 (Llama3)
        # ============================================================
        logger.info("💬 Generating natural language interpretation")

        interpretation = await self._generate_interpretation(
            ticker,
            stock.hts_kor_isnm,
            traditional_result,
            ai_result,
            hybrid_result
        )

        return {
            "ticker": ticker,
            "stock_name": stock.hts_kor_isnm,
            "market": stock.mrkt_ctg_cls_code,
            "sector": stock.sector,

            # Layer 1: 전통적 분석
            "traditional_valuation": traditional_result,

            # Layer 2: AI 분석
            "ai_analysis": ai_result if ai_result else None,

            # Layer 3: 하이브리드 결과
            "hybrid_result": hybrid_result,

            # 최종 해석
            "interpretation": interpretation["explanation"],
            "recommendation": interpretation["recommendation"],
            "key_points": interpretation.get("key_points", []),

            # 메타데이터
            "analysis_date": self._get_current_date(),
            "analysis_version": "1.0.0"
        }

    async def _run_traditional_valuation(self, ticker: str) -> Dict[str, Any]:
        """
        Layer 1: 전통적 밸류에이션 실행

        DCF, Graham, Magic Formula, 상대가치 모델을 실행하여
        객관적인 정량적 기준선 제공
        """
        try:
            comp = ComprehensiveValuation(self.db, ticker)
            result = comp.analyze(include_details=True)

            return {
                "composite_score": result["composite_score"],
                "composite_rating": result["composite_rating"],
                "model_scores": result["model_scores"],
                "model_ratings": result["model_ratings"],
                "model_details": {
                    "dcf": result.get("dcf_result", {}),
                    "relative": result.get("relative_result", {}),
                    "graham": result.get("graham_result", {}),
                    "magic": result.get("magic_result", {})
                },
                "strengths": result["strengths"],
                "weaknesses": result["weaknesses"],
                "investment_recommendation": result.get("investment_recommendation", "")
            }

        except Exception as e:
            logger.error(f"Traditional valuation failed for {ticker}: {e}")
            return {"error": str(e)}

    async def _ai_financial_quality_check(
        self,
        ticker: str,
        name: str,
        financial_data: Dict[str, Any],
        traditional_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Layer 2-1: AI 재무 품질 검증

        전통 모델이 놓칠 수 있는 요소:
        - 일회성 손익 (영업이익 vs 순이익 괴리)
        - 회계 조작 가능성
        - 수익성 트렌드 변화
        - 산업별 맥락
        """
        await self.ai_engine.initialize()

        # DCF 상세 결과 추출
        dcf_details = traditional_result.get("model_details", {}).get("dcf", {})

        prompt = f"""재무 전문가로서 다음 데이터를 분석하여 잠재적 이슈를 찾아주세요:

# 종목 정보
- 회사: {name} ({ticker})
- 섹터: {financial_data.get('sector', 'N/A')}

# 재무 데이터
- 매출액: {financial_data.get('sales', 0):,} 원
- 영업이익: {financial_data.get('operating_income', 0):,} 원
- 당기순이익: {financial_data.get('net_income', 0):,} 원
- 매출성장률: {financial_data.get('sales_growth', 0):.1f}%
- 영업이익률: {financial_data.get('operating_margin', 0):.1f}%
- ROE: {financial_data.get('roe', 0):.1f}%
- 부채비율: {financial_data.get('debt_ratio', 0):.1f}%

# 전통 모델 평가
- DCF 점수: {traditional_result.get('model_scores', {}).get('dcf', 'N/A')}
- DCF 상승여력: {dcf_details.get('upside_percentage', 'N/A')}%
- Graham 점수: {traditional_result.get('model_scores', {}).get('graham', 'N/A')}
- Magic Formula 점수: {traditional_result.get('model_scores', {}).get('magic', 'N/A')}

# 분석 항목
1. **일회성 손익 가능성**
   - 영업이익과 순이익의 괴리 분석
   - 특별이익/손실 여부

2. **수익성 트렌드**
   - 영업이익률이 개선/악화 중인가?
   - 매출 대비 이익 증가율 비교

3. **재무 건전성 경고**
   - 부채비율이 산업 평균 대비 높은가?
   - ROE가 낮은 이유는?

4. **전통 모델 과대/과소평가 가능성**
   - DCF가 너무 낙관적이지 않은가?
   - Graham 기준이 산업 특성을 반영하는가?

# 출력 형식 (JSON만)
{{
  "quality_score": 0-100,
  "issues": ["이슈1", "이슈2", ...],
  "warnings": ["경고1", "경고2", ...],
  "strengths": ["강점1", "강점2", ...],
  "adjustments": {{
    "score_adjustment": -10 to +10,
    "reason": "조정 이유 (구체적으로)",
    "confidence": "high/medium/low"
  }},
  "traditional_model_assessment": "전통 모델 평가가 타당한지 의견"
}}

JSON만 출력하세요."""

        try:
            response = await self.ai_engine.llama3.generate(prompt)
            parsed = self.ai_engine._parse_json_response(response)

            return {
                "quality_score": parsed.get("quality_score", 70),
                "issues": parsed.get("issues", []),
                "warnings": parsed.get("warnings", []),
                "strengths": parsed.get("strengths", []),
                "score_adjustment": parsed.get("adjustments", {}).get("score_adjustment", 0),
                "adjustment_reason": parsed.get("adjustments", {}).get("reason", ""),
                "adjustment_confidence": parsed.get("adjustments", {}).get("confidence", "medium"),
                "traditional_model_assessment": parsed.get("traditional_model_assessment", ""),
                "model": "FinGPT" if self.ai_engine.fingpt else "Llama3"
            }

        except Exception as e:
            logger.error(f"AI financial quality check failed: {e}")
            return {
                "quality_score": 70,
                "issues": [],
                "warnings": [],
                "strengths": [],
                "score_adjustment": 0,
                "adjustment_reason": "AI 분석 실패",
                "error": str(e)
            }

    async def _ai_sentiment_analysis(self, ticker: str) -> Dict[str, Any]:
        """
        Layer 2-2: AI 감성 분석

        투자의견 텍스트에서 숨은 시그널 추출:
        - 표면적 투자의견 (매수/보유/매도)
        - 텍스트 내 보수적 표현 탐지
        - 투자의견 트렌드 변화
        """
        await self.ai_engine.initialize()

        # 최근 투자의견 조회
        opinions = (
            self.db.query(InvestmentOpinion)
            .filter(InvestmentOpinion.ticker == ticker)
            .order_by(desc(InvestmentOpinion.stck_bsop_date))
            .limit(15)
            .all()
        )

        if not opinions:
            return {
                "sentiment": "neutral",
                "score": 0.5,
                "message": "투자의견 데이터 없음",
                "impact": "none"
            }

        # 투자의견 텍스트 추출
        texts = []
        for op in opinions:
            text = f"{op.mbcr_name}: {op.invt_opnn}"
            if op.hts_goal_prc:
                text += f" (목표가: {op.hts_goal_prc})"
            if op.rgbf_invt_opnn:
                text += f" [변경: {op.rgbf_invt_opnn} → {op.invt_opnn}]"
            texts.append(text)

        # AI 감성 분석
        try:
            sentiment_result = await self.ai_engine.analyze_sentiment(texts, aggregate=True)

            # 투자의견 통계
            opinion_counts = {
                "buy": sum(1 for op in opinions if "매수" in (op.invt_opnn or "")),
                "hold": sum(1 for op in opinions if "보유" in (op.invt_opnn or "")),
                "sell": sum(1 for op in opinions if "매도" in (op.invt_opnn or ""))
            }

            # 트렌드 분석
            recent_trend = self._calculate_sentiment_trend(opinions)

            # 감성과 투자의견 괴리 분석
            consensus_sentiment = "positive" if opinion_counts["buy"] > opinion_counts["hold"] else "neutral"
            ai_sentiment = sentiment_result.get("label", "neutral")

            discrepancy = (consensus_sentiment != ai_sentiment)

            return {
                "sentiment": ai_sentiment,
                "sentiment_score": sentiment_result.get("score", 0.5),
                "consensus_sentiment": consensus_sentiment,
                "discrepancy": discrepancy,
                "discrepancy_note": "AI가 텍스트에서 보수적 표현 탐지" if discrepancy else "",
                "opinion_counts": opinion_counts,
                "total_opinions": len(opinions),
                "recent_trend": recent_trend,
                "impact": self._assess_sentiment_impact(ai_sentiment, recent_trend),
                "model": "FinBERT" if self.ai_engine.finbert else "Llama3"
            }

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {
                "sentiment": "neutral",
                "score": 0.5,
                "error": str(e),
                "impact": "none"
            }

    def _calculate_sentiment_trend(self, opinions: List) -> str:
        """투자의견 트렌드 계산 (최근 vs 이전)"""
        if len(opinions) < 4:
            return "insufficient_data"

        # 최근 5개 vs 이전 5-10개 비교
        recent = opinions[:5]
        previous = opinions[5:10] if len(opinions) >= 10 else opinions[5:]

        if not previous:
            return "insufficient_data"

        recent_buy_ratio = sum(1 for op in recent if "매수" in (op.invt_opnn or "")) / len(recent)
        previous_buy_ratio = sum(1 for op in previous if "매수" in (op.invt_opnn or "")) / len(previous)

        if recent_buy_ratio > previous_buy_ratio + 0.2:
            return "improving"
        elif recent_buy_ratio < previous_buy_ratio - 0.2:
            return "weakening"
        else:
            return "stable"

    def _assess_sentiment_impact(self, sentiment: str, trend: str) -> str:
        """감성이 점수에 미치는 영향 평가"""
        if sentiment == "negative":
            return "negative_strong" if trend == "weakening" else "negative_moderate"
        elif sentiment == "positive":
            return "positive_strong" if trend == "improving" else "positive_moderate"
        else:
            return "neutral"

    async def _ai_anomaly_detection(
        self,
        ticker: str,
        financial_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Layer 2-3: 이상 패턴 탐지

        AI가 재무제표에서 비정상적 패턴 찾기
        """
        await self.ai_engine.initialize()

        # 3년치 재무 데이터 조회
        financials = (
            self.db.query(FinancialStatement)
            .filter(
                and_(
                    FinancialStatement.ticker == ticker,
                    FinancialStatement.period_type == "Y"
                )
            )
            .order_by(desc(FinancialStatement.stac_yymm))
            .limit(3)
            .all()
        )

        if len(financials) < 2:
            return {
                "anomalies_detected": False,
                "message": "데이터 부족"
            }

        # 3개년 트렌드 분석
        trends = []
        for i, fs in enumerate(financials):
            trends.append({
                "year": fs.stac_yymm,
                "sales": fs.sale_account or 0,
                "operating_income": fs.bsop_prti or 0,
                "net_income": fs.thtr_ntin or 0,
                "operating_margin": (fs.bsop_prti / fs.sale_account * 100) if fs.sale_account else 0
            })

        prompt = f"""다음 3개년 재무 트렌드에서 이상 패턴을 찾아주세요:

{self._format_trend_data(trends)}

이상 패턴 예시:
- 매출은 증가하는데 영업이익은 감소
- 영업이익률이 급격히 하락
- 순이익이 영업이익보다 훨씬 큼 (일회성 이익 가능성)

JSON 형식으로 출력:
{{
  "anomalies_detected": true/false,
  "patterns": ["패턴1", "패턴2"],
  "severity": "high/medium/low"
}}"""

        try:
            response = await self.ai_engine.llama3.generate(prompt)
            parsed = self.ai_engine._parse_json_response(response)

            return {
                "anomalies_detected": parsed.get("anomalies_detected", False),
                "patterns": parsed.get("patterns", []),
                "severity": parsed.get("severity", "low")
            }

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {
                "anomalies_detected": False,
                "error": str(e)
            }

    def _format_trend_data(self, trends: List[Dict]) -> str:
        """트렌드 데이터 포맷팅"""
        lines = []
        for t in trends:
            margin = t.get('operating_margin', 0)
            lines.append(
                f"- {t['year']}: 매출 {t['sales']:,}, "
                f"영업이익 {t['operating_income']:,}, "
                f"순이익 {t['net_income']:,}, "
                f"영업이익률 {margin:.1f}%"
            )
        return "\n".join(lines)

    async def _integrate_results(
        self,
        traditional: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        explain: bool
    ) -> Dict[str, Any]:
        """
        Layer 3: 전통 밸류에이션 + AI 분석 통합

        조정 로직:
        1. 재무 품질 이슈 → 점수 하향
        2. 감성 부정적 → 점수 하향
        3. 이상 패턴 탐지 → 신뢰도 하향
        4. AI 조정이 크면 신뢰도 하향
        """
        base_score = traditional.get("composite_score", 50)
        adjusted_score = base_score
        adjustments = []
        confidence_factors = []

        # 1. 재무 품질 조정
        if "financial_quality_check" in ai_analysis:
            quality_check = ai_analysis["financial_quality_check"]
            score_adj = quality_check.get("score_adjustment", 0)

            if score_adj != 0:
                adjusted_score += score_adj
                adjustments.append({
                    "type": "financial_quality",
                    "adjustment": score_adj,
                    "reason": quality_check.get("adjustment_reason", ""),
                    "confidence": quality_check.get("adjustment_confidence", "medium")
                })

                # 신뢰도 요소
                if abs(score_adj) > 10:
                    confidence_factors.append("large_quality_adjustment")

        # 2. 감성 분석 조정
        if "sentiment_analysis" in ai_analysis:
            sentiment = ai_analysis["sentiment_analysis"]
            sentiment_label = sentiment.get("sentiment", "neutral")
            sentiment_impact = sentiment.get("impact", "none")

            if "negative" in sentiment_impact:
                if "strong" in sentiment_impact:
                    sentiment_adj = -8
                else:
                    sentiment_adj = -4

                adjusted_score += sentiment_adj
                adjustments.append({
                    "type": "negative_sentiment",
                    "adjustment": sentiment_adj,
                    "reason": f"시장 감성 부정적 (트렌드: {sentiment.get('recent_trend', 'N/A')})"
                })

            elif "positive" in sentiment_impact and base_score < 70:
                if "strong" in sentiment_impact:
                    sentiment_adj = 5
                else:
                    sentiment_adj = 2

                adjusted_score += sentiment_adj
                adjustments.append({
                    "type": "positive_sentiment",
                    "adjustment": sentiment_adj,
                    "reason": f"시장 감성 긍정적 (트렌드: {sentiment.get('recent_trend', 'N/A')})"
                })

            # 감성 괴리 시 신뢰도 영향
            if sentiment.get("discrepancy"):
                confidence_factors.append("sentiment_discrepancy")

        # 3. 이상 패턴 탐지 조정
        if "anomaly_detection" in ai_analysis:
            anomaly = ai_analysis["anomaly_detection"]
            if anomaly.get("anomalies_detected"):
                severity = anomaly.get("severity", "low")

                if severity == "high":
                    anomaly_adj = -10
                elif severity == "medium":
                    anomaly_adj = -5
                else:
                    anomaly_adj = -2

                adjusted_score += anomaly_adj
                adjustments.append({
                    "type": "anomaly_detected",
                    "adjustment": anomaly_adj,
                    "reason": f"이상 패턴 탐지 ({', '.join(anomaly.get('patterns', []))})"
                })

                confidence_factors.append(f"anomaly_{severity}")

        # 4. 최종 점수 범위 제한 (0-100)
        adjusted_score = max(0, min(100, adjusted_score))

        # 5. 최종 등급
        final_rating = self._get_rating_from_score(adjusted_score)

        # 6. 신뢰도 계산
        confidence = self._calculate_confidence(adjustments, confidence_factors)

        result = {
            "base_score": round(base_score, 1),
            "adjusted_score": round(adjusted_score, 1),
            "score_change": round(adjusted_score - base_score, 1),
            "final_rating": final_rating,
            "confidence_level": confidence,
            "adjustments": adjustments,
            "adjustment_count": len(adjustments)
        }

        if explain and adjustments:
            result["explanation"] = self._explain_adjustments(
                base_score, adjusted_score, adjustments
            )

        return result

    def _get_rating_from_score(self, score: float) -> str:
        """점수를 등급으로 변환"""
        if score >= 85:
            return "strong_buy"
        elif score >= 70:
            return "buy"
        elif score >= 55:
            return "accumulate"
        elif score >= 45:
            return "hold"
        elif score >= 30:
            return "reduce"
        else:
            return "sell"

    def _calculate_confidence(
        self,
        adjustments: List[Dict],
        confidence_factors: List[str]
    ) -> str:
        """신뢰도 계산"""
        # 조정 폭
        total_adjustment = sum(abs(adj["adjustment"]) for adj in adjustments)

        # 부정적 요소 개수
        negative_count = len(confidence_factors)

        if total_adjustment > 15 or negative_count >= 3:
            return "low"
        elif total_adjustment > 8 or negative_count >= 2:
            return "medium"
        else:
            return "high"

    def _explain_adjustments(
        self,
        base_score: float,
        adjusted_score: float,
        adjustments: List[Dict]
    ) -> str:
        """조정 내용 설명"""
        msg = f"전통 모델 {base_score:.0f}점 → AI 조정 {adjusted_score:.0f}점\n\n"

        for adj in adjustments:
            sign = "+" if adj["adjustment"] > 0 else ""
            msg += f"• {adj['type']}: {sign}{adj['adjustment']}점\n  이유: {adj['reason']}\n"

        return msg.strip()

    async def _generate_interpretation(
        self,
        ticker: str,
        name: str,
        traditional: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        hybrid: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Llama3로 최종 해석 생성

        전문가처럼 숫자와 맥락을 결합하여
        일반 투자자가 이해하기 쉽게 설명
        """
        await self.ai_engine.initialize()

        prompt = f"""당신은 20년 경력의 증권 애널리스트입니다.
다음 분석 결과를 일반 투자자에게 쉽게 설명해주세요:

# 종목
{name} ({ticker})

# 1. 전통적 밸류에이션 (객관적 수치)
- 종합 점수: {traditional.get('composite_score', 0):.0f}/100
- 평가: {traditional.get('composite_rating', 'N/A')}
- 강점: {', '.join(traditional.get('strengths', ['없음']))}
- 약점: {', '.join(traditional.get('weaknesses', ['없음']))}

# 2. AI 분석 (맥락 해석)
{self._format_ai_analysis_for_llm(ai_analysis)}

# 3. 최종 판단
- 조정 후 점수: {hybrid.get('adjusted_score', 0):.0f}/100
- 최종 평가: {hybrid.get('final_rating', 'N/A')}
- 신뢰도: {hybrid.get('confidence_level', 'N/A')}

# 요구사항
1. **핵심 요약** (3-4줄)
   - 전통 모델과 AI 분석이 일치하는가/불일치하는가?
   - 왜 점수가 조정되었는가?

2. **투자 추천** (명확하게)
   - 강력 매수/매수/적립식 매수/보유/비중 축소/매도

3. **투자 포인트** (3개)
   - 투자 시 주목할 점

4. **리스크** (2-3개)
   - 주의해야 할 점

자연스러운 한글로 작성하되, 전문용어는 쉽게 풀어서 설명하세요.
숫자만 나열하지 말고, **왜 그런지** 맥락을 설명하세요."""

        try:
            response = await self.ai_engine.llama3.generate(
                prompt,
                temperature=0.3,  # 더 일관된 답변
                max_tokens=1500
            )

            # 투자 추천 추출
            recommendation = self._extract_recommendation(response, hybrid.get("final_rating"))

            # 핵심 포인트 추출
            key_points = self._extract_key_points(response)

            return {
                "explanation": response,
                "recommendation": recommendation,
                "key_points": key_points,
                "date": self._get_current_date()
            }

        except Exception as e:
            logger.error(f"Interpretation generation failed: {e}")

            # 폴백: 간단한 해석
            fallback = self._generate_fallback_interpretation(
                traditional, hybrid
            )

            return {
                "explanation": fallback,
                "recommendation": self._extract_recommendation("", hybrid.get("final_rating")),
                "key_points": [],
                "error": str(e)
            }

    def _format_ai_analysis_for_llm(self, ai_analysis: Dict[str, Any]) -> str:
        """AI 분석 결과를 LLM 프롬프트용으로 포맷팅"""
        lines = []

        if "financial_quality_check" in ai_analysis:
            fq = ai_analysis["financial_quality_check"]
            lines.append(f"재무 품질 점수: {fq.get('quality_score', 0)}/100")

            if fq.get("issues"):
                lines.append(f"이슈: {', '.join(fq['issues'])}")
            if fq.get("warnings"):
                lines.append(f"경고: {', '.join(fq['warnings'])}")
            if fq.get("strengths"):
                lines.append(f"강점: {', '.join(fq['strengths'])}")

        if "sentiment_analysis" in ai_analysis:
            sent = ai_analysis["sentiment_analysis"]
            lines.append(f"시장 감성: {sent.get('sentiment', 'N/A')}")
            lines.append(f"투자의견 추이: {sent.get('recent_trend', 'N/A')}")

            if sent.get("discrepancy"):
                lines.append(f"⚠️ 감성 괴리: {sent.get('discrepancy_note', '')}")

        if "anomaly_detection" in ai_analysis:
            anom = ai_analysis["anomaly_detection"]
            if anom.get("anomalies_detected"):
                patterns = ', '.join(anom.get("patterns", []))
                lines.append(f"⚠️ 이상 패턴: {patterns}")

        return "\n".join(lines) if lines else "AI 분석 없음"

    def _extract_recommendation(self, text: str, rating: str) -> str:
        """텍스트에서 투자 추천 추출"""
        text_lower = text.lower()

        keywords = {
            "강력 매수": ["강력 매수", "strong buy", "적극 매수"],
            "매수": ["매수", "buy"],
            "적립식 매수": ["적립식", "accumulate", "분할 매수"],
            "보유": ["보유", "hold", "유지"],
            "비중 축소": ["비중 축소", "reduce", "일부 매도"],
            "매도": ["매도", "sell"]
        }

        for rec, keys in keywords.items():
            if any(k in text for k in keys):
                return rec

        # 폴백: rating 기반
        rating_map = {
            "strong_buy": "강력 매수",
            "buy": "매수",
            "accumulate": "적립식 매수",
            "hold": "보유",
            "reduce": "비중 축소",
            "sell": "매도"
        }
        return rating_map.get(rating, "보유")

    def _extract_key_points(self, text: str) -> List[str]:
        """텍스트에서 핵심 포인트 추출"""
        points = []

        # 간단한 패턴 매칭
        if "투자 포인트" in text:
            section = text.split("투자 포인트")[1].split("리스크")[0] if "리스크" in text else text.split("투자 포인트")[1]

            for line in section.split('\n'):
                line = line.strip()
                if line.startswith('-') or line.startswith('•') or line.startswith('1') or line.startswith('2') or line.startswith('3'):
                    points.append(line.lstrip('-•123. ').strip())

        return points[:3]  # 최대 3개

    def _generate_fallback_interpretation(
        self,
        traditional: Dict[str, Any],
        hybrid: Dict[str, Any]
    ) -> str:
        """폴백: 간단한 해석 생성"""
        base = traditional.get("composite_score", 50)
        adjusted = hybrid.get("adjusted_score", 50)
        diff = adjusted - base

        if diff < -5:
            direction = "하향 조정"
        elif diff > 5:
            direction = "상향 조정"
        else:
            direction = "유지"

        return f"""전통적 밸류에이션 분석 결과 {base:.0f}점이나,
AI 분석을 통해 {adjusted:.0f}점으로 {direction}되었습니다.

최종 평가: {hybrid.get('final_rating', 'N/A')}
신뢰도: {hybrid.get('confidence_level', 'N/A')}"""

    def _get_current_date(self) -> str:
        """현재 날짜"""
        return datetime.now().strftime("%Y-%m-%d")

    def _load_stock(self, ticker: str) -> Optional[Stock]:
        """종목 정보 로드"""
        return self.db.query(Stock).filter(Stock.ticker == ticker).first()

    def _prepare_financial_data(self, ticker: str) -> Dict[str, Any]:
        """재무 데이터 준비"""
        stock = self._load_stock(ticker)

        fs = (
            self.db.query(FinancialStatement)
            .filter(
                and_(
                    FinancialStatement.ticker == ticker,
                    FinancialStatement.period_type == "Y"
                )
            )
            .order_by(desc(FinancialStatement.stac_yymm))
            .first()
        )

        if not fs:
            return {"sector": stock.sector if stock else None}

        operating_margin = 0
        if fs.sale_account and fs.sale_account > 0:
            operating_margin = (fs.bsop_prti / fs.sale_account) * 100 if fs.bsop_prti else 0

        return {
            "sector": stock.sector if stock else None,
            "sales": fs.sale_account or 0,
            "operating_income": fs.bsop_prti or 0,
            "net_income": fs.thtr_ntin or 0,
            "sales_growth": float(fs.grs) if fs.grs else 0,
            "operating_margin": operating_margin,
            "roe": float(fs.roe_val) if fs.roe_val else 0,
            "debt_ratio": float(fs.lblt_rate) if fs.lblt_rate else 0
        }


def get_hybrid_analysis_service(db: Session) -> HybridAnalysisService:
    """하이브리드 분석 서비스 반환"""
    return HybridAnalysisService(db)