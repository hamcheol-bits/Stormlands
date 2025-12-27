"""
FinGPT - 금융 특화 LLM 클라이언트
https://github.com/AI4Finance-Foundation/FinGPT
"""
import logging
from typing import Optional, Dict, Any, List
import torch

logger = logging.getLogger(__name__)


class FinGPTClient:
    """
    FinGPT 클라이언트

    특징:
    - 금융 데이터로 파인튜닝된 Llama2 기반 모델
    - 주가 예측, 투자 조언, 재무 분석 특화
    - LoRA 어댑터 사용 (메모리 효율적)
    """

    def __init__(self):
        from app.config.config import get_settings

        self.settings = get_settings()
        self.model_name = self.settings.FINGPT_MODEL
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() and self.settings.USE_GPU else "cpu"

    def load_model(self):
        """모델 로드 (지연 로딩)"""
        if self.model is not None:
            return

        logger.info(f"Loading FinGPT: {self.model_name}")
        logger.info(f"Device: {self.device}")

        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            from peft import PeftModel

            # Base 모델 로드
            base_model = "meta-llama/Llama-2-7b-chat-hf"

            self.tokenizer = AutoTokenizer.from_pretrained(
                base_model,
                cache_dir=self.settings.MODEL_CACHE_DIR,
                token=self.settings.HF_TOKEN if self.settings.HF_TOKEN else None
            )

            # LoRA 어댑터와 함께 로드
            base = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                cache_dir=self.settings.MODEL_CACHE_DIR,
                token=self.settings.HF_TOKEN if self.settings.HF_TOKEN else None
            )

            self.model = PeftModel.from_pretrained(
                base,
                self.model_name,
                cache_dir=self.settings.MODEL_CACHE_DIR
            )

            if self.device == "cpu":
                self.model = self.model.float()

            self.model.eval()

            logger.info(f"✓ FinGPT loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load FinGPT: {e}")
            logger.warning("FinGPT will not be available")
            raise

    async def analyze_stock(
            self,
            ticker: str,
            company_name: str,
            financial_data: Dict[str, Any],
            news_summary: Optional[str] = None
    ) -> str:
        """
        종목 분석

        Args:
            ticker: 종목코드
            company_name: 회사명
            financial_data: 재무 데이터
            news_summary: 뉴스 요약 (선택)

        Returns:
            분석 결과 텍스트
        """
        self.load_model()

        # 프롬프트 생성
        prompt = self._build_analysis_prompt(
            ticker, company_name, financial_data, news_summary
        )

        # 생성
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1
            )

        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 프롬프트 제거하고 답변만 추출
        if "[/INST]" in result:
            answer = result.split("[/INST]")[-1].strip()
        else:
            answer = result.strip()

        return answer

    async def compare_stocks(
            self,
            stocks: List[Dict[str, Any]]
    ) -> str:
        """
        여러 종목 비교 분석

        Args:
            stocks: 종목 리스트
                [
                    {
                        "ticker": "005930",
                        "name": "삼성전자",
                        "roe_val": 12.5,
                        "grs": 8.3,
                        "lblt_rate": 45.2,
                        "per": 10.5
                    },
                    ...
                ]

        Returns:
            비교 분석 결과
        """
        self.load_model()

        # 비교 프롬프트
        prompt = "[INST] You are a financial analyst. Compare these stocks and rank them by investment attractiveness:\n\n"

        for i, stock in enumerate(stocks, 1):
            prompt += f"{i}. {stock['name']} ({stock['ticker']})\n"
            prompt += f"   - ROE: {stock.get('roe_val', 'N/A')}%\n"
            prompt += f"   - Sales Growth: {stock.get('grs', 'N/A')}%\n"
            prompt += f"   - Debt Ratio: {stock.get('lblt_rate', 'N/A')}%\n"

            if stock.get('per'):
                prompt += f"   - PER: {stock['per']}\n"

            prompt += "\n"

        prompt += "Provide:\n"
        prompt += "1. Ranking with rationale\n"
        prompt += "2. Key strengths and weaknesses of each\n"
        prompt += "3. Best pick for different investor types (value, growth, balanced)\n"
        prompt += "[/INST]"

        # 생성
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.7,
                do_sample=True,
                top_p=0.9
            )

        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer = result.split("[/INST]")[-1].strip()

        return answer

    def _build_analysis_prompt(
            self,
            ticker: str,
            company_name: str,
            financial_data: Dict[str, Any],
            news_summary: Optional[str]
    ) -> str:
        """분석 프롬프트 생성 (Llama2 Chat 형식)"""

        prompt = f"[INST] Analyze this Korean stock:\n\n"
        prompt += f"Company: {company_name} ({ticker})\n\n"

        prompt += "Financial Metrics:\n"
        prompt += f"- Revenue: {financial_data.get('sale_account', 'N/A'):,} KRW\n"
        prompt += f"- Operating Profit: {financial_data.get('bsop_prti', 'N/A'):,} KRW\n"
        prompt += f"- Net Income: {financial_data.get('thtr_ntin', 'N/A'):,} KRW\n"
        prompt += f"- ROE: {financial_data.get('roe_val', 'N/A')}%\n"
        prompt += f"- Debt Ratio: {financial_data.get('lblt_rate', 'N/A')}%\n"
        prompt += f"- EPS: {financial_data.get('eps', 'N/A'):,} KRW\n"
        prompt += f"- BPS: {financial_data.get('bps', 'N/A'):,} KRW\n"
        prompt += f"- Sales Growth: {financial_data.get('grs', 'N/A')}%\n"

        if news_summary:
            prompt += f"\nRecent News Summary:\n{news_summary}\n"

        prompt += "\nProvide investment analysis covering:\n"
        prompt += "1. Financial Health (Strong/Moderate/Weak)\n"
        prompt += "2. Growth Potential (High/Medium/Low)\n"
        prompt += "3. Valuation Assessment (Undervalued/Fair/Overvalued)\n"
        prompt += "4. Investment Recommendation (Buy/Hold/Sell)\n"
        prompt += "5. Key Risks and Opportunities\n"
        prompt += "[/INST]"

        return prompt


_fingpt_client: Optional[FinGPTClient] = None


def get_fingpt_client() -> FinGPTClient:
    """FinGPT 클라이언트 싱글톤"""
    global _fingpt_client

    if _fingpt_client is None:
        _fingpt_client = FinGPTClient()

    return _fingpt_client