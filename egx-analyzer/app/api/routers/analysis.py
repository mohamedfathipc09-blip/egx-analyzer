# -*- coding: utf-8 -*-
"""Endpoints الخاصة بالتحليل الفني والأساسي."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.config import DEFAULT_SYMBOLS
from app.analysis.scoring import analyze_stock, analyze_multiple
from app.analysis.fundamentals import get_fundamentals
from app.analysis.chart_data import get_chart_data
from app.analysis.multi_timeframe import analyze_multi_timeframe
from app.api.schemas import AnalysisResponse, FundamentalsResponse

router = APIRouter(tags=["التحليل الفني"])


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def analysis(
    symbol: str,
    timeframe: str = Query("daily", description="daily أو weekly"),
    period: str = Query("1y", description="مدة البيانات التاريخية: 3mo, 6mo, 1y, 2y"),
    speculation_stop_loss_pct: float = Query(None, description="نسبة وقف الخسارة لخطة المضاربة القصيرة - افتراضيًا 1.5%"),
    speculation_target_pct: float = Query(None, description="نسبة الهدف لخطة المضاربة القصيرة - افتراضيًا 5%"),
):
    """
    تحليل فني متعدد المؤشرات لسهم واحد وتوصية مبنية على توافق المؤشرات.
    الاستجابة فيها خطتين: trade_plan (قائمة على ATR/الدعم/فيبوناتشي) و
    speculative_trade_plan (نسب ثابتة، افتراضيًا هدف 5%/وقف 1.5%).
    ملحوظة: راجع حقل disclaimer - هذا ليس نصيحة استثمارية.
    """
    try:
        return analyze_stock(
            symbol.upper(), timeframe=timeframe, period=period,
            speculation_stop_loss_pct=speculation_stop_loss_pct,
            speculation_target_pct=speculation_target_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر تحليل {symbol}: {e}")


@router.get("/analysis", response_model=List[AnalysisResponse])
def analysis_multiple(
    symbols: Optional[str] = Query(None, description="رموز مفصولة بفاصلة، مثال: COMI,ETEL,SWDY"),
    timeframe: str = Query("daily", description="daily أو weekly"),
    period: str = Query("1y", description="مدة البيانات التاريخية"),
):
    """تحليل فني لعدة أسهم مرة واحدة."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_SYMBOLS
    return analyze_multiple(symbol_list, timeframe=timeframe, period=period)


@router.get("/fundamentals/{symbol}", response_model=FundamentalsResponse)
def fundamentals(symbol: str):
    """يرجع البيانات المالية الأساسية المتاحة لسهم (P/E, EPS, القيمة السوقية)."""
    return get_fundamentals(symbol.upper())


@router.get("/chart/{symbol}")
def chart_data(
    symbol: str,
    timeframe: str = Query("daily", description="daily أو weekly"),
    period: str = Query("1y", description="مدة البيانات: 3mo, 6mo, 1y, 2y, 5y"),
):
    """
    بيانات جاهزة لرسم Candlestick تفاعلي: تواريخ + OHLCV + SMA50/SMA200 +
    نطاقات بولينجر. القيم اللي مفيش بيانات كافية لحسابها (بداية السلسلة)
    بترجع null بدل ما تتحذف - عشان طول كل مصفوفة يفضل متطابق مع التواريخ.
    """
    try:
        return get_chart_data(symbol.upper(), period=period, timeframe=timeframe)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر تجهيز الرسم البياني لـ {symbol}: {e}")


@router.get("/analysis/{symbol}/multi-timeframe")
def multi_timeframe_analysis(
    symbol: str,
    primary_timeframe: str = Query("daily", description="الإطار الأساسي (اللي هتتداول عليه)"),
    primary_period: str = Query("1y", description="مدة بيانات الإطار الأساسي"),
    higher_timeframe: str = Query("weekly", description="الإطار المرجعي الأكبر"),
    higher_period: str = Query("2y", description="مدة بيانات الإطار الأكبر"),
):
    """
    يحلل السهم على إطارين ويمنع الإطار الأصغر من إعطاء توصية شراء نشطة لو
    الاتجاه على الإطار الأكبر هابط بقوة - جودة الإشارة أهم من عددها. راجع
    حقل gate_applied وgate_reason لمعرفة هل حصل تخفيف وليه.
    """
    try:
        return analyze_multi_timeframe(
            symbol.upper(),
            primary_timeframe=primary_timeframe, primary_period=primary_period,
            higher_timeframe=higher_timeframe, higher_period=higher_period,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر التحليل متعدد الإطارات لـ {symbol}: {e}")
