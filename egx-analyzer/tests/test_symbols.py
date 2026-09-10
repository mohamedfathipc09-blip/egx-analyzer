# -*- coding: utf-8 -*-
"""اختبارات وحدة لقائمة أسهم EGX المنسّقة (app/data/symbols_repository.py)."""

from app.data.symbols_repository import (
    get_all_symbols, get_symbol_codes, search_symbols,
    get_symbols_by_sector, list_sectors, get_metadata,
)


def test_symbols_list_is_not_empty():
    symbols = get_all_symbols()
    assert len(symbols) > 0


def test_all_symbols_have_required_fields():
    for s in get_all_symbols():
        assert "symbol" in s and s["symbol"]
        assert "name_ar" in s and s["name_ar"]
        assert "sector" in s and s["sector"]


def test_no_duplicate_symbol_codes():
    codes = get_symbol_codes()
    assert len(codes) == len(set(codes)), "يوجد رمز مكرر في القائمة المنسّقة"


def test_search_by_symbol_code():
    results = search_symbols("COMI")
    assert any(s["symbol"] == "COMI" for s in results)


def test_search_by_arabic_name_substring():
    results = search_symbols("بنك")
    assert len(results) > 0
    assert all("بنك" in s["name_ar"] or "بنك" in s["symbol"].lower() for s in results)


def test_search_empty_query_returns_all():
    assert search_symbols("") == get_all_symbols()


def test_search_no_match_returns_empty():
    assert search_symbols("XYZ_NOT_A_REAL_SYMBOL_QUERY") == []


def test_get_symbols_by_sector():
    sectors = list_sectors()
    assert len(sectors) > 0
    first_sector = sectors[0]
    results = get_symbols_by_sector(first_sector)
    assert len(results) > 0
    assert all(s["sector"] == first_sector for s in results)


def test_metadata_includes_accuracy_note():
    meta = get_metadata()
    assert meta["note"] is not None
    assert meta["total_symbols"] == len(get_all_symbols())
