"""
Valuation API Router (테스트용)
종목 티커만 입력받아서 밸류에이션 분석 확인
"""
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.valuation import (
    DCFValuation,
    RelativeValuation,
    GrahamValuation,
    MagicFormula,
    ComprehensiveValuation
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/valuation", tags=["Valuation"])


# ============================================================
# 1. 개별 모델 테스트 엔드포인트
# ============================================================

@router.get("/{ticker}/dcf")
async def test_dcf_valuation(
        ticker: str,
        wacc: float = Query(8.0, description="WACC (%)"),
        terminal_growth: float = Query(2.0, description="영구성장률 (%)"),
        db: Session = Depends(get_db)
):
    """
    DCF 모델 테스트

    Examples:
        - GET /api/valuation/005930/dcf
        - GET /api/valuation/005930/dcf?wacc=9.0&terminal_growth=2.5
    """
    try:
        dcf = DCFValuation(
            db, ticker,
            wacc=wacc,
            terminal_growth=terminal_growth
        )
        result = dcf.calculate()
        return result
    except Exception as e:
        logger.error(f"DCF 계산 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/relative")
async def test_relative_valuation(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    상대가치 평가 테스트

    Examples:
        - GET /api/valuation/005930/relative
    """
    try:
        relative = RelativeValuation(db, ticker)
        result = relative.calculate()
        return result
    except Exception as e:
        logger.error(f"상대가치 계산 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/graham")
async def test_graham_valuation(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    Graham Number 테스트

    Examples:
        - GET /api/valuation/005930/graham
    """
    try:
        graham = GrahamValuation(db, ticker)
        result = graham.calculate()
        return result
    except Exception as e:
        logger.error(f"Graham 계산 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/magic")
async def test_magic_formula(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    Magic Formula 테스트

    Examples:
        - GET /api/valuation/005930/magic
    """
    try:
        magic = MagicFormula(db, ticker)
        result = magic.calculate()
        return result
    except Exception as e:
        logger.error(f"Magic Formula 계산 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 2. 종합 분석 엔드포인트
# ============================================================

@router.get("/{ticker}/comprehensive")
async def comprehensive_valuation(
        ticker: str,
        include_details: bool = Query(True, description="모델별 상세 결과 포함"),
        dcf_wacc: float = Query(8.0, description="DCF WACC (%)"),
        dcf_growth: float = Query(2.0, description="DCF 영구성장률 (%)"),
        db: Session = Depends(get_db)
):
    """
    종합 밸류에이션 분석 (4가지 모델 통합)

    Examples:
        - GET /api/valuation/005930/comprehensive
        - GET /api/valuation/005930/comprehensive?include_details=false
        - GET /api/valuation/005930/comprehensive?dcf_wacc=9.0

    Returns:
        {
            "ticker": "005930",
            "stock_name": "삼성전자",
            "composite_score": 75.5,
            "composite_rating": "buy",
            "investment_recommendation": "매수",
            "model_scores": {
                "dcf": 80.0,
                "relative": 70.0,
                "graham": 75.0,
                "magic": 77.0
            },
            "model_ratings": {...},
            "strengths": [...],
            "weaknesses": [...],
            "interpretation": "..."
        }
    """
    try:
        comp = ComprehensiveValuation(db, ticker)

        result = comp.analyze(
            include_details=include_details,
            dcf_params={
                "wacc": dcf_wacc,
                "terminal_growth": dcf_growth
            }
        )

        return result

    except Exception as e:
        logger.error(f"종합 분석 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}")
async def quick_valuation(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    간단 밸류에이션 (상세 결과 제외)

    Examples:
        - GET /api/valuation/005930

    Returns:
        종합 점수, 등급, 투자 추천만 반환
    """
    try:
        comp = ComprehensiveValuation(db, ticker)

        result = comp.analyze(include_details=False)

        # 간소화된 응답
        return {
            "ticker": result["ticker"],
            "stock_name": result["stock_name"],
            "composite_score": result["composite_score"],
            "composite_rating": result["composite_rating"],
            "investment_recommendation": result["investment_recommendation"],
            "model_scores": result["model_scores"],
            "strengths": result["strengths"],
            "weaknesses": result["weaknesses"]
        }

    except Exception as e:
        logger.error(f"간단 분석 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 3. 다중 종목 비교
# ============================================================

@router.post("/compare")
async def compare_valuations(
        tickers: list[str] = Query(..., description="종목코드 리스트"),
        sort_by: str = Query("composite_score", description="정렬 기준"),
        db: Session = Depends(get_db)
):
    """
    여러 종목 밸류에이션 비교

    Examples:
        - POST /api/valuation/compare?tickers=005930&tickers=000660&tickers=035720
        - POST /api/valuation/compare?tickers=005930&tickers=000660&sort_by=dcf

    Returns:
        종목별 분석 결과 (정렬됨)
    """
    if not tickers:
        raise HTTPException(status_code=400, detail="최소 1개 종목 필요")

    if len(tickers) > 20:
        raise HTTPException(status_code=400, detail="최대 20개 종목까지 비교 가능")

    try:
        comp = ComprehensiveValuation(db, tickers[0])
        results = comp.compare_multiple(tickers, sort_by=sort_by)

        return {
            "total": len(results),
            "sort_by": sort_by,
            "results": results
        }

    except Exception as e:
        logger.error(f"비교 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 4. 시장 스크리닝 (상위 N개)
# ============================================================

@router.get("/screen/top")
async def screen_top_valuations(
        market: str = Query("ALL", description="KOSPI/KOSDAQ/ALL"),
        limit: int = Query(20, ge=1, le=100, description="결과 개수"),
        min_score: float = Query(60.0, description="최소 점수"),
        db: Session = Depends(get_db)
):
    """
    밸류에이션 점수 상위 종목 스크리닝

    Examples:
        - GET /api/valuation/screen/top
        - GET /api/valuation/screen/top?market=KOSPI&limit=10
        - GET /api/valuation/screen/top?min_score=70

    Note:
        실제로는 전체 종목을 계산해야 하므로 시간이 오래 걸립니다.
        캐싱 또는 배치 처리 권장
    """
    try:
        from app.models.stock import Stock

        # 활성 종목 조회
        query = db.query(Stock).filter(Stock.is_active == True)

        if market != "ALL":
            query = query.filter(Stock.mrkt_ctg_cls_code == market)

        stocks = query.limit(limit * 5).all()  # 일부만 계산

        results = []
        for stock in stocks:
            try:
                comp = ComprehensiveValuation(db, stock.ticker)
                result = comp.analyze(include_details=False)

                if result["composite_score"] >= min_score:
                    results.append(result)

            except Exception as e:
                logger.warning(f"스크리닝 중 실패 ({stock.ticker}): {e}")
                continue

        # 점수 순 정렬
        results.sort(key=lambda x: x["composite_score"], reverse=True)

        return {
            "market": market,
            "min_score": min_score,
            "total": len(results),
            "results": results[:limit]
        }

    except Exception as e:
        logger.error(f"스크리닝 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 5. 헬스 체크
# ============================================================

@router.get("/health")
async def valuation_health():
    """
    Valuation 모듈 헬스 체크

    Examples:
        - GET /api/valuation/health
    """
    return {
        "status": "ok",
        "models": [
            "DCF",
            "Relative Valuation",
            "Graham Number",
            "Magic Formula"
        ],
        "version": "1.0.0"
    }