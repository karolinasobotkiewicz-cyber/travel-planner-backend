"""FIX #220 — ORS routing, Overpass supplement, dedup, matrix optimizer."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.routing.dedup import filter_external_duplicates, is_duplicate_of_excel
from app.infrastructure.routing.haversine import haversine_route, resolve_profile
from app.infrastructure.routing.models import RouteResult
from app.infrastructure.routing.day_optimizer import optimize_day_attraction_order
from app.infrastructure.routing.provider import clear_route_session, get_travel_route
from app.infrastructure.routing.poi_supplement import should_supplement


def test_haversine_route_returns_geometry():
    a = {"lat": 51.107, "lng": 17.038, "name": "A"}
    b = {"lat": 51.110, "lng": 17.045, "name": "B"}
    r = haversine_route(a, b, {"has_car": True, "signals": {"cluster_type": "standalone_city"}})
    assert r.duration_min >= 5
    assert r.distance_km > 0
    assert len(r.geometry) >= 2
    assert r.source == "haversine"


def test_resolve_profile_walk_for_close_points():
    a = {"lat": 51.107, "lng": 17.038}
    b = {"lat": 51.108, "lng": 17.039}
    ctx = {"has_car": True, "requested_city": "Wrocław", "region_type": "city"}
    assert resolve_profile(a, b, ctx) == "foot-walking"


def test_dedup_excel_wins():
    excel = {"name": "Muzeum Narodowe", "lat": 52.23, "lng": 21.02}
    ext = {"name": "National Museum", "lat": 52.2301, "lng": 21.0201}
    assert is_duplicate_of_excel(ext, excel)
    kept = filter_external_duplicates([ext], [excel])
    assert kept == []


def test_should_supplement_sparse_day():
    assert should_supplement(0, 0, day_num=7, num_days=7) is False
    with patch("app.infrastructure.routing.poi_supplement.settings") as mock_s:
        mock_s.ors_poi_supplement_enabled = True
        mock_s.ors_enabled = True
        assert should_supplement(0, 0, day_num=7, num_days=7) is True
        assert should_supplement(4, 30, day_num=3, num_days=5) is False


def test_get_travel_route_uses_haversine_when_ors_off():
    clear_route_session()
    a = {"lat": 50.06, "lng": 19.94, "name": "Rynek"}
    b = {"lat": 50.07, "lng": 19.95, "name": "Wawel"}
    with patch("app.infrastructure.routing.provider.settings") as mock_s:
        mock_s.ors_enabled = False
        mock_s.ors_routing_enabled = True
        mock_s.ors_api_key = ""
        mock_s.ors_cache_ttl_days = 60
        r = get_travel_route(a, b, {"has_car": True})
    assert r.duration_min > 0
    assert r.source == "haversine"


def test_get_travel_route_ors_mock():
    clear_route_session()
    a = {"lat": 51.107, "lng": 17.038}
    b = {"lat": 51.120, "lng": 17.060}
    mock_ors = MagicMock()
    mock_ors.enabled.return_value = True
    mock_ors.directions.return_value = {
        "duration_min": 18,
        "distance_km": 2.5,
        "geometry": [[17.038, 51.107], [17.060, 51.120]],
        "profile": "driving-car",
    }
    with patch("app.infrastructure.routing.provider.settings") as mock_s, \
         patch("app.infrastructure.routing.provider.get_ors_client", return_value=mock_ors):
        mock_s.ors_enabled = True
        mock_s.ors_routing_enabled = True
        mock_s.ors_api_key = "test-key"
        mock_s.ors_cache_ttl_days = 60
        r = get_travel_route(a, b, {"has_car": True})
    assert r.source == "ors"
    assert r.duration_min == 18
    assert len(r.geometry_latlng()) == 2


def test_day_optimizer_reorders():
    day = [
        {"type": "attraction", "poi": {"name": "A", "lat": 51.10, "lng": 17.03}},
        {"type": "lunch_break", "start_time": "12:00"},
        {"type": "attraction", "poi": {"name": "B", "lat": 51.12, "lng": 17.06}},
        {"type": "attraction", "poi": {"name": "C", "lat": 51.11, "lng": 17.04}},
    ]
    with patch("app.infrastructure.routing.day_optimizer.settings") as mock_s:
        mock_s.ors_matrix_enabled = True
        mock_s.ors_matrix_max_locations = 8
        out = optimize_day_attraction_order(day, {})
    names = [x["poi"]["name"] for x in out if x.get("type") == "attraction"]
    assert set(names) == {"A", "B", "C"}
    assert len(names) == 3


def test_transit_extras_for_leaflet():
    r = RouteResult(12, 1.5, "foot-walking", "ors", [[17.0, 51.0], [17.1, 51.1]])
    ex = r.to_transit_extras()
    assert ex["geometry_latlng"] == [[51.0, 17.0], [51.1, 17.1]]
    assert ex["routing_source"] == "ors"
