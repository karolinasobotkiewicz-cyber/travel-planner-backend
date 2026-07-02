"""
FIX (01.07.2026) — API / frontend consistency fixes.

Pokrywa zgłoszenia frontowca / klientki:
- image_url: podwójne rozszerzenie (.jpg.webp), NaN.webp, null obrazki
- /content/home: 15 miast + api_city + region_type + image_key bez rozszerzenia
- plan: miasto, start_date, dzień tygodnia, nazwa (zamiast "Unknown")
- PDF: generowanie planu
- kontrola dostępu: paywall (402) + auth dla planów przypisanych do konta
"""
import os
from datetime import date

import pytest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")


# ---------------------------------------------------------------------------
# image_url
# ---------------------------------------------------------------------------
from app.infrastructure.storage import (  # noqa: E402
    build_image_url, build_destination_image_url, normalize_image_key,
)


def test_image_url_no_double_extension():
    url = build_destination_image_url("destination_wroclaw.jpg")
    assert url.endswith("/destinations/destination_wroclaw.webp")
    assert ".jpg.webp" not in url


def test_image_url_plain_key():
    url = build_destination_image_url("destination_wroclaw")
    assert url.endswith("/destinations/destination_wroclaw.webp")


def test_image_url_already_webp():
    url = build_destination_image_url("destination_wroclaw.webp")
    assert url.endswith("/destinations/destination_wroclaw.webp")
    assert ".webp.webp" not in url


def test_image_url_nan_returns_none():
    assert build_destination_image_url("NaN") is None
    assert build_destination_image_url("nan") is None
    assert build_destination_image_url(float("nan")) is None
    assert build_destination_image_url("") is None
    assert build_destination_image_url(None) is None


def test_image_url_png_becomes_webp():
    url = build_image_url("poi", "poi_test.png")
    assert url.endswith("/poi/poi_test.webp")


def test_normalize_image_key():
    assert normalize_image_key("destination_wroclaw.jpg") == "destination_wroclaw"
    assert normalize_image_key("x.webp") == "x"
    assert normalize_image_key("NaN") is None
    assert normalize_image_key(float("nan")) is None


# ---------------------------------------------------------------------------
# destinations / content
# ---------------------------------------------------------------------------
from app.infrastructure.repositories import DestinationsRepository  # noqa: E402
from app.api.routes.content import get_home_content  # noqa: E402

_REQUIRED_CITIES = [
    "Zakopane", "Kraków", "Gdańsk", "Gdynia", "Sopot", "Wrocław", "Karpacz",
    "Jelenia Góra", "Szklarska Poręba", "Polanica-Zdrój", "Kudowa-Zdrój",
    "Kłodzko", "Poznań", "Katowice", "Warszawa",
]


def _repo():
    return DestinationsRepository(os.path.join("data", "destinations.json"))


def test_home_contains_all_required_cities():
    resp = get_home_content(_repo())
    names = [d.name for d in resp.destinations]
    for city in _REQUIRED_CITIES:
        assert city in names, f"Brak miasta: {city}"


def test_home_items_have_api_value_and_region_type():
    resp = get_home_content(_repo())
    for d in resp.destinations:
        assert d.api_city, d.name
        assert d.region_type in ("mountain", "sea", "city", "spa_region", "urban"), d.region_type
        # image_key bez rozszerzenia; image_url .webp bez dublowania
        if d.image_key:
            assert not d.image_key.endswith((".jpg", ".webp", ".png"))
        if d.image_url:
            assert d.image_url.endswith(".webp")
            assert ".jpg.webp" not in d.image_url


# ---------------------------------------------------------------------------
# plan context (miasto, daty, dzień tygodnia, nazwa)
# ---------------------------------------------------------------------------
from app.application.services.plan_service import (  # noqa: E402
    _trip_context_fields, _apply_day_dates,
)
from app.domain.models.trip_input import (  # noqa: E402
    TripInput, LocationInput, GroupInput, TripLengthInput,
    DailyTimeWindow, BudgetInput,
)
from app.domain.models.plan import DayPlan  # noqa: E402


def _trip():
    return TripInput(
        location=LocationInput(city="Wrocław", region_type="city"),
        group=GroupInput(type="couples", size=2),
        trip_length=TripLengthInput(days=3, start_date=date(2026, 7, 6)),
        daily_time_window=DailyTimeWindow(),
        budget=BudgetInput(level=2),
    )


def test_trip_context_fields():
    ctx = _trip_context_fields(_trip())
    assert ctx["city"] == "Wrocław"
    assert ctx["start_date"] == "2026-07-06"
    assert ctx["days_count"] == 3
    assert ctx["group_type"] == "couples"
    assert ctx["title"] == "Wrocław — 3 dni"


