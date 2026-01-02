"""
하이브리드 분석 API 라우터
전통적 밸류에이션 + AI 융합 분석
"""
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.hybrid_analysis_service import get_hybrid_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hybrid", tags=["Hybrid Analysis"])


@router.get("/{ticker}")
async def analyze_stock_hybrid(
        ticker: str,
        include_ai: bool = Query(True, description="AI 조정 포함"),
        include_sentiment: bool = Query(True, description="감성 분석 포함"),
        explain: bool = Query(True, description="차이 설명 포함"),
        db: Session = Depends(get_db)
):
    """
    ## 종목 하이브리드 분석 (전통 밸류에이션 + AI)

    ### 3-Layer 분석 구조:

    **Layer 1: 전통적 밸류에이션**
    - DCF (Discounted Cash Flow)
    - Graham Number (벤저민 그레이엄)
    - Magic Formula (조엘 그린블라트)
    - 상대가치 (Relative Valuation)
    → 정량적 기준선 제공

    **Layer 2: AI 분석**
    - FinGPT: 재무 품질 검증, 이상 패턴 탐지
    - FinBERT: 투자의견 감성 분석
    - Llama3: 맥락 이해 및 해석
    → 정성적 맥락 추가

    **Layer 3: 하이브리드 통합**
    - AI 기반 점수 조정
    - 신뢰도 평가
    - 최종 투자 판단
    → 상호 검증을 통한 신뢰성 확보

    ### 사용 예시:
    ```bash
    # 기본 (전체 분석)
    GET /api/hybrid/005930

    # 전통 밸류에이션 + AI 조정
    GET /api/hybrid/005930?include_ai=true&include_sentiment=true

    # AI 조정 제외 (전통 모델만)
    GET /api/hybrid/005930?include_ai=false
    ```

    ### 응답 구조:
    ```json
    {
      "ticker": "005930",
      "stock_name": "삼성전자",

      "traditional_valuation": {
        "composite_score": 72.5,
        "composite_rating": "buy",
        "model_scores": {
          "dcf": 75.0,
          "relative": 68.0,
          "graham": 70.0,
          "magic": 77.0
        },
        "strengths": ["DCF", "Magic Formula"],
        "weaknesses": ["상대가치"]
      },

      "ai_analysis": {
        "financial_quality_check": {
          "quality_score": 75,
          "issues": ["일회성 이익 포함 가능성"],
          "warnings": ["영업이익률 하락 추세"],
          "score_adjustment": -3,
          "adjustment_reason": "..."
        },
        "sentiment_analysis": {
          "sentiment": "positive",
          "sentiment_score": 0.85,
          "opinion_counts": {"buy": 25, "hold": 3, "sell": 0},
          "recent_trend": "improving"
        },
        "anomaly_detection": {
          "anomalies_detected": false
        }
      },

      "hybrid_result": {
        "base_score": 72.5,
        "adjusted_score": 69.5,
        "score_change": -3.0,
        "final_rating": "buy",
        "confidence_level": "high",
        "adjustments": [...]
      },

      "interpretation": "전통 모델 분석 결과 72.5점(매수)이나...",
      "recommendation": "매수",
      "key_points": ["포인트1", "포인트2", "포인트3"]
    }
    ```
    """
    try:
        service = get_hybrid_analysis_service(db)

        result = await service.analyze_stock(
            ticker,
            include_ai_adjustment=include_ai,
            include_sentiment=include_sentiment,
            explain_differences=explain
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hybrid analysis failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/comparison")
async def compare_traditional_vs_ai(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    ## 전통 vs AI 비교 분석

    전통적 밸류에이션과 AI 조정 후 결과를 직접 비교하여
    두 접근법의 차이와 일치도를 확인

    ### 사용 예시:
    ```bash
    GET /api/hybrid/005930/comparison
    ```

    ### 응답 구조:
    ```json
    {
      "ticker": "005930",
      "stock_name": "삼성전자",

      "traditional_score": 72.5,
      "traditional_rating": "buy",

      "ai_adjusted_score": 69.5,
      "ai_adjusted_rating": "buy",

      "score_difference": -3.0,
      "agreement_level": "mostly_agree",

      "adjustments": [
        {
          "type": "financial_quality",
          "adjustment": -3,
          "reason": "일회성 이익 제외 필요"
        }
      ],

      "interpretation": "전통 모델과 AI 분석이 대체로 일치하나..."
    }
    ```

    ### 일치도 기준:
    - **strong_agree**: 차이 ≤ 3점
    - **mostly_agree**: 차이 ≤ 8점
    - **some_disagreement**: 차이 ≤ 15점
    - **strong_disagreement**: 차이 > 15점
    """
    try:
        service = get_hybrid_analysis_service(db)

        result = await service.analyze_stock(
            ticker,
            include_ai_adjustment=True,
            include_sentiment=True,
            explain_differences=True
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        trad_score = result["traditional_valuation"]["composite_score"]
        ai_score = result["hybrid_result"]["adjusted_score"]
        diff = ai_score - trad_score

        # 일치도 판단
        if abs(diff) <= 3:
            agreement = "strong_agree"
            agreement_desc = "전통 모델과 AI가 강하게 일치"
        elif abs(diff) <= 8:
            agreement = "mostly_agree"
            agreement_desc = "전통 모델과 AI가 대체로 일치"
        elif abs(diff) <= 15:
            agreement = "some_disagreement"
            agreement_desc = "전통 모델과 AI에 다소 차이 있음"
        else:
            agreement = "strong_disagreement"
            agreement_desc = "전통 모델과 AI가 크게 불일치"

        return {
            "ticker": result["ticker"],
            "stock_name": result["stock_name"],

            # 전통 모델
            "traditional_score": trad_score,
            "traditional_rating": result["traditional_valuation"]["composite_rating"],

            # AI 조정
            "ai_adjusted_score": ai_score,
            "ai_adjusted_rating": result["hybrid_result"]["final_rating"],

            # 차이 분석
            "score_difference": round(diff, 1),
            "agreement_level": agreement,
            "agreement_description": agreement_desc,

            # 조정 내역
            "adjustments": result["hybrid_result"].get("adjustments", []),
            "explanation": result["hybrid_result"].get("explanation", ""),

            # 최종 해석
            "interpretation": result.get("interpretation", "")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def analyze_batch_hybrid(
        tickers: list[str] = Query(..., description="종목코드 리스트 (최대 10개)"),
        mode: str = Query("summary", description="응답 모드: summary/full"),
        db: Session = Depends(get_db)
):
    """
    ## 여러 종목 일괄 하이브리드 분석

    여러 종목을 동시에 분석하여 비교 가능한 형태로 제공

    ### 사용 예시:
    ```bash
    # 간단한 요약 (기본)
    POST /api/hybrid/batch?tickers=005930&tickers=000660&tickers=035720

    # 전체 상세 정보
    POST /api/hybrid/batch?tickers=005930&tickers=000660&mode=full
    ```

    ### 제한사항:
    - 최대 10개 종목까지 가능
    - `mode=summary`: 핵심 정보만 (점수, 등급, 추천)
    - `mode=full`: 전체 분석 결과
    """
    if not tickers:
        raise HTTPException(status_code=400, detail="최소 1개 종목 필요")

    if len(tickers) > 10:
        raise HTTPException(status_code=400, detail="최대 10개 종목까지 가능")

    service = get_hybrid_analysis_service(db)
    results = []

    for ticker in tickers:
        try:
            result = await service.analyze_stock(
                ticker,
                include_ai_adjustment=True,
                include_sentiment=True,
                explain_differences=(mode == "full")
            )

            if mode == "summary":
                # 간소화된 응답
                simplified = {
                    "ticker": result["ticker"],
                    "stock_name": result["stock_name"],
                    "traditional_score": result["traditional_valuation"]["composite_score"],
                    "adjusted_score": result["hybrid_result"]["adjusted_score"],
                    "final_rating": result["hybrid_result"]["final_rating"],
                    "confidence": result["hybrid_result"]["confidence_level"],
                    "recommendation": result.get("recommendation", "보유")
                }
                results.append(simplified)
            else:
                # 전체 응답
                results.append(result)

        except Exception as e:
            logger.warning(f"Analysis failed for {ticker}: {e}")
            results.append({
                "ticker": ticker,
                "error": str(e)
            })

    # 점수 순으로 정렬 (조정 후 점수 기준)
    results_sorted = sorted(
        [r for r in results if "error" not in r],
        key=lambda x: x.get("adjusted_score", 0) if mode == "summary" else x["hybrid_result"]["adjusted_score"],
        reverse=True
    )

    # 에러 건 추가
    errors = [r for r in results if "error" in r]

    return {
        "mode": mode,
        "total": len(results),
        "success": len(results_sorted),
        "failed": len(errors),
        "results": results_sorted + errors
    }


@router.get("/{ticker}/traditional-only")
async def analyze_traditional_only(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    ## 전통적 밸류에이션만 (AI 제외)

    AI 조정 없이 순수하게 전통적 밸류에이션 모델만 실행

    ### 사용 예시:
    ```bash
    GET /api/hybrid/005930/traditional-only
    ```
    """
    try:
        service = get_hybrid_analysis_service(db)

        result = await service.analyze_stock(
            ticker,
            include_ai_adjustment=False,
            include_sentiment=False,
            explain_differences=False
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return {
            "ticker": result["ticker"],
            "stock_name": result["stock_name"],
            "market": result.get("market"),
            "sector": result.get("sector"),
            "valuation": result["traditional_valuation"],
            "analysis_date": result.get("analysis_date")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traditional analysis failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/ai-only")
async def analyze_ai_only(
        ticker: str,
        db: Session = Depends(get_db)
):
    """
    ## AI 분석만 (전통 밸류에이션 제외)

    재무 품질 검증, 감성 분석, 이상 패턴 탐지만 수행

    ### 사용 예시:
    ```bash
    GET /api/hybrid/005930/ai-only
    ```
    """
    try:
        service = get_hybrid_analysis_service(db)

        result = await service.analyze_stock(
            ticker,
            include_ai_adjustment=True,
            include_sentiment=True,
            explain_differences=False
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return {
            "ticker": result["ticker"],
            "stock_name": result["stock_name"],
            "ai_analysis": result.get("ai_analysis", {}),
            "analysis_date": result.get("analysis_date")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def hybrid_health():
    """
    ## 하이브리드 분석 헬스 체크

    사용 가능한 AI 모델 및 전통 밸류에이션 상태 확인

    ### 사용 예시:
    ```bash
    GET /api/hybrid/health
    ```
    """
    from app.core.ai_models import get_ai_engine

    ai_engine = get_ai_engine()

    # AI 엔진 초기화 시도
    try:
        await ai_engine.initialize()
    except:
        pass

    return {
        "status": "ok",
        "service": "Hybrid Analysis (Traditional + AI)",
        "version": "1.0.0",

        "components": {
            "traditional_valuation": {
                "status": "available",
                "models": ["DCF", "Graham", "Magic Formula", "Relative Valuation"]
            },
            "ai_models": {
                "llama3": "available" if ai_engine.llama3 else "unavailable",
                "fingpt": "available" if ai_engine.fingpt else "unavailable",
                "finbert": "available" if ai_engine.finbert else "unavailable"
            }
        },

        "capabilities": [
            "정량적 밸류에이션 (DCF, Graham, Magic, Relative)",
            "재무 품질 검증 (일회성 손익, 회계 이상)",
            "투자의견 감성 분석",
            "이상 패턴 탐지",
            "AI 기반 점수 조정",
            "자연어 해석 생성"
        ]
    }