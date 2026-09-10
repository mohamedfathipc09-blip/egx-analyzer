# -*- coding: utf-8 -*-
"""Endpoints الخاصة بقائمة أسهم EGX المنسّقة (بديل عن صفحة مباشر المعتمدة على جافاسكريبت)."""

from typing import Optional
from fastapi import APIRouter, Query

from app.data.symbols_repository import (
    get_all_symbols, search_symbols, get_symbols_by_sector, list_sectors, get_metadata,
)
from app.data.stockanalysis_client import get_full_symbol_list

router = APIRouter(tags=["قائمة الأسهم"])


@router.get("/symbols")
def list_symbols(
    sector: Optional[str] = Query(None, description="فلترة بقطاع معين - استخدم /symbols/sectors لمعرفة القطاعات المتاحة"),
    q: Optional[str] = Query(None, description="بحث بالرمز أو الاسم العربي"),
):
    """
    يرجع قائمة أسهم EGX المنسّقة (رمز + اسم عربي + قطاع). هذه قائمة منسّقة
    يدويًا وليست مستخرجة آليًا لحظيًا - راجع /symbols/metadata لمعرفة تاريخ
    آخر مراجعة وتنبيه الدقة.
    """
    if q:
        return search_symbols(q)
    if sector:
        return get_symbols_by_sector(sector)
    return get_all_symbols()


@router.get("/symbols/sectors")
def get_available_sectors():
    """يرجع كل القطاعات المتاحة في القائمة - مفيد لبناء فلتر في الواجهة."""
    return list_sectors()


@router.get("/symbols/metadata")
def get_symbols_metadata():
    """معلومات عن مصدر القائمة: ملاحظة الدقة، تاريخ آخر مراجعة، العدد الإجمالي."""
    return get_metadata()


@router.get("/symbols/full-market")
def get_full_market_symbols(force_refresh: bool = Query(False, description="تجاهل الكاش وجيب القائمة من المصدر الحي مباشرة")):
    """
    القائمة الكاملة لكل الأسهم المُدرجة في البورصة المصرية (~229 سهم) من
    stockanalysis.com - بديل عن القائمة المنسّقة الأساسية (39 سهم). بيرجع
    من كاش محلي عادةً (أسرع)، أو المصدر الحي لو force_refresh=true. لو
    المصدر الحي فشل، بيرجع تلقائيًا للقائمة المنسّقة كاحتياط.
    """
    return get_full_symbol_list(force_refresh=force_refresh)
