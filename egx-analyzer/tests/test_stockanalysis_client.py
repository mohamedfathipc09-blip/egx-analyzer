# -*- coding: utf-8 -*-
"""اختبارات وحدة لجلب القائمة الكاملة لأسهم البورصة المصرية (app/data/stockanalysis_client.py)."""

from unittest.mock import patch, MagicMock

from app.data.stockanalysis_client import fetch_full_symbol_list_live, get_full_symbol_list


_FAKE_HTML = """
<table>
<tr><th>No.</th><th>Symbol</th><th>Company Name</th><th>Market Cap</th></tr>
<tr><td>1</td><td><a href="/quote/egx/COMI/">COMI</a></td><td>Commercial International Bank Egypt (CIB) S.A.E.</td><td>480.12B</td></tr>
<tr><td>2</td><td><a href="/quote/egx/SWDY/">SWDY</a></td><td>El Sewedy Electric Company</td><td>278.12B</td></tr>
<tr><td>3</td><td><a href="/quote/egx/TMGH/">TMGH</a></td><td>Talaat Moustafa Group Holding</td><td>201.53B</td></tr>
</table>
"""


def test_fetch_full_symbol_list_live_parses_real_page_structure():
    resp = MagicMock()
    resp.text = _FAKE_HTML
    with patch("app.data.stockanalysis_client._fetch_page", return_value=resp):
        symbols = fetch_full_symbol_list_live()
    assert len(symbols) == 3
    assert symbols[0]["symbol"] == "COMI"
    assert "Commercial International Bank" in symbols[0]["name_en"]


def test_fetch_full_symbol_list_live_deduplicates():
    html_with_dupe = _FAKE_HTML + '<a href="/quote/egx/COMI/">COMI dup link</a>'
    resp = MagicMock()
    resp.text = html_with_dupe
    with patch("app.data.stockanalysis_client._fetch_page", return_value=resp):
        symbols = fetch_full_symbol_list_live()
    codes = [s["symbol"] for s in symbols]
    assert codes.count("COMI") == 1


def test_get_full_symbol_list_falls_back_to_curated_on_failure():
    with patch("app.data.stockanalysis_client.fetch_full_symbol_list_live") as m_live, \
         patch("app.data.stockanalysis_client.Path") as m_path:
        m_path.return_value.exists.return_value = False
        m_live.side_effect = Exception("فشل اتصال")
        result = get_full_symbol_list()
    assert result["source"] == "fallback_curated_list"
    assert result["count"] > 0
    assert "error" in result


def test_get_full_symbol_list_returns_live_data_on_success():
    with patch("app.data.stockanalysis_client.fetch_full_symbol_list_live") as m_live, \
         patch("app.data.stockanalysis_client.Path") as m_path, \
         patch("builtins.open", MagicMock()):
        m_path.return_value.exists.return_value = False
        m_live.return_value = [{"symbol": "COMI", "name_en": "CIB"}]
        result = get_full_symbol_list()
    assert result["source"] == "live"
    assert result["count"] == 1


def test_get_full_symbol_list_raises_no_exception_on_empty_live_result():
    """لو الصفحة استجابت لكن مفيش رموز اتستخرجت (تغيّر تصميم مثلًا)، لازم يرجع fallback مش يكسر."""
    with patch("app.data.stockanalysis_client.fetch_full_symbol_list_live") as m_live, \
         patch("app.data.stockanalysis_client.Path") as m_path:
        m_path.return_value.exists.return_value = False
        m_live.return_value = []
        result = get_full_symbol_list()
    assert result["source"] == "fallback_curated_list"
