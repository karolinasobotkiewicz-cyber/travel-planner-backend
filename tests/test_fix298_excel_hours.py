"""FIX #298 — Excel hours are loaded for all cities; Palmiarnia closed Monday."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.domain.planner.engine import is_open
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.infrastructure.repositories.load_zakopane import _parse_seasonal_list


EXCEL = Path(__file__).resolve().parents[1] / "data" / "multi_city_attractions.xlsx"


def test_parser_accepts_bare_quoted_date_from_block():
    raw = (
        '  "date_from": "01-01",\n'
        '  "date_to": "12-31",\n'
        '  "mon": "closed",\n'
        '  "tue": "10:00-16:00",\n'
        '  "wed": "10:00-16:00",\n'
        '  "thu": "10:00-16:00",\n'
        '  "fri": "10:00-16:00",\n'
        '  "sat": "10:00-16:00",\n'
        '  "sun": "10:00-16:00"\n'
        "}"
    )
    parsed = _parse_seasonal_list(raw)
    assert parsed
    assert parsed[0]["mon"].lower() == "closed"


def test_parser_accepts_double_quoted_object_string():
    raw = (
        '"{\n'
        "  date_from: 01-01,\n"
        "  date_to: 12-31,\n"
        "  mon:0:00-23:59,\n"
        "  tue:0:00-23:59,\n"
        "  wed:0:00-23:59,\n"
        "  thu:0:00-23:59,\n"
        "  fri:0:00-23:59,\n"
        "  sat:0:00-23:59,\n"
        "  sun:0:00-23:59\n"
        '},"'
    )
    parsed = _parse_seasonal_list(raw)
    assert parsed
    assert "0:00" in parsed[0]["mon"] or "00:00" in parsed[0]["mon"]


def test_poznan_loads_palmiarnia_seasonal_hours():
    pois = load_multi_city_poi(str(EXCEL), ["Poznań"])
    palm = next(p for p in pois if "palmiarnia" in str(p.get("name") or "").lower())
    seasons = palm.get("opening_hours_seasonal") or []
    assert seasons, "Poznań must load opening_hours_seasonal from Excel"
    assert str(seasons[0].get("mon") or "").lower() == "closed"


def test_palmiarnia_closed_on_monday_from_excel():
    pois = load_multi_city_poi(str(EXCEL), ["Poznań"])
    palm = next(p for p in pois if "palmiarnia" in str(p.get("name") or "").lower())
    ctx = {"date": date(2026, 2, 16)}  # Monday
    assert is_open(palm, 16 * 60, 60, season="winter", context=ctx) is False


def test_poznan_zamek_ticket_is_20():
    pois = load_multi_city_poi(str(EXCEL), ["Poznań"])
    zamek = next(
        p for p in pois
        if "zamek kr" in str(p.get("name") or "").lower()
        and "wawel" not in str(p.get("name") or "").lower()
    )
    ticket = zamek.get("ticket_normal") or zamek.get("Ticket_normal")
    assert int(ticket) == 20
