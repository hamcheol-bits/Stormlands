"""
Valuation 기본 클래스 (완전판: TTM + 유틸리티 메서드)
"""
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.stock import Stock
from app.models.stock_price import StockPrice
from app.models.financial_statement import FinancialStatement


class BaseValuation(ABC):
    """밸류에이션 기본 클래스 (완전판)"""

    def __init__(self, db: Session, ticker: str):
        self.db = db
        self.ticker = ticker

        # 종목 정보
        self.stock = self._load_stock()

        # 최신 재무제표
        self.latest_financial = self._load_latest_financial()

        # 최신 주가
        self.current_price_data = self._load_current_price()

    def _load_stock(self) -> Optional[Stock]:
        """종목 정보 로드"""
        return self.db.query(Stock).filter(Stock.ticker == self.ticker).first()

    def _load_latest_financial(self) -> Optional[FinancialStatement]:
        """최신 연간 재무제표 로드"""
        return (
            self.db.query(FinancialStatement)
            .filter(
                and_(
                    FinancialStatement.ticker == self.ticker,
                    FinancialStatement.period_type == "Y"
                )
            )
            .order_by(desc(FinancialStatement.stac_yymm))
            .first()
        )

    def _load_current_price(self) -> Optional[StockPrice]:
        """최신 주가 로드"""
        return (
            self.db.query(StockPrice)
            .filter(StockPrice.ticker == self.ticker)
            .order_by(desc(StockPrice.stck_bsop_date))
            .first()
        )

    def _load_financial_history(self, years: int = 5) -> list[FinancialStatement]:
        """최근 N년 연간 재무제표 로드"""
        return (
            self.db.query(FinancialStatement)
            .filter(
                and_(
                    FinancialStatement.ticker == self.ticker,
                    FinancialStatement.period_type == "Y"
                )
            )
            .order_by(desc(FinancialStatement.stac_yymm))
            .limit(years)
            .all()
        )

    # ========================================
    # 🆕 TTM (Trailing Twelve Months) 지원
    # ========================================

    def _load_quarterly_history(self, quarters: int = 8) -> list[FinancialStatement]:
        """
        최근 N개 분기 재무제표 로드 (분기별 실적)

        Args:
            quarters: 조회할 분기 수

        Returns:
            분기별 재무제표 리스트 (최신순)

        Note:
            Riverlands 변경사항: 분기 데이터는 이제 누적이 아닌 분기별 실적
        """
        return (
            self.db.query(FinancialStatement)
            .filter(
                and_(
                    FinancialStatement.ticker == self.ticker,
                    FinancialStatement.period_type == "Q"
                )
            )
            .order_by(desc(FinancialStatement.stac_yymm))
            .limit(quarters)
            .all()
        )

    def _calculate_ttm(self, field_name: str, quarters: int = 4) -> Optional[int]:
        """
        TTM (Trailing Twelve Months) 계산
        최근 N개 분기 합산

        Args:
            field_name: 합산할 필드명 ('thtr_ntin', 'sale_account', 'bsop_prti' 등)
            quarters: 합산할 분기 수 (기본 4분기 = 12개월)

        Returns:
            TTM 값 또는 None

        Example:
            net_income_ttm = self._calculate_ttm('thtr_ntin')  # 최근 4분기 순이익 합산
            sales_ttm = self._calculate_ttm('sale_account')    # 최근 4분기 매출 합산
        """
        quarterly_data = self._load_quarterly_history(quarters)

        if len(quarterly_data) < quarters:
            return None

        total = 0
        for q in quarterly_data:
            value = getattr(q, field_name, None)
            if value is None:
                return None
            total += value

        return total

    def get_net_income_ttm(self) -> Optional[int]:
        """당기순이익 TTM (최근 4분기 합산)"""
        return self._calculate_ttm('thtr_ntin')

    def get_sales_ttm(self) -> Optional[int]:
        """매출액 TTM (최근 4분기 합산)"""
        return self._calculate_ttm('sale_account')

    def get_operating_income_ttm(self) -> Optional[int]:
        """영업이익 TTM (최근 4분기 합산)"""
        return self._calculate_ttm('bsop_prti')

    def get_eps_ttm(self) -> Optional[float]:
        """
        EPS TTM 계산 (최근 4분기 기준)

        Returns:
            EPS TTM 또는 None
        """
        net_income_ttm = self.get_net_income_ttm()
        if not net_income_ttm:
            return None

        # 발행주식수 추정 (최신 재무제표 기준)
        if not self.latest_financial:
            return None

        bps = self.latest_financial.bps
        total_cptl = self.latest_financial.total_cptl

        if not bps or not total_cptl or bps <= 0:
            return None

        # 발행주식수 = 자본총계 / BPS
        shares_outstanding = total_cptl / bps

        if shares_outstanding <= 0:
            return None

        return net_income_ttm / shares_outstanding

    def get_per_ttm(self) -> Optional[float]:
        """
        PER TTM 계산 (주가 / EPS_TTM)

        Returns:
            PER TTM 또는 None
        """
        eps_ttm = self.get_eps_ttm()
        current_price = self.current_price

        if not eps_ttm or not current_price or eps_ttm <= 0:
            return None

        return current_price / eps_ttm

    # ========================================
    # 기존 속성들
    # ========================================

    @property
    def current_price(self) -> Optional[float]:
        """현재가"""
        if self.current_price_data:
            return float(self.current_price_data.stck_clpr)
        return None

    @property
    def stock_name(self) -> str:
        """종목명"""
        if self.stock:
            return self.stock.hts_kor_isnm
        return "Unknown"

    @property
    def market(self) -> str:
        """시장구분"""
        if self.stock:
            return self.stock.mrkt_ctg_cls_code
        return "Unknown"

    @property
    def sector(self) -> str:
        """섹터"""
        if self.stock:
            return self.stock.bstp_kor_isnm or self.stock.sector or "Unknown"
        return "Unknown"

    @abstractmethod
    def calculate(self) -> Dict[str, Any]:
        """
        밸류에이션 계산 (추상 메서드)

        Returns:
            {
                "model": 모델명,
                "score": 점수 (0-100),
                "rating": 평가 등급,
                "intrinsic_value": 내재가치 (optional),
                "details": 세부 계산 결과,
                "interpretation": 해석
            }
        """
        pass

    # ========================================
    # 유틸리티 메서드들
    # ========================================

    def validate_data(self) -> bool:
        """필수 데이터 유효성 검사"""
        if not self.stock:
            return False
        if not self.latest_financial:
            return False
        if not self.current_price_data:
            return False
        return True

    def get_error_result(self, message: str) -> Dict[str, Any]:
        """에러 결과 반환"""
        return {
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "error": message,
            "score": None,
            "rating": "N/A"
        }

    def normalize_score(
            self,
            value: float,
            excellent_threshold: float,
            good_threshold: float,
            fair_threshold: float,
            inverse: bool = False
    ) -> float:
        """
        값을 0-100 점수로 정규화

        Args:
            value: 입력 값
            excellent_threshold: 우수 기준
            good_threshold: 양호 기준
            fair_threshold: 보통 기준
            inverse: True면 값이 낮을수록 좋음 (PER 등)

        Returns:
            0-100 점수
        """
        if value is None:
            return 50  # 기본값

        if inverse:
            # 낮을수록 좋음 (PER, PBR 등)
            if value <= excellent_threshold:
                return 100
            elif value <= good_threshold:
                return 80
            elif value <= fair_threshold:
                return 60
            else:
                return 40
        else:
            # 높을수록 좋음 (ROE, 성장률 등)
            if value >= excellent_threshold:
                return 100
            elif value >= good_threshold:
                return 80
            elif value >= fair_threshold:
                return 60
            else:
                return 40

    def get_rating_from_score(self, score: float) -> str:
        """점수를 등급으로 변환"""
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "fair"
        elif score >= 30:
            return "poor"
        else:
            return "very_poor"

    # ========================================
    # 안전한 속성 접근 헬퍼 메서드들
    # ========================================

    def get_financial_attr(self, attr_name: str, default=None):
        """
        재무제표 속성 안전하게 가져오기

        Args:
            attr_name: 속성명
            default: 기본값 (None)

        Returns:
            속성 값 또는 기본값
        """
        if not self.latest_financial:
            return default
        return getattr(self.latest_financial, attr_name, default)

    def get_bsop_prti(self) -> Optional[int]:
        """영업이익 (연간)"""
        return self.get_financial_attr('bsop_prti')

    def get_total_aset(self) -> Optional[int]:
        """자산총계"""
        return self.get_financial_attr('total_aset')

    def get_total_cptl(self) -> Optional[int]:
        """자본총계"""
        return self.get_financial_attr('total_cptl')

    def get_total_lblt(self) -> Optional[int]:
        """부채총계"""
        return self.get_financial_attr('total_lblt')

    def get_sale_account(self) -> Optional[int]:
        """매출액 (연간)"""
        return self.get_financial_attr('sale_account')

    def get_thtr_ntin(self) -> Optional[int]:
        """당기순이익 (연간)"""
        return self.get_financial_attr('thtr_ntin')

    def get_eps(self) -> Optional[float]:
        """EPS (주당순이익, 연간)"""
        eps = self.get_financial_attr('eps')
        return float(eps) if eps else None

    def get_bps(self) -> Optional[float]:
        """BPS (주당순자산)"""
        bps = self.get_financial_attr('bps')
        return float(bps) if bps else None

    def get_roe_val(self) -> Optional[float]:
        """ROE (자기자본이익률)"""
        roe = self.get_financial_attr('roe_val')
        return float(roe) if roe else None

    def get_sps(self) -> Optional[float]:
        """SPS (주당매출액)"""
        sps = self.get_financial_attr('sps')
        return float(sps) if sps else None

    def get_cras(self) -> Optional[int]:
        """유동자산"""
        return self.get_financial_attr('cras')

    def get_flow_lblt(self) -> Optional[int]:
        """유동부채"""
        return self.get_financial_attr('flow_lblt')