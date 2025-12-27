"""
Stormlands 프로젝트 환경 설정
RAG 기반 AI 주식 분석 엔진
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # ============================================================
    # 프로젝트 기본 정보
    # ============================================================
    PROJECT_NAME: str = "Stormlands"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "RAG-based AI Stock Analysis Engine"

    # ============================================================
    # 데이터베이스 설정 (Valyria MySQL - 읽기 전용)
    # ============================================================
    DATABASE_URL: str

    # ============================================================
    # ChromaDB 설정
    # ============================================================
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "financial_statements"

    # ============================================================
    # AI 모델 설정
    # ============================================================

    # 1. Llama3 (범용 추론) - Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # 2. FinGPT (금융 특화) - Hugging Face
    FINGPT_MODEL: str = "FinGPT/fingpt-forecaster_dow30_llama2-7b_lora"
    FINGPT_ENABLED: bool = False  # 비활성화하면 Llama3만 사용

    # 3. FinBERT (감성 분석) - Hugging Face
    FINBERT_MODEL: str = "ProsusAI/finbert"
    FINBERT_ENABLED: bool = True

    # 4. Hugging Face Token (선택)
    HF_TOKEN: str = ""

    # 모델 캐시 디렉토리
    MODEL_CACHE_DIR: str = "./models"

    # GPU 사용 여부
    USE_GPU: bool = True

    # ============================================================
    # 임베딩 모델 설정
    # ============================================================
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ============================================================
    # 분석 설정 (기본값 - AI가 자체 판단할 때 참고)
    # ============================================================

    # 밸류에이션 참고 기준
    REFERENCE_MAX_PBR: float = 1.0
    REFERENCE_MIN_ROE: float = 10.0
    REFERENCE_MAX_DEBT_RATIO: float = 150.0
    REFERENCE_MIN_PER: float = 5.0
    REFERENCE_MAX_PER: float = 15.0

    # 성장주 참고 기준
    REFERENCE_MIN_SALES_GROWTH: float = 20.0
    REFERENCE_MIN_PROFIT_GROWTH: float = 15.0
    REFERENCE_MIN_ASSET_GROWTH: float = 10.0

    # 배당주 참고 기준
    REFERENCE_MIN_DIVIDEND_YIELD: float = 3.0
    REFERENCE_MIN_CONSECUTIVE_YEARS: int = 3

    # ============================================================
    # 쿼리 분석 설정
    # ============================================================

    # 기본 결과 개수
    DEFAULT_RESULT_COUNT: int = 5
    MAX_RESULT_COUNT: int = 20

    # AI 응답 설정
    AI_TEMPERATURE: float = 0.7  # 창의성 (0.0 ~ 1.0)
    AI_MAX_TOKENS: int = 2000

    # 재무 데이터 기간
    FINANCIAL_PERIOD: str = "Y"  # Y: 연간, Q: 분기
    PRICE_HISTORY_DAYS: int = 365

    # ============================================================
    # 포트폴리오 최적화
    # ============================================================
    MAX_STOCKS_IN_PORTFOLIO: int = 10
    DEFAULT_BUDGET: int = 10000000
    REBALANCE_THRESHOLD: float = 0.05

    # ============================================================
    # 로깅 설정
    # ============================================================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/stormlands.log"

    # ============================================================
    # API 설정
    # ============================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8200
    API_RELOAD: bool = True

    # Riverlands API (데이터 수집용)
    RIVERLANDS_API_URL: str = "http://localhost:8100"

    # Timezone
    TZ: str = "Asia/Seoul"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    # ============================================================
    # 유틸리티 프로퍼티
    # ============================================================

    @property
    def chroma_url(self) -> str:
        """ChromaDB 연결 URL"""
        return f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"

    @property
    def database_url(self) -> str:
        """MySQL 연결 URL"""
        return self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    """설정 객체 반환 (캐싱)"""
    return Settings()