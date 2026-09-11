import pandas as pd
import numpy as np

def validate_ohlcv(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Data Quality Layer: يفحص سلامة البيانات التاريخية قبل أي تحليل.
    """
    if df is None or df.empty:
        return False, "لا توجد بيانات (Empty DataFrame)."
    
    if len(df) < 50:
        return False, f"بيانات غير كافية للتحليل (مطلوب 50 شمعة على الأقل، المتاح {len(df)})."

    # 1. فحص الشموع المستحيلة
    invalid_high_low = df[df['High'] < df['Low']]
    if not invalid_high_low.empty:
        return False, "DATA QUALITY WARNING: توجد شموع سعر الـ High فيها أقل من الـ Low."

    invalid_open_close = df[(df['Open'] > df['High']) | (df['Open'] < df['Low']) | 
                            (df['Close'] > df['High']) | (df['Close'] < df['Low'])]
    if not invalid_open_close.empty:
        return False, "DATA QUALITY WARNING: سعر الإغلاق أو الافتتاح خارج نطاق High/Low."

    # 2. فحص الفوليوم السلبي
    if (df['Volume'] < 0).any():
        return False, "DATA QUALITY WARNING: توجد قيم Volume سلبية غير منطقية."

    # 3. فحص الشموع المفقودة أو المكررة (Duplicate Index)
    if df.index.duplicated().any():
        return False, "DATA QUALITY WARNING: توجد بيانات مكررة في التواريخ."

    return True, "Data is Valid"