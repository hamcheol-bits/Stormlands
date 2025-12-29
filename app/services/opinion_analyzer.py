"""
투자의견 분석 서비스
증권사 투자의견을 FinBERT로 분석하여 컨센서스 도출
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.ai_models import get_ai_engine
from app.models.stock import Stock

logger = logging.getLogger(__name__)


class OpinionAnalyzer:
    """
    투자의견 분석기

    기능:
    1. 증권사 투자의견 감성 분석 (FinBERT)
    2. 컨센서스 도출
    3. 종목별 투자 추천 생성 (한글)
    """

    def __init__(self):
        self.ai_engine = get_ai_engine()

    async def analyze_stock_opinions(
            self,
            db: Session,
            ticker: str,
            include_analysis: bool = True
    ) -> Dict[str, Any]:
        """
        특정 종목의 투자의견 분석

        Args:
            db: DB 세션
            ticker: 종목코드
            include_analysis: AI 분석 포함 여부

        Returns:
            {
                "ticker": "005930",
                "name": "삼성전자",
                "opinions": [...],
                "consensus": {
                    "sentiment": "positive",
                    "buy_count": 5,
                    "hold_count": 2,
                    "sell_count": 0,
                    "buy_ratio": 0.71
                },
                "analysis": "AI 종합 분석 (한글)"
            }
        """
        # 종목 정보 조회
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()

        if not stock:
            raise ValueError(f"Stock {ticker} not found")

        # 투자의견 조회
        try:
            from app.models.investment_opinion import InvestmentOpinion

            opinions = (
                db.query(InvestmentOpinion)
                .filter(InvestmentOpinion.ticker == ticker)
                .order_by(desc(InvestmentOpinion.stck_bsop_date))
                .all()
            )
        except:
            opinions = []
            logger.warning("InvestmentOpinion table not available")

        if not opinions:
            return {
                "ticker": ticker,
                "name": stock.hts_kor_isnm,
                "opinions": [],
                "consensus": None,
                "message": "투자의견 데이터가 없습니다."
            }

        # FinBERT로 감성 분석
        await self.ai_engine.initialize()

        opinion_dicts = [
            {
                "mbcr_name": op.mbcr_name,
                "invt_opnn": op.invt_opnn,
                "hts_goal_prc": op.hts_goal_prc,
                "stck_bsop_date": op.stck_bsop_date
            }
            for op in opinions
        ]

        # 투자의견은 키워드 기반으로 직접 분류 (FinBERT 사용 안함)
        # FinBERT는 투자의견 텍스트를 뉴스로 오인하여 잘못 분류함
        consensus = self._calculate_consensus(opinion_dicts)

        result = {
            "ticker": ticker,
            "name": stock.hts_kor_isnm,
            "market": stock.mrkt_ctg_cls_code,
            "sector": stock.bstp_kor_isnm,
            "opinions": [
                {
                    "firm": op.mbcr_name,
                    "opinion": op.invt_opnn,
                    "target_price": op.hts_goal_prc,
                    "date": op.stck_bsop_date
                }
                for op in opinions[:10]  # 최신 10개만
            ],
            "consensus": consensus
        }

        # AI 종합 분석 (선택) - 한글로 생성
        if include_analysis and opinions:
            analysis = await self._generate_opinion_analysis(
                ticker,
                stock.hts_kor_isnm,
                opinion_dicts,
                consensus
            )
            result["analysis"] = analysis

        return result

    async def batch_analyze_opinions(
            self,
            db: Session,
            tickers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        여러 종목의 투자의견 일괄 분석

        Args:
            db: DB 세션
            tickers: 종목코드 리스트

        Returns:
            종목별 분석 결과 리스트
        """
        results = []

        for ticker in tickers:
            try:
                result = await self.analyze_stock_opinions(
                    db, ticker, include_analysis=False
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {ticker}: {e}")
                results.append({
                    "ticker": ticker,
                    "error": str(e)
                })

        return results

    async def find_bullish_stocks(
            self,
            db: Session,
            min_buy_ratio: float = 0.6,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        투자의견이 긍정적인 종목 찾기

        Args:
            db: DB 세션
            min_buy_ratio: 최소 매수 의견 비율 (0.6 = 60%)
            limit: 결과 개수

        Returns:
            긍정적 투자의견 종목 리스트
        """
        try:
            from app.models.investment_opinion import InvestmentOpinion
            from sqlalchemy import func

            # 종목별 투자의견 집계
            subquery = (
                db.query(
                    InvestmentOpinion.ticker,
                    func.count(InvestmentOpinion.mbcr_name).label("total_count"),
                    func.sum(
                        func.case(
                            (InvestmentOpinion.invt_opnn.like('%매수%'), 1),
                            (InvestmentOpinion.invt_opnn.like('%BUY%'), 1),
                            else_=0
                        )
                    ).label("buy_count")
                )
                .group_by(InvestmentOpinion.ticker)
                .having(func.count(InvestmentOpinion.mbcr_name) >= 3)  # 최소 3개 의견
                .subquery()
            )

            # 매수 비율 계산
            stocks = (
                db.query(Stock, subquery)
                .join(subquery, Stock.ticker == subquery.c.ticker)
                .filter(Stock.is_active == True)
                .all()
            )

            # 매수 비율 필터링 및 정렬
            results = []
            for stock, counts in stocks:
                buy_ratio = counts.buy_count / counts.total_count if counts.total_count > 0 else 0

                if buy_ratio >= min_buy_ratio:
                    results.append({
                        "ticker": stock.ticker,
                        "name": stock.hts_kor_isnm,
                        "market": stock.mrkt_ctg_cls_code,
                        "sector": stock.bstp_kor_isnm,
                        "buy_ratio": round(buy_ratio, 2),
                        "total_opinions": counts.total_count,
                        "buy_count": counts.buy_count
                    })

            # 매수 비율 높은 순 정렬
            results.sort(key=lambda x: x["buy_ratio"], reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to find bullish stocks: {e}")
            return []

    def _calculate_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        투자의견 컨센서스 계산 (키워드 기반)

        FinBERT 감성 분석은 투자의견 텍스트를 잘못 분류하므로
        키워드 기반으로 직접 분류
        """
        buy_keywords = ["매수", "BUY", "Buy", "강력매수", "적극매수", "STRONG BUY"]
        hold_keywords = ["보유", "HOLD", "Hold", "중립", "NEUTRAL", "Neutral", "MARKET PERFORM"]
        sell_keywords = ["매도", "SELL", "Sell", "비중축소", "REDUCE", "UNDERPERFORM"]

        buy_count = 0
        hold_count = 0
        sell_count = 0

        for op in opinions:
            opinion = op.get('invt_opnn', '').strip()
            if not opinion:
                continue

            # 매수 의견
            if any(kw in opinion for kw in buy_keywords):
                buy_count += 1
            # 매도 의견
            elif any(kw in opinion for kw in sell_keywords):
                sell_count += 1
            # 보유/중립 의견
            elif any(kw in opinion for kw in hold_keywords):
                hold_count += 1
            else:
                # 알 수 없는 의견은 중립으로 처리
                hold_count += 1

        total = len(opinions)
        if total == 0:
            return {
                "consensus": "neutral",
                "sentiment_score": 0.5,
                "sentiment_details": {
                    "positive": 0.33,
                    "neutral": 0.34,
                    "negative": 0.33
                },
                "buy_count": 0,
                "hold_count": 0,
                "sell_count": 0,
                "total_opinions": 0,
                "buy_ratio": 0
            }

        buy_ratio = buy_count / total
        sell_ratio = sell_count / total

        # 컨센서스 결정
        if buy_ratio >= 0.6:
            consensus = "positive"
            sentiment_score = buy_ratio
        elif sell_ratio >= 0.5:
            consensus = "negative"
            sentiment_score = 1 - buy_ratio
        else:
            consensus = "neutral"
            sentiment_score = 0.5

        return {
            "consensus": consensus,
            "sentiment_score": sentiment_score,
            "sentiment_details": {
                "positive": round(buy_ratio, 4),
                "neutral": round(hold_count / total, 4),
                "negative": round(sell_ratio, 4)
            },
            "buy_count": buy_count,
            "hold_count": hold_count,
            "sell_count": sell_count,
            "total_opinions": total,
            "buy_ratio": round(buy_ratio, 2)
        }

    async def _generate_opinion_analysis(
            self,
            ticker: str,
            name: str,
            opinions: List[Dict[str, Any]],
            consensus: Dict[str, Any]
    ) -> str:
        """AI로 투자의견 종합 분석 (한글)"""

        # 프롬프트 생성 (한글)
        prompt = f"""종목: {name} ({ticker})

증권사 투자의견 ({len(opinions)}개):
"""
        for op in opinions[:5]:  # 최신 5개
            prompt += f"- {op.get('mbcr_name')}: {op.get('invt_opnn')} (목표가: {op.get('hts_goal_prc')})\n"

        prompt += f"\n컨센서스 요약:\n"
        prompt += f"- 매수: {consensus.get('buy_count')}개 ({consensus.get('buy_ratio', 0) * 100:.0f}%)\n"
        prompt += f"- 보유: {consensus.get('hold_count')}개\n"
        prompt += f"- 매도: {consensus.get('sell_count')}개\n"
        prompt += f"- 종합 감성: {consensus.get('sentiment')}\n"

        prompt += """

⚠️ 중요: 반드시 한글로만 답변하세요. 영어 사용 금지.

다음 형식으로 작성하세요:

**1. 증권사들의 전반적인 시각**

(증권사들이 이 종목을 어떻게 평가하는지 종합)

**2. 투자 포인트와 리스크**

투자 포인트:
- (핵심 강점 2-3가지)

주요 리스크:
- (주의할 점 1-2가지)

**3. 투자자 관점에서의 의견**

(실제 투자 결정시 고려사항과 추천)
"""

        analysis = await self.ai_engine.llama3.generate(
            prompt,
            system_prompt="""당신은 한국의 전문 증권 애널리스트입니다. 

규칙:
1. 반드시 한글로만 답변
2. 영어 단어 사용 금지 (ticker 같은 용어도 '종목코드'로 표현)
3. 전문적이고 객관적인 분석
4. 투자 리스크 반드시 언급
5. "Based on", "securities firms" 같은 영어 표현 절대 사용 금지""",
            temperature=0.5,
            max_tokens=1000
        )

        return analysis


def get_opinion_analyzer() -> OpinionAnalyzer:
    """투자의견 분석기 싱글톤"""
    return OpinionAnalyzer()