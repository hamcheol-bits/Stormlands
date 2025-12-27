"""
ChromaDB 연결 및 관리
벡터 임베딩 저장 및 유사도 검색
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional, List, Dict, Any
import logging

from app.config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ChromaDBClient:
    """ChromaDB 클라이언트 (싱글톤)"""

    _instance: Optional['ChromaDBClient'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            # ChromaDB 클라이언트 초기화
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=ChromaSettings(
                    anonymized_telemetry=False
                )
            )

            # 연결 테스트
            self.client.heartbeat()
            logger.info(f"ChromaDB connected: {settings.chroma_url}")

            self._initialized = True

        except Exception as e:
            logger.error(f"ChromaDB connection failed: {e}")
            self.client = None

    def get_or_create_collection(
            self,
            name: str,
            metadata: Optional[Dict[str, Any]] = None
    ):
        """
        컬렉션 조회 또는 생성

        Args:
            name: 컬렉션 이름
            metadata: 컬렉션 메타데이터

        Returns:
            ChromaDB Collection
        """
        if not self.client:
            raise RuntimeError("ChromaDB client not initialized")

        try:
            collection = self.client.get_or_create_collection(
                name=name,
                metadata=metadata or {}
            )
            logger.info(f"Collection ready: {name}")
            return collection

        except Exception as e:
            logger.error(f"Failed to get/create collection {name}: {e}")
            raise

    def delete_collection(self, name: str) -> bool:
        """
        컬렉션 삭제

        Args:
            name: 컬렉션 이름

        Returns:
            삭제 성공 여부
        """
        if not self.client:
            return False

        try:
            self.client.delete_collection(name=name)
            logger.info(f"Collection deleted: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """
        전체 컬렉션 목록 조회

        Returns:
            컬렉션 이름 리스트
        """
        if not self.client:
            return []

        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def get_collection_stats(self, name: str) -> Dict[str, Any]:
        """
        컬렉션 통계 조회

        Args:
            name: 컬렉션 이름

        Returns:
            통계 정보 (문서 수, 메타데이터 등)
        """
        if not self.client:
            return {}

        try:
            collection = self.client.get_collection(name=name)
            count = collection.count()

            return {
                "name": name,
                "count": count,
                "metadata": collection.metadata
            }

        except Exception as e:
            logger.error(f"Failed to get collection stats for {name}: {e}")
            return {}


def get_chroma_client() -> ChromaDBClient:
    """ChromaDB 클라이언트 싱글톤 반환"""
    return ChromaDBClient()


def check_chroma_connection() -> bool:
    """ChromaDB 연결 확인"""
    try:
        client = get_chroma_client()
        if client.client:
            client.client.heartbeat()
            return True
        return False
    except Exception as e:
        logger.error(f"ChromaDB health check failed: {e}")
        return False