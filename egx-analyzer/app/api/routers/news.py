# -*- coding: utf-8 -*-
"""Endpoint الخاص بالأخبار."""

from typing import List
from fastapi import APIRouter, Query

from app.data.news_client import get_news
from app.api.schemas import NewsItem

router = APIRouter(tags=["الأخبار"])


@router.get("/news", response_model=List[NewsItem])
def news(limit: int = Query(20, ge=1, le=100, description="عدد الأخبار المطلوبة")):
    """يرجع آخر أخبار البورصة المصرية (من صفحة الأخبار الحية، مع RSS كخطة احتياطية)."""
    return get_news(limit=limit)
