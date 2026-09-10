# -*- coding: utf-8 -*-
"""صفحة التوصيات: تقرير تحليل شامل لسهم واحد (فني + باك-تيستنج + بيانات أساسية)."""

import sys
import os
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, api_post, render_recommendation_badge
from formatters import format_price, format_percent, format_currency, format_ratio, format_large_number

inject_rtl_style(st)

st.title("🎯 التوصيات")

# ====================================================================
# القسم 1: أفضل 5 فرص تلقائيًا - بدون أي تدخل من المستخدم
# ====================================================================
st.markdown("### 🏆 أفضل 5 فرص الآن")
st.caption(
    "رادار تلقائي بيفحص **كل سوق البورصة المصرية** (~229 سهم مُدرج، مش قائمة "
    "محدودة) بالتوازي - بضغطة واحدة، من غير ما تحدد رمز أو إعدادات. بيرجع بس "
    "الفرص اللي عندها خطة تنفيذ صالحة فعلاً (R:R مقبول) ومفيش تضارب إشارات."
)

if st.button("🔍 افحص السوق كله دلوقتي", type="primary", use_container_width=True):
    with st.spinner("جاري تحليل كل سهم في السوق بالتوازي... ممكن ياخد دقيقة لدقيقتين"):
        top_data, top_err = api_get("/opportunities/top", params={"limit": 5})
    if top_err:
        st.error(top_err)
    else:
        st.session_state["top_opportunities"] = top_data

if "top_opportunities" in st.session_state:
    top_data = st.session_state["top_opportunities"]
    st.caption(
        f"تم فحص {top_data['scanned_count']} سهم - "
        f"{top_data['qualifying_count']} فرصة فعلية مستوفية (خطة تنفيذ صالحة + مفيش تضارب)"
        + (f" - تعذر تحليل {top_data['failed_count']} سهم" if top_data.get("failed_count") else "")
    )

    if not top_data["top_opportunities"]:
        st.info("⚪ مفيش فرص فعلية مستوفية الشروط حاليًا في كل الأسهم المفحوصة - ده نتيجة صحيحة، مش خطأ.")
    else:
        for i, opp in enumerate(top_data["top_opportunities"], 1):
            plan = opp["trade_plan"]
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"#### #{i} — {opp['symbol']} ({format_currency(opp['last_close'])})")
                with c2:
                    st.markdown(
                        f'<div style="text-align:left;">{render_recommendation_badge(opp["recommendation"])}</div>',
                        unsafe_allow_html=True,
                    )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Score", f"{opp['score']:+.1f}")
                m2.metric("الدخول", format_currency(plan["entry"]))
                m3.metric("الوقف", format_currency(plan["stop_loss"]))
                m4.metric("R:R", format_ratio(plan["risk_reward_ratio"]))
                st.caption(f"الأهداف: {' / '.join(format_currency(t) for t in plan['targets'])}")

        st.warning(
            "⚠️ الترتيب ده مبني على تحليل فني لحظي - راجع صفحة الباك-تيستنج لأي "
            "سهم قبل اتخاذ قرار فعلي، وهذا ليس نصيحة استثمارية."
        )

st.divider()

# ====================================================================
# القسم 2: تقرير تفصيلي لسهم واحد بالاختيار اليدوي
# ====================================================================
st.markdown("### 📋 تقرير تفصيلي لسهم معيّن")

col1, col2, col3, col4 = st.columns(4)
with col1:
    symbol = st.text_input("رمز السهم", value="COMI").upper()
with col2:
    timeframe = st.selectbox("الإطار الزمني", ["daily", "weekly"])
with col3:
    backtest_period = st.selectbox("فترة اختبار الأداء", ["1y", "2y", "5y"], index=1)
with col4:
    holding_days = st.number_input("مدة الاحتفاظ (أيام)", min_value=1, max_value=60, value=10)

if st.button("📋 إنشاء التقرير", use_container_width=True):
    with st.spinner(f"جاري تحليل {symbol} وبناء التقرير الكامل..."):
        data, err = api_get(f"/report/{symbol}", params={
            "timeframe": timeframe,
            "backtest_period": backtest_period,
            "holding_days": holding_days,
        })
    if err:
        st.error(err)
    else:
        st.session_state["report_data"] = data