def test_apply_day_dates_sets_date_and_weekday():
    days = [DayPlan(day=i, items=[]) for i in (1, 2, 3)]
    _apply_day_dates(days, "2026-07-06")
    assert days[0].date == "2026-07-06" and days[0].weekday == "poniedziałek"
    assert days[1].date == "2026-07-07" and days[1].weekday == "wtorek"
    assert days[2].date == "2026-07-08" and days[2].weekday == "środa"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
from app.infrastructure.pdf import build_plan_pdf  # noqa: E402
from app.domain.models.plan import (  # noqa: E402
    PlanResponse, AttractionItem, LunchBreakItem, DayStartItem, DayEndItem,
    ParkingInfo, TicketInfo,
)


def _sample_plan():
    attr = AttractionItem(
        poi_id="poi_1", name="Ostrów Tumski", start_time="09:00", end_time="10:30",
        duration_min=90, description_short="Najstarsza część", lat=51.1, lng=17.0,
        address="Wrocław", city="Wrocław", cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="P", walk_time_min=2),
    )
    lunch = LunchBreakItem(start_time="12:00", end_time="13:00", duration_min=60, suggestions=[])
    return PlanResponse(
        plan_id="a2f5e80a-9e3c-44fb-b1eb-617f933b148b", version=1,
        city="Wrocław", region_type="city", group_type="couples",
        start_date="2026-07-06", days_count=1, title="Wrocław — 1 dzień",
        paid=False, payment_status="unpaid",
        days=[DayPlan(day=1, date="2026-07-06", weekday="poniedziałek",
                      title="Stare Miasto",
                      items=[DayStartItem(time="09:00"), attr, lunch,
                             DayEndItem(time="18:00")])],
    )


def test_build_plan_pdf_returns_pdf_bytes():
    pdf = build_plan_pdf(_sample_plan())
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


def test_build_plan_pdf_empty_plan():
    plan = PlanResponse(plan_id="00000000-0000-0000-0000-000000000000", version=1, days=[])
    pdf = build_plan_pdf(plan)
    assert pdf[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# access control (paywall + assigned-plan auth)
# ---------------------------------------------------------------------------
import uuid  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from app.api.routes.plan import _owner_matches, _enforce_plan_access  # noqa: E402
from app.api.dependencies import OwnerIdentity  # noqa: E402
from app.infrastructure.config.settings import settings  # noqa: E402


class _FakeRepo:
    def __init__(self, user_id=None, guest_id=None, paid=False):
        self._user_id = user_id
        self._guest_id = guest_id
        self._paid = paid

    def get_owner_ids(self, plan_id):
        return {"user_id": self._user_id, "guest_id": self._guest_id}

    def is_plan_paid(self, plan_id):
        return self._paid


def test_owner_matches_guest():
    owner = OwnerIdentity(guest_id="g1")
    assert _owner_matches(owner, {"user_id": None, "guest_id": "g1"})
    assert not _owner_matches(owner, {"user_id": None, "guest_id": "g2"})


def test_unpaid_plan_blocks_stranger_402():
    repo = _FakeRepo(guest_id="g1", paid=False)
    prev = settings.enforce_plan_payment
    settings.enforce_plan_payment = True
    try:
        with pytest.raises(HTTPException) as exc:
            _enforce_plan_access("pid", repo, owner=None)
        assert exc.value.status_code == 402
    finally:
        settings.enforce_plan_payment = prev


def test_unpaid_plan_allows_owner():
    repo = _FakeRepo(guest_id="g1", paid=False)
    prev = settings.enforce_plan_payment
    settings.enforce_plan_payment = True
    try:
        # owner (guest) — brak wyjątku
        _enforce_plan_access("pid", repo, owner=OwnerIdentity(guest_id="g1"))
    finally:
        settings.enforce_plan_payment = prev


def test_paid_guest_plan_accessible_by_uid():
    repo = _FakeRepo(guest_id="g1", paid=True)
    # opłacony plan gościa — dostępny nawet bez ownera (zachowanie legacy)
    _enforce_plan_access("pid", repo, owner=None)


def test_assigned_plan_requires_auth_when_flag_on():
    uid = uuid.uuid4()
    repo = _FakeRepo(user_id=uid, paid=True)
    prev = settings.enforce_assigned_plan_auth
    settings.enforce_assigned_plan_auth = True
    try:
        with pytest.raises(HTTPException) as exc:
            _enforce_plan_access("pid", repo, owner=None)
        assert exc.value.status_code == 401
    finally:
        settings.enforce_assigned_plan_auth = prev


def test_assigned_plan_auth_enabled_by_default():
    assert settings.enforce_assigned_plan_auth is True
