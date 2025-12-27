"""
투자의견 분석 API
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.services.opinion_analyzer import get_opinion_analyzer

router = APIRouter(prefix="/api/opinions", tags=["opinions"])


@router.get("/{ticker}")
async def analyze_opinions(
        ticker: str,
        include_analysis: bool = Query(True, description="AI 분석 포함 여부"),
        db: Session = Depends(get_db)
):
    """
    종목의 투자의견 분석

    **Args:**
    - ticker: 종목코드
    - include_analysis: AI 종합 분석 포함 여부

    **Returns:**
    ```json
    {
      "ticker": "005930",
      "name": "삼성전자",
      "opinions": [
        {
          "firm": "한국투자증권",
          "opinion": "매수",
          "target_price": "85000",
          "date": "20241220"
        },
        ...
      ],
      "consensus": {
        "sentiment": "positive",
        "sentiment_score": 0.85,
        "buy_count": 5,
        "hold_count": 2,
        "sell_count": 0,
        "buy_ratio": 0.71
      },
      "analysis": "AI 종합 분석..." (optional)
    }
    ```
    """
    try:
        analyzer = get_opinion_analyzer()
        result = await analyzer.analyze_stock_opinions(db, ticker, include_analysis)

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


@router.post("/batch")
async def batch_analyze_opinions(
        tickers: List[str] = Query(..., description="종목코드 리스트"),
        db: Session = Depends(get_db)
):
    """
    여러 종목의 투자의견 일괄 분석

    **Args:**
    - tickers: 종목코드 리스트 (최대 20개)

    **Returns:**
    종목별 투자의견 분석 결과 리스트
    """
    if len(tickers) > 20:
        raise HTTPException(status_code=400, detail="최대 20개까지 분석 가능합니다")

    try:
        analyzer = get_opinion_analyzer()
        results = await analyzer.batch_analyze_opinions(db, tickers)

        return {
            "total": len(tickers),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"일괄 분석 실패: {str(e)}")


@router.get("/bullish/list")
async def get_bullish_stocks(
        min_buy_ratio: float = Query(0.6, ge=0.0, le=1.0, description="최소 매수 의견 비율"),
        limit: int = Query(20, ge=1, le=50, description="결과 개수"),
        db: Session = Depends(get_db)
):
    """
    투자의견이 긍정적인 종목 찾기

    증권사들의 매수 의견 비율이 높은 종목을 찾습니다.

    **Args:**
    - min_buy_ratio: 최소 매수 의견 비율 (0.6 = 60%)
    - limit: 결과 개수

    **Returns:**
    ```json
    {
      "criteria": {
        "min_buy_ratio": 0.6,
        "limit": 20
      },
      "stocks": [
        {
          "ticker": "005930",
          "name": "삼성전자",
          "buy_ratio": 0.85,
          "total_opinions": 7,
          "buy_count": 6
        },
        ...
      ],
      "count": 15
    }
    ```
    """
    try:
        analyzer = get_opinion_analyzer()
        stocks = await analyzer.find_bullish_stocks(db, min_buy_ratio, limit)

        return {
            "criteria": {
                "min_buy_ratio": min_buy_ratio,
                "limit": limit
            },
            "stocks": stocks,
            "count": len(stocks)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


@router.get("/consensus/summary")
async def get_consensus_summary(
        market: str = Query("ALL", description="시장 구분 (KOSPI/KOSDAQ/ALL)"),
        limit: int = Query(10, ge=1, le=50, description="종목 개수"),
        db: Session = Depends(get_db)
):
    """
    시장별 투자의견 컨센서스 요약

    **Args:**
    - market: 시장 구분
    - limit: 표시할 종목 개수

    **Returns:**
    투자의견이 가장 긍정적인 상위 종목 리스트
    """
    try:
        from app.models.stock import Stock

        # 활성 종목 조회
        query = db.query(Stock).filter(Stock.is_active == True)

        if market != "ALL":
            query = query.filter(Stock.mrkt_ctg_cls_code == market)

        stocks = query.limit(100).all()  # 최대 100개
        tickers = [s.ticker for s in stocks]

        # 일괄 분석
        analyzer = get_opinion_analyzer()
        results = await analyzer.batch_analyze_opinions(db, tickers)

        # 긍정적인 순으로 정렬
        sorted_results = sorted(
            [r for r in results if r.get("consensus")],
            key=lambda x: x["consensus"].get("buy_ratio", 0),
            reverse=True
        )

        return {
            "market": market,
            "analyzed": len(results),
            "top_stocks": sorted_results[:limit]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 실패: {str(e)}")