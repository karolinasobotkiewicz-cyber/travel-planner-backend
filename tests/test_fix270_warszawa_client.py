"""FIX #270 — Warszawa remaining client: caps, pro_tip, why_selected, daytrips."""
from __future__ import annotations

from app.domain.planner.engine import (
    is_morning_preferred_poi,
    visit_duration_hard_cap,
)
from app.domain.planner.explainability import _explain_profile_match
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def test_fix270_tepfactor_capped():
    assert visit_duration_hard_cap({"name": "Tepfactor"}, for_scheduling=True) == 120


def test_fix270_czersk_capped():
    assert visit_duration_hard_cap({"name": "Zamek w Czersku"}, for_scheduling=True) == 150


def test_fix270_zamek_is_morning_preferred():
    assert is_morning_preferred_poi({"name": "Zamek Królewski"})


def test_fix270_smart_kids_family_why():
    reason = _explain_profile_match(
        {"name": "Smart Kids Planet", "tags": []},
        {"target_group": "family_kids", "travel_style": "balanced"},
        {},
    )
    assert reason
    assert "rodzin" in reason.lower() or "dzieci" in reason.lower()


def test_fix270_browary_denied_for_family_nature():
    assert should_deny_poi_for_profile(
        {"name": "Browary Warszawskie"},
        {
            "target_group": "family_kids",
            "preferences": ["kids_attractions", "nature_landscape"],
            "travel_style": "balanced",
        },
    )


def test_fix270_nature_relax_museum_cap():
    from types import SimpleNamespace

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType

    svc = PlanService.__new__(PlanService)
    items = [
        SimpleNamespace(type=ItemType.ATTRACTION, name="Muzeum Polskiej Wódki"),
        SimpleNamespace(type=ItemType.ATTRACTION, name="Muzeum Powstania Warszawskiego"),
        SimpleNamespace(type=ItemType.ATTRACTION, name="Muzeum Historii Żydów Polskich POLIN"),
    ]
    out = svc._strip_excessive_museums_same_day(
        items,
        {
            "target_group": "solo",
            "preferences": ["nature_landscape", "relaxation"],
            "travel_style": "relax",
        },
        day_num=3,
    )
    museums = [it.name for it in out if "Muzeum" in (it.name or "")]
    assert len(museums) == 1
