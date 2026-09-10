# -*- coding: utf-8 -*-
"""
جلب آخر أخبار البورصة المصرية من مباشر.

ملحوظة مهمة: الـ RSS الرسمي لمباشر (feeds.mubasher.info/ar/EGX/news) متوقف
عن التحديث فعليًا منذ يناير 2021 - تم التأكد من ذلك بالفحص المباشر. لذلك
المصدر الأساسي هنا هو صفحة "آخر الأخبار" الفعلية على الموقع
(mubasher.info/news/eg/now/latest)، وهي مُحدَّثة لحظيًا وتُعرض بالكامل من
السيرفر (وليست معتمدة على جافاسكريبت زي صفحة أسعار الأسهم الشاملة).
الـ RSS القديم لسه موجود كخيار احتياطي (fallback) فقط.
"""

import re
import logging

import requests
from bs4 import BeautifulSoup

from app.config import MUBASHER_NEWS_RSS_URL, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("news_client")

MUBASHER_LATEST_NEWS_URL = "https://www.mubasher.info/news/eg/now/latest"

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

SESSION = requests.Session()
SESSION.headers.update(REQUEST_HEADERS)

# نمط رابط الخبر على مباشر: /news/<رقم>/<عنوان-مختصر>/
_ARTICLE_LINK_RE = re.compile(r"/news/\d+/")
# نصوص الوقت النسبي أو المطلق اللي بتظهر بجانب كل خبر
_TIME_TEXT_RE = re.compile(
    r"^(\d+\s+(?:ثانية|ثوانٍ|دقيقة|دقائق|ساعة|ساعات)\s+مضت|أمس|اليوم|"
    r"\d{1,2}\s+\S+\s+\d{1,2}:\d{2}\s+[صم])$"
)


def _clean_html(raw_html: str) -> str:
    return BeautifulSoup(raw_html or "", "html.parser").get_text(strip=True)


def _absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return "https://www.mubasher.info" + href


@retry_with_backoff(
    max_attempts=3, base_delay=1.0,
    exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
)
def _fetch_page(url: str):
    resp = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp


def get_news_live(limit: int = 20) -> list:
    """
    يجيب آخر الأخبار من صفحة "آخر الأخبار" الفعلية (محدّثة لحظيًا).
    هذا هو المصدر الافتراضي لأن الـ RSS الرسمي متجمد.
    """
    try:
        resp = _fetch_page(MUBASHER_LATEST_NEWS_URL)
    except requests.RequestException as e:
        log.warning("فشل تحميل صفحة آخر الأخبار بعد إعادة المحاولة: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _ARTICLE_LINK_RE.search(href):
            continue

        title = a.get_text(strip=True)
        # روابط الصور بتكون فاضية من النص (بس <img> جواها) - نتجاهلها ونستنى
        # رابط العنوان الحقيقي اللي معاه نص
        if not title or len(title) < 8:
            continue

        abs_href = _absolute_url(href)
        if abs_href in seen_links:
            continue
        seen_links.add(abs_href)

        # نلاقي أقرب نص وقت (نسبي زي "14 دقائق مضت" أو تاريخ كامل) قبل الرابط.
        # بنستخدم دالة بدل الريجيكس المباشر عشان نتعامل مع مسافات/أسطر زيادة
        # حوالين النص، لأن ^...$ بيفشل لو فيه فراغ أو سطر جديد في البداية/النهاية.
        published = None
        time_node = a.find_previous(string=lambda t: bool(t and _TIME_TEXT_RE.match(t.strip())))
        if time_node:
            published = time_node.strip()

        # أقرب فقرة نصية بعد رابط العنوان تعتبر ملخص الخبر
        summary = None
        desc_tag = a.find_next("p")
        if desc_tag:
            summary_text = desc_tag.get_text(strip=True)
            if summary_text:
                summary = summary_text

        items.append({
            "title": title,
            "link": abs_href,
            "published": published,
            "summary": summary,
        })

        if len(items) >= limit:
            break

    return items


def get_news_rss_fallback(limit: int = 20) -> list:
    """
    مصدر احتياطي فقط عبر RSS - تحذير: هذا الـ feed غير محدّث (آخر تحديث
    معروف: يناير 2021). لا يُستخدم افتراضيًا، فقط كخطة بديلة لو صفحة
    الأخبار الحية فشلت لأي سبب.
    """
    if HAS_FEEDPARSER:
        feed = feedparser.parse(MUBASHER_NEWS_RSS_URL)
        return [
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published", entry.get("updated")),
                "summary": _clean_html(entry.get("summary", "")),
            }
            for entry in feed.entries[:limit]
        ]

    import xml.etree.ElementTree as ET

    try:
        resp = SESSION.get(MUBASHER_NEWS_RSS_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("فشل تحميل RSS: %s", e)
        return []

    root = ET.fromstring(resp.content)
    items = []
    for item in root.findall(".//item")[:limit]:
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "summary": _clean_html(item.findtext("description") or ""),
        })
    return items


def get_news(limit: int = 20) -> list:
    """
    نقطة الدخول المستخدمة في باقي المشروع. تجرب المصدر الحي أولًا، ولو رجع
    فاضي (فشل الاتصال مثلًا) ترجع لآخر حل احتياطي عبر الـ RSS القديم مع
    تحذير في اللوج.
    """
    items = get_news_live(limit=limit)
    if items:
        return items

    log.warning("تعذر جلب الأخبار من المصدر الحي - جاري المحاولة عبر RSS الاحتياطي (قد يكون قديمًا)")
    return get_news_rss_fallback(limit=limit)
