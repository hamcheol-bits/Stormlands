"""
Graham Number 밸류에이션 (벤저민 그레이엄)
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy import and_, desc

from .base_valuation import BaseValuation

logger = logging.getLogger(__name__)


class GrahamValuation(BaseValuation):
    """
    Graham Number (벤저민 그레이엄의 방어적 투자자 기준)

    공식: GN = SQRT(22.5 × EPS × BPS)

    그레이엄의 7가지 투자 기준:
    1. PER < 15
    2. PBR < 1.5
    3. 부채비율 < 200%
    4. 유동비율 > 200%
    5. 순이익 증가 (최근 3년)
    6. 배당 지급 이력 (3년 이상)
    7. ROE > 15%
    """

    def calculate(self) -> Dict[str, Any]:
        """Graham Number 계산"""
        if not self.validate_data():
            return self.get_error_result("필수 데이터 없음")

        # Graham Number 계산
        graham_number = self._calculate_graham_number()

        # 안전마진
        margin_of_safety = None
        if graham_number and self.current_price:
            margin_of_safety = (
                                       (graham_number - self.current_price) / graham_number
                               ) * 100

        # 7가지 기준 체크
        criteria = self._check_graham_criteria()
        criteria_passed = sum(criteria.values())

        # 점수 계산 (0-100)
        # 기준 충족 개수 + 안전마진
        criteria_score = (criteria_passed / 7) * 70  # 70점 배점

        safety_score = 0
        if margin_of_safety:
            # 안전마진 30% 이상 = 30점, -30% = 0점
            safety_score = max(0, min(30, (margin_of_safety + 30) / 60 * 30))

        score = criteria_score + safety_score

        # 평가 등급
        rating = self._get_graham_rating(criteria_passed, margin_of_safety)

        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "model": "Graham Number",
            "score": round(score, 2),
            "rating": rating,
            "graham_number": round(graham_number, 2) if graham_number else None,
            "current_price": self.current_price,
            "margin_of_safety": round(margin_of_safety, 2) if margin_of_safety else None,
            "criteria_passed": criteria_passed,
            "criteria_details": criteria,
            "interpretation": self._get_interpretation(
                graham_number, margin_of_safety, criteria_passed, criteria
            )
        }

    def _calculate_graham_number(self) -> Optional[float]:
        """
        Graham Number 계산

        GN = SQRT(22.5 × EPS × BPS)
        """
        if not self.latest_financial:
            return None

        eps = float(self.latest_financial.eps) if self.latest_financial.eps else None
        bps = float(self.latest_financial.bps) if self.latest_financial.bps else None

        if not eps or not bps or eps <= 0 or bps <= 0:
            return None

        graham_number = pow(22.5 * eps * bps, 0.5)

        return graham_number

    def _check_graham_criteria(self) -> Dict[str, bool]:
        """그레이엄의 7가지 기준 체크"""
        criteria = {
            "per_ok": False,
            "pbr_ok": False,
            "debt_ok": False,
            "current_ratio_ok": False,
            "earnings_growth_ok": False,
            "dividend_ok": False,
            "roe_ok": False
        }

        if not self.latest_financial:
            return criteria

        fs = self.latest_financial

        # 1. PER < 15
        if fs.eps and fs.eps > 0 and self.current_price:
            per = self.current_price / float(fs.eps)
            criteria["per_ok"] = per < 15

        # 2. PBR < 1.5
        if fs.bps and fs.bps > 0 and self.current_price:
            pbr = self.current_price / float(fs.bps)
            criteria["pbr_ok"] = pbr < 1.5

        # 3. 부채비율 < 200%
        if fs.lblt_rate:
            criteria["debt_ok"] = float(fs.lblt_rate) < 200

        # 4. 유동비율 > 200%
        if fs.cras and fs.flow_lblt and fs.flow_lblt > 0:
            current_ratio = (fs.cras / fs.flow_lblt) * 100
            criteria["current_ratio_ok"] = current_ratio > 200

        # 5. 순이익 증가 (최근 3년)
        criteria["earnings_growth_ok"] = self._check_earnings_growth()

        # 6. 배당 지급 이력 (3년 이상)
        criteria["dividend_ok"] = self._check_dividend_history()

        # 7. ROE > 15%
        if fs.roe_val:
            criteria["roe_ok"] = float(fs.roe_val) > 15

        return criteria

    def _check_earnings_growth(self, years: int = 3) -> bool:
        """순이익 증가 확인 (최근 N년)"""
        history = self._load_financial_history(years + 1)

        if len(history) < 2:
            return False

        # 최신과 최오래된 순이익 비교
        latest = history[0].thtr_ntin
        oldest = history[-1].thtr_ntin

        if not latest or not oldest or oldest <= 0:
            return False

        # 증가했는지 확인
        return latest > oldest

    def _check_dividend_history(self, min_years: int = 3) -> bool:
        """배당 지급 이력 확인"""
        try:
            from app.models.dividend import Dividend

            dividend_count = (
                self.db.query(Dividend)
                .filter(Dividend.ticker == self.ticker)
                .count()
            )

            return dividend_count >= min_years

        except Exception as e:
            logger.warning(f"배당 테이블 접근 실패: {e}")
            return False

    def _get_graham_rating(
            self,
            criteria_passed: int,
            margin_of_safety: Optional[float]
    ) -> str:
        """Graham 평가 등급"""
        # 기준 충족 개수가 우선
        if criteria_passed >= 6:
            if margin_of_safety and margin_of_safety > 20:
                return "excellent"
            else:
                return "good"
        elif criteria_passed >= 4:
            if margin_of_safety and margin_of_safety > 10:
                return "good"
            else:
                return "fair"
        elif criteria_passed >= 2:
            return "fair"
        else:
            return "poor"

    def _get_interpretation(
            self,
            graham_number: Optional[float],
            margin_of_safety: Optional[float],
            criteria_passed: int,
            criteria: Dict[str, bool]
    ) -> str:
        """해석 생성"""
        msg = "**그레이엄 방어적 투자 기준 분석**\n\n"

        # Graham Number
        if graham_number and self.current_price:
            msg += f"Graham Number: {graham_number:,.0f}원\n"
            msg += f"현재가: {self.current_price:,.0f}원\n"

            if margin_of_safety:
                if margin_of_safety > 20:
                    msg += f"안전마진: +{margin_of_safety:.1f}% (매우 우수)\n\n"
                elif margin_of_safety > 0:
                    msg += f"안전마진: +{margin_of_safety:.1f}% (양호)\n\n"
                else:
                    msg += f"안전마진: {margin_of_safety:.1f}% (부족)\n\n"

        # 7가지 기준
        msg += f"**7가지 기준 충족: {criteria_passed}/7**\n\n"

        criteria_labels = {
            "per_ok": "✓ PER < 15" if criteria["per_ok"] else "✗ PER ≥ 15",
            "pbr_ok": "✓ PBR < 1.5" if criteria["pbr_ok"] else "✗ PBR ≥ 1.5",
            "debt_ok": "✓ 부채비율 < 200%" if criteria["debt_ok"] else "✗ 부채비율 ≥ 200%",
            "current_ratio_ok": "✓ 유동비율 > 200%" if criteria["current_ratio_ok"] else "✗ 유동비율 ≤ 200%",
            "earnings_growth_ok": "✓ 순이익 증가" if criteria["earnings_growth_ok"] else "✗ 순이익 정체/감소",
            "dividend_ok": "✓ 배당 이력 (3년+)" if criteria["dividend_ok"] else "✗ 배당 이력 부족",
            "roe_ok": "✓ ROE > 15%" if criteria["roe_ok"] else "✗ ROE ≤ 15%"
        }

        for label in criteria_labels.values():
            msg += f"{label}\n"

        # 종합 평가
        msg += "\n**종합 평가:**\n"
        if criteria_passed >= 6:
            msg += "그레이엄의 방어적 투자 기준을 거의 충족하는 우수한 종목입니다. "
            msg += "장기 가치투자에 적합합니다."
        elif criteria_passed >= 4:
            msg += "그레이엄의 기준을 어느 정도 충족하는 양호한 종목입니다. "
            msg += "추가 분석 후 투자를 고려할 수 있습니다."
        elif criteria_passed >= 2:
            msg += "일부 기준만 충족하여 신중한 접근이 필요합니다."
        else:
            msg += "그레이엄의 방어적 투자 기준에는 부합하지 않습니다."

        return msg