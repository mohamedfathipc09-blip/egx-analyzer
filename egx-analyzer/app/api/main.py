# -*- coding: utf-8 -*-
"""
تطبيق FastAPI الرئيسي - منصة تحليل فني ومالي لأسهم البورصة المصرية.

التشغيل:
    uvicorn app.api.main:app --reload --port 8000

التوثيق التلقائي:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI

from app.api.routers import prices, news, analysis, backtest, recommendations, history, alerts, symbols, strategies
from app.data.health import check_all_sources
from app.scheduler import start_scheduler, stop_scheduler, is_running

app = FastAPI(
    title="EGX Analyzer API",
    description=(
        "API لأسعار وأخبار وتحليل فني وأساسي لأسهم البورصة المصرية "
        "(المصدر: مباشر - mubasher.info، وYahoo Finance للبيانات التاريخية)."
    ),
    version="1.0.0",
)

app.include_router(prices.router)
app.include_router(news.router)
app.include_router(analysis.router)
app.include_router(backtest.router)
app.include_router(recommendations.router)
app.include_router(history.router)
app.include_router(alerts.router)
app.include_router(symbols.router)
app.include_router(strategies.router)


@app.on_event("startup")
def _on_startup():
    """يبدأ الجدولة التلقائية للتنبيهات مع تشغيل الـ API - مفيش تدخل يدوي مطلوب."""
    start_scheduler()


@app.on_event("shutdown")
def _on_shutdown():
    stop_scheduler()


@app.get("/health", tags=["عام"])
def health():
    """
    يفحص كل مصدر بيانات على حدة (مباشر، الأخبار الحية، Yahoo Finance)
    ويرجع حالته: ok / degraded / down، مع حالة عامة مجمّعة لكل المصادر.
    """
    return check_all_sources()


@app.get("/scheduler/status", tags=["عام"])
def scheduler_status():
    """يوضح هل الجدولة التلقائية لفحص التنبيهات شغالة حاليًا ولا لأ."""
    from app.scheduler import CHECK_INTERVAL_MINUTES
    return {"is_running": is_running(), "check_interval_minutes": CHECK_INTERVAL_MINUTES}


@app.get("/", tags=["عام"])
def root():
    return {
        "message": "EGX Analyzer API شغال",
        "docs": "/docs",
        "endpoints": [
            "/health - فحص حالة كل مصدر بيانات",
            "/price/{symbol}",
            "/prices?symbols=...",
            "/news?limit=...",
            "/analysis/{symbol}?timeframe=daily|weekly&period=...",
            "/analysis?symbols=...",
            "/analysis/{symbol}/multi-timeframe - تأكيد الاتجاه من إطار زمني أكبر",
            "/backtest/{symbol}?period=...&holding_days=...",
            "/backtest/{symbol}/train-test-split?split_ratio=...",
            "/backtest/{symbol}/walk-forward?n_folds=...",
            "/backtest/{symbol}/by-market-regime",
            "/recommendations (POST) - حفظ توصية للمتابعة",
            "/recommendations?symbol=...&status=... (GET) - سجل التوصيات",
            "/recommendations/performance - أداء النظام الفعلي",
            "/recommendations/{id}/refresh (POST) - تحديث حالة توصية",
            "/recommendations/refresh-all (POST) - تحديث كل التوصيات المفتوحة",
            "/settings (GET/POST) - إعدادات التنبيهات (معطّلة افتراضيًا)",
            "/alerts/test (POST) - رسالة تجربة تليجرام",
            "/alerts/check-watchlist (POST) - فحص قايمة المتابعة",
            "/alerts/check-open-positions (POST) - فحص الصفقات المفتوحة",
            "/symbols?sector=...&q=... - قائمة أسهم EGX المنسّقة",
            "/symbols/sectors - القطاعات المتاحة",
            "/symbols/metadata - معلومات عن مصدر القائمة",
            "/strategies/best/{symbol} - أفضل استراتيجية تداول لهذا السهم تحديدًا (باك-تيستنج فعلي)",
            "/fundamentals/{symbol}",
            "/chart/{symbol}?timeframe=daily|weekly&period=... - بيانات Candlestick + SMA/Bollinger",
            "/screener/bullish?min_score=...&min_agreement=...",
            "/report/{symbol}",
            "/opportunities/top?limit=5 - فحص تلقائي كامل بدون إعدادات، أفضل الفرص الفعلية",
        ],
    }
