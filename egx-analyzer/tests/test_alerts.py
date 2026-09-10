# -*- coding: utf-8 -*-
"""اختبارات وحدة لنظام التنبيهات: settings_store, telegram, alert engine."""

import os
import tempfile

import pytest
from unittest.mock import patch

from app.data.settings_store import get_settings, save_settings, DEFAULT_SETTINGS
from app.notifications.telegram import send_alert


@pytest.fixture
def temp_settings_path():
    path = tempfile.mktemp(suffix=".json")
    yield path
    if os.path.exists(path):
        os.remove(path)


# ------------------------------------------------------------- settings_store

def test_alerts_disabled_by_default(temp_settings_path):
    settings = get_settings(path=temp_settings_path)
    assert settings["alerts_enabled"] is False


def test_missing_settings_file_returns_defaults(temp_settings_path):
    assert get_settings(path=temp_settings_path) == DEFAULT_SETTINGS


def test_save_settings_merges_not_replaces(temp_settings_path):
    save_settings({"watchlist": ["COMI"]}, path=temp_settings_path)
    updated = save_settings({"alerts_enabled": True}, path=temp_settings_path)
    # لازم watchlist تفضل موجودة رغم إننا بعتنا alerts_enabled بس في الطلب التاني
    assert updated["watchlist"] == ["COMI"]
    assert updated["alerts_enabled"] is True


def test_corrupted_settings_file_falls_back_to_defaults(temp_settings_path):
    with open(temp_settings_path, "w") as f:
        f.write("{not valid json!!")
    settings = get_settings(path=temp_settings_path)
    assert settings == DEFAULT_SETTINGS


# ------------------------------------------------------------- telegram sender

def test_send_alert_refuses_when_disabled():
    with patch("app.notifications.telegram.get_settings") as m:
        m.return_value = {"alerts_enabled": False, "telegram_bot_token": "x", "telegram_chat_id": "y"}
        result = send_alert("test")
        assert result["sent"] is False
        assert "معطّلة" in result["reason"]


def test_send_alert_refuses_without_credentials():
    with patch("app.notifications.telegram.get_settings") as m:
        m.return_value = {"alerts_enabled": True, "telegram_bot_token": "", "telegram_chat_id": ""}
        result = send_alert("test")
        assert result["sent"] is False
        assert "Token" in result["reason"]


def test_send_alert_never_raises_on_network_failure():
    """حتى لو فشل الاتصال بالإنترنت، send_alert لازم يرجع dict مش يرمي استثناء."""
    with patch("app.notifications.telegram.get_settings") as m_settings, \
         patch("app.notifications.telegram.requests.post") as m_post:
        m_settings.return_value = {"alerts_enabled": True, "telegram_bot_token": "x", "telegram_chat_id": "y"}
        import requests
        m_post.side_effect = requests.exceptions.ConnectionError("no internet")
        result = send_alert("test")
        assert result["sent"] is False
        assert result["reason"] is not None


# ------------------------------------------------------------- alert engine

def test_watchlist_check_stops_early_when_disabled():
    from app.alerts.engine import check_watchlist_for_buy_alerts
    with patch("app.alerts.engine.get_settings") as m:
        m.return_value = {"alerts_enabled": False}
        result = check_watchlist_for_buy_alerts()
        assert result["alerts_sent"] == 0
        assert result["checked"] == 0


def test_open_positions_check_stops_early_when_disabled():
    from app.alerts.engine import check_open_positions_for_exit_alerts
    with patch("app.alerts.engine.get_settings") as m:
        m.return_value = {"alerts_enabled": False}
        result = check_open_positions_for_exit_alerts()
        assert result["alerts_sent"] == 0


def test_watchlist_alert_skips_symbol_already_tracked():
    """لو السهم عليه توصية مفتوحة بالفعل، ما يتبعتش تنبيه شراء تاني عليه."""
    from app.alerts.engine import check_watchlist_for_buy_alerts
    with patch("app.alerts.engine.get_settings") as m_settings, \
         patch("app.alerts.engine.list_recommendations") as m_list, \
         patch("app.alerts.engine.analyze_stock") as m_analyze, \
         patch("app.alerts.engine.send_alert") as m_send:
        m_settings.return_value = {"alerts_enabled": True, "watchlist": ["COMI"],
                                    "min_score_alert": 20.0, "min_agreement_alert": 40.0}
        m_list.return_value = [{"id": 1, "symbol": "COMI", "status": "OPEN"}]  # متابَع بالفعل
        result = check_watchlist_for_buy_alerts()
        m_analyze.assert_not_called()  # ما اتعملش تحليل أصلًا - اتجاهل من البداية
        m_send.assert_not_called()
        assert result["alerts_sent"] == 0


def test_watchlist_alert_fires_when_conditions_met():
    from app.alerts.engine import check_watchlist_for_buy_alerts
    with patch("app.alerts.engine.get_settings") as m_settings, \
         patch("app.alerts.engine.list_recommendations", return_value=[]), \
         patch("app.alerts.engine.analyze_stock") as m_analyze, \
         patch("app.alerts.engine.send_alert", return_value={"sent": True, "reason": None}) as m_send:
        m_settings.return_value = {"alerts_enabled": True, "watchlist": ["COMI"],
                                    "min_score_alert": 20.0, "min_agreement_alert": 40.0}
        m_analyze.return_value = {
            "last_close": 105.0, "score": 35.0, "agreement_percent": 70.0,
            "trade_plan": {"status": "valid_long_setup", "entry": 105.0, "stop_loss": 95.0,
                           "targets": [120.0, 130.0], "risk_reward_ratio": 1.6},
        }
        result = check_watchlist_for_buy_alerts()
        assert result["alerts_sent"] == 1
        m_send.assert_called_once()


def test_watchlist_alert_skipped_below_score_threshold():
    """حتى لو trade_plan صالحة، لو الـ Score أقل من الحد الأدنى في الإعدادات - مفيش تنبيه."""
    from app.alerts.engine import check_watchlist_for_buy_alerts
    with patch("app.alerts.engine.get_settings") as m_settings, \
         patch("app.alerts.engine.list_recommendations", return_value=[]), \
         patch("app.alerts.engine.analyze_stock") as m_analyze, \
         patch("app.alerts.engine.send_alert") as m_send:
        m_settings.return_value = {"alerts_enabled": True, "watchlist": ["COMI"],
                                    "min_score_alert": 50.0, "min_agreement_alert": 40.0}
        m_analyze.return_value = {
            "last_close": 105.0, "score": 25.0, "agreement_percent": 70.0,  # score أقل من الحد
            "trade_plan": {"status": "valid_long_setup", "entry": 105.0, "stop_loss": 95.0,
                           "targets": [120.0], "risk_reward_ratio": 1.6},
        }
        result = check_watchlist_for_buy_alerts()
        assert result["alerts_sent"] == 0
        m_send.assert_not_called()
