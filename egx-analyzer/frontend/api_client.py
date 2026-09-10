# -*- coding: utf-8 -*-
"""دالة مشتركة للتواصل مع الـ API، تستخدمها كل صفحات التطبيق."""

import requests

API_BASE = "http://127.0.0.1:8000"


def api_get(path: str, params: dict = None):
    """
    يرجع (data, error). لو نجح الطلب: (json, None). لو فشل: (None, "رسالة خطأ بالعربي").
    """
    try:
        resp = requests.get(f"{API_BASE}{path}", params=params or {}, timeout=60)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "تعذر الاتصال بالـ API. تأكد إنه شغال على http://127.0.0.1:8000 (uvicorn app.api.main:app --reload)"
    except requests.exceptions.Timeout:
        return None, "استغرق الطلب وقتًا طويلًا جدًا (timeout). جرب تقليل عدد الأسهم أو المحاولة مرة أخرى."
    except requests.exceptions.HTTPError as e:
        detail = None
        try:
            detail = e.response.json().get("detail")
        except Exception:
            pass
        return None, detail or f"خطأ من السيرفر: {e}"
    except Exception as e:
        return None, f"خطأ غير متوقع: {e}"


def api_post(path: str, json_body: dict = None):
    """
    نفس فكرة api_get بس لطلبات POST (الأفعال اللي بتغيّر حاجة - زي حفظ
    توصية أو تحديث حالتها). يرجع (data, error) بنفس الشكل.
    """
    try:
        resp = requests.post(f"{API_BASE}{path}", json=json_body or {}, timeout=60)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "تعذر الاتصال بالـ API. تأكد إنه شغال على http://127.0.0.1:8000 (uvicorn app.api.main:app --reload)"
    except requests.exceptions.Timeout:
        return None, "استغرق الطلب وقتًا طويلًا جدًا (timeout)."
    except requests.exceptions.HTTPError as e:
        detail = None
        try:
            detail = e.response.json().get("detail")
        except Exception:
            pass
        return None, detail or f"خطأ من السيرفر: {e}"
    except Exception as e:
        return None, f"خطأ غير متوقع: {e}"


def inject_rtl_style(st):
    """
    ثيم احترافي موحّد للتطبيق كله - يُستدعى في بداية كل صفحة. بيشمل:
    دعم RTL، لوحة ألوان داكنة زي منصات التداول الاحترافية، بطاقات (cards)،
    وبادجات ملوّنة للتوصيات (buy/sell/hold).
    """
    st.markdown("""
    <style>
        :root {
            --egx-green: #2ecc71;
            --egx-green-dark: #27ae60;
            --egx-red: #e74c3c;
            --egx-red-dark: #c0392b;
            --egx-yellow: #f1c40f;
            --egx-muted: #9ca3af;
            --egx-card-bg: #1a1d24;
            --egx-card-border: #2d3139;
        }

        .stApp { direction: rtl; text-align: right; }

        div[data-testid="stMetricValue"] {
            direction: ltr; text-align: center; font-weight: 700; font-size: 1.4rem;
        }
        div[data-testid="stMetricLabel"] { justify-content: center; color: var(--egx-muted); }
        div[data-testid="stMetricDelta"] { justify-content: center; }

        /* بطاقة عامة لتجميع محتوى مرتبط - استخدمها بلف أي قسم بـ <div class="egx-card"> */
        .egx-card {
            background-color: var(--egx-card-bg);
            border: 1px solid var(--egx-card-border);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }

        /* بادجات التوصية - ألوان واضحة ومتسقة في كل الصفحات */
        .egx-badge {
            display: inline-block;
            padding: 6px 18px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 1rem;
            direction: rtl;
        }
        .egx-badge-strong-buy { background-color: rgba(46, 204, 113, 0.18); color: var(--egx-green-dark); border: 1.5px solid var(--egx-green-dark); }
        .egx-badge-buy        { background-color: rgba(46, 204, 113, 0.12); color: var(--egx-green); border: 1.5px solid var(--egx-green); }
        .egx-badge-hold       { background-color: rgba(241, 196, 15, 0.15); color: var(--egx-yellow); border: 1.5px solid var(--egx-yellow); }
        .egx-badge-sell       { background-color: rgba(231, 76, 60, 0.12); color: var(--egx-red); border: 1.5px solid var(--egx-red); }
        .egx-badge-strong-sell{ background-color: rgba(231, 76, 60, 0.18); color: var(--egx-red-dark); border: 1.5px solid var(--egx-red-dark); }
        .egx-badge-neutral    { background-color: rgba(156, 163, 175, 0.15); color: var(--egx-muted); border: 1.5px solid var(--egx-muted); }
    </style>
    """, unsafe_allow_html=True)


def recommendation_badge_kind(recommendation: str) -> str:
    """يحدد نوع البادج المناسب من نص التوصية (يدعم العربي والإنجليزي المختلط)."""
    if not recommendation:
        return "neutral"
    text = recommendation
    is_buy = "شراء" in text or "Buy" in text
    is_sell = "بيع" in text or "Sell" in text
    is_strong = "قوي" in text or "Strong" in text
    if is_buy:
        return "strong-buy" if is_strong else "buy"
    if is_sell:
        return "strong-sell" if is_strong else "sell"
    return "hold"


def render_badge(text: str, kind: str = None) -> str:
    """يرجع HTML للبادج - استخدمه مع st.markdown(..., unsafe_allow_html=True)."""
    kind = kind or "neutral"
    return f'<span class="egx-badge egx-badge-{kind}">{text}</span>'


def render_recommendation_badge(recommendation: str) -> str:
    """اختصار: بادج جاهز مباشرة من نص التوصية نفسه."""
    return render_badge(recommendation, recommendation_badge_kind(recommendation))


DEFAULT_SYMBOLS = ["COMI", "ETEL", "HRHO", "TMGH", "SWDY", "EAST", "ABUK", "AMOC", "ORAS"]
