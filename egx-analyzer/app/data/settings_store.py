# -*- coding: utf-8 -*-
"""
تخزين إعدادات المستخدم محليًا في ملف JSON بسيط (مفيش قاعدة بيانات إضافية
مطلوبة). بيشمل إعدادات التنبيهات (معطّلة افتراضيًا) وقائمة المتابعة
الشخصية (Watchlist).
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("settings_store")

DEFAULT_SETTINGS_PATH = str(Path(__file__).resolve().parent.parent.parent / "settings.json")

DEFAULT_SETTINGS = {
    "alerts_enabled": False,  # معطّلة افتراضيًا - لازم تفعيل صريح من المستخدم
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "watchlist": [],
    "min_score_alert": 20.0,
    "min_agreement_alert": 50.0,
}


def get_settings(path: str = DEFAULT_SETTINGS_PATH) -> dict:
    """يرجع الإعدادات الحالية، أو القيم الافتراضية لو الملف مش موجود أو تالف."""
    p = Path(path)
    if not p.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        log.warning("تعذرت قراءة ملف الإعدادات (%s) - استخدام القيم الافتراضية: %s", path, e)
        return dict(DEFAULT_SETTINGS)


def save_settings(new_values: dict, path: str = DEFAULT_SETTINGS_PATH) -> dict:
    """يدمج القيم الجديدة مع الموجودة (مش استبدال كامل) ويحفظ الملف."""
    current = get_settings(path)
    current.update(new_values)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current
