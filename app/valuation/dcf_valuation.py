"""
DCF (Discounted Cash Flow) 밸류에이션 모델
"""
import logging
from typing import Dict, Any, Optional

from .base_valuation import BaseValuation

logger = logging.getLogger(__name__)


class DCFValuation(BaseValuation):
    """
    DCF (현금흐름할인) 모델

    내재가치 = Σ(FCF_t / (1+WACC)^t) + Terminal Value / (1+WACC)^n

    간이 계산:
    - FCF = 영업이익 × (1 - 세율)
    - Terminal Value = FCF × (1+g) / (WACC - g)
    """

    def __init__(
            self,
            db,
            ticker: str,
            wacc: float = 8.0,
            terminal_growth: float = 2.0,
            projection_years: int = 5,
            tax_rate: float = 22.0
    ):
        """
        Args:
            wacc: 가중평균자본비용 (%, 기본값 8%)
            terminal_growth: 영구성장률 (%, 기본값 2%)
            projection_years: 예측기간 (년, 기본값 5년)
            tax_rate: 법인세율 (%, 기본값 22%)
        """
        super().__init__(db, ticker)

        self.wacc = wacc
        self.terminal_growth = terminal_growth
        self.projection_years = projection_years
        self.tax_rate = tax_rate

    def calculate(self) -> Dict[str, Any]:
        """DCF 계산"""
        if not self.validate_data():
            return self.get_error_result("필수 데이터 없음")

        # FCF 계산
        fcf_result = self._calculate_fcf()
        if not fcf_result or fcf_result["fcf"] <= 0:
            return self.get_error_result("FCF가 음수이거나 계산 불가")

        # 내재가치 계산
        intrinsic_value = self._calculate_intrinsic_value(fcf_result["fcf"])

        if not intrinsic_value or not self.current_price:
            return self.get_error_result("내재가치 또는 현재가 없음")

        # 상승여력
        upside_pct = ((intrinsic_value - self.current_price) / self.current_price) * 100

        # 점수 계산 (0-100)
        # 상승여력 +50% = 100점, -50% = 0점
        score = max(0, min(100, (upside_pct + 50) / 100 * 100))

        # 평가 등급
        rating = self._get_dcf_rating(upside_pct)

        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "model": "DCF",
            "score": round(score, 2),
            "rating": rating,
            "intrinsic_value": round(intrinsic_value, 2),
            "current_price": self.current_price,
            "upside_pct": round(upside_pct, 2),
            "details": {
                "fcf": fcf_result["fcf"],
                "fcf_per_share": round(fcf_result["fcf_per_share"], 2),
                "operating_income": fcf_result["operating_income"],
                "wacc": self.wacc,
                "terminal_growth": self.terminal_growth,
                "projection_years": self.projection_years,
                "tax_rate": self.tax_rate
            },
            "interpretation": self._get_interpretation(upside_pct, intrinsic_value)
        }

    def _calculate_fcf(self) -> Optional[Dict[str, Any]]:
        """잉여현금흐름(FCF) 계산"""
        if not self.latest_financial or not self.latest_financial.bsop_prti:
            return None

        operating_income = self.latest_financial.bsop_prti

        # FCF = 영업이익 × (1 - 세율)
        # 실무: 영업현금흐름 - 투자현금흐름
        fcf = int(operating_income * (1 - self.tax_rate / 100))

        # 주당 FCF (시가총액 대신 주식수 필요)
        # 간이 계산: FCF / (시가총액 / 현재가)
        shares_outstanding = self._estimate_shares_outstanding()
        fcf_per_share = fcf / shares_outstanding if shares_outstanding else None

        return {
            "fcf": fcf,
            "fcf_per_share": fcf_per_share,
            "operating_income": operating_income,
            "shares_outstanding": shares_outstanding
        }

    def _estimate_shares_outstanding(self) -> Optional[float]:
        """
        상장주식수 추정

        방법 1: 시가총액 / 현재가
        방법 2: 자본총계 / BPS
        """
        if not self.latest_financial:
            return None

        # 방법 1: BPS로 추정
        if self.latest_financial.bps and self.latest_financial.bps > 0:
            if self.latest_financial.total_cptl:
                shares = self.latest_financial.total_cptl / float(self.latest_financial.bps)
                return shares

        # 방법 2: EPS로 추정
        if self.latest_financial.eps and self.latest_financial.eps > 0:
            if self.latest_financial.thtr_ntin:
                shares = self.latest_financial.thtr_ntin / float(self.latest_financial.eps)
                return shares

        return None

    def _calculate_intrinsic_value(self, fcf: int) -> Optional[float]:
        """
        내재가치 계산 (영구성장 모델)

        Terminal Value = FCF × (1+g) / (WACC - g)
        Intrinsic Value = Terminal Value / Shares
        """
        if self.wacc <= self.terminal_growth:
            logger.warning(f"WACC({self.wacc}) <= 성장률({self.terminal_growth})")
            return None

        # 터미널 밸류 (영구가치)
        terminal_value = fcf * (1 + self.terminal_growth / 100) / (
                (self.wacc - self.terminal_growth) / 100
        )

        # 주당 내재가치
        shares = self._estimate_shares_outstanding()
        if not shares or shares <= 0:
            return None

        intrinsic_value_per_share = terminal_value / shares

        return intrinsic_value_per_share

    def _get_dcf_rating(self, upside_pct: float) -> str:
        """DCF 평가 등급"""
        if upside_pct >= 50:
            return "strong_buy"
        elif upside_pct >= 30:
            return "buy"
        elif upside_pct >= 10:
            return "undervalued"
        elif upside_pct >= -10:
            return "fair"
        elif upside_pct >= -30:
            return "overvalued"
        else:
            return "strong_sell"

    def _get_interpretation(self, upside_pct: float, intrinsic_value: float) -> str:
        """해석 생성"""
        msg = f"DCF 모델 기준 내재가치는 {intrinsic_value:,.0f}원이며, "
        msg += f"현재가({self.current_price:,.0f}원) 대비 "

        if upside_pct > 30:
            msg += f"{upside_pct:.1f}% 저평가되어 있습니다. 강력 매수 관점입니다."
        elif upside_pct > 10:
            msg += f"{upside_pct:.1f}% 저평가되어 있습니다. 매수 관점입니다."
        elif upside_pct > -10:
            msg += "적정 가격 수준입니다."
        elif upside_pct > -30:
            msg += f"{abs(upside_pct):.1f}% 고평가되어 있습니다. 매도 관점입니다."
        else:
            msg += f"{abs(upside_pct):.1f}% 고평가되어 있습니다. 강력 매도 관점입니다."

        msg += f"\n\n가정: WACC {self.wacc}%, 영구성장률 {self.terminal_growth}%, 법인세율 {self.tax_rate}%"

        return msg