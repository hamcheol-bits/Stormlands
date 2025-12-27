"""
재무제표 모델 (읽기 전용)
"""
from sqlalchemy import Column, String, BIGINT, DECIMAL, CHAR, TIMESTAMP, ForeignKey, Index
from app.core.database import Base


class FinancialStatement(Base):
    """재무제표 통합 테이블"""

    __tablename__ = "financial_statements"

    # Primary Key
    id = Column(BIGINT, primary_key=True, autoincrement=True)

    # Foreign Key
    ticker = Column(String(20), ForeignKey("stocks.ticker"), nullable=False, index=True)

    # 기준 정보
    stac_yymm = Column(String(6), nullable=False, index=True, comment="결산년월")
    period_type = Column(CHAR(1), nullable=False, comment="기간구분 (Y:연간, Q:분기)")

    # 대차대조표
    total_aset = Column(BIGINT, nullable=True, comment="자산총계")
    total_lblt = Column(BIGINT, nullable=True, comment="부채총계")
    total_cptl = Column(BIGINT, nullable=True, comment="자본총계")

    # 손익계산서
    sale_account = Column(BIGINT, nullable=True, comment="매출액")
    bsop_prti = Column(BIGINT, nullable=True, comment="영업이익")
    thtr_ntin = Column(BIGINT, nullable=True, comment="당기순이익")

    # 재무비율
    grs = Column(DECIMAL(20, 4), nullable=True, comment="매출액증가율")
    bsop_prfi_inrt = Column(DECIMAL(20, 4), nullable=True, comment="영업이익증가율")
    ntin_inrt = Column(DECIMAL(20, 4), nullable=True, comment="순이익증가율")
    roe_val = Column(DECIMAL(10, 4), nullable=True, comment="ROE")
    eps = Column(DECIMAL(15, 2), nullable=True, comment="EPS")
    bps = Column(DECIMAL(15, 2), nullable=True, comment="BPS")
    lblt_rate = Column(DECIMAL(20, 4), nullable=True, comment="부채비율")

    # 수익성비율
    sale_ntin_rate = Column(DECIMAL(10, 4), nullable=True, comment="매출액순이익률")

    # 타임스탬프
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<FinancialStatement(ticker={self.ticker}, period={self.stac_yymm}, type={self.period_type})>"

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "stac_yymm": self.stac_yymm,
            "period_type": self.period_type,
            "total_aset": self.total_aset,
            "total_lblt": self.total_lblt,
            "total_cptl": self.total_cptl,
            "sale_account": self.sale_account,
            "bsop_prti": self.bsop_prti,
            "thtr_ntin": self.thtr_ntin,
            "grs": float(self.grs) if self.grs else None,
            "bsop_prfi_inrt": float(self.bsop_prfi_inrt) if self.bsop_prfi_inrt else None,
            "ntin_inrt": float(self.ntin_inrt) if self.ntin_inrt else None,
            "roe_val": float(self.roe_val) if self.roe_val else None,
            "eps": float(self.eps) if self.eps else None,
            "bps": float(self.bps) if self.bps else None,
            "lblt_rate": float(self.lblt_rate) if self.lblt_rate else None,
            "sale_ntin_rate": float(self.sale_ntin_rate) if self.sale_ntin_rate else None
        }