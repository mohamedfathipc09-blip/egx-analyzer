# -*- coding: utf-8 -*-
"""Endpoint الخاص باختبار الأداء التاريخي."""

from fastapi import APIRouter, HTTPException, Query

from app.backtesting.engine import backtest_symbol
from app.backtesting.robustness import (
    train_test_split_backtest,
    walk_forward_backtest,
    backtest_by_market_regime,
)
from app.api.schemas import BacktestResponse

router = APIRouter(tags=["التحليل الفني"])


@router.get("/backtest/{symbol}", response_model=BacktestResponse)
def backtest(
    symbol: str,
    period: str = Query("2y", description="مدة الاختبار: 1y, 2y, 5y"),
    holding_days: int = Query(10, ge=1, le=60, description="مدة الاحتفاظ بالصفقة بالأيام"),
    buy_threshold: float = Query(20.0, description="عتبة اعتبار الإشارة شراء"),
    sell_threshold: float = Query(-20.0, description="عتبة اعتبار الإشارة بيع"),
):
    """
    يختبر أداء نظام التوصيات على بيانات تاريخية فعلية، ويرجع نسبة نجاح
    حقيقية محسوبة من التاريخ (وليست تقديرية) لإشارات الشراء والبيع.
    """
    try:
        return backtest_symbol(
            symbol.upper(),
            period=period,
            holding_days=holding_days,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر اختبار {symbol}: {e}")


@router.get("/backtest/{symbol}/train-test-split")
def backtest_train_test_split(
    symbol: str,
    period: str = Query("5y", description="مدة الاختبار الكلية: 2y, 5y"),
    split_ratio: float = Query(0.7, ge=0.3, le=0.9, description="نسبة بيانات البناء (in-sample) من إجمالي الفترة"),
    holding_days: int = Query(10, ge=1, le=60),
    buy_threshold: float = Query(20.0),
    sell_threshold: float = Query(-20.0),
):
    """
    يقسّم الفترة التاريخية لجزئين منفصلين تمامًا (بناء واختبار) ويقارن نسبة
    النجاح بينهم - مؤشر مباشر على استقرار النظام وعدم اعتماده على فترة
    واحدة بالذات.
    """
    try:
        return train_test_split_backtest(
            symbol.upper(), period=period, split_ratio=split_ratio,
            holding_days=holding_days, buy_threshold=buy_threshold, sell_threshold=sell_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر اختبار {symbol}: {e}")


@router.get("/backtest/{symbol}/walk-forward")
def backtest_walk_forward(
    symbol: str,
    period: str = Query("5y", description="مدة الاختبار الكلية"),
    n_folds: int = Query(4, ge=2, le=10, description="عدد الفترات الزمنية المتتالية للمقارنة"),
    holding_days: int = Query(10, ge=1, le=60),
    buy_threshold: float = Query(20.0),
    sell_threshold: float = Query(-20.0),
):
    """
    يقسّم الفترة لعدة فترات زمنية متتالية ويقيس مدى استقرار نسبة النجاح
    عبرها (الانحراف المعياري). تذبذب كبير = تحذير من عدم استقرار النظام.
    """
    try:
        return walk_forward_backtest(
            symbol.upper(), period=period, n_folds=n_folds,
            holding_days=holding_days, buy_threshold=buy_threshold, sell_threshold=sell_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر اختبار {symbol}: {e}")


@router.get("/backtest/{symbol}/by-market-regime")
def backtest_market_regime(
    symbol: str,
    period: str = Query("5y", description="مدة الاختبار الكلية"),
    holding_days: int = Query(10, ge=1, le=60),
    buy_threshold: float = Query(20.0),
    sell_threshold: float = Query(-20.0),
):
    """
    يحسب أداء إشارات الشراء منفصلًا لكل حالة سوق (صاعد/هابط/عرضي) - للتأكد
    إن الأداء العام مش مدفوع بس بموجة صعود عامة في السوق.
    """
    try:
        return backtest_by_market_regime(
            symbol.upper(), period=period,
            holding_days=holding_days, buy_threshold=buy_threshold, sell_threshold=sell_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"تعذر اختبار {symbol}: {e}")
