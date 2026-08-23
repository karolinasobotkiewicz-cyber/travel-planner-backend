"""Safe plan preview for mobile paywall — never serializes the paid itinerary."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.domain.models.plan import ItemType, PlanResponse
from app.infrastructure.storage import build_poi_image_url


_MAX_HIGHLIGHTS = 3
_MAX_PREVIEW_ATTRACTIONS = 2


class PlanDayTeaser(BaseModel):
    """One day of the trip without items, times, or coordinates."""

    day: int
    date: Optional[str] = None
    weekday: Optional[str] = None
    title: Optional[str] = None
    attraction_count: int = 0


class PlanPreviewAttraction(BaseModel):
    """First attractions on the paywall — name + image only."""

    name: str
    image_key: Optional[str] = None
    image_url: Optional[str] = None


class PlanSafePreviewResponse(BaseModel):
    """What the mobile app may download before payment.

    Intentionally has no ``days`` / ``items`` — that is the paid itinerary.
    After payment the app should call ``GET /plan/{plan_id}``.
    """

    plan_id: str
    version: int = 1
    city: Optional[str] = None
    title: Optional[str] = None
    region_type: Optional[str] = None
    group_type: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    travel_style: Optional[str] = None
    start_date: Optional[str] = None
    days_count: Optional[int] = None
    paid: bool = False
    payment_status: str = "unpaid"
    full_plan_unlocked: bool = False
    days_preview: List[PlanDayTeaser] = Field(default_factory=list)
    highlights: List[str] = Field(
        default_factory=list,
        description="Up to 3 attraction names to sell the plan — no times or addresses",
    )
    preview_attractions: List[PlanPreviewAttraction] = Field(
        default_factory=list,
        description="First 2 attractions with images for the mobile paywall",
    )
    attraction_count_total: int = 0


def _is_attraction(item: Any) -> bool:
    t = getattr(item, "type", None)
    value = getattr(t, "value", t)
    return value == ItemType.ATTRACTION.value or value == "attraction"


def _preview_image(item: Any) -> tuple[Optional[str], Optional[str]]:
    """Return (image_key, image_url). Rebuild URL from key when the snapshot omitted it."""
    raw_key = getattr(item, "image_key", None)
    key = str(raw_key).strip() if raw_key else None
    if key and key.lower() in ("nan", "none", "null"):
        key = None
    url = getattr(item, "image_url", None)
    url = str(url).strip() if url else None
    if not url and key:
        try:
            url = build_poi_image_url(key)
        except Exception:
            url = None
    return key, url or None


def build_safe_plan_preview(plan: PlanResponse) -> PlanSafePreviewResponse:
    """Strip a stored PlanResponse down to paywall-safe fields."""
    highlights: List[str] = []
    preview_attractions: List[PlanPreviewAttraction] = []
    days_preview: List[PlanDayTeaser] = []
    total = 0
    for day in plan.days or []:
        n_attr = 0
        for it in day.items or []:
            if not _is_attraction(it):
                continue
            n_attr += 1
            name = (getattr(it, "name", None) or "").strip()
            if name and len(highlights) < _MAX_HIGHLIGHTS:
                highlights.append(name)
            if name and len(preview_attractions) < _MAX_PREVIEW_ATTRACTIONS:
                image_key, image_url = _preview_image(it)
                preview_attractions.append(
                    PlanPreviewAttraction(
                        name=name,
                        image_key=image_key,
                        image_url=image_url,
                    )
                )
        total += n_attr
        days_preview.append(
            PlanDayTeaser(
                day=int(getattr(day, "day", 0) or 0),
                date=getattr(day, "date", None),
                weekday=getattr(day, "weekday", None),
                title=getattr(day, "title", None),
                attraction_count=n_attr,
            )
        )

    paid = bool(getattr(plan, "paid", False))
    payment_status = getattr(plan, "payment_status", None) or (
        "paid" if paid else "unpaid"
    )
    days_count = getattr(plan, "days_count", None)
    if days_count is None:
        days_count = len(plan.days or [])

    return PlanSafePreviewResponse(
        plan_id=plan.plan_id,
        version=int(getattr(plan, "version", 1) or 1),
        city=getattr(plan, "city", None),
        title=getattr(plan, "title", None),
        region_type=getattr(plan, "region_type", None),
        group_type=getattr(plan, "group_type", None),
        preferences=list(getattr(plan, "preferences", None) or []),
        travel_style=getattr(plan, "travel_style", None),
        start_date=getattr(plan, "start_date", None),
        days_count=days_count,
        paid=paid,
        payment_status=payment_status,
        full_plan_unlocked=paid,
        days_preview=days_preview,
        highlights=highlights,
        preview_attractions=preview_attractions,
        attraction_count_total=total,
    )
