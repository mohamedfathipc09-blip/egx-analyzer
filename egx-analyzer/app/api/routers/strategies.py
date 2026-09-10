# -*- coding: utf-8 -*-
"""Endpoint الخاص بمحرك مقارنة استراتيجيات التداول (Strategy Engine)."""

from fastapi import APIRouter, HTTPException, Query

from app.strategies.engine import find_best_strategy

router = APIRouter(tags=["استراتيجيات التداول"])


@router.get("/strategies/best/{symbol}")
def best_strategy(
    symbol: str,
    period: str = Query("2y", description="مدة بيانات الباك-تيستنج: 1y, 2y, 5y"),
    holding_days: int = Query(10, ge=1, le=60, description="مدة الاحتفاظ بالصفقة بالأيام"),
    buy_threshold: float = Query(20.0, description="الحد الأدنى لدرجة الاستراتيجية لاعتبارها إشارة شراء"),
):
    """
    يختبر عدة استراتيجيات تداول مختلفة فعليًا على تاريخ السهم (باك-تيستنج
    حقيقي لكل واحدة)، ويرشّح الأفضل بناءً على Profit Factor مخصوم حسب حجم
    العينة - مش نسبة نجاح لوحدها ومش رقم من عدد صفقات قليل. استراتيجيات
    بعينة غير كافية بتتعرض لوحدها بره الترتيب.
    """
    try:
        return find_best_strategy(
            symbol.upper(), period=period,
            holding_days=holding_days, buy_threshold=buy_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر مقارنة الاستراتيجيات لـ {symbol}: {e}")
