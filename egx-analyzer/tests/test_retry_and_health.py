# -*- coding: utf-8 -*-
"""اختبارات وحدة لـ retry_with_backoff (app/data/retry_utils.py) وفحص الصحة (app/data/health.py)."""

import time
import pytest
from unittest.mock import patch

from app.data.retry_utils import retry_with_backoff
from app.data.health import check_all_sources


# ------------------------------------------------------------------ retry_with_backoff

def test_succeeds_immediately_without_retry():
    calls = []

    @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
    def fn():
        calls.append(1)
        return "ok"

    assert fn() == "ok"
    assert len(calls) == 1


def test_retries_until_success():
    calls = []

    @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("فشل مؤقت")
        return "نجح أخيرًا"

    assert fn() == "نجح أخيرًا"
    assert len(calls) == 3


def test_raises_last_exception_after_max_attempts():
    calls = []

    @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
    def fn():
        calls.append(1)
        raise ValueError(f"فشل رقم {len(calls)}")

    with pytest.raises(ValueError, match="فشل رقم 3"):
        fn()
    assert len(calls) == 3


def test_does_not_retry_on_non_matching_exception():
    calls = []

    @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
    def fn():
        calls.append(1)
        raise TypeError("نوع مختلف")

    with pytest.raises(TypeError):
        fn()
    assert len(calls) == 1  # مفيش إعادة محاولة لأن النوع مش في القايمة


def test_delay_grows_exponentially():
    observed_delays = []

    @retry_with_backoff(max_attempts=4, base_delay=1.0, backoff_factor=2.0, exceptions=(ValueError,))
    def fn():
        raise ValueError("x")

    with patch("app.data.retry_utils.time.sleep", side_effect=observed_delays.append):
        with pytest.raises(ValueError):
            fn()

    assert observed_delays == [1.0, 2.0, 4.0]


# ------------------------------------------------------------------ health check

def test_health_all_sources_ok():
    with patch("app.data.health.get_stock_data") as m1, \
         patch("app.data.health.get_news_live") as m2, \
         patch("app.data.health.fetch_history") as m3:
        import pandas as pd
        m1.return_value = {"last_price": 116.29, "error": None}
        m2.return_value = [{"title": "خبر"}]
        m3.return_value = pd.DataFrame({"Close": [1, 2, 3]})

        result = check_all_sources()
        assert result["overall_status"] == "ok"
        assert all(s["status"] == "ok" for s in result["sources"].values())


def test_health_reports_degraded_when_one_source_down():
    with patch("app.data.health.get_stock_data") as m1, \
         patch("app.data.health.get_news_live") as m2, \
         patch("app.data.health.fetch_history") as m3:
        import pandas as pd
        m1.return_value = {"last_price": None, "error": "Connection refused"}
        m2.return_value = [{"title": "خبر"}]
        m3.return_value = pd.DataFrame({"Close": [1, 2, 3]})

        result = check_all_sources()
        assert result["overall_status"] == "degraded"
        assert result["sources"]["mubasher"]["status"] == "down"
        assert result["sources"]["news"]["status"] == "ok"


def test_health_reports_down_when_all_sources_fail():
    with patch("app.data.health.get_stock_data") as m1, \
         patch("app.data.health.get_news_live") as m2, \
         patch("app.data.health.fetch_history") as m3:
        m1.side_effect = Exception("timeout")
        m2.side_effect = Exception("timeout")
        m3.side_effect = Exception("timeout")

        result = check_all_sources()
        assert result["overall_status"] == "down"


def test_health_includes_timestamp():
    with patch("app.data.health.get_stock_data") as m1, \
         patch("app.data.health.get_news_live") as m2, \
         patch("app.data.health.fetch_history") as m3:
        import pandas as pd
        m1.return_value = {"last_price": 1, "error": None}
        m2.return_value = [{"title": "خبر"}]
        m3.return_value = pd.DataFrame({"Close": [1]})
        result = check_all_sources()
        assert "checked_at" in result
