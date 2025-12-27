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
    3. 종목별 투자 추천 생성
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
                "analysis": "AI 종합 분석" (optional)
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

        if self.ai_engine.finbert:
            consensus = self.ai_engine.finbert.analyze_investment_opinions(opinion_dicts)
        else:
            # 폴백: 단순 집계
            consensus = self._simple_consensus(opinion_dicts)

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

        # AI 종합 분석 (선택)
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

    def _simple_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """단순 투자의견 집계 (FinBERT 없을 때)"""
        buy_keywords = ["매수", "BUY", "강력매수", "적극매수"]
        hold_keywords = ["보유", "HOLD", "중립", "Neutral"]
        sell_keywords = ["매도", "SELL"]

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

        total = len(opinions)
        buy_ratio = buy_count / total if total > 0 else 0

        # 컨센서스 결정
        if buy_ratio >= 0.6:
            sentiment = "positive"
        elif sell_count / total >= 0.5:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "sentiment_score": buy_ratio,
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
        """AI로 투자의견 종합 분석"""

        # 프롬프트 생성
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

        prompt += "\n위 투자의견들을 종합하여 다음을 분석하세요:\n"
        prompt += "1. 증권사들의 전반적인 시각\n"
        prompt += "2. 투자 포인트와 리스크\n"
        prompt += "3. 투자자 관점에서의 의견\n"

        analysis = await self.ai_engine.llama3.generate(
            prompt,
            system_prompt="당신은 증권 애널리스트입니다. 여러 증권사의 투자의견을 종합 분석하세요."
        )

        return analysis


def get_opinion_analyzer() -> OpinionAnalyzer:
    """투자의견 분석기 싱글톤"""
    return OpinionAnalyzer()