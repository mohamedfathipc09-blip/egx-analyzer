# -*- coding: utf-8 -*-
"""نماذج Pydantic لاستجابات الـ API."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class StockPrice(BaseModel):
    symbol: str
    name: Optional[str] = None
    last_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    prev_close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    market_cap: Optional[float] = None
    eps: Optional[float] = None
    pe_ratio: Optional[float] = None
    url: Optional[str] = None
    fetched_at: Optional[str] = None
    error: Optional[str] = None


class NewsItem(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    published: Optional[str] = None
    summary: Optional[str] = None


class AnalysisResponse(BaseModel):
    symbol: str
    timeframe: Optional[str] = None
    analyzed_at: Optional[str] = None
    last_close: Optional[float] = None
    recommendation: Optional[str] = None
    score: Optional[float] = None
    agreement_percent: Optional[float] = None
    indicators_bullish: Optional[int] = None
    indicators_bearish: Optional[int] = None
    indicators_neutral: Optional[int] = None
    signal_conflict: Optional[Dict[str, Any]] = None
    data_quality: Optional[Dict[str, Any]] = None
    categories: Optional[Dict[str, Any]] = None
    support_resistance: Optional[Dict[str, Any]] = None
    fibonacci_levels: Optional[Dict[str, Any]] = None
    pivot_points: Optional[Dict[str, Any]] = None
    candlestick_patterns: Optional[List[str]] = None
    trade_plan: Optional[Dict[str, Any]] = None
    speculative_trade_plan: Optional[Dict[str, Any]] = None
    disclaimer: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


class BacktestResponse(BaseModel):
    symbol: str
    period_tested: Optional[str] = None
    holding_days: Optional[int] = None
    buy_signal_threshold: Optional[float] = None
    sell_signal_threshold: Optional[float] = None
    buy_signals_performance: Optional[Dict[str, Any]] = None
    sell_signals_performance: Optional[Dict[str, Any]] = None
    buy_and_hold_return_percent: Optional[float] = None
    max_drawdown_percent_buy_signals: Optional[float] = None
    sharpe_ratio_buy_signals: Optional[float] = None
    note: Optional[str] = None
    error: Optional[str] = None


class ReportResponse(BaseModel):
    symbol: str
    generated_at: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    backtest: Optional[Dict[str, Any]] = None
    fundamentals: Optional[Dict[str, Any]] = None
    disclaimer: Optional[str] = None
    error: Optional[str] = None


class FundamentalsResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    market_cap: Optional[float] = None
    eps: Optional[float] = None
    pe_ratio: Optional[float] = None
    error: Optional[str] = None
