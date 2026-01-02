"""
주식 밸류에이션 캐시 모델 (읽기 전용)
"""
from sqlalchemy import Column, String, BIGINT, DECIMAL, Date, TIMESTAMP, ForeignKey, Index
from app.core.database import Base


class StockValuationCache(Base):
    """
    주식 밸류에이션 지표 캐시 테이블

    - 주가, 재무제표 기반 지표를 미리 계산하여 저장
    - 스크리닝 쿼리 성능 최적화
    - TTM (Trailing Twelve Months) 지표 포함
    """

    __tablename__ = "stock_valuation_cache"

    # ========================================
    # Primary Key
    # ========================================
    ticker = Column(String(20), ForeignKey("stocks.ticker"), primary_key=True, comment="종목코드")

    # ========================================
    # 주가 정보 (최신 영업일 기준)
    # ========================================
    current_price = Column(DECIMAL(20, 2), nullable=False, comment="현재가")
    price_date = Column(Date, nullable=False, comment="주가 기준일")

    # ========================================
    # 재무제표 정보 (최신 연간 기준)
    # ========================================
    eps = Column(DECIMAL(15, 2), nullable=True, comment="EPS (주당순이익)")
    eps_ttm = Column(DECIMAL(15, 2), nullable=True, comment="EPS TTM (최근 4분기 합산)")
    bps = Column(DECIMAL(15, 2), nullable=True, comment="BPS (주당순자산)")
    roe_val = Column(DECIMAL(10, 4), nullable=True, comment="ROE (%)")
    stac_yymm = Column(String(6), nullable=True, comment="재무제표 기준년월")

    # ========================================
    # TTM 손익 지표 (최근 4분기 합산)
    # ========================================
    net_income_ttm = Column(BIGINT, nullable=True, comment="당기순이익 TTM (최근 4분기 합산)")
    sales_ttm = Column(BIGINT, nullable=True, comment="매출액 TTM (최근 4분기 합산)")
    operating_income_ttm = Column(BIGINT, nullable=True, comment="영업이익 TTM (최근 4분기 합산)")

    # ========================================
    # 계산된 밸류에이션 지표
    # ========================================
    per = Column(DECIMAL(10, 2), nullable=True, comment="PER (주가/EPS)")
    per_ttm = Column(DECIMAL(10, 2), nullable=True, comment="PER TTM (주가/EPS_TTM)")
    pbr = Column(DECIMAL(10, 2), nullable=True, comment="PBR (주가/BPS)")

    # ========================================
    # 추가 지표
    # ========================================
    market_cap = Column(BIGINT, nullable=True, comment="시가총액 (현재가 × 상장주식수)")
    dividend_yield = Column(DECIMAL(10, 4), nullable=True, comment="배당수익률 (%)")

    # ========================================
    # 메타 정보
    # ========================================
    last_calculated_at = Column(TIMESTAMP, comment="마지막 계산 시각")
    ttm_base_quarter = Column(String(6), nullable=True, comment="TTM 기준 분기 (YYYYMM)")

    def __repr__(self):
        return f"<StockValuationCache(ticker={self.ticker}, per_ttm={self.per_ttm}, pbr={self.pbr})>"

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            # 기본 정보
            "ticker": self.ticker,
            "current_price": float(self.current_price) if self.current_price else None,
            "price_date": self.price_date.isoformat() if self.price_date else None,

            # 재무제표 정보
            "eps": float(self.eps) if self.eps else None,
            "eps_ttm": float(self.eps_ttm) if self.eps_ttm else None,
            "bps": float(self.bps) if self.bps else None,
            "roe_val": float(self.roe_val) if self.roe_val else None,
            "stac_yymm": self.stac_yymm,

            # TTM 손익 지표
            "net_income_ttm": self.net_income_ttm,
            "sales_ttm": self.sales_ttm,
            "operating_income_ttm": self.operating_income_ttm,

            # 밸류에이션 지표
            "per": float(self.per) if self.per else None,
            "per_ttm": float(self.per_ttm) if self.per_ttm else None,
            "pbr": float(self.pbr) if self.pbr else None,

            # 추가 지표
            "market_cap": self.market_cap,
            "dividend_yield": float(self.dividend_yield) if self.dividend_yield else None,

            # 메타 정보
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
            "ttm_base_quarter": self.ttm_base_quarter
        }