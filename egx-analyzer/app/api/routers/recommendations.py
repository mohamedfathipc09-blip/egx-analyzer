from fastapi import APIRouter, HTTPException
from typing import Dict, Any

# استدعاء الملفات بتاعتنا
from app.data.history_client import fetch_history
from app.data.validation import validate_ohlcv
from app.analysis.strategy_engine import QuantStrategyEngine

# السطر اللي كان ناقص واللي بسببه السيرفر وقع!
router = APIRouter(prefix="/recommendations", tags=["التوصيات"])

@router.get("/quant-analysis/{symbol}", summary="تحليل كمّي احترافي للسهم (للمضاربة)")
def get_quant_analysis(symbol: str) -> Dict[str, Any]:
    try:
        # Phase 2: جلب اليومي والأسبوعي (Multi-Timeframe)
        df_daily = fetch_history(symbol, period="2y", interval="1d")
        df_weekly = fetch_history(symbol, period="2y", interval="1wk")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"فشل جلب بيانات السهم: {str(e)}")

    is_valid, msg = validate_ohlcv(df_daily)
    if not is_valid:
        return {
            "symbol": symbol.upper(),
            "signal": "NO TRADE",
            "score": 0,
            "confidence": 0,
            "error_msg": f"DATA QUALITY WARNING: {msg}"
        }

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