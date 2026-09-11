# مسار الملف: app/analysis/backtester.py
import pandas as pd
import numpy as np

class VectorizedBacktester:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.trades = []

    def run_trend_breakout_test(self) -> dict:
        """
        بيعمل محاكاة حقيقية للصفقات التاريخية بناءً على الاستراتيجية.
        Entry: تقاطع إيجابي مع EMA20 + فوليوم عالي + RSI صحي
        Exit: ضرب الهدف (TP)، ضرب الوقف (SL)، أو كسر EMA50
        """
        in_position = False
        entry_price = 0
        sl = 0
        tp = 0

        # بنمشي على الشموع التاريخية
        for i in range(1, len(self.df)):
            current = self.df.iloc[i]
            prev = self.df.iloc[i-1]

            if not in_position:
                # شروط الدخول (Confluence)
                if (current['Close'] > current['EMA20'] and 
                    current['RSI'] > 50 and 
                    current['Rel_Vol'] > 1.0 and 
                    prev['Close'] <= prev['EMA20']): # Breakout
                    
                    in_position = True
                    entry_price = current['Close']
                    sl = entry_price - (current['ATR'] * 1.5)
                    tp = entry_price + (current['ATR'] * 3.0) # R:R 1:2
            else:
                # شروط الخروج
                if current['Low'] <= sl: # Stop Loss Hit
                    self.trades.append({'return': (sl - entry_price) / entry_price, 'type': 'loss'})
                    in_position = False
                elif current['High'] >= tp: # Take Profit Hit
                    self.trades.append({'return': (tp - entry_price) / entry_price, 'type': 'win'})
                    in_position = False
                elif current['Close'] < current['EMA50']: # Trend Change Exit
                    ret = (current['Close'] - entry_price) / entry_price
                    self.trades.append({'return': ret, 'type': 'win' if ret > 0 else 'loss'})
                    in_position = False

        return self._calculate_metrics()

    def _calculate_metrics(self) -> dict:
        if not self.trades or len(self.trades) < 5:
            return {
                "historical_win_rate": "بيانات غير كافية", 
                "trades_tested": len(self.trades),
                "profit_factor": "N/A",
                "max_drawdown": "N/A"
            }

        returns = [t['return'] for t in self.trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        win_rate = (len(wins) / len(self.trades)) * 100
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0)

        # حساب الـ Max Drawdown الحقيقي
        cumulative = np.cumprod(1 + np.array(returns))
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        max_dd = np.max(drawdown) * 100 if len(drawdown) > 0 else 0

        return {
            "historical_win_rate": f"{win_rate:.1f}%",
            "trades_tested": len(self.trades),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": f"{max_dd:.1f}%"
        }