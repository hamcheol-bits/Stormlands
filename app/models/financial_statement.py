"""
재무제표 모델 (읽기 전용)
DB 스키마와 완전히 일치하는 버전
"""
from sqlalchemy import Column, String, BIGINT, DECIMAL, CHAR, TIMESTAMP, ForeignKey, Index
from app.core.database import Base


class FinancialStatement(Base):
    """재무제표 통합 테이블 (완전판)"""

    __tablename__ = "financial_statements"

    # ========================================
    # Primary Key
    # ========================================
    id = Column(BIGINT, primary_key=True, autoincrement=True, comment="PK")

    # ========================================
    # Foreign Key & 기준 정보
    # ========================================
    ticker = Column(String(20), ForeignKey("stocks.ticker"), nullable=False, index=True, comment="종목코드")
    stac_yymm = Column(String(6), nullable=False, index=True, comment="결산년월 (YYYYMM)")
    period_type = Column(CHAR(1), nullable=False, comment="기간구분 (Y:연간, Q:분기)")

    # ========================================
    # 대차대조표 (Balance Sheet)
    # KIS API: FHKST66430100
    # ========================================
    cras = Column(BIGINT, nullable=True, comment="유동자산")
    fxas = Column(BIGINT, nullable=True, comment="고정자산")
    total_aset = Column(BIGINT, nullable=True, comment="자산총계")
    flow_lblt = Column(BIGINT, nullable=True, comment="유동부채")
    fix_lblt = Column(BIGINT, nullable=True, comment="고정부채")
    total_lblt = Column(BIGINT, nullable=True, comment="부채총계")
    cpfn = Column(BIGINT, nullable=True, comment="자본금")
    total_cptl = Column(BIGINT, nullable=True, comment="자본총계")

    # ========================================
    # 손익계산서 (Income Statement)
    # KIS API: FHKST66430200
    # ========================================
    sale_account = Column(BIGINT, nullable=True, comment="매출액")
    sale_cost = Column(BIGINT, nullable=True, comment="매출원가")
    sale_totl_prfi = Column(BIGINT, nullable=True, comment="매출총이익")
    bsop_prti = Column(BIGINT, nullable=True, comment="영업이익")
    op_prfi = Column(BIGINT, nullable=True, comment="특별이익")
    spec_prfi = Column(BIGINT, nullable=True, comment="특별손실")
    thtr_ntin = Column(BIGINT, nullable=True, comment="당기순이익")

    # ========================================
    # 재무비율 (Financial Ratios)
    # KIS API: FHKST66430300
    # ========================================
    grs = Column(DECIMAL(20, 4), nullable=True, comment="매출액증가율 (%)")
    bsop_prfi_inrt = Column(DECIMAL(20, 4), nullable=True, comment="영업이익증가율 (%)")
    ntin_inrt = Column(DECIMAL(20, 4), nullable=True, comment="순이익증가율 (%)")
    roe_val = Column(DECIMAL(20, 2), nullable=True, comment="ROE (%)")
    eps = Column(DECIMAL(15, 2), nullable=True, comment="EPS (원)")
    sps = Column(DECIMAL(15, 2), nullable=True, comment="주당매출액 (원)")
    bps = Column(DECIMAL(15, 2), nullable=True, comment="BPS (원)")
    rsrv_rate = Column(DECIMAL(20, 4), nullable=True, comment="유보율 (%)")
    lblt_rate = Column(DECIMAL(20, 4), nullable=True, comment="부채비율 (%)")

    # ========================================
    # 수익성비율 (Profitability Ratios)
    # KIS API: FHKST66430400
    # ========================================
    cptl_ntin_rate = Column(DECIMAL(20, 2), nullable=True, comment="총자본순이익률 (%)")
    self_cptl_ntin_inrt = Column(DECIMAL(20, 2), nullable=True, comment="자기자본순이익률 (%)")
    sale_ntin_rate = Column(DECIMAL(20, 2), nullable=True, comment="매출액순이익률 (%)")
    sale_totl_rate = Column(DECIMAL(20, 2), nullable=True, comment="매출액총이익률 (%)")

    # ========================================
    # 기타주요비율 (Other Major Ratios)
    # KIS API: FHKST66430500
    # ========================================
    eva = Column(BIGINT, nullable=True, comment="EVA (Economic Value Added)")
    ebitda = Column(BIGINT, nullable=True, comment="EBITDA")
    ev_ebitda = Column(DECIMAL(20, 2), nullable=True, comment="EV/EBITDA")

    # ========================================
    # 성장성비율 (Growth Ratios)
    # KIS API: FHKST66430800
    # ========================================
    equt_inrt = Column(DECIMAL(10, 4), nullable=True, comment="자기자본증가율 (%)")
    totl_aset_inrt = Column(DECIMAL(10, 4), nullable=True, comment="총자산증가율 (%)")

    # ========================================
    # 타임스탬프
    # ========================================
    created_at = Column(TIMESTAMP, comment="생성일시")
    updated_at = Column(TIMESTAMP, comment="수정일시")

    def __repr__(self):
        return f"<FinancialStatement(ticker={self.ticker}, period={self.stac_yymm}, type={self.period_type})>"

    def to_dict(self):
        """딕셔너리 변환 (완전판)"""
        return {
            # 기본 정보
            "ticker": self.ticker,
            "stac_yymm": self.stac_yymm,
            "period_type": self.period_type,

            # 대차대조표
            "cras": self.cras,
            "fxas": self.fxas,
            "total_aset": self.total_aset,
            "flow_lblt": self.flow_lblt,
            "fix_lblt": self.fix_lblt,
            "total_lblt": self.total_lblt,
            "cpfn": self.cpfn,
            "total_cptl": self.total_cptl,

            # 손익계산서
            "sale_account": self.sale_account,
            "sale_cost": self.sale_cost,
            "sale_totl_prfi": self.sale_totl_prfi,
            "bsop_prti": self.bsop_prti,
            "op_prfi": self.op_prfi,
            "spec_prfi": self.spec_prfi,
            "thtr_ntin": self.thtr_ntin,

            # 재무비율
            "grs": float(self.grs) if self.grs else None,
            "bsop_prfi_inrt": float(self.bsop_prfi_inrt) if self.bsop_prfi_inrt else None,
            "ntin_inrt": float(self.ntin_inrt) if self.ntin_inrt else None,
            "roe_val": float(self.roe_val) if self.roe_val else None,
            "eps": float(self.eps) if self.eps else None,
            "sps": float(self.sps) if self.sps else None,
            "bps": float(self.bps) if self.bps else None,
            "rsrv_rate": float(self.rsrv_rate) if self.rsrv_rate else None,
            "lblt_rate": float(self.lblt_rate) if self.lblt_rate else None,

            # 수익성비율
            "cptl_ntin_rate": float(self.cptl_ntin_rate) if self.cptl_ntin_rate else None,
            "self_cptl_ntin_inrt": float(self.self_cptl_ntin_inrt) if self.self_cptl_ntin_inrt else None,
            "sale_ntin_rate": float(self.sale_ntin_rate) if self.sale_ntin_rate else None,
            "sale_totl_rate": float(self.sale_totl_rate) if self.sale_totl_rate else None,

            # 기타주요비율
            "eva": self.eva,
            "ebitda": self.ebitda,
            "ev_ebitda": float(self.ev_ebitda) if self.ev_ebitda else None,

            # 성장성비율
            "equt_inrt": float(self.equt_inrt) if self.equt_inrt else None,
            "totl_aset_inrt": float(self.totl_aset_inrt) if self.totl_aset_inrt else None,

            # 타임스탬프
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }