import pandas as pd
import numpy as np

class QuantStrategyEngine:
    def __init__(self, df_daily: pd.DataFrame, df_1h: pd.DataFrame = None):
        self.df = df_daily.copy()
        self.df_1h = df_1h
        self._calculate_base_indicators()
    
    def _calculate_base_indicators(self):
        """حساب المؤشرات الأساسية بفاعلية باستخدام Pandas"""
        # Trend
        self.df['EMA20'] = self.df['Close'].ewm(span=20, adjust=False).mean()
        self.df['EMA50'] = self.df['Close'].ewm(span=50, adjust=False).mean()
        self.df['SMA200'] = self.df['Close'].rolling(window=200).mean()
        
        # Volatility & ATR
        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        self.df['ATR'] = true_range.rolling(14).mean()
        
        # Momentum (RSI)
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume
        self.df['Vol_SMA20'] = self.df['Volume'].rolling(20).mean()
        self.df['Rel_Vol'] = self.df['Volume'] / self.df['Vol_SMA20']

        # Support & Resistance (Swing Highs/Lows - 20 periods)
        self.df['Swing_High'] = self.df['High'].rolling(window=20, center=True).max()
        self.df['Swing_Low'] = self.df['Low'].rolling(window=20, center=True).min()

    def get_market_regime(self):
        latest = self.df.iloc[-1]
        if latest['Close'] > latest['EMA20'] > latest['EMA50'] > latest['SMA200']:
            return "STRONG_UPTREND"
        elif latest['Close'] > latest['EMA50']:
            return "UPTREND"
        elif latest['Close'] < latest['EMA20'] and latest['Close'] < latest['EMA50']:
            return "DOWNTREND"
        else:
            return "SIDEWAYS"

    def calculate_trade_setup(self):
        """حساب Score, Confidence, ومناطق الدخول والأهداف (Phases 3, 4, 6)"""
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        regime = self.get_market_regime()
        
        score = 0
        confidence = 0
        reasons = []
        risks = []

        # 1. Trend Analysis (Max 25)
        trend_score = 0
        if regime in ["STRONG_UPTREND", "UPTREND"]:
            trend_score += 15
            reasons.append("✓ Daily trend is Bullish")
        if latest['Close'] > latest['EMA20']:
            trend_score += 10
            reasons.append("✓ Price above EMA20")
        else:
            risks.append("⚠ Price below short-term EMA20")
        score += trend_score

        # 2. Momentum (Max 20)
        mom_score = 0
        if 40 <= latest['RSI'] <= 65:
            mom_score += 15 # Healthy momentum
            reasons.append(f"✓ Healthy RSI ({latest['RSI']:.1f})")
        elif latest['RSI'] > 70:
            risks.append("⚠ RSI is Overbought (Risk of pullback)")
        if latest['RSI'] > prev['RSI']:
            mom_score += 5
        score += mom_score

        # 3. Volume (Max 15)
        vol_score = 0
        if latest['Rel_Vol'] > 1.2:
            vol_score += 15
            reasons.append(f"✓ Strong Relative Volume ({latest['Rel_Vol']:.1f}x)")
        elif latest['Rel_Vol'] > 0.8:
            vol_score += 8
        else:
            risks.append("⚠ Low trading volume")
        score += vol_score
        
        # S/R & Price Action (Simulated for constraints)
        support = self.df['Swing_Low'].ffill().iloc[-1]
        resistance = self.df['Swing_High'].ffill().iloc[-1]
        
        # 4. Entry, SL, TP Generation based on ATR
        atr = latest['ATR']
        current_price = latest['Close']
        
        # Entry Zone (Current price to Support or -0.5 ATR)
        entry_high = current_price
        entry_low = max(support, current_price - (atr * 0.5))
        
        # Stop Loss (Below support and ATR)
        sl = support - (atr * 1.5)
        if sl >= current_price: 
            sl = current_price - (atr * 2) # Fallback

        risk_per_share = entry_high - sl
        
        tp1 = entry_high + (risk_per_share * 1.5) # R/R 1:1.5
        tp2 = entry_high + (risk_per_share * 2.5) # R/R 1:2.5
        tp3 = max(resistance, entry_high + (risk_per_share * 4.0))

        risk_reward_ratio = (tp1 - entry_high) / risk_per_share if risk_per_share > 0 else 0

        # Base Confidence on Confluence & Risk/Reward
        if risk_reward_ratio >= 1.5: confidence += 40
        if trend_score >= 15: confidence += 30
        if vol_score >= 15: confidence += 30

        # Signal Classification
        signal = "NO TRADE"
        if score >= 85 and confidence >= 80 and risk_reward_ratio >= 1.5:
            signal = "STRONG BUY"
        elif score >= 75:
            signal = "BUY"
        elif score >= 65:
            signal = "WATCH"

        return {
            "signal": signal,
            "score": score,
            "confidence": confidence,
            "regime": regime,
            "entry_zone": f"{entry_low:.2f} - {entry_high:.2f}",
            "stop_loss": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "tp3": round(tp3, 2),
            "risk_reward": round(risk_reward_ratio, 2),
            "reasons": reasons,
            "risks": risks,
            # Placeholders for Backtest Engine (Phase 5) - Strictly NO FAKE DATA
            "historical_win_rate": "بيانات غير كافية", 
            "trades_tested": 0
        }