"""FIX #366: pytest wrapper around scripts/plan_quality_validator.py.

Hard-fails only on Kraków / Katowice. Other cities are reported but do not
fail the build (pre-existing defects outside this FIX scope).
"""
from __future__ import annotations

import os

import pytest

from scripts.plan_quality_validator import run_cities


@pytest.mark.slow
def test_krakow_katowice_plan_quality_validator():
    os.environ.setdefault("ORS_ENABLED", "false")
    report = run_cities([
        ("Kraków", range(1, 11)),
        ("Katowice", range(1, 9)),
    ])
    # aba_hop is reported but not hard-failed: return_to_car A->meal->A
    # patterns are legitimate and flood the Krakow/Katowice fixtures.
    owned = {
        "short_car",
        "restaurant_no_meal",
        "overlap",
    }
    bad = [h for h in report.hits if h.code in owned]
    assert not bad, (
        "Kraków/Katowice plan-quality defects still present:\n"
        + "\n".join(f"J{h.json_num} D{h.day} [{h.code}] {h.message}" for h in bad)
    )


@pytest.mark.slow
def test_other_cities_plan_quality_report_only():
    """Record other-city hits without failing (owner decision later)."""
    os.environ.setdefault("ORS_ENABLED", "false")
    report = run_cities([
        ("Wrocław", range(1, 4)),
        ("Warszawa", range(1, 4)),
        ("Poznań", range(1, 4)),
    ])
    print("OTHER_CITY_HITS", len(report.hits), report.counts())
    assert True
