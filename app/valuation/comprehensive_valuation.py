"""
종합 밸류에이션 분석
4가지 모델 통합 및 스코어링
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .dcf_valuation import DCFValuation
from .relative_valuation import RelativeValuation
from .graham_valuation import GrahamValuation
from .magic_formula import MagicFormula

logger = logging.getLogger(__name__)


class ComprehensiveValuation:
    """
    종합 밸류에이션 분석

    4가지 전통적 모델을 통합하여 종합 점수 및 투자 등급 제공:
    1. DCF (현금흐름 할인)
    2. 상대가치 평가
    3. Graham Number
    4. Magic Formula
    """

    def __init__(
            self,
            db: Session,
            ticker: str,
            weights: Optional[Dict[str, float]] = None
    ):
        """
        Args:
            db: 데이터베이스 세션
            ticker: 종목코드
            weights: 모델별 가중치 (기본값: 균등)
                {
                    "dcf": 0.30,
                    "relative": 0.25,
                    "graham": 0.25,
                    "magic": 0.20
                }
        """
        self.db = db
        self.ticker = ticker

        # 기본 가중치
        self.weights = weights or {
            "dcf": 0.30,
            "relative": 0.25,
            "graham": 0.25,
            "magic": 0.20
        }

        # 가중치 합이 1.0인지 검증
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(f"가중치 합이 {weight_sum}입니다. 1.0으로 정규화합니다.")
            self.weights = {k: v / weight_sum for k, v in self.weights.items()}

    def analyze(
            self,
            include_details: bool = True,
            dcf_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        종합 밸류에이션 분석 실행

        Args:
            include_details: 각 모델의 상세 결과 포함 여부
            dcf_params: DCF 파라미터 (wacc, terminal_growth 등)

        Returns:
            {
                "ticker": 종목코드,
                "stock_name": 종목명,
                "composite_score": 종합 점수 (0-100),
                "composite_rating": 종합 등급,
                "investment_recommendation": 투자 추천,
                "model_scores": {모델별 점수},
                "model_ratings": {모델별 등급},
                "model_details": {모델별 상세 결과} (optional),
                "strengths": [강점 리스트],
                "weaknesses": [약점 리스트],
                "interpretation": 종합 해석
            }
        """
        logger.info(f"종합 밸류에이션 분석 시작: {self.ticker}")

        # 1. 각 모델 실행
        dcf_params = dcf_params or {}

        dcf_result = self._run_dcf(**dcf_params)
        relative_result = self._run_relative()
        graham_result = self._run_graham()
        magic_result = self._run_magic()

        # 2. 점수 및 등급 추출
        model_scores = {
            "dcf": dcf_result.get("score"),
            "relative": relative_result.get("score"),
            "graham": graham_result.get("score"),
            "magic": magic_result.get("score")
        }

        model_ratings = {
            "dcf": dcf_result.get("rating"),
            "relative": relative_result.get("rating"),
            "graham": graham_result.get("rating"),
            "magic": magic_result.get("rating")
        }

        # 3. 종합 점수 계산 (가중 평균)
        composite_score = self._calculate_composite_score(model_scores)

        # 4. 종합 등급
        composite_rating = self._get_composite_rating(composite_score)

        # 5. 투자 추천
        recommendation = self._get_investment_recommendation(
            composite_score, model_scores
        )

        # 6. 강점/약점 분석
        strengths, weaknesses = self._analyze_strengths_weaknesses(
            model_scores, model_ratings
        )

        # 7. 종목명 (첫 번째 성공한 모델에서 가져오기)
        stock_name = (
                dcf_result.get("stock_name") or
                relative_result.get("stock_name") or
                graham_result.get("stock_name") or
                magic_result.get("stock_name") or
                "Unknown"
        )

        # 결과 구성
        result = {
            "ticker": self.ticker,
            "stock_name": stock_name,
            "composite_score": round(composite_score, 2),
            "composite_rating": composite_rating,
            "investment_recommendation": recommendation,
            "model_scores": {k: round(v, 2) if v else None for k, v in model_scores.items()},
            "model_ratings": model_ratings,
            "weights": self.weights,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "interpretation": self._generate_interpretation(
                composite_score, model_scores, strengths, weaknesses
            )
        }

        # 상세 결과 포함
        if include_details:
            result["model_details"] = {
                "dcf": dcf_result,
                "relative": relative_result,
                "graham": graham_result,
                "magic": magic_result
            }

        return result

    def _run_dcf(self, **kwargs) -> Dict[str, Any]:
        """DCF 모델 실행"""
        try:
            dcf = DCFValuation(self.db, self.ticker, **kwargs)
            return dcf.calculate()
        except Exception as e:
            logger.error(f"DCF 계산 실패 ({self.ticker}): {e}")
            return {"error": str(e), "score": None, "rating": "N/A"}

    def _run_relative(self) -> Dict[str, Any]:
        """상대가치 모델 실행"""
        try:
            relative = RelativeValuation(self.db, self.ticker)
            return relative.calculate()
        except Exception as e:
            logger.error(f"상대가치 계산 실패 ({self.ticker}): {e}")
            return {"error": str(e), "score": None, "rating": "N/A"}

    def _run_graham(self) -> Dict[str, Any]:
        """Graham 모델 실행"""
        try:
            graham = GrahamValuation(self.db, self.ticker)
            return graham.calculate()
        except Exception as e:
            logger.error(f"Graham 계산 실패 ({self.ticker}): {e}")
            return {"error": str(e), "score": None, "rating": "N/A"}

    def _run_magic(self) -> Dict[str, Any]:
        """Magic Formula 실행"""
        try:
            magic = MagicFormula(self.db, self.ticker)
            return magic.calculate()
        except Exception as e:
            logger.error(f"Magic Formula 계산 실패 ({self.ticker}): {e}")
            return {"error": str(e), "score": None, "rating": "N/A"}

    def _calculate_composite_score(
            self, model_scores: Dict[str, Optional[float]]
    ) -> float:
        """
        종합 점수 계산 (가중 평균)

        에러 모델은 제외하고 계산
        """
        weighted_sum = 0
        valid_weight_sum = 0

        for model, score in model_scores.items():
            if score is not None:
                weight = self.weights.get(model, 0)
                weighted_sum += score * weight
                valid_weight_sum += weight

        if valid_weight_sum == 0:
            return 0

        # 유효한 가중치로 정규화
        composite_score = weighted_sum / valid_weight_sum * sum(self.weights.values())

        return composite_score

    def _get_composite_rating(self, score: float) -> str:
        """종합 등급"""
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

    def _get_investment_recommendation(
            self,
            composite_score: float,
            model_scores: Dict[str, Optional[float]]
    ) -> str:
        """투자 추천"""
        # 종합 점수 기반
        if composite_score >= 80:
            base_rec = "강력 매수"
        elif composite_score >= 65:
            base_rec = "매수"
        elif composite_score >= 50:
            base_rec = "적립식 매수"
        elif composite_score >= 40:
            base_rec = "보유"
        else:
            base_rec = "매도 검토"

        # 모델 간 의견 일치도 체크
        valid_scores = [s for s in model_scores.values() if s is not None]
        if len(valid_scores) >= 3:
            max_diff = max(valid_scores) - min(valid_scores)
            if max_diff > 40:
                base_rec += " (모델 간 이견 큼 - 신중 검토 필요)"

        return base_rec

    def _analyze_strengths_weaknesses(
            self,
            model_scores: Dict[str, Optional[float]],
            model_ratings: Dict[str, str]
    ) -> tuple[list[str], list[str]]:
        """강점/약점 분석"""
        strengths = []
        weaknesses = []

        model_names = {
            "dcf": "DCF (현금흐름)",
            "relative": "상대가치",
            "graham": "Graham (가치투자)",
            "magic": "Magic Formula"
        }

        for model, score in model_scores.items():
            if score is None:
                continue

            model_name = model_names.get(model, model)

            if score >= 75:
                strengths.append(f"{model_name} 우수 ({score:.0f}점)")
            elif score < 40:
                weaknesses.append(f"{model_name} 취약 ({score:.0f}점)")

        if not strengths:
            strengths.append("명확한 강점 없음")
        if not weaknesses:
            weaknesses.append("명확한 약점 없음")

        return strengths, weaknesses

    def _generate_interpretation(
            self,
            composite_score: float,
            model_scores: Dict[str, Optional[float]],
            strengths: list[str],
            weaknesses: list[str]
    ) -> str:
        """종합 해석 생성"""
        msg = f"**종합 밸류에이션 분석**\n\n"
        msg += f"종합 점수: {composite_score:.0f}/100\n\n"

        # 개별 모델 점수
        msg += "**모델별 점수:**\n"
        for model, score in model_scores.items():
            model_name = {
                "dcf": "DCF",
                "relative": "상대가치",
                "graham": "Graham",
                "magic": "Magic Formula"
            }.get(model, model)

            if score:
                msg += f"- {model_name}: {score:.0f}점\n"
            else:
                msg += f"- {model_name}: 계산 불가\n"

        # 강점
        msg += f"\n**강점:**\n"
        for strength in strengths:
            msg += f"✓ {strength}\n"

        # 약점
        msg += f"\n**약점:**\n"
        for weakness in weaknesses:
            msg += f"✗ {weakness}\n"

        # 종합 의견
        msg += f"\n**종합 의견:**\n"
        if composite_score >= 75:
            msg += "4가지 전통적 밸류에이션 모델 분석 결과 우수한 투자 기회입니다. "
            msg += "여러 모델에서 일관되게 긍정적인 평가를 받았습니다."
        elif composite_score >= 55:
            msg += "전반적으로 양호한 투자 대상입니다. "
            msg += "일부 모델에서 긍정적인 평가를 받았습니다."
        elif composite_score >= 40:
            msg += "중립적인 평가입니다. 추가 분석을 통해 신중하게 판단하세요."
        else:
            msg += "전반적으로 매력적이지 않은 투자 대상입니다. "
            msg += "여러 모델에서 부정적인 평가를 받았습니다."

        return msg

    def compare_multiple(
            self,
            tickers: list[str],
            sort_by: str = "composite_score"
    ) -> list[Dict[str, Any]]:
        """
        여러 종목 비교 분석

        Args:
            tickers: 종목코드 리스트
            sort_by: 정렬 기준 (composite_score, dcf, etc.)

        Returns:
            종목별 분석 결과 리스트 (정렬됨)
        """
        results = []

        for ticker in tickers:
            try:
                comp = ComprehensiveValuation(self.db, ticker, self.weights)
                result = comp.analyze(include_details=False)
                results.append(result)
            except Exception as e:
                logger.error(f"분석 실패 ({ticker}): {e}")

        # 정렬
        results.sort(
            key=lambda x: x.get(sort_by) or 0,
            reverse=True
        )

        return results