"""
LLM 클라이언트 (Llama3)
Ollama 또는 Hugging Face 사용
"""
import logging
from typing import Optional, List, Dict, Any
import httpx

from app.config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """Ollama를 통한 Llama3 클라이언트"""

    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(timeout=300.0)  # 5분 타임아웃

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 2000,
            stream: bool = False
    ) -> str:
        """
        텍스트 생성

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (역할 정의)
            temperature: 생성 온도 (0.0 ~ 1.0)
            max_tokens: 최대 토큰 수
            stream: 스트리밍 여부

        Returns:
            생성된 텍스트
        """
        try:
            # 시스템 프롬프트가 있으면 결합
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            else:
                full_prompt = prompt

            # Ollama API 호출
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stream": stream
                }
            )

            response.raise_for_status()
            result = response.json()

            return result.get("response", "")

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def chat(
            self,
            messages: List[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: int = 2000
    ) -> str:
        """
        채팅 형식 생성

        Args:
            messages: 메시지 목록 [{"role": "user", "content": "..."}, ...]
            temperature: 생성 온도
            max_tokens: 최대 토큰 수

        Returns:
            생성된 응답
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stream": False
                }
            )

            response.raise_for_status()
            result = response.json()

            return result.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise

    async def check_model(self) -> bool:
        """
        모델 사용 가능 여부 확인

        Returns:
            모델 존재 여부
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            is_available = self.model in model_names

            if is_available:
                logger.info(f"Model {self.model} is available")
            else:
                logger.warning(f"Model {self.model} not found. Available: {model_names}")

            return is_available

        except Exception as e:
            logger.error(f"Failed to check model: {e}")
            return False


class LLMClient:
    """LLM 클라이언트 (싱글톤)"""

    _instance: Optional['LLMClient'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Ollama 클라이언트 초기화
        self.ollama = OllamaClient()

        logger.info(f"LLM client initialized: {settings.OLLAMA_MODEL}")
        self._initialized = True

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            **kwargs
    ) -> str:
        """
        텍스트 생성 (Ollama 사용)

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 파라미터

        Returns:
            생성된 텍스트
        """
        return await self.ollama.generate(prompt, system_prompt, **kwargs)

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        채팅 형식 생성

        Args:
            messages: 메시지 목록
            **kwargs: 추가 파라미터

        Returns:
            생성된 응답
        """
        return await self.ollama.chat(messages, **kwargs)

    async def check_health(self) -> bool:
        """
        LLM 서비스 헬스 체크

        Returns:
            서비스 정상 여부
        """
        return await self.ollama.check_model()


def get_llm_client() -> LLMClient:
    """LLM 클라이언트 싱글톤 반환"""
    return LLMClient()


async def check_llm_connection() -> bool:
    """LLM 연결 확인"""
    try:
        client = get_llm_client()
        return await client.check_health()
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return False