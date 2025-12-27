"""
FinBERT - 금융 뉴스/리포트 감성 분석
https://github.com/ProsusAI/finBERT
"""
import logging
from typing import List, Dict, Any
import torch
from torch.nn.functional import softmax

logger = logging.getLogger(__name__)


class FinBERTClient:
    """
    FinBERT 감성 분석 클라이언트

    출력:
    - positive: 긍정 (강세, 주가 상승 기대)
    - neutral: 중립
    - negative: 부정 (약세, 주가 하락 우려)
    """

    def __init__(self):
        from app.config.config import get_settings

        self.settings = get_settings()
        self.model_name = self.settings.FINBERT_MODEL
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() and self.settings.USE_GPU else "cpu"
        self.labels = ["positive", "neutral", "negative"]

    def load_model(self):
        """모델 로드"""
        if self.model is not None:
            return

        logger.info(f"Loading FinBERT: {self.model_name}")
        logger.info(f"Device: {self.device}")

        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.settings.MODEL_CACHE_DIR
            )

            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                cache_dir=self.settings.MODEL_CACHE_DIR
            )

            self.model.to(self.device)
            self.model.eval()

            logger.info(f"✓ FinBERT loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load FinBERT: {e}")
            logger.warning("FinBERT will not be available")
            raise

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        단일 텍스트 감성 분석

        Args:
            text: 분석할 텍스트 (뉴스, 리포트, 투자의견 등)

        Returns:
            {
                "label": "positive" | "neutral" | "negative",
                "score": 0.95,
                "scores": {
                    "positive": 0.95,
                    "neutral": 0.03,
                    "negative": 0.02
                }
            }
        """
        self.load_model()

        # 토큰화
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        ).to(self.device)

        # 추론
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = softmax(outputs.logits, dim=-1)

        # 결과 파싱
        scores_dict = {
            label: float(probs[0][i])
            for i, label in enumerate(self.labels)
        }

        max_label = max(scores_dict, key=scores_dict.get)
        max_score = scores_dict[max_label]

        return {
            "label": max_label,
            "score": max_score,
            "scores": scores_dict
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        여러 텍스트 배치 분석

        Args:
            texts: 텍스트 리스트

        Returns:
            감성 분석 결과 리스트
        """
        return [self.analyze_sentiment(text) for text in texts]

    def aggregate_sentiment(
            self,
            texts: List[str],
            weights: List[float] = None
    ) -> Dict[str, Any]:
        """
        여러 텍스트의 감성 집계

        Args:
            texts: 텍스트 리스트
            weights: 각 텍스트의 가중치 (선택)
                예: 최근 뉴스일수록 높은 가중치

        Returns:
            집계된 감성 분석 결과
        """
        if not texts:
            return {
                "label": "neutral",
                "score": 0.5,
                "scores": {
                    "positive": 0.33,
                    "neutral": 0.34,
                    "negative": 0.33
                },
                "num_texts": 0
            }

        results = self.analyze_batch(texts)

        # 가중치 기본값 (모두 동일)
        if weights is None:
            weights = [1.0] * len(texts)

        # 가중 평균 계산
        weighted_scores = {label: 0.0 for label in self.labels}
        total_weight = sum(weights)

        for result, weight in zip(results, weights):
            for label in self.labels:
                weighted_scores[label] += result["scores"][label] * weight

        # 정규화
        for label in self.labels:
            weighted_scores[label] /= total_weight

        max_label = max(weighted_scores, key=weighted_scores.get)
        max_score = weighted_scores[max_label]

        return {
            "label": max_label,
            "score": max_score,
            "scores": weighted_scores,
            "num_texts": len(texts),
            "details": results
        }

    def analyze_investment_opinions(
            self,
            opinions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        투자의견 감성 분석

        Args:
            opinions: 투자의견 리스트
                [
                    {
                        "mbcr_name": "한국투자증권",
                        "invt_opnn": "매수",
                        "hts_goal_prc": "85000",
                        "stck_bsop_date": "20241220"
                    },
                    ...
                ]

        Returns:
            {
                "consensus": "positive" | "neutral" | "negative",
                "buy_count": 5,
                "hold_count": 2,
                "sell_count": 0,
                "avg_sentiment_score": 0.85
            }
        """
        if not opinions:
            return {
                "consensus": "neutral",
                "buy_count": 0,
                "hold_count": 0,
                "sell_count": 0,
                "avg_sentiment_score": 0.5
            }

        # 투자의견 텍스트 추출
        texts = [
            f"{op.get('mbcr_name', '증권사')}: {op.get('invt_opnn', '의견없음')} (목표가: {op.get('hts_goal_prc', 'N/A')})"
            for op in opinions
        ]

        # 시간 기반 가중치 (최근일수록 높음)
        from datetime import datetime

        weights = []
        for op in opinions:
            try:
                date_str = op.get('stck_bsop_date', '')
                if date_str:
                    date = datetime.strptime(date_str, '%Y%m%d')
                    days_ago = (datetime.now() - date).days
                    # 최근 30일 이내는 가중치 1.0, 그 이후는 감소
                    weight = max(0.5, 1.0 - (days_ago / 90))
                else:
                    weight = 1.0
            except:
                weight = 1.0

            weights.append(weight)

        # 감성 분석
        sentiment_result = self.aggregate_sentiment(texts, weights)

        # 투자의견 집계
        buy_keywords = ["매수", "BUY", "강력매수", "적극매수", "Trading Buy"]
        hold_keywords = ["보유", "HOLD", "중립", "Neutral", "Market Perform"]
        sell_keywords = ["매도", "SELL", "Under Perform"]

        buy_count = 0
        hold_count = 0
        sell_count = 0

        for op in opinions:
            opinion = op.get('invt_opnn', '').upper()

            if any(kw.upper() in opinion for kw in buy_keywords):
                buy_count += 1
            elif any(kw.upper() in opinion for kw in sell_keywords):
                sell_count += 1
            else:
                hold_count += 1

        return {
            "consensus": sentiment_result["label"],
            "sentiment_score": sentiment_result["score"],
            "sentiment_details": sentiment_result["scores"],
            "buy_count": buy_count,
            "hold_count": hold_count,
            "sell_count": sell_count,
            "total_opinions": len(opinions),
            "buy_ratio": buy_count / len(opinions) if opinions else 0
        }


_finbert_client = None


def get_finbert_client() -> FinBERTClient:
    """FinBERT 클라이언트 싱글톤"""
    global _finbert_client

    if _finbert_client is None:
        _finbert_client = FinBERTClient()

    return _finbert_client