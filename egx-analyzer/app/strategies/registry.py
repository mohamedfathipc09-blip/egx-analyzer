# -*- coding: utf-8 -*-
"""
سجل الاستراتيجيات (Strategy Registry) - كل استراتيجية جديدة تتضاف هنا
بس، من غير ما تلمس منطق الـ Strategy Engine نفسه في app/strategies/engine.py.
"""

from app.strategies import definitions as d

STRATEGY_REGISTRY = {
    "classic_trend": {
        "label": "الاتجاه الكلاسيكي (EMA20/50 + RSI + حجم)",
        "compute": d.strategy_classic_trend,
    },
    "strong_trend": {
        "label": "الاتجاه بالزخم القوي (EMA + MACD + ADX)",
        "compute": d.strategy_strong_trend,
    },
    "breakout": {
        "label": "الاختراق المؤكد بالحجم",
        "compute": d.strategy_breakout,
    },
    "mean_reversion": {
        "label": "الارتداد من التذبذب (بولينجر + RSI)",
        "compute": d.strategy_mean_reversion,
    },
    "volume_momentum": {
        "label": "الزخم المدعوم بالحجم (VWAP)",
        "compute": d.strategy_volume_momentum,
    },
}
