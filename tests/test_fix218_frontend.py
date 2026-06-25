"""FIX #218 — images, replace, restaurant suggestions."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.application.services.edit_helpers import (
    load_pois_for_plan,
    poi_id_of,
    find_poi_by_id,
)
from app.application.services.plan_editor import PlanEditor
from app.application.services.plan_service import (
    _restaurant_dict_to_suggestion,
    _parse_meal_suggestions,
)
from app.domain.models.plan import (
    PlanResponse,
    DayPlan,
    AttractionItem,
    DayStartItem,
    DayEndItem,
    ItemType,
    TicketInfo,
    ParkingInfo,
    ParkingType,
)
from app.infrastructure.storage import build_poi_image_url, build_restaurant_image_url


def test_image_key_loaded_from_excel():
    path = os.path.join("data", "multi_city_attractions.xlsx")
    pois = load_multi_city_poi(path, ["Poznań"])
    with_key = [p for p in pois if p.get("image_key")]
    assert len(with_key) > 0, "Expected image_key from Excel for Poznań POIs"
    assert with_key[0]["image_key"]


def test_image_url_builder():
    url = build_poi_image_url("poi_morskie_oko")
    assert url is None or url.endswith("poi_morskie_oko.webp")
    rurl = build_restaurant_image_url("restaurant_testowe")
    assert rurl is None or "restaurant_testowe" in rurl


def test_replace_swaps_poi():
    path = os.path.join("data", "multi_city_attractions.xlsx")
    pois = load_multi_city_poi(path, ["Kraków"])
    assert len(pois) > 5
    first = pois[0]
    second = pois[1]
    pid1 = poi_id_of(first)
    pid2 = poi_id_of(second)

    attraction = AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id=pid1,
        name=first.get("name", ""),
        start_time="10:00",
        end_time="11:00",
        duration_min=60,
        description_short=first.get("description_short", "test"),
        lat=float(first.get("lat") or 0),
        lng=float(first.get("lng") or 0),
        address=first.get("address", ""),
        city="Kraków",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="Parking", walk_time_min=5, parking_type=ParkingType.FREE),
    )
    day = DayPlan(
        day=1,
        items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            attraction,
            DayEndItem(type=ItemType.DAY_END, time="19:00"),
        ],
    )
    plan = PlanResponse(plan_id="test-plan", days=[day])
    pool = load_pois_for_plan(plan, "data/zakopane.xlsx")
    assert find_poi_by_id(pid1, pool), "Target POI should be in edit pool"

    editor = PlanEditor(poi_repository=None)
    updated, changed = editor.replace_item(
        day_plan=day,
        item_id=pid1,
        all_pois=pool,
        context={"season": "summer", "transport": "car", "has_car": True},
        user={"group_type": "couples", "preferences": [], "target_group": "couples"},
    )
    assert changed, "Replace should succeed for Kraków plan"
    new_attr = next(i for i in updated.items if i.type == ItemType.ATTRACTION)
    assert new_attr.poi_id != pid1
    assert new_attr.poi_id == pid2 or new_attr.poi_id != pid1


def test_restaurant_suggestions_full_objects():
    raw = {
        "id": "abc-123",
        "name": "Test Restauracja",
        "address": "ul. Test 1",
        "lat": 50.0,
        "lng": 19.0,
        "cuisine_type": "polish",
        "meal_type": "lunch",
        "image_key": "restaurant_testowe",
        "price_level": 2,
        "avg_meal_cost": 45,
        "city": "Kraków",
    }
    sugg = _restaurant_dict_to_suggestion(raw, "lunch")
    assert sugg.id == "abc-123"
    assert sugg.name == "Test Restauracja"
    assert sugg.lat == 50.0
    assert sugg.image_key == "restaurant_testowe"

    parsed = _parse_meal_suggestions([raw], "lunch")
    assert len(parsed) == 1
    assert parsed[0].id == "abc-123"
