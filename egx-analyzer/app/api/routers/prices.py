# -*- coding: utf-8 -*-
"""Endpoints الخاصة بالأسعار اللحظية."""

from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

from app.config import DEFAULT_SYMBOLS
from app.data.mubasher_client import get_stock_data
from app.api.schemas import StockPrice

router = APIRouter(tags=["الأسعار"])


@router.get("/price/{symbol}", response_model=StockPrice)
def price(symbol: str):
    """يرجع بيانات سهم واحد. مثال: /price/ETEL"""
    data = get_stock_data(symbol.upper(), delay=0)
    if data.get("last_price") is None and data.get("error"):
        raise HTTPException(status_code=502, detail=f"تعذر جلب بيانات {symbol}: {data['error']}")
    return data


@router.get("/prices", response_model=List[StockPrice])
def prices(symbols: Optional[str] = Query(
        None, description="رموز الأسهم مفصولة بفاصلة، مثال: ETEL,COMI,SWDY")):
    """يرجع أسعار عدة أسهم مرة واحدة (بالتوازي)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_SYMBOLS
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda s: get_stock_data(s, delay=0), symbol_list))
    return results
