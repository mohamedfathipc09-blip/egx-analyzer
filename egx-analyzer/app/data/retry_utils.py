# -*- coding: utf-8 -*-
"""
decorator موحّد لإعادة محاولة استدعاءات الشبكة تلقائيًا عند فشل مؤقت
(انقطاع اتصال، مهلة انتهت)، بتأخير متزايد (exponential backoff) بين كل
محاولة والتانية - بدل ما نفشل فورًا من أول خطأ عابر.

ملحوظة مهمة: بيعيد المحاولة بس على الأخطاء "المؤقتة" (انقطاع/مهلة)، مش
على أخطاء زي 404 (رمز غير موجود) اللي إعادة المحاولة فيها مضيعة وقت -
المشكلة مش هتتحل بإعادة الطلب.
"""

import time
import logging
import functools

log = logging.getLogger("retry_utils")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    مثال: @retry_with_backoff(max_attempts=3, exceptions=(requests.exceptions.ConnectionError,))
    لو الدالة فشلت بنفس نوع الاستثناء المحدد، بتتعاد المحاولة حتى
    max_attempts مرة، بتأخير بيتضاعف كل مرة (1s, 2s, 4s...). لو فشلت كل
    المحاولات، بيرمي آخر استثناء زي ما هو (مفيش إخفاء للخطأ الحقيقي).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt >= max_attempts:
                        break
                    log.warning(
                        "محاولة %d/%d فشلت لـ %s: %s - إعادة المحاولة بعد %.1f ثانية",
                        attempt, max_attempts, func.__name__, e, delay,
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
            raise last_exception
        return wrapper
    return decorator
