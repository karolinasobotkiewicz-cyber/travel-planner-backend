"""
Helpers for plan edit endpoints (replace / remove).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from app.domain.config import DestinationClusters
from app.domain.models.plan import PlanResponse, ItemType, AttractionItem
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi


def poi_id_of(poi: Dict[str, Any]) -> str:
    """Normalize POI id from Excel loader variants (id / ID / poi_id)."""
    for key in ("id", "ID", "poi_id"):
        val = poi.get(key)
        if val is not None and str(val).strip() not in ("", "nan"):
            return str(val).strip()
    return ""


def ensure_poi_id_aliases(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure each POI dict has both id and ID keys for legacy callers."""
    for poi in pois:
        pid = poi_id_of(poi)
        if pid:
            poi["id"] = pid
            poi["ID"] = pid
    return pois


def _cities_from_plan(plan: PlanResponse) -> Set[str]:
    cities: Set[str] = set()
    for day in plan.days:
        for item in day.items:
            if getattr(item, "type", None) == ItemType.ATTRACTION:
                city = (getattr(item, "city", None) or "").strip()
                if city:
                    cities.add(city)
    return cities


def load_pois_for_plan(plan: PlanResponse, zakopane_excel_path: str) -> List[Dict[str, Any]]:
    """
    Load POI pool for edit operations based on cities present in the plan.
    Expands destination clusters (Trójmiasto, Kotlina, Karkonosze).
    """
    cities = _cities_from_plan(plan)
    expanded: Set[str] = set(cities)

    for city in list(cities):
        cluster = DestinationClusters.get_cluster(city)
        if cluster:
            expanded.update(cluster.get("cities", []))

    all_pois: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    def _extend(pois: List[Dict[str, Any]]) -> None:
        for poi in pois:
            pid = poi_id_of(poi)
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_pois.append(poi)

    multi_city_path = os.path.join("data", "multi_city_attractions.xlsx")

    if expanded:
        try:
            _extend(load_multi_city_poi(multi_city_path, sorted(expanded)))
        except Exception as e:
            print(f"[EDIT] multi_city load failed: {e}")

        if any(c.lower() == "zakopane" for c in expanded):
            try:
                _extend(load_zakopane_poi(zakopane_excel_path, city_filter="Zakopane"))
            except Exception as e:
                print(f"[EDIT] zakopane load failed: {e}")
    else:
        try:
            _extend(load_zakopane_poi(zakopane_excel_path))
        except Exception as e:
            print(f"[EDIT] zakopane fallback load failed: {e}")

    return ensure_poi_id_aliases(all_pois)


def find_poi_by_id(poi_id: str, all_pois: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for poi in all_pois:
        if poi_id_of(poi) == poi_id:
            return poi
    return None


def attraction_item_to_poi_dict(item: AttractionItem) -> Dict[str, Any]:
    """Build a minimal POI dict from a plan snapshot for similarity scoring."""
    return {
        "id": item.poi_id,
        "ID": item.poi_id,
        "name": item.name,
        "Name": item.name,
        "description_short": item.description_short,
        "Description_short": item.description_short,
        "lat": item.lat,
        "Lng": item.lng,
        "lng": item.lng,
        "Lat": item.lat,
        "address": item.address,
        "Address": item.address,
        "city": item.city,
        "City": item.city,
        "image_key": item.image_key or "",
        "time_min": item.duration_min,
        "Type of attraction": "",
        "type_of_attraction": "",
        "category": "",
        "Target group": "",
        "target_groups": [],
        "tags": [],
        "Tags": "",
    }


def build_replacement_attraction_dict(
    similar_poi: Dict[str, Any],
    target_item: Dict[str, Any],
) -> Dict[str, Any]:
    """Build attraction item dict for plan_editor from a candidate POI."""
    pid = poi_id_of(similar_poi)
    ticket_normal = similar_poi.get("ticket_normal") or 0
    ticket_reduced = similar_poi.get("ticket_reduced") or 0
    image_key = similar_poi.get("image_key") or None

    return {
        "type": "attraction",
        "poi_id": pid,
        "name": similar_poi.get("name") or similar_poi.get("Name") or "",
        "start_time": target_item.get("start_time"),
        "end_time": target_item.get("end_time"),
        "duration_min": similar_poi.get("time_min") or target_item.get("duration_min", 60),
        "description_short": (
            similar_poi.get("description_short")
            or similar_poi.get("Description_short")
            or ""
        ),
        "lat": similar_poi.get("lat") or similar_poi.get("Lat") or 0.0,
        "lng": similar_poi.get("lng") or similar_poi.get("Lng") or 0.0,
        "address": similar_poi.get("address") or similar_poi.get("Address") or "",
        "city": similar_poi.get("city") or similar_poi.get("City") or "",
        "image_key": image_key,
        "cost_estimate": target_item.get("cost_estimate", 0),
        "ticket_info": target_item.get(
            "ticket_info",
            {
                "ticket_normal": int(ticket_normal or 0),
                "ticket_reduced": int(ticket_reduced or 0),
                "free_entry": bool(similar_poi.get("free_entry", False)),
            },
        ),
        "parking": target_item.get("parking", {}),
        "pro_tip": similar_poi.get("pro_tip") or similar_poi.get("Pro_tip"),
        "why_selected": target_item.get("why_selected", []),
        "quality_badges": target_item.get("quality_badges", []),
    }
