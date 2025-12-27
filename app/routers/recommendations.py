"""
자연어 종목 추천 API
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.services.query_analyzer import get_query_analyzer

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("/query")
async def recommend_by_query(
        query: str = Query(..., description="자연어 질문"),
        max_results: int = Query(10, ge=1, le=20, description="최대 결과 개수"),
        db: Session = Depends(get_db)
):
    """
    자연어 질문으로 종목 추천

    **예시 질문:**
    - "KOSPI에서 저평가되고 영업이익률이 상승중인 3개만 추천해줘"
    - "저평가된 반도체 종목 3개 추천해줘"
    - "배당수익률 높은 안정적인 종목 5개"
    - "성장성 높은 바이오 종목"
    - "ROE 15% 이상, 부채비율 100% 이하인 KOSDAQ 종목"

    **Args:**
    - query: 자연어 질문
    - max_results: 최대 결과 개수 (1~20)

    **Returns:**
    ```json
    {
      "query": "원본 질문",
      "analysis": {
        "market": "KOSPI",
        "sector": "반도체",
        "financial_conditions": {...},
        "count": 3
      },
      "stocks": [
        {
          "ticker": "005930",
          "name": "삼성전자",
          "market": "KOSPI",
          "sector": "전기전자",
          "financials": {
            "roe": 12.5,
            "sales_growth": 8.3,
            ...
          }
        },
        ...
      ],
      "reasoning": "AI 추천 이유",
      "count": 3
    }
    ```
    """
    try:
        analyzer = get_query_analyzer()
        result = await analyzer.analyze_and_recommend(db, query, max_results)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추천 실패: {str(e)}")


@router.get("/examples")
async def get_example_queries():
    """
    예시 질문 목록

    **Returns:**
    카테고리별 예시 질문 리스트
    """
    return {
        "valuation": [
            "저평가된 반도체 종목 3개 추천해줘",
            "KOSPI에서 PBR 1.0 이하, ROE 10% 이상인 종목",
            "ROE는 높고 부채비율은 낮은 안정적인 가치주 5개"
        ],
        "growth": [
            "성장성 높은 바이오 종목",
            "매출 성장률 20% 이상인 IT 종목",
            "영업이익이 크게 증가하고 있는 종목 추천해줘"
        ],
        "dividend": [
            "배당수익률 높은 안정적인 종목 5개",
            "고배당 우량주 추천해줘",
            "꾸준히 배당을 지급하는 KOSPI 대형주"
        ],
        "sector": [
            "자동차 부품 관련 유망주",
            "2차전지 관련주 중 재무 건전한 종목",
            "화장품 업종에서 성장성 좋은 종목"
        ],
        "mixed": [
            "KOSDAQ에서 저평가되고 성장성 있는 중소형주 5개",
            "ROE 15% 이상, 매출성장률 10% 이상, 부채비율 100% 이하",
            "반도체 장비 관련주 중 밸류에이션 매력적인 종목"
        ]
    }