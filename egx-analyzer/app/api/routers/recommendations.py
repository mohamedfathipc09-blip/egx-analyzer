# -*- coding: utf-8 -*-
"""Endpoints الخاصة بفحص الأسهم الصاعدة وتقارير التوصية الشاملة."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.config import DEFAULT_SYMBOLS
from app.analysis.screener import screen_bullish_stocks
from app.analysis.report import generate_full_report
from app.analysis.top_opportunities import get_top_opportunities
from app.api.schemas import AnalysisResponse, ReportResponse

router = APIRouter(tags=["التوصيات"])


def clean_data(obj):
    """دالة مساعدة لتنظيف البيانات من أنواع Numpy عشان FastAPI يقدر يبعتها كـ JSON بدون كراش"""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    elif hasattr(obj, "dict"):
        obj = obj.dict()
        
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(v) for v in obj]
    elif type(obj).__module__ == 'numpy' or hasattr(obj, 'item'):
        try:
            return obj.item()
        except:
            pass
    return obj


@router.get("/screener/bullish", response_model=List[AnalysisResponse])
def bullish_screener(
    symbols: Optional[str] = Query(None, description="رموز مفصولة بفاصلة. لو فاضية بيفحص القايمة الافتراضية"),
    min_score: float = Query(20.0, description="الحد الأدنى لدرجة التحليل الفني (score) لاعتبار السهم مستوفيًا شروط الصعود"),
    min_agreement: float = Query(50.0, description="الحد الأدنى لنسبة توافق المؤشرات"),
    timeframe: str = Query("daily", description="daily أو weekly"),
    period: str = Query("1y", description="مدة البيانات التاريخية"),
):
    """
    يفحص قائمة أسهم ويرجع فقط الأسهم اللي استوفت "شروط الصعود": درجة تحليل
    فني >= min_score ونسبة توافق مؤشرات >= min_agreement، مرتبة تنازليًا
    حسب قوة الإشارة. ملحوظة: راجع disclaimer في كل نتيجة قبل اتخاذ أي قرار.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_SYMBOLS
    result = screen_bullish_stocks(
        symbol_list, min_score=min_score, min_agreement=min_agreement,
        timeframe=timeframe, period=period,
    )
    return clean_data(result)


@router.get("/report/{symbol}", response_model=ReportResponse)
def full_report(
    symbol: str,
    timeframe: str = Query("daily", description="daily أو weekly"),
    analysis_period: str = Query("1y", description="مدة بيانات التحليل الفني"),
    backtest_period: str = Query("2y", description="مدة بيانات اختبار الأداء التاريخي"),
    holding_days: int = Query(10, ge=1, le=60, description="مدة الاحتفاظ بالصفقة في الباك-تيستنج"),
):
    """
    تقرير توصية شامل لسهم واحد: التحليل الفني الكامل + نتائج الباك-تيستنج
    الفعلية + البيانات الأساسية، في استجابة واحدة - مناسب لصفحة "التوصيات".
    """
    try:
        result = generate_full_report(
            symbol.upper(), timeframe=timeframe, analysis_period=analysis_period,
            backtest_period=backtest_period, holding_days=holding_days,
        )
        return clean_data(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر بناء تقرير {symbol}: {e}")


@router.get("/opportunities/top")
def top_opportunities(
    limit: int = Query(5, ge=1, le=20, description="عدد الفرص المطلوبة"),
    symbols: Optional[str] = Query(None, description="رموز مخصصة مفصولة بفاصلة - لو فاضية بيفحص السوق كله تلقائيًا"),
    timeframe: str = Query("daily", description="daily أو weekly"),
    period: str = Query("1y", description="مدة البيانات التاريخية"),
    use_full_market: bool = Query(True, description="فحص كل السوق (~229 سهم) بدل القائمة المنسّقة الصغيرة (39 سهم)"),
):
    """
    فحص تلقائي كامل بدون أي إعدادات مطلوبة - بيحلل كل سوق EGX (~229 سهم
    بشكل افتراضي عبر use_full_market=True) بالتوازي، ويرجع أفضل الفرص
    الفعلية بس: خطة تنفيذ صالحة (R:R مقبول من Risk Engine) ومفيش تضارب
    إشارات (NO_TRADE). ملحوظة: الفحص ممكن ياخد دقيقة أو أكتر حسب عدد
    الأسهم لأنه بيحلل كل واحد فيهم من الصفر.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    result = get_top_opportunities(
        limit=limit, symbols=symbol_list, timeframe=timeframe,
        period=period, use_full_market=use_full_market,
    )
    return clean_data(result)