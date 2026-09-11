# مسار الملف: app/analysis/strategy_engine.py
import pandas as pd
import numpy as np
from app.analysis.backtester import VectorizedBacktester

class QuantStrategyEngine:
    # أضفنا df_weekly لدمج الفريم الأكبر
    def __init__(self, df_daily: pd.DataFrame, df_weekly: pd.DataFrame = None):
        self.df = df_daily.copy()
        self.df_weekly = df_weekly
        self._calculate_base_indicators()
    
    def _calculate_base_indicators(self):
        self.df['EMA20'] = self.df['Close'].ewm(span=20, adjust=False).mean()
        self.df['EMA50'] = self.df['Close'].ewm(span=50, adjust=False).mean()
        self.df['SMA200'] = self.df['Close'].rolling(window=200).mean()
        
        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        self.df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
        
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        self.df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        self.df['Vol_SMA20'] = self.df['Volume'].rolling(20).mean()
        self.df['Rel_Vol'] = self.df['Volume'] / self.df['Vol_SMA20']
        
        self.df['Swing_High'] = self.df['High'].rolling(window=20, center=True).max()
        self.df['Swing_Low'] = self.df['Low'].rolling(window=20, center=True).min()

    def get_market_regime(self):
        latest = self.df.iloc[-1]
        if latest['Close'] > latest['EMA20'] > latest['EMA50'] > latest['SMA200']: return "STRONG_UPTREND"
        elif latest['Close'] > latest['EMA50']: return "UPTREND"
        elif latest['Close'] < latest['EMA20'] and latest['Close'] < latest['EMA50']: return "DOWNTREND"
        return "SIDEWAYS"

    def _check_higher_timeframe(self) -> str:
        """Phase 2: Multi-Timeframe Analysis"""
        if self.df_weekly is None or self.df_weekly.empty or len(self.df_weekly) < 20:
            return "UNKNOWN"
        
        latest_w = self.df_weekly.iloc[-1]
        ema20_w = self.df_weekly['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        
        if latest_w['Close'] > ema20_w: return "BULLISH"
        return "BEARISH"

    def calculate_trade_setup(self):
        latest = self.df.iloc[-1]
        regime = self.get_market_regime()
        htf_trend = self._check_higher_timeframe()
        
        score = 0
        confidence = 0
        reasons = []
        risks = []

        # Multi-Timeframe Filter
        if htf_trend == "BULLISH":
            score += 15
            reasons.append("✓ Weekly Trend is Bullish (MTF Confirmed)")
        elif htf_trend == "BEARISH":
            risks.append("⚠ Weekly Trend is BEARISH (Trading against major trend)")

        # Trend & Momentum
        if regime in ["STRONG_UPTREND", "UPTREND"]: score += 15
        if latest['Close'] > latest['EMA20']: score += 10
        if 40 <= latest['RSI'] <= 65:
            score += 15
            reasons.append(f"✓ Healthy RSI ({latest['RSI']:.1f})")
        
        # Volume
        if latest['Rel_Vol'] > 1.2:
            score += 15
            reasons.append(f"✓ Strong Relative Volume ({latest['Rel_Vol']:.1f}x)")
            
        support = self.df['Swing_Low'].ffill().iloc[-1]
        resistance = self.df['Swing_High'].ffill().iloc[-1]
        atr = latest['ATR']
        current_price = latest['Close']
        
        entry_high = current_price
        entry_low = max(support, current_price - (atr * 0.5))
        sl = support - (atr * 1.5)
        if sl >= current_price: sl = current_price - (atr * 2) 

        risk_per_share = entry_high - sl
        tp1 = entry_high + (risk_per_share * 1.5)
        tp2 = entry_high + (risk_per_share * 2.5)
        tp3 = max(resistance, entry_high + (risk_per_share * 4.0))

        risk_reward_ratio = (tp1 - entry_high) / risk_per_share if risk_per_share > 0 else 0

        # Confidence Calculation
        if risk_reward_ratio >= 1.5: confidence += 30
        if htf_trend == "BULLISH": confidence += 20
        if score >= 50: confidence += 30

        signal = "NO TRADE"
        if score >= 80 and confidence >= 70 and risk_reward_ratio >= 1.5 and htf_trend != "BEARISH":
            signal = "STRONG BUY"
        elif score >= 65 and risk_reward_ratio >= 1.2:
            signal = "BUY"
        elif score >= 50:
            signal = "WATCH"

        # Phase 5: Run Actual Backtest Engine
        backtester = VectorizedBacktester(self.df)
        backtest_stats = backtester.run_trend_breakout_test()

        return {
            "signal": signal,
            "score": score,
            "confidence": confidence,
            "regime": regime,
            "htf_trend": htf_trend,
            "entry_zone": f"{entry_low:.2f} - {entry_high:.2f}",
            "stop_loss": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "tp3": round(tp3, 2),
            "risk_reward": round(risk_reward_ratio, 2),
            "reasons": reasons,
            "risks": risks,
            **backtest_stats  # دمج إحصائيات الباك-تيست هنا
        }