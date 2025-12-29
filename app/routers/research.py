"""
Research Analysis API Router
리서치 리포트 메타데이터 분석 API
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.services.research_analysis_service import get_research_analysis_service

router = APIRouter(prefix="/api/research", tags=["research"])


# ============================================================
# 종목별 리포트 조회
# ============================================================

@router.get("/{ticker}/reports")
async def get_reports(
        ticker: str,
        days: int = Query(180, ge=1, le=365, description="조회 기간 (일)"),
        limit: int = Query(50, ge=1, le=200, description="결과 개수"),
        db: Session = Depends(get_db)
):
    """
    특정 종목의 최근 리포트 조회

    Args:
        ticker: 종목코드
        days: 조회 기간 (일)
        limit: 결과 개수

    Examples:
        - GET /api/research/005930/reports
        - GET /api/research/005930/reports?days=90&limit=20

    Returns:
        리포트 리스트
    """
    service = get_research_analysis_service()
    reports = service.get_reports_by_ticker(db, ticker, days, limit)

    return {
        "ticker": ticker,
        "period_days": days,
        "total": len(reports),
        "items": [r.to_dict() for r in reports]
    }


@router.get("/{ticker}/latest")
async def get_latest_report(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    최신 리포트 조회

    Args:
        ticker: 종목코드

    Examples:
        - GET /api/research/005930/latest

    Returns:
        최신 리포트
    """
    service = get_research_analysis_service()
    report = service.get_latest_report_by_ticker(db, ticker)

    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for {ticker}"
        )

    return report.to_dict()


# ============================================================
# 투자의견 분석
# ============================================================

@router.get("/{ticker}/opinion-consensus")
async def get_opinion_consensus(
        ticker: str,
        days: int = Query(180, ge=1, le=365, description="분석 기간 (일)"),
        db: Session = Depends(get_db)
):
    """
    투자의견 컨센서스 조회

    Args:
        ticker: 종목코드
        days: 분석 기간 (일)

    Examples:
        - GET /api/research/005930/opinion-consensus
        - GET /api/research/005930/opinion-consensus?days=90

    Returns:
        투자의견 컨센서스
    """
    service = get_research_analysis_service()
    consensus = service.get_opinion_consensus(db, ticker, days)

    if consensus["total_reports"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for {ticker} in last {days} days"
        )

    return consensus


@router.get("/{ticker}/target-price")
async def get_target_price_consensus(
        ticker: str,
        days: int = Query(180, ge=1, le=365, description="분석 기간 (일)"),
        db: Session = Depends(get_db)
):
    """
    목표가 컨센서스 조회

    Args:
        ticker: 종목코드
        days: 분석 기간 (일)

    Examples:
        - GET /api/research/005930/target-price
        - GET /api/research/005930/target-price?days=90

    Returns:
        목표가 통계
    """
    service = get_research_analysis_service()
    consensus = service.get_target_price_consensus(db, ticker, days)

    if consensus["count"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No target prices found for {ticker} in last {days} days"
        )

    return consensus


# ============================================================
# 종합 분석
# ============================================================

@router.get("/{ticker}/summary")
async def get_stock_analysis_summary(
        ticker: str,
        days: int = Query(180, ge=1, le=365, description="분석 기간 (일)"),
        db: Session = Depends(get_db)
):
    """
    종목 종합 분석 요약

    리포트 집계, 투자의견 컨센서스, 목표가 분석을 한 번에 제공

    Args:
        ticker: 종목코드
        days: 분석 기간 (일)

    Examples:
        - GET /api/research/005930/summary
        - GET /api/research/005930/summary?days=90

    Returns:
        종합 분석 결과
    """
    service = get_research_analysis_service()
    summary = service.get_stock_analysis_summary(db, ticker, days)

    if summary["report_summary"]["total_reports"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for {ticker} in last {days} days"
        )

    return summary


# ============================================================
# 증권사별 분석
# ============================================================

@router.get("/brokerages/statistics")
async def get_brokerage_statistics(
        days: int = Query(180, ge=1, le=365, description="분석 기간 (일)"),
        db: Session = Depends(get_db)
):
    """
    증권사별 리포트 발행 통계

    Args:
        days: 분석 기간 (일)

    Examples:
        - GET /api/research/brokerages/statistics
        - GET /api/research/brokerages/statistics?days=30

    Returns:
        증권사별 통계
    """
    service = get_research_analysis_service()
    stats = service.get_brokerage_statistics(db, days)

    return {
        "period_days": days,
        "total_brokerages": len(stats),
        "items": stats
    }


@router.get("/brokerages/{brokerage}/reports")
async def get_reports_by_brokerage(
        brokerage: str,
        days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
        limit: int = Query(50, ge=1, le=200, description="결과 개수"),
        db: Session = Depends(get_db)
):
    """
    특정 증권사의 최근 리포트 조회

    Args:
        brokerage: 증권사명
        days: 조회 기간 (일)
        limit: 결과 개수

    Examples:
        - GET /api/research/brokerages/미래에셋증권/reports
        - GET /api/research/brokerages/한국투자증권/reports?days=7

    Returns:
        리포트 리스트
    """
    service = get_research_analysis_service()
    reports = service.get_reports_by_brokerage(db, brokerage, days, limit)

    return {
        "brokerage": brokerage,
        "period_days": days,
        "total": len(reports),
        "items": [r.to_dict() for r in reports]
    }


# ============================================================
# 전체 시장 분석
# ============================================================

@router.get("/market/coverage")
async def get_market_coverage(
        days: int = Query(30, ge=1, le=365, description="분석 기간 (일)"),
        db: Session = Depends(get_db)
):
    """
    전체 시장 리포트 커버리지

    Args:
        days: 분석 기간 (일)

    Examples:
        - GET /api/research/market/coverage
        - GET /api/research/market/coverage?days=7

    Returns:
        시장 커버리지 통계
    """
    service = get_research_analysis_service()
    coverage = service.get_market_coverage(db, days)

    return coverage


@router.get("/market/top-covered")
async def get_most_covered_stocks(
        days: int = Query(30, ge=1, le=365, description="분석 기간 (일)"),
        limit: int = Query(20, ge=1, le=100, description="결과 개수"),
        db: Session = Depends(get_db)
):
    """
    가장 많이 커버된 종목 TOP N

    Args:
        days: 분석 기간 (일)
        limit: 결과 개수

    Examples:
        - GET /api/research/market/top-covered
        - GET /api/research/market/top-covered?days=7&limit=10

    Returns:
        리포트가 많은 종목 순위
    """
    service = get_research_analysis_service()
    top_stocks = service.get_most_covered_stocks(db, days, limit)

    return {
        "period_days": days,
        "total": len(top_stocks),
        "items": top_stocks
    }