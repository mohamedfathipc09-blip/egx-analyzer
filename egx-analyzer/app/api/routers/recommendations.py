import pandas as pd
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.data.history_client import fetch_history
from app.data.validation import validate_ohlcv
from app.analysis.strategy_engine import QuantStrategyEngine

router = APIRouter(prefix="/recommendations", tags=["التوصيات"])

@router.get("/quant-analysis/{symbol}", summary="تحليل كمّي احترافي للسهم (للمضاربة)")
def get_quant_analysis(symbol: str) -> Dict[str, Any]:
    try:
        # 1. جلب البيانات اليومية (مرة واحدة فقط لتخطي حظر ياهو)
        df_daily = fetch_history(symbol, period="2y", interval="1d")
        
        # 2. بناء الفريم الأسبوعي داخلياً في السيرفر (Resampling)
        # الطريقة دي بتمنع البلوك تماماً وبتكون أسرع وأدق
        logic = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        df_weekly = df_daily.resample('W').agg(logic).dropna()
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"فشل جلب بيانات السهم: {str(e)}")

    # 3. فحص جودة البيانات
    is_valid, msg = validate_ohlcv(df_daily)
    if not is_valid:
        return {
            "symbol": symbol.upper(),
            "signal": "NO TRADE",
            "score": 0,
            "confidence": 0,
            "error_msg": f"DATA QUALITY WARNING: {msg}"
        }

    # 4. تشغيل محرك الاستراتيجية
    try:
        engine = QuantStrategyEngine(df_daily=df_daily, df_weekly=df_weekly)
        analysis = engine.calculate_trade_setup()
        
        return {
            "symbol": symbol.upper(),
            "current_price": round(df_daily.iloc[-1]['Close'], 2),
            **analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ داخلي أثناء تحليل البيانات: {str(e)}")