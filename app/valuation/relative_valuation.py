"""
상대가치 평가 (Relative Valuation)
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy import text

from .base_valuation import BaseValuation

logger = logging.getLogger(__name__)


class RelativeValuation(BaseValuation):
    """
    상대가치 평가

    업종 평균 대비 상대 배수 분석:
    - PER (Price to Earnings Ratio)
    - PBR (Price to Book Ratio)
    - PEG (PER to Growth)
    - PSR (Price to Sales Ratio)
    """

    def calculate(self) -> Dict[str, Any]:
        """상대가치 평가 계산"""
        if not self.validate_data():
            return self.get_error_result("필수 데이터 없음")

        # 종목 지표 계산
        stock_metrics = self._calculate_stock_metrics()
        if not stock_metrics:
            return self.get_error_result("종목 지표 계산 실패")

        # 섹터 평균 계산
        sector_metrics = self._calculate_sector_metrics()
        if not sector_metrics:
            return self.get_error_result("섹터 평균 계산 실패")

        # 상대 배수 계산
        relative_multiples = self._calculate_relative_multiples(
            stock_metrics, sector_metrics
        )

        # 성장률 계산
        growth_rate = self._calculate_growth_rate()

        # PEG Ratio
        peg = None
        if stock_metrics["per"] and growth_rate and growth_rate > 0:
            peg = stock_metrics["per"] / growth_rate

        # 점수 계산
        score = self._calculate_score(relative_multiples, peg)

        # 평가 등급
        rating = self.get_rating_from_score(score)

        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "model": "Relative Valuation",
            "score": round(score, 2),
            "rating": rating,
            "stock_metrics": stock_metrics,
            "sector_metrics": sector_metrics,
            "relative_multiples": relative_multiples,
            "growth_rate": round(growth_rate, 2) if growth_rate else None,
            "peg_ratio": round(peg, 2) if peg else None,
            "interpretation": self._get_interpretation(
                relative_multiples, peg, score
            )
        }

    def _calculate_stock_metrics(self) -> Optional[Dict[str, Any]]:
        """종목 밸류에이션 지표 계산"""
        if not self.latest_financial or not self.current_price:
            return None

        fs = self.latest_financial

        # PER
        per = None
        if fs.eps and fs.eps > 0:
            per = self.current_price / float(fs.eps)

        # PBR
        pbr = None
        if fs.bps and fs.bps > 0:
            pbr = self.current_price / float(fs.bps)

        # PSR
        psr = None
        if fs.sps and fs.sps > 0:
            psr = self.current_price / float(fs.sps)

        # ROE
        roe = float(fs.roe_val) if fs.roe_val else None

        return {
            "per": per,
            "pbr": pbr,
            "psr": psr,
            "roe": roe,
            "eps": float(fs.eps) if fs.eps else None,
            "bps": float(fs.bps) if fs.bps else None,
            "sps": float(fs.sps) if fs.sps else None
        }

    def _calculate_sector_metrics(self) -> Optional[Dict[str, Any]]:
        """섹터 평균 지표 계산"""
        sector = self.sector

        # 동일 섹터 종목들의 평균
        query = text("""
                     SELECT AVG(CASE WHEN fs.eps > 0 THEN sp.stck_clpr / fs.eps ELSE NULL END) as avg_per,
                            AVG(CASE WHEN fs.bps > 0 THEN sp.stck_clpr / fs.bps ELSE NULL END) as avg_pbr,
                            AVG(CASE WHEN fs.sps > 0 THEN sp.stck_clpr / fs.sps ELSE NULL END) as avg_psr,
                            AVG(fs.roe_val)                                                    as avg_roe,
                            COUNT(DISTINCT s.ticker)                                           as stock_count
                     FROM stocks s
                              JOIN financial_statements fs ON s.ticker = fs.ticker
                              JOIN (SELECT ticker, stck_clpr, stck_bsop_date
                                    FROM stock_prices sp1
                                    WHERE stck_bsop_date = (SELECT MAX(stck_bsop_date)
                                                            FROM stock_prices sp2
                                                            WHERE sp2.ticker = sp1.ticker)) sp ON s.ticker = sp.ticker
                     WHERE s.bstp_kor_isnm = :sector
                       AND s.is_active = TRUE
                       AND fs.period_type = 'Y'
                       AND fs.stac_yymm = (SELECT MAX(stac_yymm)
                                           FROM financial_statements fs2
                                           WHERE fs2.ticker = s.ticker
                                             AND fs2.period_type = 'Y')
                     """)

        result = self.db.execute(query, {"sector": sector}).fetchone()

        if not result or not result.stock_count:
            return None

        return {
            "avg_per": float(result.avg_per) if result.avg_per else None,
            "avg_pbr": float(result.avg_pbr) if result.avg_pbr else None,
            "avg_psr": float(result.avg_psr) if result.avg_psr else None,
            "avg_roe": float(result.avg_roe) if result.avg_roe else None,
            "stock_count": result.stock_count
        }

    def _calculate_relative_multiples(
            self,
            stock_metrics: Dict[str, Any],
            sector_metrics: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        """상대 배수 계산"""
        per_to_sector = None
        if stock_metrics["per"] and sector_metrics["avg_per"]:
            per_to_sector = stock_metrics["per"] / sector_metrics["avg_per"]

        pbr_to_sector = None
        if stock_metrics["pbr"] and sector_metrics["avg_pbr"]:
            pbr_to_sector = stock_metrics["pbr"] / sector_metrics["avg_pbr"]

        psr_to_sector = None
        if stock_metrics["psr"] and sector_metrics["avg_psr"]:
            psr_to_sector = stock_metrics["psr"] / sector_metrics["avg_psr"]

        return {
            "per_to_sector": per_to_sector,
            "pbr_to_sector": pbr_to_sector,
            "psr_to_sector": psr_to_sector
        }

    def _calculate_growth_rate(self, years: int = 3) -> Optional[float]:
        """
        순이익 연평균 성장률 (CAGR) 계산

        CAGR = ((최종값 / 초기값)^(1/년수) - 1) × 100
        """
        history = self._load_financial_history(years + 1)

        if len(history) < 2:
            return None

        # 최신, 최오래된 순이익
        latest = history[0].thtr_ntin
        oldest = history[-1].thtr_ntin

        if not latest or not oldest or oldest <= 0:
            return None

        n = len(history) - 1
        cagr = (pow(latest / oldest, 1 / n) - 1) * 100

        return cagr

    def _calculate_score(
            self,
            relative_multiples: Dict[str, Optional[float]],
            peg: Optional[float]
    ) -> float:
        """
        상대가치 점수 계산 (0-100)

        평가 기준:
        - PER/섹터PER < 0.7: 저평가
        - PER/섹터PER < 0.9: 약간 저평가
        - PER/섹터PER 0.9-1.1: 적정
        - PER/섹터PER > 1.3: 고평가
        - PEG < 1: 저평가
        """
        scores = []

        # PER 상대 점수
        per_ratio = relative_multiples.get("per_to_sector")
        if per_ratio:
            per_score = self.normalize_score(
                per_ratio,
                excellent_threshold=0.7,
                good_threshold=0.9,
                fair_threshold=1.1,
                inverse=True  # 낮을수록 좋음
            )
            scores.append(per_score)

        # PBR 상대 점수
        pbr_ratio = relative_multiples.get("pbr_to_sector")
        if pbr_ratio:
            pbr_score = self.normalize_score(
                pbr_ratio,
                excellent_threshold=0.7,
                good_threshold=0.9,
                fair_threshold=1.1,
                inverse=True
            )
            scores.append(pbr_score)

        # PEG 점수
        if peg:
            peg_score = self.normalize_score(
                peg,
                excellent_threshold=0.7,
                good_threshold=1.0,
                fair_threshold=1.5,
                inverse=True
            )
            scores.append(peg_score * 1.2)  # PEG 가중치 높임

        # 평균
        if not scores:
            return 50  # 기본값

        return sum(scores) / len(scores)

    def _get_interpretation(
            self,
            relative_multiples: Dict[str, Optional[float]],
            peg: Optional[float],
            score: float
    ) -> str:
        """해석 생성"""
        per_ratio = relative_multiples.get("per_to_sector")
        pbr_ratio = relative_multiples.get("pbr_to_sector")

        msg = f"{self.sector} 섹터 평균 대비 "

        # PER 분석
        if per_ratio:
            if per_ratio < 0.7:
                msg += f"PER이 30% 이상 낮아 저평가되어 있으며, "
            elif per_ratio < 0.9:
                msg += f"PER이 약간 낮아 저평가 가능성이 있으며, "
            elif per_ratio < 1.1:
                msg += f"PER이 적정 수준이며, "
            else:
                msg += f"PER이 {(per_ratio - 1) * 100:.0f}% 높아 고평가되어 있으며, "

        # PBR 분석
        if pbr_ratio:
            if pbr_ratio < 0.8:
                msg += f"PBR도 낮은 편입니다. "
            elif pbr_ratio > 1.2:
                msg += f"PBR은 높은 편입니다. "
            else:
                msg += f"PBR은 적정 수준입니다. "

        # PEG 분석
        if peg:
            msg += f"\n\nPEG Ratio는 {peg:.2f}로 "
            if peg < 1.0:
                msg += "성장률 대비 저평가되어 있습니다."
            elif peg < 1.5:
                msg += "성장률 대비 적정 수준입니다."
            else:
                msg += "성장률 대비 고평가되어 있습니다."

        # 종합 평가
        msg += f"\n\n상대가치 점수: {score:.0f}/100"

        return msg