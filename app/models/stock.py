"""
주식 기본 정보 모델 (읽기 전용)
Riverlands DB에서 조회만 수행
"""
from sqlalchemy import Column, String, Boolean, Date, TIMESTAMP
from sqlalchemy.orm import relationship
from app.core.database import Base


class Stock(Base):
    """주식 기본 정보 테이블"""

    __tablename__ = "stocks"

    # Primary Key
    ticker = Column(String(20), primary_key=True, comment="종목코드")

    # 기본 정보
    hts_kor_isnm = Column(String(200), nullable=False, comment="HTS한글종목명")
    name_en = Column(String(200), nullable=True, comment="영문명")
    mrkt_ctg_cls_code = Column(String(20), nullable=False, comment="시장범주구분코드")
    bstp_kor_isnm = Column(String(100), nullable=True, comment="업종한글종목명")
    sector = Column(String(100), nullable=True, comment="섹터")
    listed_date = Column(Date, nullable=True, comment="상장일")

    # 상태
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 여부")

    # 타임스탬프
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<Stock(ticker={self.ticker}, name={self.hts_kor_isnm}, market={self.mrkt_ctg_cls_code})>"

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "name": self.hts_kor_isnm,
            "name_en": self.name_en,
            "market": self.mrkt_ctg_cls_code,
            "sector": self.bstp_kor_isnm,
            "listed_date": self.listed_date.isoformat() if self.listed_date else None,
            "is_active": self.is_active
        }