"""
Research Report 모델 (Riverlands DB 읽기 전용)
Stormlands는 Riverlands의 research_reports 테이블을 읽어서 분석
"""
from sqlalchemy import Column, String, Date, Integer, TIMESTAMP
from app.core.database import Base


class ResearchReport(Base):
    """
    리서치 리포트 메타데이터 (읽기 전용)

    Riverlands의 research_reports 테이블과 동일한 스키마
    """
    __tablename__ = "research_reports"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 종목 정보
    ticker = Column(String(20), nullable=False, index=True, comment="종목코드")
    stock_name = Column(String(200), nullable=True, comment="종목명")

    # 리포트 기본 정보
    title = Column(String(500), nullable=False, comment="리포트 제목")
    brokerage = Column(String(100), nullable=False, index=True, comment="증권사")
    author = Column(String(100), nullable=True, comment="애널리스트")
    publish_date = Column(Date, nullable=False, index=True, comment="발행일")

    # 투자 의견
    investment_opinion = Column(String(50), nullable=True, index=True, comment="투자의견")
    target_price = Column(Integer, nullable=True, comment="목표가")

    # 리포트 링크
    report_url = Column(String(500), nullable=True, comment="리포트 URL")
    pdf_url = Column(String(500), nullable=True, comment="PDF URL")

    # 파일 정보
    pdf_filename = Column(String(500), nullable=True, comment="저장된 PDF 파일명")
    is_downloaded = Column(Integer, nullable=False, default=0, comment="PDF 다운로드 여부")

    # 타임스탬프
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    def __repr__(self):
        return (
            f"<ResearchReport("
            f"ticker={self.ticker}, "
            f"brokerage={self.brokerage}, "
            f"opinion={self.investment_opinion}, "
            f"target={self.target_price})>"
        )

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "stock_name": self.stock_name,
            "title": self.title,
            "brokerage": self.brokerage,
            "author": self.author,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "investment_opinion": self.investment_opinion,
            "target_price": self.target_price,
            "report_url": self.report_url,
            "pdf_url": self.pdf_url,
            "pdf_filename": self.pdf_filename,
            "is_downloaded": bool(self.is_downloaded),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }