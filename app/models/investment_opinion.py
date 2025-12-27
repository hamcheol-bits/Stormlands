"""
투자의견 모델 (읽기 전용)
"""
from sqlalchemy import Column, String, DateTime
from app.core.database import Base


class InvestmentOpinion(Base):
    """투자의견 컨센서스"""

    __tablename__ = "investment_opinions"

    # Composite Primary Key
    ticker = Column(String(12), primary_key=True, comment="종목코드")
    mbcr_name = Column(String(100), primary_key=True, comment="증권사명")

    # 투자의견 정보
    stck_bsop_date = Column(String(8), nullable=False, comment="영업일자")
    invt_opnn = Column(String(50), comment="투자의견")
    invt_opnn_cls_code = Column(String(10), comment="투자의견구분코드")
    rgbf_invt_opnn = Column(String(50), comment="직전투자의견")
    rgbf_invt_opnn_cls_code = Column(String(10), comment="직전투자의견구분코드")
    hts_goal_prc = Column(String(20), comment="목표가격")

    # 타임스탬프
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def __repr__(self):
        return f"<InvestmentOpinion(ticker={self.ticker}, firm={self.mbcr_name}, opinion={self.invt_opnn})>"

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "firm": self.mbcr_name,
            "date": self.stck_bsop_date,
            "opinion": self.invt_opnn,
            "target_price": self.hts_goal_prc,
            "previous_opinion": self.rgbf_invt_opnn
        }