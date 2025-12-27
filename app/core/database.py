"""
데이터베이스 연결 및 세션 관리
Valyria MySQL (읽기 전용)
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from app.config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# SQLAlchemy 엔진 생성 (읽기 전용)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # SQL 로그 출력 (개발 시 True)
)

# 세션 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base 클래스 (모델 상속용)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    데이터베이스 세션 의존성

    읽기 전용 세션 제공
    Stormlands는 분석만 수행하므로 쓰기 권한 불필요

    Usage:
        @app.get("/analysis")
        async def analyze(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """데이터베이스 연결 확인"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_db_stats() -> dict:
    """
    데이터베이스 통계 조회

    Returns:
        dict: 종목 수, 주가 데이터 수, 재무제표 수 등
    """
    try:
        db = SessionLocal()

        stats = {
            "stocks": db.execute(text(
                "SELECT COUNT(*) FROM stocks WHERE is_active = TRUE"
            )).scalar(),

            "stock_prices": db.execute(text(
                "SELECT COUNT(*) FROM stock_prices"
            )).scalar(),

            "financial_statements": db.execute(text(
                "SELECT COUNT(*) FROM financial_statements"
            )).scalar(),

            "dividends": db.execute(text(
                "SELECT COUNT(*) FROM dividends"
            )).scalar(),

            "investment_opinions": db.execute(text(
                "SELECT COUNT(*) FROM investment_opinions"
            )).scalar()
        }

        db.close()
        return stats

    except Exception as e:
        logger.error(f"Failed to get DB stats: {e}")
        return {}