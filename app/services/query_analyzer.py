"""
자연어 쿼리 분석 서비스
사용자의 자연어 질문을 분석하여 종목 추천
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.core.ai_models import get_ai_engine
from app.models.stock import Stock
from app.models.financial_statement import FinancialStatement

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    자연어 쿼리 분석 및 실행

    예시:
    - "KOSPI에서 저평가되고 영업이익률이 상승중인 3개만 추천해줘"
    - "저평가된 반도체 종목 3개 추천해줘"
    - "배당수익률 높은 안정적인 종목 5개"
    - "성장성 높은 바이오 종목"
    """

    def __init__(self):
        self.ai_engine = get_ai_engine()

    async def analyze_and_recommend(
            self,
            db: Session,
            query: str,
            max_results: int = 10
    ) -> Dict[str, Any]:
        """
        자연어 쿼리 분석 및 종목 추천

        Args:
            db: DB 세션
            query: 사용자 질문
            max_results: 최대 결과 개수

        Returns:
            {
                "query": "원본 질문",
                "analysis": {
                    "market": "KOSPI",
                    "sector": "반도체",
                    "conditions": {...},
                    "count": 3
                },
                "stocks": [...],
                "reasoning": "AI 분석 결과"
            }
        """
        # 1. AI로 쿼리 분석
        logger.info(f"Analyzing query: {query}")
        analysis = await self.ai_engine.analyze_query(query)

        # 2. DB 조회용 필터 생성
        filters, order_by = self._build_sql_conditions(analysis)

        # 3. 종목 조회
        limit = min(analysis.get("count", 5), max_results)
        stocks_with_financials = self._execute_query(db, filters, order_by, limit)

        if not stocks_with_financials:
            return {
                "query": query,
                "analysis": analysis,
                "stocks": [],
                "reasoning": "조건에 맞는 종목을 찾지 못했습니다. 조건을 완화해보세요."
            }

        # 4. AI로 추천 이유 생성
        reasoning = await self._generate_reasoning(stocks_with_financials, analysis, query)

        # 5. 결과 포맷팅
        stocks_data = [
            self._format_stock_result(stock, fs)
            for stock, fs in stocks_with_financials
        ]

        return {
            "query": query,
            "analysis": analysis,
            "stocks": stocks_data,
            "reasoning": reasoning,
            "count": len(stocks_data)
        }

    def _build_sql_conditions(self, analysis: Dict[str, Any]) -> tuple[List, List]:
        """
        AI 분석 결과를 SQLAlchemy 조건으로 변환

        Args:
            analysis: AI 분석 결과

        Returns:
            (filters, order_by)
        """
        filters = []
        order_by = []

        # 기본 필터: 활성 종목만
        filters.append(Stock.is_active == True)
        filters.append(FinancialStatement.period_type == "Y")  # 연간 데이터만

        # 시장 필터
        market = analysis.get("market")
        if market and market != "ALL":
            filters.append(Stock.mrkt_ctg_cls_code == market)

        # 섹터 필터
        sector = analysis.get("sector")
        if sector:
            filters.append(Stock.bstp_kor_isnm.like(f"%{sector}%"))

        # 재무 조건
        conditions = analysis.get("financial_conditions", {})

        # 밸류에이션
        valuation = conditions.get("valuation")
        if valuation == "undervalued":
            # 저평가: ROE 높고 PBR 낮음
            filters.append(FinancialStatement.roe_val >= 10.0)
            # PBR은 BPS/EPS로 간접 계산 (현재가 필요시 별도 처리)

        # ROE 조건
        min_roe = conditions.get("min_roe")
        if min_roe:
            filters.append(FinancialStatement.roe_val >= min_roe)

        # 부채비율
        max_debt = conditions.get("max_debt_ratio")
        if max_debt:
            filters.append(FinancialStatement.lblt_rate <= max_debt)

        # 성장성
        growth = conditions.get("growth")
        if growth == "high":
            filters.append(FinancialStatement.grs >= 15.0)  # 매출성장률 15% 이상

        # 수익성 추세
        profitability = conditions.get("profitability")
        if profitability == "improving":
            filters.append(FinancialStatement.bsop_prfi_inrt > 0)  # 영업이익 증가

        # 정렬 조건
        sort_criteria = analysis.get("sort_by", [])

        if not sort_criteria:
            # 기본 정렬: ROE 높은 순
            order_by.append(desc(FinancialStatement.roe_val))
        else:
            for criterion in sort_criteria:
                field = criterion.get("field")
                direction = criterion.get("direction", "desc")

                column = self._map_field_to_column(field)
                if column is not None:
                    if direction == "desc":
                        order_by.append(desc(column))
                    else:
                        order_by.append(asc(column))

        return filters, order_by

    def _map_field_to_column(self, field: str):
        """필드명을 SQLAlchemy 컬럼으로 매핑"""
        mapping = {
            "roe": FinancialStatement.roe_val,
            "sales_growth": FinancialStatement.grs,
            "profit_growth": FinancialStatement.bsop_prfi_inrt,
            "debt_ratio": FinancialStatement.lblt_rate,
            "eps": FinancialStatement.eps,
            "bps": FinancialStatement.bps,
            "revenue": FinancialStatement.sale_account,
            "net_income": FinancialStatement.thtr_ntin,
            "pbr": None,  # 현재가 필요
        }

        return mapping.get(field.lower())

    def _execute_query(
            self,
            db: Session,
            filters: List,
            order_by: List,
            limit: int
    ) -> List[tuple]:
        """
        SQL 실행

        Returns:
            [(Stock, FinancialStatement), ...]
        """
        # 주식 + 최신 재무제표 조인
        subquery = (
            db.query(
                FinancialStatement.ticker,
                func.max(FinancialStatement.stac_yymm).label("latest_period")
            )
            .filter(FinancialStatement.period_type == "Y")
            .group_by(FinancialStatement.ticker)
            .subquery()
        )

        query = (
            db.query(Stock, FinancialStatement)
            .join(
                FinancialStatement,
                Stock.ticker == FinancialStatement.ticker
            )
            .join(
                subquery,
                and_(
                    FinancialStatement.ticker == subquery.c.ticker,
                    FinancialStatement.stac_yymm == subquery.c.latest_period
                )
            )
            .filter(*filters)
        )

        # 정렬
        if order_by:
            query = query.order_by(*order_by)

        # 제한
        results = query.limit(limit).all()

        logger.info(f"Found {len(results)} stocks matching criteria")

        return results

    async def _generate_reasoning(
            self,
            stocks_with_financials: List[tuple],
            analysis: Dict[str, Any],
            original_query: str
    ) -> str:
        """
        AI로 추천 이유 생성
        """
        # 종목 데이터 준비
        stocks_data = []
        for stock, fs in stocks_with_financials[:5]:  # 상위 5개만
            stocks_data.append({
                "ticker": stock.ticker,
                "name": stock.hts_kor_isnm,
                "market": stock.mrkt_ctg_cls_code,
                "sector": stock.bstp_kor_isnm,
                "roe_val": float(fs.roe_val) if fs.roe_val else None,
                "grs": float(fs.grs) if fs.grs else None,
                "lblt_rate": float(fs.lblt_rate) if fs.lblt_rate else None,
                "eps": float(fs.eps) if fs.eps else None,
                "bps": float(fs.bps) if fs.bps else None,
                "per": self._calculate_per(fs) if fs.eps and fs.bps else None
            })

        # FinGPT로 비교 분석 (사용 가능한 경우)
        if self.ai_engine.fingpt:
            try:
                reasoning = await self.ai_engine.fingpt.compare_stocks(stocks_data)
                return reasoning
            except Exception as e:
                logger.warning(f"FinGPT failed, using Llama3: {e}")

        # 폴백: Llama3
        prompt = f"""사용자 질문: "{original_query}"

추천 종목 ({len(stocks_data)}개):
"""
        for i, stock in enumerate(stocks_data, 1):
            prompt += f"\n{i}. {stock['name']} ({stock['ticker']}) - {stock['market']}\n"
            prompt += f"   섹터: {stock['sector']}\n"
            prompt += f"   ROE: {stock['roe_val']}%, 매출성장률: {stock['grs']}%\n"
            prompt += f"   부채비율: {stock['lblt_rate']}%\n"

        prompt += "\n위 종목들을 추천한 이유를 간결하게 설명하세요."

        reasoning = await self.ai_engine.llama3.generate(
            prompt,
            system_prompt="당신은 투자 애널리스트입니다."
        )

        return reasoning

    def _calculate_per(self, fs: FinancialStatement) -> Optional[float]:
        """PER 간이 계산 (BPS/EPS)"""
        if fs.bps and fs.eps and fs.eps > 0:
            return round(float(fs.bps / fs.eps), 2)
        return None

    def _format_stock_result(
            self,
            stock: Stock,
            fs: FinancialStatement
    ) -> Dict[str, Any]:
        """결과 포맷팅"""
        return {
            "ticker": stock.ticker,
            "name": stock.hts_kor_isnm,
            "market": stock.mrkt_ctg_cls_code,
            "sector": stock.bstp_kor_isnm,
            "financials": {
                "period": fs.stac_yymm,
                "revenue": fs.sale_account,
                "operating_profit": fs.bsop_prti,
                "net_income": fs.thtr_ntin,
                "roe": float(fs.roe_val) if fs.roe_val else None,
                "sales_growth": float(fs.grs) if fs.grs else None,
                "profit_growth": float(fs.bsop_prfi_inrt) if fs.bsop_prfi_inrt else None,
                "debt_ratio": float(fs.lblt_rate) if fs.lblt_rate else None,
                "eps": float(fs.eps) if fs.eps else None,
                "bps": float(fs.bps) if fs.bps else None,
            }
        }


def get_query_analyzer() -> QueryAnalyzer:
    """쿼리 분석기 싱글톤"""
    return QueryAnalyzer()