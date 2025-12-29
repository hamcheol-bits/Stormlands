"""
Research Report Analysis Service
리서치 리포트 메타데이터 기반 종목 분석
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from collections import defaultdict

from app.models.research_report import ResearchReport

logger = logging.getLogger(__name__)


class ResearchAnalysisService:
    """
    리서치 리포트 분석 서비스

    - 종목별 리포트 집계
    - 투자의견 컨센서스
    - 목표가 분석
    - 증권사별 분석
    """

    def __init__(self):
        pass

    # ============================================================
    # 종목별 리포트 조회
    # ============================================================

    def get_reports_by_ticker(
        self,
        db: Session,
        ticker: str,
        days: int = 180,
        limit: int = 50
    ) -> List[ResearchReport]:
        """
        특정 종목의 최근 리포트 조회

        Args:
            db: 데이터베이스 세션
            ticker: 종목코드
            days: 조회 기간 (일)
            limit: 결과 개수 제한

        Returns:
            리포트 리스트
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        reports = db.query(ResearchReport).filter(
            and_(
                ResearchReport.ticker == ticker,
                ResearchReport.publish_date >= cutoff_date
            )
        ).order_by(
            ResearchReport.publish_date.desc()
        ).limit(limit).all()

        logger.info(f"Found {len(reports)} reports for {ticker} in last {days} days")
        return reports

    def get_latest_report_by_ticker(
        self,
        db: Session,
        ticker: str
    ) -> Optional[ResearchReport]:
        """최신 리포트 조회"""
        return db.query(ResearchReport).filter(
            ResearchReport.ticker == ticker
        ).order_by(
            ResearchReport.publish_date.desc()
        ).first()

    # ============================================================
    # 투자의견 컨센서스
    # ============================================================

    def get_opinion_consensus(
        self,
        db: Session,
        ticker: str,
        days: int = 180
    ) -> Dict[str, Any]:
        """
        투자의견 컨센서스 계산

        Args:
            db: 데이터베이스 세션
            ticker: 종목코드
            days: 분석 기간 (일)

        Returns:
            {
                "ticker": "005930",
                "period_days": 180,
                "total_reports": 15,
                "opinion_distribution": {
                    "매수": 8,
                    "BUY": 5,
                    "중립": 2
                },
                "consensus": "매수",
                "consensus_ratio": 0.87
            }
        """
        reports = self.get_reports_by_ticker(db, ticker, days)

        if not reports:
            return {
                "ticker": ticker,
                "period_days": days,
                "total_reports": 0,
                "opinion_distribution": {},
                "consensus": None,
                "consensus_ratio": 0.0
            }

        # 투자의견 집계
        opinion_counts = defaultdict(int)
        for report in reports:
            if report.investment_opinion:
                opinion_counts[report.investment_opinion] += 1

        # 가장 많은 의견이 컨센서스
        if opinion_counts:
            consensus = max(opinion_counts, key=opinion_counts.get)
            consensus_count = opinion_counts[consensus]
            consensus_ratio = consensus_count / len(reports)
        else:
            consensus = None
            consensus_ratio = 0.0

        return {
            "ticker": ticker,
            "period_days": days,
            "total_reports": len(reports),
            "opinion_distribution": dict(opinion_counts),
            "consensus": consensus,
            "consensus_ratio": round(consensus_ratio, 2)
        }

    def normalize_opinion(self, opinion: str) -> str:
        """
        투자의견 정규화

        매수/BUY/강력매수 → BUY
        보유/HOLD/중립 → HOLD
        매도/SELL → SELL
        """
        if not opinion:
            return "UNKNOWN"

        opinion_upper = opinion.upper()

        # 매수 계열
        if any(keyword in opinion_upper for keyword in ["매수", "BUY", "적극매수"]):
            return "BUY"

        # 보유/중립 계열
        if any(keyword in opinion_upper for keyword in ["보유", "HOLD", "중립", "NEUTRAL"]):
            return "HOLD"

        # 매도 계열
        if any(keyword in opinion_upper for keyword in ["매도", "SELL"]):
            return "SELL"

        return "UNKNOWN"

    # ============================================================
    # 목표가 분석
    # ============================================================

    def get_target_price_consensus(
        self,
        db: Session,
        ticker: str,
        days: int = 180
    ) -> Dict[str, Any]:
        """
        목표가 컨센서스 계산

        Args:
            db: 데이터베이스 세션
            ticker: 종목코드
            days: 분석 기간 (일)

        Returns:
            {
                "ticker": "005930",
                "period_days": 180,
                "count": 15,
                "average": 75000,
                "median": 73000,
                "min": 65000,
                "max": 85000,
                "std_dev": 5200
            }
        """
        reports = self.get_reports_by_ticker(db, ticker, days)

        # 목표가 추출
        target_prices = [
            r.target_price for r in reports
            if r.target_price and r.target_price > 0
        ]

        if not target_prices:
            return {
                "ticker": ticker,
                "period_days": days,
                "count": 0,
                "average": None,
                "median": None,
                "min": None,
                "max": None,
                "std_dev": None
            }

        # 통계 계산
        import numpy as np

        target_prices = np.array(target_prices)

        return {
            "ticker": ticker,
            "period_days": days,
            "count": len(target_prices),
            "average": int(np.mean(target_prices)),
            "median": int(np.median(target_prices)),
            "min": int(np.min(target_prices)),
            "max": int(np.max(target_prices)),
            "std_dev": int(np.std(target_prices))
        }

    # ============================================================
    # 증권사별 분석
    # ============================================================

    def get_brokerage_statistics(
        self,
        db: Session,
        days: int = 180
    ) -> List[Dict[str, Any]]:
        """
        증권사별 리포트 발행 통계

        Returns:
            [
                {
                    "brokerage": "미래에셋증권",
                    "report_count": 125,
                    "unique_tickers": 87
                },
                ...
            ]
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        # 증권사별 리포트 수 집계
        brokerage_counts = db.query(
            ResearchReport.brokerage,
            func.count(ResearchReport.id).label('report_count'),
            func.count(func.distinct(ResearchReport.ticker)).label('unique_tickers')
        ).filter(
            ResearchReport.publish_date >= cutoff_date
        ).group_by(
            ResearchReport.brokerage
        ).order_by(
            desc('report_count')
        ).all()

        result = [
            {
                "brokerage": row.brokerage,
                "report_count": row.report_count,
                "unique_tickers": row.unique_tickers
            }
            for row in brokerage_counts
        ]

        logger.info(f"Found {len(result)} brokerages with reports in last {days} days")
        return result

    def get_reports_by_brokerage(
        self,
        db: Session,
        brokerage: str,
        days: int = 30,
        limit: int = 50
    ) -> List[ResearchReport]:
        """특정 증권사의 최근 리포트 조회"""
        cutoff_date = datetime.now().date() - timedelta(days=days)

        return db.query(ResearchReport).filter(
            and_(
                ResearchReport.brokerage == brokerage,
                ResearchReport.publish_date >= cutoff_date
            )
        ).order_by(
            ResearchReport.publish_date.desc()
        ).limit(limit).all()

    # ============================================================
    # 종합 분석
    # ============================================================

    def get_stock_analysis_summary(
        self,
        db: Session,
        ticker: str,
        days: int = 180
    ) -> Dict[str, Any]:
        """
        종목 종합 분석 요약

        Returns:
            {
                "ticker": "005930",
                "stock_name": "삼성전자",
                "analysis_period": 180,
                "report_summary": {...},
                "opinion_consensus": {...},
                "target_price_consensus": {...},
                "recent_reports": [...]
            }
        """
        # 1. 최신 리포트로 종목명 조회
        latest = self.get_latest_report_by_ticker(db, ticker)
        stock_name = latest.stock_name if latest else None

        # 2. 리포트 기본 정보
        reports = self.get_reports_by_ticker(db, ticker, days)

        # 증권사별 리포트 수
        brokerage_counts = defaultdict(int)
        for report in reports:
            brokerage_counts[report.brokerage] += 1

        # 3. 투자의견 컨센서스
        opinion_consensus = self.get_opinion_consensus(db, ticker, days)

        # 4. 목표가 컨센서스
        target_price_consensus = self.get_target_price_consensus(db, ticker, days)

        # 5. 최근 5개 리포트
        recent_reports = [r.to_dict() for r in reports[:5]]

        # 분석 결과 (한글)
        analysis = self._generate_analysis_kr(
            ticker=ticker,
            stock_name=stock_name,
            reports=reports,
            opinion_consensus=opinion_consensus,
            target_price_consensus=target_price_consensus
        )

        return {
            "ticker": ticker,
            "stock_name": stock_name,
            "analysis_period_days": days,
            "report_summary": {
                "total_reports": len(reports),
                "unique_brokerages": len(brokerage_counts),
                "top_brokerages": dict(
                    sorted(brokerage_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                )
            },
            "opinion_consensus": opinion_consensus,
            "target_price_consensus": target_price_consensus,
            "analysis": analysis,  # 한글 분석 추가
            "recent_reports": recent_reports
        }

    # ============================================================
    # 전체 시장 분석
    # ============================================================

    def get_market_coverage(
        self,
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        전체 시장 리포트 커버리지

        Returns:
            {
                "period_days": 30,
                "total_reports": 1523,
                "unique_tickers": 342,
                "unique_brokerages": 15,
                "reports_per_day": 50.8
            }
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        # 전체 리포트 수
        total_reports = db.query(ResearchReport).filter(
            ResearchReport.publish_date >= cutoff_date
        ).count()

        # 유니크 종목 수
        unique_tickers = db.query(
            func.count(func.distinct(ResearchReport.ticker))
        ).filter(
            ResearchReport.publish_date >= cutoff_date
        ).scalar()

        # 유니크 증권사 수
        unique_brokerages = db.query(
            func.count(func.distinct(ResearchReport.brokerage))
        ).filter(
            ResearchReport.publish_date >= cutoff_date
        ).scalar()

        reports_per_day = total_reports / days if days > 0 else 0

        return {
            "period_days": days,
            "total_reports": total_reports,
            "unique_tickers": unique_tickers,
            "unique_brokerages": unique_brokerages,
            "reports_per_day": round(reports_per_day, 1)
        }

    def get_most_covered_stocks(
        self,
        db: Session,
        days: int = 30,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        가장 많이 커버된 종목 TOP N

        Returns:
            [
                {
                    "ticker": "005930",
                    "stock_name": "삼성전자",
                    "report_count": 15,
                    "unique_brokerages": 8
                },
                ...
            ]
        """
        cutoff_date = datetime.now().date() - timedelta(days=days)

        # 종목별 리포트 수 집계
        most_covered = db.query(
            ResearchReport.ticker,
            ResearchReport.stock_name,
            func.count(ResearchReport.id).label('report_count'),
            func.count(func.distinct(ResearchReport.brokerage)).label('unique_brokerages')
        ).filter(
            ResearchReport.publish_date >= cutoff_date
        ).group_by(
            ResearchReport.ticker,
            ResearchReport.stock_name
        ).order_by(
            desc('report_count')
        ).limit(limit).all()

        return [
            {
                "ticker": row.ticker,
                "stock_name": row.stock_name,
                "report_count": row.report_count,
                "unique_brokerages": row.unique_brokerages
            }
            for row in most_covered
        ]


    # ============================================================
    # 한글 분석 생성
    # ============================================================

    def _generate_analysis_kr(
        self,
        ticker: str,
        stock_name: str,
        reports: List[ResearchReport],
        opinion_consensus: Dict[str, Any],
        target_price_consensus: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        종목 분석 결과를 한글로 생성

        Returns:
            {
                "summary": "종합 분석 요약",
                "opinion_analysis": "투자의견 분석",
                "target_price_analysis": "목표가 분석",
                "recommendation": "투자 추천"
            }
        """
        # 1. 종합 요약
        total_reports = len(reports)
        period = opinion_consensus.get("period_days", 180)

        summary = f"{stock_name}({ticker})에 대해 최근 {period}일간 {total_reports}개의 리서치 리포트가 발행되었습니다."

        # 2. 투자의견 분석
        consensus = opinion_consensus.get("consensus")
        consensus_ratio = opinion_consensus.get("consensus_ratio", 0)
        opinion_dist = opinion_consensus.get("opinion_distribution", {})

        if consensus and total_reports > 0:
            opinion_analysis = f"증권사들의 투자의견 컨센서스는 '{consensus}'이며, "
            opinion_analysis += f"전체 리포트의 {consensus_ratio * 100:.1f}%가 이 의견에 동의하고 있습니다. "

            # 의견 분포 설명
            if len(opinion_dist) > 1:
                opinion_list = [f"{k} {v}개" for k, v in sorted(opinion_dist.items(), key=lambda x: x[1], reverse=True)]
                opinion_analysis += f"의견 분포는 {', '.join(opinion_list)}입니다."

            # 컨센서스 강도 평가
            if consensus_ratio >= 0.8:
                opinion_analysis += " 증권사들의 의견이 매우 일치하는 편입니다."
            elif consensus_ratio >= 0.6:
                opinion_analysis += " 증권사들의 의견이 대체로 일치합니다."
            elif consensus_ratio >= 0.4:
                opinion_analysis += " 증권사들의 의견이 다소 엇갈립니다."
            else:
                opinion_analysis += " 증권사들의 의견이 크게 엇갈리고 있습니다."
        else:
            opinion_analysis = "투자의견 컨센서스를 도출하기에 리포트가 부족합니다."

        # 3. 목표가 분석
        count = target_price_consensus.get("count", 0)

        if count > 0:
            average = target_price_consensus.get("average", 0)
            min_price = target_price_consensus.get("min", 0)
            max_price = target_price_consensus.get("max", 0)
            std_dev = target_price_consensus.get("std_dev", 0)

            target_analysis = f"목표가는 평균 {average:,}원으로, "
            target_analysis += f"최저 {min_price:,}원에서 최고 {max_price:,}원까지 분포되어 있습니다. "

            # 목표가 분산도 평가
            if average > 0:
                cv = (std_dev / average) * 100  # 변동계수
                if cv < 10:
                    target_analysis += "증권사들의 목표가 전망이 매우 일치하는 편입니다."
                elif cv < 20:
                    target_analysis += "증권사들의 목표가 전망이 비교적 일치합니다."
                elif cv < 30:
                    target_analysis += "증권사들의 목표가 전망이 다소 엇갈립니다."
                else:
                    target_analysis += "증권사들의 목표가 전망이 크게 엇갈리고 있습니다."
        else:
            target_analysis = "목표가 정보가 충분하지 않습니다."

        # 4. 투자 추천
        recommendation = self._generate_recommendation_kr(
            consensus=consensus,
            consensus_ratio=consensus_ratio,
            target_count=count
        )

        return {
            "summary": summary,
            "opinion_analysis": opinion_analysis,
            "target_price_analysis": target_analysis,
            "recommendation": recommendation
        }

    def _generate_recommendation_kr(
        self,
        consensus: Optional[str],
        consensus_ratio: float,
        target_count: int
    ) -> str:
        """투자 추천 메시지 생성"""

        if not consensus or target_count < 3:
            return "리포트 수가 부족하여 명확한 투자 의견을 제시하기 어렵습니다. 추가 정보 수집을 권장합니다."

        # 긍정적 의견 키워드
        positive_keywords = ["매수", "BUY", "강력매수", "적극매수", "STRONG BUY"]
        # 중립 의견 키워드
        neutral_keywords = ["보유", "HOLD", "중립", "NEUTRAL", "MARKET PERFORM"]
        # 부정적 의견 키워드
        negative_keywords = ["매도", "SELL", "비중축소", "REDUCE", "UNDERPERFORM"]

        consensus_upper = consensus.upper()

        # 긍정적 컨센서스
        if any(keyword.upper() in consensus_upper for keyword in positive_keywords):
            if consensus_ratio >= 0.7:
                return "다수의 증권사가 긍정적인 투자의견을 제시하고 있어, 매수 관점에서 접근할 수 있습니다. 다만, 개인의 투자 성향과 포트폴리오 상황을 고려한 신중한 판단이 필요합니다."
            else:
                return "증권사들이 대체로 긍정적이나 의견이 다소 엇갈리므로, 추가적인 재무제표 분석과 시장 상황 점검 후 투자를 결정하시기 바랍니다."

        # 중립 컨센서스
        elif any(keyword.upper() in consensus_upper for keyword in neutral_keywords):
            return "증권사들의 중립적인 의견을 고려할 때, 현재 보유 중인 경우 유지하되 신규 매수는 신중한 접근이 필요합니다. 시장 상황 변화를 지켜보는 것을 권장합니다."

        # 부정적 컨센서스
        elif any(keyword.upper() in consensus_upper for keyword in negative_keywords):
            if consensus_ratio >= 0.6:
                return "다수의 증권사가 부정적인 의견을 제시하고 있어, 신규 투자는 보류하고 보유 물량 정리를 검토해볼 필요가 있습니다."
            else:
                return "증권사들의 의견이 부정적이나 다소 엇갈리므로, 기업의 펀더멘털과 업종 전망을 종합적으로 검토 후 판단하시기 바랍니다."

        # 기타
        else:
            return "투자의견이 명확하지 않으므로, 추가적인 정보 수집과 분석 후 투자 결정을 내리시기 바랍니다."


def get_research_analysis_service() -> ResearchAnalysisService:
    """ResearchAnalysisService 싱글톤 반환"""
    return ResearchAnalysisService()