from fastapi import APIRouter, HTTPException
from typing import Dict, Any

# استدعاء الدوال والمحركات الجديدة (تأكد من إنشاء الملفات كما وضحنا سابقاً)
from app.data.history_client import fetch_history
from app.data.validation import validate_ohlcv
from app.analysis.strategy_engine import QuantStrategyEngine

# إذا كان الـ router معرفاً مسبقاً في ملفك، لا تقم بإعادة تعريفه، فقط أضف الـ @router.get أدناه
# router = APIRouter(prefix="/recommendations", tags=["التوصيات"])

@router.get("/quant-analysis/{symbol}", summary="تحليل كمّي احترافي للسهم (للمضاربة)")
def get_quant_analysis(symbol: str) -> Dict[str, Any]:
    """
    يقوم بعمل تحليل فني كمي كامل للسهم يشمل:
    - فحص جودة البيانات (Data Quality)
    - تحديد حالة السوق (Market Regime)
    - حساب Score & Confidence
    - استخراج مناطق الدخول والأهداف ووقف الخسارة
    """
    try:
        # 1. جلب البيانات التاريخية (سنة واحدة تكفي للتحليل اليومي كمرحلة أولى)
        df_daily = fetch_history(symbol, period="1y", interval="1d")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"فشل جلب بيانات السهم: {str(e)}")

    # 2. فحص جودة البيانات (Data Validation Layer)
    is_valid, msg = validate_ohlcv(df_daily)
    if not is_valid:
        return {
            "symbol": symbol.upper(),
            "signal": "NO TRADE",
            "score": 0,
            "confidence": 0,
            "error_msg": f"DATA QUALITY WARNING: {msg}"
        }

    # 3. تشغيل محرك الاستراتيجيات (Strategy Engine)
    try:
        engine = QuantStrategyEngine(df_daily)
        analysis = engine.calculate_trade_setup()
        
        return {
            "symbol": symbol.upper(),
            "current_price": round(df_daily.iloc[-1]['Close'], 2),
            **analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ داخلي أثناء تحليل البيانات: {str(e)}")