"""
Magic Formula (조엘 그린블라트)
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy import text

from .base_valuation import BaseValuation

logger = logging.getLogger(__name__)


class MagicFormula(BaseValuation):
    """
    Magic Formula (마법공식)
    조엘 그린블라트의 "주식시장을 이기는 작은 책"

    핵심 지표:
    1. ROIC (Return on Invested Capital)
       = EBIT / (순운전자본 + 순고정자산)
       간이: EBIT / (총자산 - 총부채)

    2. Earnings Yield (이익수익률)
       = EBIT / 기업가치(EV)
       간이: EBIT / 시가총액

    전략: ROIC와 Earnings Yield가 모두 높은 종목
    """

    def calculate(self) -> Dict[str, Any]:
        """Magic Formula 계산"""
        if not self.validate_data():
            return self.get_error_result("필수 데이터 없음")

        # ROIC 계산
        roic = self._calculate_roic()

        # Earnings Yield 계산
        earnings_yield = self._calculate_earnings_yield()

        if roic is None or earnings_yield is None:
            return self.get_error_result("ROIC 또는 EY 계산 실패")

        # 점수 계산 (0-100)
        score = self._calculate_score(roic, earnings_yield)

        # 평가 등급
        rating = self.get_rating_from_score(score)

        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "model": "Magic Formula",
            "score": round(score, 2),
            "rating": rating,
            "roic": round(roic, 2),
            "earnings_yield": round(earnings_yield, 2),
            "details": {
                "ebit": self.latest_financial.bsop_prti,
                "invested_capital": self._get_invested_capital(),
                "market_cap": self._estimate_market_cap()
            },
            "interpretation": self._get_interpretation(roic, earnings_yield, score)
        }

    def _calculate_roic(self) -> Optional[float]:
        """
        ROIC (투하자본수익률) 계산

        ROIC = EBIT / Invested Capital
        Invested Capital = 총자산 - 총부채
        """
        if not self.latest_financial:
            return None

        ebit = self.latest_financial.bsop_prti  # 영업이익
        if not ebit or ebit <= 0:
            return None

        invested_capital = self._get_invested_capital()
        if not invested_capital or invested_capital <= 0:
            return None

        roic = (ebit / invested_capital) * 100

        return roic

    def _get_invested_capital(self) -> Optional[int]:
        """투하자본 계산"""
        if not self.latest_financial:
            return None

        total_assets = self.latest_financial.total_aset
        total_liabilities = self.latest_financial.total_lblt

        if not total_assets or not total_liabilities:
            return None

        # Invested Capital = 총자산 - 총부채
        # 또는: 자본총계 = 총자산 - 총부채
        invested_capital = total_assets - total_liabilities

        return invested_capital

    def _calculate_earnings_yield(self) -> Optional[float]:
        """
        Earnings Yield (이익수익률) 계산

        EY = EBIT / 기업가치
        기업가치(EV) = 시가총액 + 순부채
        간이: EBIT / 시가총액
        """
        if not self.latest_financial:
            return None

        ebit = self.latest_financial.bsop_prti
        if not ebit or ebit <= 0:
            return None

        market_cap = self._estimate_market_cap()
        if not market_cap or market_cap <= 0:
            return None

        earnings_yield = (ebit / market_cap) * 100

        return earnings_yield

    def _estimate_market_cap(self) -> Optional[int]:
        """
        시가총액 추정

        시가총액 = 현재가 × 주식수
        주식수 = 자본총계 / BPS
        """
        if not self.latest_financial or not self.current_price:
            return None

        # 주식수 추정
        if self.latest_financial.bps and self.latest_financial.bps > 0:
            if self.latest_financial.total_cptl:
                shares = self.latest_financial.total_cptl / float(
                    self.latest_financial.bps
                )
                market_cap = int(self.current_price * shares)
                return market_cap

        # 대안: EPS로 추정
        if self.latest_financial.eps and self.latest_financial.eps > 0:
            if self.latest_financial.thtr_ntin:
                shares = self.latest_financial.thtr_ntin / float(
                    self.latest_financial.eps
                )
                market_cap = int(self.current_price * shares)
                return market_cap

        return None

    def _calculate_score(self, roic: float, earnings_yield: float) -> float:
        """
        Magic Formula 점수 계산 (0-100)

        평가 기준:
        - ROIC: 20% 이상 = 우수, 10% 이상 = 양호
        - EY: 10% 이상 = 우수, 5% 이상 = 양호

        두 지표 모두 높을수록 좋음
        """
        # ROIC 점수 (50점 배점)
        roic_score = self.normalize_score(
            roic,
            excellent_threshold=20,
            good_threshold=10,
            fair_threshold=5,
            inverse=False  # 높을수록 좋음
        ) * 0.5

        # Earnings Yield 점수 (50점 배점)
        ey_score = self.normalize_score(
            earnings_yield,
            excellent_threshold=10,
            good_threshold=5,
            fair_threshold=2,
            inverse=False
        ) * 0.5

        total_score = roic_score + ey_score

        return total_score

    def _get_interpretation(
            self,
            roic: float,
            earnings_yield: float,
            score: float
    ) -> str:
        """해석 생성"""
        msg = "**Magic Formula 분석 (조엘 그린블라트)**\n\n"

        # ROIC 평가
        msg += f"**1. ROIC (투하자본수익률): {roic:.1f}%**\n"
        if roic >= 20:
            msg += "→ 매우 우수한 자본 효율성입니다. 투하자본 대비 높은 수익을 창출합니다.\n\n"
        elif roic >= 10:
            msg += "→ 양호한 자본 효율성입니다. 안정적인 수익 창출 능력이 있습니다.\n\n"
        elif roic >= 5:
            msg += "→ 보통 수준의 자본 효율성입니다.\n\n"
        else:
            msg += "→ 낮은 자본 효율성입니다. 투하자본 대비 수익이 부족합니다.\n\n"

        # Earnings Yield 평가
        msg += f"**2. Earnings Yield (이익수익률): {earnings_yield:.1f}%**\n"
        if earnings_yield >= 10:
            msg += "→ 매우 높은 이익수익률로 저평가 가능성이 큽니다.\n\n"
        elif earnings_yield >= 5:
            msg += "→ 적정한 이익수익률 수준입니다.\n\n"
        elif earnings_yield >= 2:
            msg += "→ 낮은 이익수익률로 고평가 가능성이 있습니다.\n\n"
        else:
            msg += "→ 매우 낮은 이익수익률로 고평가되어 있습니다.\n\n"

        # 종합 평가
        msg += f"**종합 점수: {score:.0f}/100**\n\n"

        if score >= 85:
            msg += "Magic Formula 기준으로 매우 우수한 종목입니다. "
            msg += "높은 수익성과 저평가가 동시에 확인됩니다."
        elif score >= 70:
            msg += "Magic Formula 기준으로 우수한 종목입니다. "
            msg += "수익성과 밸류에이션이 양호합니다."
        elif score >= 50:
            msg += "Magic Formula 기준으로 보통 수준입니다. "
            msg += "추가 분석이 필요합니다."
        else:
            msg += "Magic Formula 기준으로는 매력적이지 않습니다."

        return msg

    def get_rank_in_market(self, market: str = "ALL") -> Optional[Dict[str, Any]]:
        """
        전체 시장에서 순위 계산

        Args:
            market: KOSPI, KOSDAQ, ALL

        Returns:
            {
                "roic_rank": ROIC 순위,
                "ey_rank": EY 순위,
                "combined_rank": 종합 순위,
                "total_stocks": 전체 종목 수
            }
        """
        try:
            # 이 종목의 지표
            my_result = self.calculate()
            if "error" in my_result:
                return None

            my_roic = my_result["roic"]
            my_ey = my_result["earnings_yield"]

            # 시장 필터
            market_filter = ""
            if market != "ALL":
                market_filter = f"AND s.mrkt_ctg_cls_code = '{market}'"

            # ROIC 순위
            roic_rank_query = text(f"""
                SELECT COUNT(*) + 1 as rank
                FROM stocks s
                JOIN financial_statements fs ON s.ticker = fs.ticker
                WHERE s.is_active = TRUE
                  AND fs.period_type = 'Y'
                  AND fs.stac_yymm = (
                      SELECT MAX(stac_yymm)
                      FROM financial_statements fs2
                      WHERE fs2.ticker = s.ticker AND fs2.period_type = 'Y'
                  )
                  AND fs.bsop_prti > 0
                  AND (fs.total_aset - fs.total_lblt) > 0
                  AND (fs.bsop_prti / (fs.total_aset - fs.total_lblt)) * 100 > :my_roic
                  {market_filter}
            """)

            roic_rank = self.db.execute(
                roic_rank_query, {"my_roic": my_roic}
            ).scalar()

            # 전체 종목 수
            total_query = text(f"""
                SELECT COUNT(DISTINCT s.ticker)
                FROM stocks s
                WHERE s.is_active = TRUE
                  {market_filter}
            """)

            total_stocks = self.db.execute(total_query).scalar()

            return {
                "roic_rank": roic_rank,
                "total_stocks": total_stocks,
                "percentile": round((1 - roic_rank / total_stocks) * 100, 1)
            }

        except Exception as e:
            logger.error(f"순위 계산 실패: {e}")
            return None