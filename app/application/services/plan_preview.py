"""Safe plan preview for mobile paywall — never serializes the paid itinerary."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.domain.models.plan import ItemType, PlanResponse


_MAX_HIGHLIGHTS = 3


class PlanDayTeaser(BaseModel):
    """One day of the trip without items, times, or coordinates."""

    day: int
    date: Optional[str] = None
    weekday: Optional[str] = None
    title: Optional[str] = None
    attraction_count: int = 0


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
    attraction_count_total: int = 0


def _is_attraction(item: Any) -> bool:
    t = getattr(item, "type", None)
    value = getattr(t, "value", t)
    return value == ItemType.ATTRACTION.value or value == "attraction"


def build_safe_plan_preview(plan: PlanResponse) -> PlanSafePreviewResponse:
    """Strip a stored PlanResponse down to paywall-safe fields."""
    highlights: List[str] = []
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
        attraction_count_total=total,
    )
