"""
Stormlands FastAPI 메인 애플리케이션
RAG 기반 AI 주식 분석 엔진
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.config.config import get_settings
from app.core.database import check_db_connection, get_db_stats
from app.core.chroma_client import check_chroma_connection, get_chroma_client
from app.core.llm_client import check_llm_connection, get_llm_client
from app.core.ai_models import get_ai_engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("="*60)

    # 1. MySQL 연결 확인
    if check_db_connection():
        logger.info("✓ MySQL connection successful")

        # DB 통계 조회
        stats = get_db_stats()
        logger.info(f"  - Stocks: {stats.get('stocks', 0):,}")
        logger.info(f"  - Stock Prices: {stats.get('stock_prices', 0):,}")
        logger.info(f"  - Financial Statements: {stats.get('financial_statements', 0):,}")
        logger.info(f"  - Dividends: {stats.get('dividends', 0):,}")
        logger.info(f"  - Investment Opinions: {stats.get('investment_opinions', 0):,}")
    else:
        logger.error("✗ MySQL connection failed")

    # 2. ChromaDB 연결 확인
    if check_chroma_connection():
        logger.info("✓ ChromaDB connection successful")

        # 컬렉션 목록 조회
        chroma_client = get_chroma_client()
        collections = chroma_client.list_collections()
        logger.info(f"  - Collections: {collections}")
    else:
        logger.warning("✗ ChromaDB connection failed (optional)")

    # 3. LLM 연결 확인
    try:
        llm_client = get_llm_client()
        if await llm_client.check_health():
            logger.info(f"✓ LLM ({settings.OLLAMA_MODEL}) ready")
        else:
            logger.warning(f"✗ LLM model {settings.OLLAMA_MODEL} not found")
    except Exception as e:
        logger.warning(f"✗ LLM connection failed: {e}")

    # 4. AI 모델 초기화
    logger.info("")
    logger.info("Initializing AI models...")
    try:
        ai_engine = get_ai_engine()
        await ai_engine.initialize()
        logger.info("✓ All AI models initialized")

        if ai_engine.llama3:
            logger.info("  - Llama3: Ready (범용 추론)")
        if ai_engine.fingpt:
            logger.info("  - FinGPT: Ready (금융 특화)")
        if ai_engine.finbert:
            logger.info("  - FinBERT: Ready (감성 분석)")

    except Exception as e:
        logger.warning(f"AI models initialization failed: {e}")
        logger.warning("Some features may not be available")

    logger.info("="*60)
    logger.info(f"{settings.PROJECT_NAME} is ready!")
    logger.info(f"API running on http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info("="*60)

    yield

    logger.info("Shutting down Stormlands")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "status": "running",
        "features": [
            "자연어 종목 추천",
            "AI 기반 재무 분석",
            "투자의견 감성 분석",
            "종목 비교 분석"
        ]
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""

    # MySQL 상태
    db_status = "healthy" if check_db_connection() else "unhealthy"

    # ChromaDB 상태
    chroma_status = "healthy" if check_chroma_connection() else "unavailable"

    # LLM 상태
    llm_status = "healthy" if await check_llm_connection() else "unavailable"

    # DB 통계
    db_stats = get_db_stats()

    # ChromaDB 통계
    chroma_stats = {}
    try:
        chroma_client = get_chroma_client()
        collections = chroma_client.list_collections()
        chroma_stats = {
            "collections": collections,
            "count": len(collections)
        }
    except:
        pass

    # AI 모델 상태
    ai_status = {}
    try:
        ai_engine = get_ai_engine()
        ai_status = {
            "llama3": ai_engine.llama3 is not None,
            "fingpt": ai_engine.fingpt is not None,
            "finbert": ai_engine.finbert is not None,
            "initialized": ai_engine._initialized
        }
    except:
        pass

    return {
        "status": "ok",
        "services": {
            "database": db_status,
            "chromadb": chroma_status,
            "llm": llm_status
        },
        "ai_models": ai_status,
        "data": {
            "mysql": db_stats,
            "chromadb": chroma_stats
        },
        "version": settings.VERSION
    }


# ============================================================
# 라우터 등록
# ============================================================
from app.routers import recommendations, opinions

app.include_router(recommendations.router)
app.include_router(opinions.router)

logger.info("All routers registered successfully")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )