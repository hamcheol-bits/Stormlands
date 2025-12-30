"""
밸류에이션 모델 베이스 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.stock import Stock
from app.models.financial_statement import FinancialStatement
from app.models.stock_price import StockPrice


class BaseValuation(ABC):
    """
    밸류에이션 모델 추상 베이스 클래스

    모든 밸류에이션 모델이 구현해야 하는 인터페이스
    """

    def __init__(self, db: Session, ticker: str):
        """
        Args:
            db: 데이터베이스 세션
            ticker: 종목코드
        """
        self.db = db
        self.ticker = ticker

        # 기본 데이터 로드
        self.stock = self._load_stock()
        self.latest_financial = self._load_latest_financial()
        self.current_price_data = self._load_current_price()

    def _load_stock(self) -> Optional[Stock]:
        """종목 기본 정보 로드"""
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
        """최근 N년 재무제표 로드"""
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
        """시장 (KOSPI/KOSDAQ)"""
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