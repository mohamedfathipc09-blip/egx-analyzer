# -*- coding: utf-8 -*-
"""Endpoints الخاصة بسجل التوصيات وأداء النظام الفعلي."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Body, Query

from app.data.db import (
    save_recommendation, list_recommendations, get_recommendation,
    refresh_recommendation, compute_performance_summary, OPEN_STATUSES,
)
from app.data.mubasher_client import get_stock_data
from app.analysis.scoring import analyze_stock

router = APIRouter(tags=["سجل التوصيات"])


@router.post("/recommendations")
def create_recommendation(symbol: str = Body(..., embed=True)):
    """
    يحلل السهم الآن، ولو فيه خطة تداول صالحة (trade_plan.status ==
    valid_long_setup)، يحفظها في السجل للمتابعة. لو مفيش فرصة مناسبة
    حاليًا، يرجع توضيح بدل ما يحفظ حاجة فاضية.
    """
    try:
        analysis = analyze_stock(symbol.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    plan = analysis.get("trade_plan", {})
    if plan.get("status") != "valid_long_setup":
        raise HTTPException(
            status_code=400,
            detail=f"لا توجد خطة تداول صالحة لحفظها حاليًا لـ {symbol}: {plan.get('status_label')}",
        )

    rec_id = save_recommendation({
        "symbol": symbol.upper(),
        "recommendation": analysis["recommendation"],
        "score": analysis["score"],
        "entry": plan["entry"],
        "stop_loss": plan["stop_loss"],
        "target1": plan["targets"][0],
        "target2": plan["targets"][1] if len(plan["targets"]) > 1 else None,
        "target3": plan["targets"][2] if len(plan["targets"]) > 2 else None,
        "risk_reward_ratio": plan["risk_reward_ratio"],
    })
    return get_recommendation(rec_id)


@router.get("/recommendations")
def get_recommendations_history(
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="OPEN, TARGET1_HIT, TARGET2_HIT, CLOSED_PROFIT, CLOSED_LOSS"),
    limit: int = Query(50, ge=1, le=200),
):
    """يرجع سجل التوصيات المحفوظة، مع إمكانية الفلترة برمز أو حالة."""
    return list_recommendations(symbol=symbol, status=status, limit=limit)


@router.get("/recommendations/performance")
def get_system_performance():
    """
    أداء النظام الفعلي من التوصيات المقفولة فعليًا (مش توقعات). لو مفيش
    توصيات مقفولة كفاية، بيوضح ده صراحة بدل رقم مصطنع.
    """
    return compute_performance_summary()


@router.post("/recommendations/{rec_id}/refresh")
def refresh_single_recommendation(rec_id: int):
    """يجيب السعر الحالي للسهم ويعيد تقييم توصية واحدة ضده."""
    rec = get_recommendation(rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"لا توجد توصية بالمعرف {rec_id}")

    price_data = get_stock_data(rec["symbol"], delay=0)
    current_price = price_data.get("last_price")
    if current_price is None:
        raise HTTPException(status_code=502, detail=f"تعذر جلب السعر الحالي لـ {rec['symbol']}")

    return refresh_recommendation(rec_id, current_price)


@router.post("/recommendations/refresh-all")
def refresh_all_open_recommendations():
    """يعيد تقييم كل التوصيات المفتوحة حاليًا ضد أسعارها الحية دفعة واحدة."""
    updated = []
    for status in OPEN_STATUSES:
        for rec in list_recommendations(status=status, limit=200):
            price_data = get_stock_data(rec["symbol"], delay=0)
            current_price = price_data.get("last_price")
            if current_price is None:
                continue
            updated.append(refresh_recommendation(rec["id"], current_price))
    return {"updated_count": len(updated), "recommendations": updated}