if "report_data" in st.session_state:
    data = st.session_state["report_data"]
    analysis = data.get("analysis", {})
    backtest = data.get("backtest", {})
    fundamentals = data.get("fundamentals", {})
    plan = analysis.get("trade_plan", {})

    if analysis.get("error"):
        st.warning(analysis["error"])
    else:
        # ------------------------------------------------ رأس التقرير: السعر + البادج
        header_col1, header_col2 = st.columns([3, 2])
        with header_col1:
            st.markdown(f"## {data['symbol']} — {format_currency(analysis.get('last_close'))}")
        with header_col2:
            st.markdown(
                f'<div style="text-align:left; padding-top:10px;">{render_recommendation_badge(analysis["recommendation"])}</div>',
                unsafe_allow_html=True,
            )

        # ------------------------------------------------ الرسم البياني (زي TradingView: سعر + حجم + RSI)
        chart_data, chart_err = api_get(f"/chart/{symbol}", params={"timeframe": timeframe, "period": backtest_period})
        if chart_err:
            st.caption(f"⚠️ تعذر تحميل الرسم البياني: {chart_err}")
        elif chart_data:
            dark_bg = "#0e1117"
            grid_color = "#2d3139"

            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                row_heights=[0.62, 0.18, 0.20], vertical_spacing=0.02,
            )

            # --- اللوحة 1: الشموع + SMA + بولينجر
            fig.add_trace(go.Candlestick(
                x=chart_data["dates"], open=chart_data["open"], high=chart_data["high"],
                low=chart_data["low"], close=chart_data["close"], name=symbol,
                increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
                increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data["dates"], y=chart_data["sma50"],
                                      name="SMA50", line=dict(color="#42a5f5", width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data["dates"], y=chart_data["sma200"],
                                      name="SMA200", line=dict(color="#ffa726", width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data["dates"], y=chart_data["bollinger_upper"],
                                      name="بولينجر أعلى", line=dict(color="#78909c", width=1, dash="dot"),
                                      showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data["dates"], y=chart_data["bollinger_lower"],
                                      name="بولينجر", line=dict(color="#78909c", width=1, dash="dot"),
                                      fill="tonexty", fillcolor="rgba(120,144,156,0.08)"), row=1, col=1)

            # --- لوحة الدعم/المقاومة وخطة التداول فوق نفس الرسم (زي أدوات TradingView)
            sr = analysis.get("support_resistance", {})
            if sr.get("resistance"):
                fig.add_hline(y=sr["resistance"], line=dict(color="#ef5350", width=1, dash="dash"),
                               annotation_text="مقاومة", annotation_position="right", row=1, col=1)
            if sr.get("support"):
                fig.add_hline(y=sr["support"], line=dict(color="#26a69a", width=1, dash="dash"),
                               annotation_text="دعم", annotation_position="right", row=1, col=1)
            if plan.get("status") == "valid_long_setup":
                fig.add_hline(y=plan["entry"], line=dict(color="#42a5f5", width=1, dash="dot"),
                               annotation_text="دخول", annotation_position="left", row=1, col=1)
                fig.add_hline(y=plan["stop_loss"], line=dict(color="#ef5350", width=1.3),
                               annotation_text="وقف", annotation_position="left", row=1, col=1)
                for i, t in enumerate(plan["targets"], 1):
                    fig.add_hline(y=t, line=dict(color="#26a69a", width=1, dash="dot"),
                                   annotation_text=f"هدف {i}", annotation_position="left", row=1, col=1)

            # --- اللوحة 2: الحجم (أعمدة ملوّنة حسب اتجاه الشمعة)
            volume_colors = [
                "#26a69a" if c >= o else "#ef5350"
                for o, c in zip(chart_data["open"], chart_data["close"])
            ]
            fig.add_trace(go.Bar(x=chart_data["dates"], y=chart_data["volume"], name="الحجم",
                                  marker_color=volume_colors, showlegend=False), row=2, col=1)

            # --- اللوحة 3: RSI مع مناطق التشبع
            fig.add_trace(go.Scatter(x=chart_data["dates"], y=chart_data["rsi"], name="RSI",
                                      line=dict(color="#ab47bc", width=1.3), showlegend=False), row=3, col=1)
            fig.add_hline(y=70, line=dict(color="#ef5350", width=0.8, dash="dot"), row=3, col=1)
            fig.add_hline(y=30, line=dict(color="#26a69a", width=0.8, dash="dot"), row=3, col=1)

            fig.update_layout(
                height=650, margin=dict(l=10, r=60, t=10, b=10),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                            font=dict(color="#d1d4dc")),
                paper_bgcolor=dark_bg, plot_bgcolor=dark_bg,
                font=dict(color="#d1d4dc"),
            )
            for r in (1, 2, 3):
                fig.update_xaxes(gridcolor=grid_color, showgrid=True, row=r, col=1)
                fig.update_yaxes(gridcolor=grid_color, showgrid=True, row=r, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
            fig.update_xaxes(rangeslider_visible=False, row=1, col=1)

            st.plotly_chart(fig, use_container_width=True)

        # ------------------------------------------------ تحذير التضارب (NO TRADE)
        conflict = analysis.get("signal_conflict", {})
        if conflict.get("is_conflicted"):
            st.error(
                f"🚫 **NO TRADE - إشارات متضاربة بشدة**\n\n{conflict['reason']}\n\n"
                "النظام رفض إجبار نفسه على توصية شراء/بيع - المخاطرة أعلى من الظاهر وقت عدم اليقين ده."
            )

        dq = analysis.get("data_quality", {})
        if dq.get("has_critical_issues"):
            st.warning(
                "⚠️ **DATA QUALITY WARNING** - فيه مشكلة في جودة البيانات المصدرية، "
                "فالنظام قيّد قوة أي إشارة لحد ما البيانات تتأكد:\n\n"
                + "\n".join(f"- {w}" for w in dq.get("warnings", []))
            )
        elif dq.get("warnings"):
            with st.expander("ℹ️ ملاحظات على جودة البيانات (غير حرجة)"):
                for w in dq["warnings"]:
                    st.caption(w)

        # ------------------------------------------------ ملخص التوصية
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("الدرجة (Score)", f"{analysis['score']:+.1f}")
        c2.metric("نسبة توافق المؤشرات", format_percent(analysis["agreement_percent"], show_sign=False))
        bt_perf = backtest.get("buy_signals_performance", {}) if not backtest.get("error") else {}
        c3.metric("نسبة نجاح تاريخية فعلية", format_percent(bt_perf.get("win_rate_percent"), show_sign=False))
        c4.metric("عدد الصفقات المُختبرة", bt_perf.get("n_trades") if bt_perf.get("n_trades") is not None else "—")

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=analysis["score"],
            number={"font": {"size": 36}},
            gauge={
                "axis": {"range": [-100, 100], "tickwidth": 1},
                "bar": {"color": "#1f2937", "thickness": 0.25},
                "steps": [
                    {"range": [-100, -50], "color": "#e74c3c"},
                    {"range": [-50, -20], "color": "#f5a397"},
                    {"range": [-20, 20], "color": "#f0e68c"},
                    {"range": [20, 50], "color": "#a3e4a3"},
                    {"range": [50, 100], "color": "#2ecc71"},
                ],
            },
        ))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # ------------------------------------------------ خطة التداول (Risk Engine)
        spec_plan = analysis.get("speculative_trade_plan", {})

        plan_col1, plan_col2 = st.columns(2)

        with plan_col1:
            st.markdown("#### 📋 الخطة القياسية (ATR/دعم/فيبوناتشي)")
            if plan.get("status") == "valid_long_setup":
                st.success(plan["status_label"])
                if plan.get("based_on_fibonacci"):
                    st.caption("📐 مبنية جزئيًا على مستويات فيبوناتشي (دعم/مقاومة)")
                c1, c2 = st.columns(2)
                c1.metric("الدخول", format_currency(plan["entry"]))
                c2.metric("الوقف", format_currency(plan["stop_loss"]))
                c3, c4 = st.columns(2)
                c3.metric("الهدف الأول", format_currency(plan["targets"][0]))
                c4.metric("R:R", format_ratio(plan["risk_reward_ratio"]))
                if len(plan["targets"]) > 1:
                    extra_targets = " / ".join(format_currency(t) for t in plan["targets"][1:])
                    st.caption(f"أهداف إضافية: {extra_targets}")
            elif plan.get("status") == "rejected_low_rr":
                st.warning(plan["status_label"])
            else:
                st.info(plan.get("status_label", "⚪ لا توجد فرصة مناسبة حاليًا"))

        with plan_col2:
            st.markdown(f"#### 🎯 خطة مضاربة قصيرة ({spec_plan.get('target_pct', 5)}% / {spec_plan.get('stop_loss_pct', 1.5)}%)")
            if spec_plan.get("status") == "valid_long_setup":
                st.success(spec_plan["status_label"])
                c1, c2 = st.columns(2)
                c1.metric("الدخول", format_currency(spec_plan["entry"]))
                c2.metric("الوقف", format_currency(spec_plan["stop_loss"]))
                c3, c4 = st.columns(2)
                c3.metric("الهدف", format_currency(spec_plan["targets"][0]))
                c4.metric("R:R", format_ratio(spec_plan["risk_reward_ratio"]))
            elif spec_plan.get("status") == "rejected_low_rr":
                st.warning(spec_plan["status_label"])
            else:
                st.info(spec_plan.get("status_label", "⚪ لا توجد فرصة مناسبة حاليًا"))

            with st.expander("⚙️ خصّص نسب المضاربة"):
                custom_stop = st.number_input("وقف الخسارة %", min_value=0.1, max_value=20.0, value=1.5, step=0.1, key="custom_stop_pct")
                custom_target = st.number_input("الهدف %", min_value=0.1, max_value=50.0, value=5.0, step=0.5, key="custom_target_pct")
                if st.button("طبّق النسب المخصصة", key="apply_custom_spec"):
                    custom_data, custom_err = api_get(f"/analysis/{symbol}", params={
                        "timeframe": timeframe,
                        "speculation_stop_loss_pct": custom_stop,
                        "speculation_target_pct": custom_target,
                    })
                    if custom_err:
                        st.error(custom_err)
                    else:
                        st.session_state["report_data"]["analysis"]["speculative_trade_plan"] = custom_data["speculative_trade_plan"]
                        st.rerun()

        if plan.get("status") == "valid_long_setup":
            if st.button("💾 احفظ التوصية دي للمتابعة", key="save_recommendation"):
                saved, err = api_post("/recommendations", json_body={"symbol": symbol})
                if err:
                    st.error(err)
                else:
                    st.success(f"✅ اتحفظت برقم #{saved['id']} - تقدر تتابع حالتها من صفحة السجل")

        with st.expander("🔍 تأكيد من الإطار الزمني الأكبر (Multi-Timeframe Confirmation)"):
            st.caption(
                "بيحلل نفس السهم على إطار أكبر (أسبوعي افتراضيًا) ويتأكد إن الاتجاه العام مش "
                "معاكس بشدة قبل ما يوافق على إشارة الشراء."
            )
            if st.button("تأكيد الآن", key="mtf_confirm"):
                with st.spinner("جاري تحليل الإطار الأكبر..."):
                    mtf_result, mtf_err = api_get(f"/analysis/{symbol}/multi-timeframe")
                if mtf_err:
                    st.error(mtf_err)
                else:
                    st.write(
                        f"اتجاه الإطار الأكبر ({mtf_result['higher_timeframe']}): "
                        f"**{mtf_result['higher_trend_classification']}** "
                        f"(درجة {mtf_result['higher_trend_score']:+.1f})"
                    )
                    if mtf_result["gate_applied"]:
                        st.warning(f"⚠️ {mtf_result['gate_reason']}")
                        st.markdown(f"**التوصية بعد التأكيد:** {mtf_result['final_recommendation']}")
                    else:
                        st.success("✅ الإطاران متوافقان - لا يوجد تعارض في الاتجاه العام.")

        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 التحليل الفني", "🔬 اختبار الأداء التاريخي", "💼 البيانات الأساسية", "🏆 أفضل استراتيجية"
        ])

        with tab1:
            st.markdown(
                f"🟢 مؤشرات صاعدة: **{analysis['indicators_bullish']}**  |  "
                f"🔴 مؤشرات هابطة: **{analysis['indicators_bearish']}**  |  "
                f"⚪ مؤشرات محايدة: **{analysis['indicators_neutral']}**"
            )
            category_names = {"trend": "الاتجاه", "momentum": "الزخم", "volatility": "التذبذب", "volume": "الحجم"}
            for category, indicators in analysis["categories"].items():
                with st.expander(category_names.get(category, category), expanded=True):
                    for name, info in indicators.items():
                        icon = info.get("status_icon", "⚪")
                        impact = info.get("impact")
                        impact_text = f"  `{impact:+.1f}`" if impact is not None else ""
                        st.markdown(f"{icon} **{name}** — {info['signal']}{impact_text}")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("##### الدعم والمقاومة")
                sr = analysis["support_resistance"]
                st.markdown(f"🔻 الدعم: **{format_currency(sr.get('support'))}**  \n🔺 المقاومة: **{format_currency(sr.get('resistance'))}**")
                st.markdown("##### نقاط بيفوت")
                piv = analysis["pivot_points"]
                st.markdown(
                    f"P: {format_currency(piv.get('pivot'))} | "
                    f"R1: {format_currency(piv.get('resistance_1'))} | "
                    f"S1: {format_currency(piv.get('support_1'))}"
                )
            with col_b:
                st.markdown("##### مستويات فيبوناتشي")
                fib = analysis["fibonacci_levels"]
                st.markdown("  \n".join(f"{k}: **{format_currency(v)}**" for k, v in fib.items()))
                if analysis.get("candlestick_patterns"):
                    st.markdown("##### أنماط الشموع")
                    for p in analysis["candlestick_patterns"]:
                        st.write(f"🕯️ {p}")

        with tab2:
            if backtest.get("error"):
                st.warning(backtest["error"])
            else:
                st.markdown("##### أداء إشارات الشراء تاريخيًا")
                buy_perf = backtest["buy_signals_performance"]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("عدد الصفقات", buy_perf.get("n_trades") or "—")
                c2.metric("نسبة النجاح الفعلية", format_percent(buy_perf.get("win_rate_percent"), show_sign=False))
                c3.metric("متوسط العائد", format_percent(buy_perf.get("avg_return_percent")))
                c4.metric("Profit Factor", buy_perf.get("profit_factor") or "—")

                st.markdown("##### أداء إشارات البيع تاريخيًا")
                sell_perf = backtest["sell_signals_performance"]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("عدد الصفقات", sell_perf.get("n_trades") or "—")
                c2.metric("نسبة النجاح الفعلية", format_percent(sell_perf.get("win_rate_percent"), show_sign=False))
                c3.metric("متوسط العائد", format_percent(sell_perf.get("avg_return_percent")))
                c4.metric("Profit Factor", sell_perf.get("profit_factor") or "—")

                st.markdown("##### مقارنة عامة")
                c1, c2, c3 = st.columns(3)
                c1.metric("عائد الشراء والاحتفاظ", format_percent(backtest.get("buy_and_hold_return_percent")))
                c2.metric("أقصى تراجع", format_percent(backtest.get("max_drawdown_percent_buy_signals")))
                c3.metric("نسبة شارب", backtest.get("sharpe_ratio_buy_signals") if backtest.get("sharpe_ratio_buy_signals") is not None else "—")

                st.caption(backtest["note"])

        with tab3:
            if fundamentals.get("error"):
                st.warning(fundamentals["error"])
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("القيمة السوقية", format_large_number(fundamentals.get("market_cap")))
                c2.metric("ربحية السهم (EPS)", format_currency(fundamentals.get("eps")))
                c3.metric("مضاعف الربحية (P/E)", format_price(fundamentals.get("pe_ratio")))
                st.caption("بيانات أساسية تكميلية - قد لا تكون متاحة لكل الأسهم على مباشر.")

        with tab4:
            st.caption(
                "بيختبر كذا استراتيجية تداول مختلفة فعليًا على تاريخ السهم ده تحديدًا "
                "(باك-تيستنج حقيقي لكل واحدة) ويرشّح الأفضل - مش استراتيجية عامة واحدة للكل."
            )
            if st.button("🔍 اختبر الاستراتيجيات الآن", key="run_strategy_comparison"):
                with st.spinner("جاري اختبار كل استراتيجية على تاريخ السهم..."):
                    strat_data, strat_err = api_get(f"/strategies/best/{symbol}", params={"period": backtest_period})
                if strat_err:
                    st.error(strat_err)
                else:
                    st.session_state["strategy_data"] = strat_data

            if "strategy_data" in st.session_state:
                sd = st.session_state["strategy_data"]
                if sd.get("best_strategy"):
                    best = sd["best_strategy"]
                    st.success(f"🏆 الأفضل: **{best['strategy_label']}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("عدد الصفقات", best["n_trades"])
                    c2.metric("نسبة النجاح", format_percent(best["win_rate_percent"], show_sign=False))
                    c3.metric("Profit Factor", best["profit_factor"] or "—")
                    c4.metric("ثقة العينة", f"{best['sample_confidence']*100:.0f}%")
                else:
                    st.info("⚪ مفيش استراتيجية بعينة كافية للترشيح حاليًا لهذا السهم.")

                if sd["ranked_strategies"]:
                    st.markdown("##### الترتيب الكامل")
                    for r in sd["ranked_strategies"]:
                        st.markdown(
                            f"- **{r['strategy_label']}** — صفقات: {r['n_trades']} | "
                            f"نجاح: {format_percent(r['win_rate_percent'], show_sign=False)} | "
                            f"PF: {r['profit_factor']} | PF معدّل بالثقة: {r['confidence_adjusted_profit_factor']}"
                        )

                if sd["insufficient_sample_strategies"]:
                    with st.expander(f"استراتيجيات بعينة غير كافية ({len(sd['insufficient_sample_strategies'])})"):
                        for r in sd["insufficient_sample_strategies"]:
                            st.caption(f"{r['strategy_label']}: {r['n_trades']} صفقة فقط (أقل من {sd['min_trades_required']})")

                st.caption(sd["note"])

        st.divider()
        st.error(data["disclaimer"])
else:
    st.info("اكتب رمز السهم واضغط 'إنشاء التقرير'.")
