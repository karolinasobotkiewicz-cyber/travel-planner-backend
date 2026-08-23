"""Safe preview must never serialize the paid itinerary."""
from __future__ import annotations

from app.application.services.plan_preview import (
    PlanSafePreviewResponse,
    build_safe_plan_preview,
)
from app.domain.models.plan import (
    AttractionItem,
    DayPlan,
    ItemType,
    PlanResponse,
    TransitItem,
    TransitMode,
)


def _plan() -> PlanResponse:
    return PlanResponse(
        plan_id="11111111-1111-1111-1111-111111111111",
        version=1,
        city="Warszawa",
        title="Warszawa — 3 dni",
        group_type="couples",
        preferences=["museum_heritage", "relaxation"],
        travel_style="cultural",
        start_date="2026-08-01",
        days_count=3,
        paid=False,
        payment_status="unpaid",
        days=[
            DayPlan(
                day=1,
                date="2026-08-01",
                weekday="sobota",
                title="Stare Miasto",
                items=[
                    AttractionItem.model_construct(
                        type=ItemType.ATTRACTION,
                        poi_id="poi-zamek",
                        name="Zamek Królewski",
                        description_short="Pełny opis którego nie wolno oddać",
                        start_time="10:00",
                        end_time="12:00",
                        duration_min=120,
                        lat=52.2478,
                        lng=21.0145,
                        address="plac Zamkowy 4",
                        city="Warszawa",
                        cost_estimate=40,
                    ),
                    TransitItem(
                        type=ItemType.TRANSIT,
                        start_time="12:00",
                        end_time="12:20",
                        duration_min=20,
                        mode=TransitMode.WALK,
                        from_location="Zamek Królewski",
                        to_location="POLIN",
                        routing_source="estimated_walk",
                        distance_km=1.2,
                    ),
                    AttractionItem.model_construct(
                        type=ItemType.ATTRACTION,
                        poi_id="poi-polin",
                        name="POLIN",
                        description_short="",
                        start_time="12:20",
                        end_time="14:20",
                        duration_min=120,
                        lat=52.249,
                        lng=20.993,
                        address="Anielewicza 6",
                        city="Warszawa",
                        cost_estimate=30,
                    ),
                ],
            ),
            DayPlan(
                day=2,
                date="2026-08-02",
                weekday="niedziela",
                title="Łazienki",
                items=[
                    AttractionItem.model_construct(
                        type=ItemType.ATTRACTION,
                        poi_id="poi-laz",
                        name="Łazienki Królewskie",
                        description_short="",
                        start_time="10:00",
                        end_time="12:00",
                        duration_min=120,
                        lat=52.215,
                        lng=21.035,
                        address="Agrykola",
                        city="Warszawa",
                        cost_estimate=0,
                    ),
                ],
            ),
        ],
    )


def test_preview_has_teaser_not_itinerary():
    preview = build_safe_plan_preview(_plan())
    dump = preview.model_dump()

    assert dump["plan_id"] == "11111111-1111-1111-1111-111111111111"
    assert dump["city"] == "Warszawa"
    assert dump["days_count"] == 3
    assert dump["paid"] is False
    assert dump["full_plan_unlocked"] is False
    assert dump["attraction_count_total"] == 3
    assert dump["highlights"] == [
        "Zamek Królewski",
        "POLIN",
        "Łazienki Królewskie",
    ]
    assert len(dump["days_preview"]) == 2
    assert dump["days_preview"][0]["title"] == "Stare Miasto"
    assert dump["days_preview"][0]["attraction_count"] == 2

    assert "days" not in dump
    blob = str(dump)
    assert "plac Zamkowy" not in blob
    assert "52.2478" not in blob
    assert "poi-zamek" not in blob
    assert "10:00" not in blob
    assert "estimated_walk" not in blob
    assert "Pełny opis" not in blob


def test_preview_caps_highlights_at_three():
    days = []
    for i in range(5):
        days.append(
            DayPlan(
                day=i + 1,
                items=[
                    AttractionItem.model_construct(
                        type=ItemType.ATTRACTION,
                        poi_id=f"p{i}",
                        name=f"POI {i}",
                        description_short="",
                        start_time="10:00",
                        end_time="11:00",
                        duration_min=60,
                        lat=52.2,
                        lng=21.0,
                        address="secret",
                        city="Warszawa",
                        cost_estimate=0,
                    )
                ],
            )
        )
    preview = build_safe_plan_preview(
        PlanResponse(plan_id="p", days=days, paid=True, payment_status="paid")
    )
    assert preview.highlights == ["POI 0", "POI 1", "POI 2"]
    assert preview.full_plan_unlocked is True
    assert preview.attraction_count_total == 5


def test_openapi_exposes_safe_preview_routes():
    from app.api.main import app

    paths = app.openapi()["paths"]
    assert "/plan/safe-preview" in paths
    assert paths["/plan/safe-preview"]["post"]
    assert "/plan/{plan_id}/safe-preview" in paths
    assert paths["/plan/{plan_id}/safe-preview"]["get"]
    get_schema = paths["/plan/{plan_id}"]["get"]
    # Full GET stays the paid itinerary contract.
    assert get_schema["responses"]["200"]


def test_safe_preview_schema_has_no_days_items():
    schema = PlanSafePreviewResponse.model_json_schema()
    props = schema.get("properties") or {}
    assert "days" not in props
    assert "items" not in props
    assert "days_preview" in props
