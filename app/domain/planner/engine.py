# type: ignore
import math
import random
from math import radians, sin, cos, sqrt, atan2

from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.opening_hours_parser import is_poi_open_at_time
from app.domain.scoring import (
    calculate_family_score,
    calculate_budget_score,
    calculate_premium_penalty,
    calculate_crowd_score,
    calculate_body_transition_score,
    get_next_body_state,
)
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.intensity_scoring import should_exclude_by_intensity, calculate_intensity_score
from app.domain.scoring.preferences import calculate_preference_score, calculate_priority_bonus
from app.domain.scoring.travel_style import calculate_travel_style_score
from app.domain.scoring.space_scoring import calculate_space_score
from app.domain.scoring.weather_scoring import calculate_weather_dependency_score
from app.domain.scoring.type_matching import calculate_type_matching_score
from app.domain.scoring.time_of_day_scoring import calculate_time_of_day_score
from app.domain.scoring.tag_preferences import calculate_tag_preference_score  # CLIENT DATA UPDATE (05.02.2026)
from app.domain.filters.seasonality import filter_by_season

# =========================
# Helper Functions
# =========================

def calculate_poi_cost_for_group(poi: dict, user: dict) -> float:
    """
    Calculate total POI cost for entire group using consistent logic.
    
    FIX #2 (22.02.2026 - Budget Tracking): Unified cost calculation.
    Used by both engine.py (budget tracking) and plan_service.py (cost_estimate).
    
    Logic (matches plan_service._estimate_cost):
    - free_entry POI: 0 PLN
    - family_kids: (2 adults × ticket_normal) + (children × ticket_reduced)
    - couples: group_size × ticket_normal
    - friends: group_size × ticket_normal
    - seniors: group_size × ticket_reduced (senior discount)
    - solo: ticket_normal (1 person)
    - fallback (no price data): 50 PLN × group_size
    
    Args:
        poi: POI dict with ticket_normal, ticket_reduced, free_entry
        user: User dict with target_group, group_size, children_age
    
    Returns:
        Total cost in PLN for entire group
    """
    free_entry = poi.get("free_entry", False)
    if free_entry:
        return 0.0
    
    # FIX #71 (03.06.2026): Distinguish genuinely-free POI (ticket=0 explicitly set)
    # from POI with no price data (ticket=None/NaN/missing).
    # Old bug: ticket_normal=0, ticket_reduced=0, free_entry=False → 50 PLN/person fallback (WRONG)
    # These are genuinely free POIs (parks, squares, viewpoints) where Excel has 0, not empty.
    import math as _math_engine
    def _parse_ticket_e(val):
        if val is None:
            return None
        try:
            f = float(val)
            return None if _math_engine.isnan(f) else f
        except (TypeError, ValueError):
            return None
    
    t_normal = _parse_ticket_e(poi.get("ticket_normal"))
    t_reduced = _parse_ticket_e(poi.get("ticket_reduced"))
    
    # Explicitly 0 for both → genuinely free
    if t_normal == 0 and t_reduced == 0:
        return 0.0
    
    ticket_normal = t_normal if t_normal is not None else 0.0
    ticket_reduced = t_reduced if t_reduced is not None else 0.0
    
    group_type = user.get("target_group", "solo")
    group_size = user.get("group_size", 1)
    
    # Fallback ONLY for POI where both tickets are truly missing (None/NaN)
    if t_normal is None and t_reduced is None and not free_entry:
        return group_size * 50.0  # 50 PLN per person default
    
    # Group-specific calculation
    if group_type == "family_kids":
        # Assume: 2 adults + (group_size - 2) children
        adults = 2
        children = max(0, group_size - 2)
        return (adults * ticket_normal) + (children * ticket_reduced)
    
    elif group_type == "seniors":
        # All members use reduced ticket
        return group_size * ticket_reduced
    
    elif group_type == "solo":
        return ticket_normal
    
    else:
        # couples, friends: all use normal ticket
        return group_size * ticket_normal


def is_core_poi(poi):
    """
    Check if POI is a core attraction.
    Core POI have priority_level = 12 (highest priority) or "core" (string).
    CLIENT REQUIREMENT (08.02.2026): Used for core POI rotation logic.
    FIX #75: Support string "core" from multi_city_attractions.xlsx loader.
    """
    pl = poi.get("priority_level", 0)
    if isinstance(pl, str):
        return pl.strip().lower() == "core"
    try:
        return int(pl) == 12
    except (ValueError, TypeError):
        return False


def _check_time_overlap(plan, new_start_time, new_end_time):
    """
    Check if new item overlaps with existing items in plan.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2):
    Validate time continuity - no overlapping events.
    
    Args:
        plan: List of plan items (dicts with start_time/end_time)
        new_start_time: Start time string "HH:MM"
        new_end_time: End time string "HH:MM"
    
    Returns:
        tuple: (overlaps: bool, conflicting_item: dict or None)
    """
    new_start_min = time_to_minutes(new_start_time)
    new_end_min = time_to_minutes(new_end_time)
    
    for item in plan:
        # Skip items without time range (e.g., accommodation_start)
        if "start_time" not in item or "end_time" not in item:
            continue
        
        item_start_min = time_to_minutes(item["start_time"])
        item_end_min = time_to_minutes(item["end_time"])
        
        # Check overlap: new starts before existing ends AND new ends after existing starts
        if new_start_min < item_end_min and new_end_min > item_start_min:
            return True, item
    
    return False, None


def _add_buffer_item(plan, now, buffer_type, duration_min, reason_context=None, day_end=None):
    """
    Add a buffer item to explain time gaps in the plan.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4):
    Client requirement: "Oś czasu ma dziury, które nie są opisane"
    Solution: Add explicit buffer items for parking_walk, tickets_queue, restroom, photo_stop
    
    BUGFIX (17.02.2026): Added day_end parameter to prevent buffers from exceeding day_end
    
    Args:
        plan: List of plan items
        now: Current time in minutes from midnight
        buffer_type: Type of buffer ("parking_walk", "tickets_queue", "restroom", "photo_stop", "traffic_margin")
        duration_min: Duration of buffer in minutes
        reason_context: Optional context dict (poi_name, etc.)
        day_end: Optional day_end in minutes - if buffer would exceed, skip or shorten it
    
    Returns:
        Updated time (now + duration_min) or now if buffer skipped
    
    Buffer Types:
    - parking_walk: 5-15 min (walking from parking to attraction entrance)
    - tickets_queue: 5-20 min (waiting in line at popular attractions)
    - restroom: 5-10 min (bathroom break after long attractions)
    - photo_stop: 5-15 min (photo opportunity at scenic locations)
    - traffic_margin: 5-10 min (buffer for unexpected delays)
    """
    if duration_min <= 0:
        return now
    
    # BUGFIX (17.02.2026): Check if buffer would exceed day_end
    if day_end is not None and now + duration_min > day_end:
        # Calculate remaining time
        remaining = day_end - now
        if remaining <= 0:
            # No time left - skip buffer
            print(f"[SKIP BUFFER] {buffer_type} would exceed day_end ({minutes_to_time(now)} + {duration_min}min > {minutes_to_time(day_end)})")
            return now
        elif remaining < duration_min:
            # Shorten buffer to fit remaining time
            print(f"[SHORTEN BUFFER] {buffer_type} shortened from {duration_min} to {remaining}min to fit day_end")
            duration_min = remaining
    
    buffer_start = minutes_to_time(now)
    buffer_end = minutes_to_time(now + duration_min)
    
    # Check overlap before adding
    overlaps, conflict = _check_time_overlap(plan, buffer_start, buffer_end)
    if overlaps:
        print(f"[SKIP BUFFER] {buffer_type} {buffer_start}-{buffer_end} overlaps with {conflict.get('type')}")
        return now  # Don't add buffer if it creates overlap
    
    # Generate description based on buffer type
    descriptions = {
        "parking_walk": f"Przejscie z parkingu ({duration_min} min)",
        "tickets_queue": f"Oczekiwanie w kolejce ({duration_min} min)",
        "restroom": f"Przerwa sanitarna ({duration_min} min)",
        "photo_stop": f"Sesja zdjęciowa ({duration_min} min)",
        "traffic_margin": f"Margines na nieprzewidziane opoznienia ({duration_min} min)",
    }
    
    description = descriptions.get(buffer_type, f"Buffer: {buffer_type} ({duration_min} min)")
    
    # Add context to description if provided
    if reason_context:
        poi_name = reason_context.get("poi_name")
        if poi_name and buffer_type in ["parking_walk", "tickets_queue"]:
            # Remove Polish characters from POI name for Windows terminal compatibility
            poi_name_safe = poi_name.encode('ascii', errors='ignore').decode('ascii')
            description = f"{description} - {poi_name_safe}"
    
    buffer_item = {
        "type": "buffer",
        "buffer_type": buffer_type,
        "start_time": buffer_start,
        "end_time": buffer_end,
        "duration_min": duration_min,
        "description": description,
    }
    
    plan.append(buffer_item)
    print(f"[BUFFER ADDED] {buffer_type} at {buffer_start}-{buffer_end}: {description.encode('ascii', errors='ignore').decode('ascii')}")
    
    return now + duration_min


def _get_free_time_label(plan, now_min, duration_min, day_end_min, profile=None):
    """
    Generate smart, context-aware label for free_time items.
    
    BUGFIX (19.02.2026 - UAT Round 2, Bug #3):
    Client requirement: Free time should have meaningful, context-aware descriptions.
    Tests show 2-3h gaps with generic "Czas wolny" - need smart labels!
    
    FIX #104 (28.05.2026): Added profile parameter + activity-context labels.
    Client approved 24.05.2026: context-aware descriptions for post-activity recovery.
    
    Args:
        plan: List of plan items (to check previous item)
        now_min: Current time in minutes from midnight
        duration_min: Duration of free_time in minutes
        day_end_min: Day end time in minutes
        profile: User target_group (e.g. "family_kids", "seniors", "couples", "solo")
    
    Returns:
        str: Smart description for free_time
    
    Context Detection:
    - After lunch_break → "Czas wolny po lunchu: kawa, lekki spacer, zakupy"
    - After dinner_break → "Wieczór: spacer, zakupy, relaks w hotelu"
    - After trail/mountain → "Regeneracja po trasie: masaż, termy, odpoczynek w hotelu"
    - After termy/water → "Spokojny czas po termach: kawa, zakupy, relaks"
    - Profile family_kids → "Przerwa rodzinna: lody, plac zabaw, chwila oddechu"
    - End of day (>60 min to day_end) → "Kolacja i wieczorny wypoczynek: restauracja, spacer, zakupy"
    - Long gap (>90 min) → "Czas wolny: spacer po okolicy, kawa, zakupy, zwiedzanie na własną rękę"
    - Short gap (60-90 min) → "Przerwa kawowa: kawa, przekąska, odpoczynek"
    """
    # Check previous item in plan
    last_item = None
    if plan:
        # Find last item with type (skip empty items)
        for item in reversed(plan):
            if "type" in item:
                last_item = item
                break
    
    # Context 1: After lunch_break
    if last_item and last_item.get("type") == "lunch_break":
        return "Czas wolny po lunchu: kawa, lekki spacer, zakupy, relaks"
    
    # Context 2: After dinner_break
    if last_item and last_item.get("type") == "dinner_break":
        return "Wieczór: spacer, zakupy, relaks w hotelu"
    
    # FIX #104 (28.05.2026): Context labels based on previous POI type and user profile
    if last_item:
        _prev_poi = last_item.get("poi", {}) or {}
        _prev_poi_type = _prev_poi.get("type") or last_item.get("type", "")
        if _prev_poi_type in ("mountain_trails", "trail"):
            return "Regeneracja po trasie: masaż, termy, odpoczynek w hotelu"
        if _prev_poi_type == "water_attractions":
            return "Spokojny czas po termach: kawa, zakupy, relaks"
        if _prev_poi_type == "local_food_experience":
            return "Regionalny przystanek: oscypki, herbata góralska"
        # FIX EXTRA4 (01.06.2026): Context label after museum/gallery/cultural POI
        # Client approved 24.05.2026: post-museum free time = coffee + relaxed exploration
        if _prev_poi_type in ("museum", "muzeum", "gallery", "galeria", "galeria_sztuki",
                              "historic_building", "monument", "castle"):
            return "Kawa i spacer: kawiarnia, pamiątki, chwila odpoczynku po zwiedzaniu"
    if profile == "family_kids":
        return "Przerwa rodzinna: lody, plac zabaw, chwila oddechu"
    if profile == "seniors":
        return "Spokojna przerwa regeneracyjna"
    if profile == "couples":
        return "Romantyczna przerwa: kawa, spacer, zakupy"
    if profile == "solo":
        return "Spokojny reset: kawa, notes, własny czas"

    # Context 3: End of day (check if free_time brings us close to day_end)
    # Check 1: Does this free_time END within 60 min of day_end?
    # Check 2: OR is the gap to day_end large (>90 min) suggesting end-of-day period?
    end_of_free_time = now_min + duration_min
    remaining_to_day_end = day_end_min - now_min
    
    # If free_time ends near day_end (within 60 min) OR fills large end-of-day gap
    if end_of_free_time >= day_end_min - 60 or (remaining_to_day_end > 90 and now_min >= 840):  # After 14:00
        # FIX #86 (28.05.2026): Use "Wieczorny relaks" label for afternoon/evening free_time
        # Client specifically requested: "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
        # FIX EXTRA4 (01.06.2026): Split 18:00+ into "Kolacja i Krupówki" — client approved 24.05.2026
        if now_min >= 1080:  # After 18:00 → Kolacja i Krupówki
            return "Kolacja i Krupówki: restauracja, spacer po Krupówkach, zakupy pamiątek"
        elif now_min >= 900:  # After 15:00 → wieczorny relaks territory
            return "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
        else:
            return "Czas wolny do końca dnia: kolacja, spacer, zakupy, relaks"
    
    # Context 4: Long gap (>90 min)
    if duration_min > 90:
        return "Czas wolny: spacer po okolicy, kawa, zakupy, zwiedzanie na własną rękę"
    
    # Context 5: Medium gap (60-90 min)
    if duration_min >= 60:
        return "Przerwa: kawa, przekąska, odpoczynek, krótki spacer"
    
    # Default: Short gap (<60 min, but shouldn't happen since threshold is 60)
    return "Przerwa kawowa: kawa, odpoczynek"


def _log_preference_coverage(plan, user):
    """
    Validate and log preference coverage for the day.
    
    BUGFIX (19.02.2026 - UAT Round 2, Issue #5):
    Client requirement: "preferences są ignorowane przez engine"
    Problem: Tests 03-06, 09-10 show user preferences (kids_attractions, relaxation,
             active_sport, history_mystery) not realized in plan.
    
    Solution: Log warning if day is missing attractions matching top 3 preferences.
    This doesn't enforce coverage (scoring already boosted), but alerts developers.
    
    Args:
        plan: List of plan items (dicts with type, poi, etc.)
        user: User dict with "preferences" list
    
    Returns:
        None (logs only)
    
    Logic:
        - Get top 3 user preferences
        - For each preference, check if ANY attraction in plan matches it
        - Log warning if missing coverage
        - Examples:
          * User prefers ["relaxation", "kids_attractions", "nature"]
          * Day has: Krokiew (sports), Muzeum (culture), Termy (relaxation)
          * Missing: kids_attractions (OK if not family), nature (should warn)
    """
    user_prefs = user.get("preferences", [])
    if not user_prefs:
        return  # No preferences to check
    
    top_3_prefs = user_prefs[:3]
    
    # Get all attractions from plan with their POI tags
    attractions = [
        item for item in plan 
        if item.get("type") == "attraction" and item.get("poi")
    ]
    
    if not attractions:
        print(f"[PREFERENCE COVERAGE] WARNING: No attractions in plan, cannot validate preferences")
        return
    
    # Check coverage for each top 3 preference
    missing_prefs = []
    for pref in top_3_prefs:
        # Check if ANY attraction has this preference in tags
        has_match = False
        for item in attractions:
            poi = item.get("poi", {})
            poi_tags = set(poi.get("tags", []))
            if pref in poi_tags:
                has_match = True
                break
        
        if not has_match:
            missing_prefs.append(pref)
    
    # Log results
    if missing_prefs:
        print(f"[PREFERENCE COVERAGE] WARNING: Day missing top preferences: {missing_prefs}")
        print(f"  - User top 3 preferences: {top_3_prefs}")
        print(f"  - Attractions in plan: {len(attractions)}")
        print(f"  - Suggestion: Check if POI tags cover these preferences or if scoring weights are too low")
    else:
        print(f"[PREFERENCE COVERAGE] [OK] Day covers all top 3 preferences: {top_3_prefs}")


def _validate_and_fix_time_continuity(plan, day_end_str):
    """
    Validate time continuity in plan and fix issues.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #7):
    Client requirement: "Generator powinien automatycznie sprawdzać ciągłość czasu"
    
    Validates:
    1. No unexplained gaps >10 min between items
    2. No overlapping events
    3. All items within day boundaries (day_start → day_end)
    4. If last item ends before day_end with gap >30 min, add free_time
    
    Args:
        plan: List of plan items
        day_end_str: End time string "HH:MM"
    
    Returns:
        tuple: (is_valid: bool, issues: list of strings, fixed_plan: list)
    """
    issues = []
    fixed_plan = list(plan)  # Copy plan for modifications
    
    # Get day_end in minutes
    day_end_min = time_to_minutes(day_end_str)
    
    # Find items with time ranges (skip accommodation_start/end)
    timed_items = []
    for item in fixed_plan:
        if "start_time" in item and "end_time" in item:
            item_copy = dict(item)
            item_copy["start_min"] = time_to_minutes(item["start_time"])
            item_copy["end_min"] = time_to_minutes(item["end_time"])
            timed_items.append(item_copy)
    
    if not timed_items:
        return True, [], fixed_plan  # Empty plan is valid
    
    # Sort by start time
    timed_items.sort(key=lambda x: x["start_min"])
    
    # Check 1: Gaps and overlaps between consecutive items
    items_to_remove_keys = set()  # Track (start_time, end_time, type) to remove
    # FIX B (02.06.2026): Reschedule meals instead of deleting them on overlap.
    # Key: (start_time, end_time, type); Value: (new_start_min, duration_min)
    items_to_reschedule = {}
    
    for i in range(len(timed_items) - 1):
        current = timed_items[i]
        next_item = timed_items[i + 1]
        
        gap = next_item["start_min"] - current["end_min"]
        
        if gap > 10:
            # Large gap detected
            gap_start = minutes_to_time(current["end_min"])
            gap_end = minutes_to_time(next_item["start_min"])
            issues.append(
                f"GAP: {gap} min between {current.get('type')} (ends {current['end_time']}) "
                f"and {next_item.get('type')} (starts {next_item['start_time']})"
            )
            print(f"[TIME CONTINUITY] WARNING: {gap} min gap {gap_start}-{gap_end}")
        
        elif gap < 0:
            # OVERLAP DETECTED - AUTO-FIX
            overlap_duration = abs(gap)
            issues.append(
                f"OVERLAP: {current.get('type')} (ends {current['end_time']}) "
                f"overlaps with {next_item.get('type')} (starts {next_item['start_time']}) by {overlap_duration} min"
            )
            print(f"[TIME CONTINUITY] ERROR: Overlap detected ({overlap_duration} min)!")
            
            # AUTO-FIX STRATEGY: Remove lower-priority item
            # Priority: attraction > lunch/dinner > buffer > free_time
            priority_map = {
                "attraction": 4,
                "lunch_break": 3,
                "dinner_break": 3,
                "parking_walk": 2,
                "tickets_queue": 2,
                "restroom": 2,
                "photo_stop": 2,
                "traffic_margin": 2,
                "free_time": 1,
                "accommodation_start": 0,
                "accommodation_end": 0,
            }
            
            current_priority = priority_map.get(current.get('type'), 1)
            next_priority = priority_map.get(next_item.get('type'), 1)
            
            if current_priority > next_priority:
                # FIX B (02.06.2026): Reschedule meals instead of removing them.
                # Removing lunch/dinner leaves the day without any meal — worse than an overlap.
                # Shift the meal to start immediately after the conflicting higher-priority item ends.
                if next_item.get('type') in ('lunch_break', 'dinner_break'):
                    item_key = (next_item.get('start_time'), next_item.get('end_time'), next_item.get('type'))
                    items_to_reschedule[item_key] = (current["end_min"], next_item.get("duration_min", 40))
                    print(f"[FIX B] Rescheduling {next_item.get('type')} to {minutes_to_time(current['end_min'])} (after {current.get('type')} ends at {current['end_time']})")
                else:
                    # Remove next_item (lower priority)
                    item_key = (next_item.get('start_time'), next_item.get('end_time'), next_item.get('type'))
                    items_to_remove_keys.add(item_key)
                    print(f"[OVERLAP FIX] Marking {next_item.get('type')} for removal (lower priority, {next_priority} < {current_priority})")
            elif next_priority > current_priority:
                # FIX B: Also reschedule meal when it's the earlier (current) item with lower priority.
                if current.get('type') in ('lunch_break', 'dinner_break'):
                    item_key = (current.get('start_time'), current.get('end_time'), current.get('type'))
                    items_to_reschedule[item_key] = (next_item["end_min"], current.get("duration_min", 40))
                    print(f"[FIX B] Rescheduling {current.get('type')} to {minutes_to_time(next_item['end_min'])} (after {next_item.get('type')} ends at {next_item['end_time']})")
                else:
                    # Remove current (lower priority)
                    item_key = (current.get('start_time'), current.get('end_time'), current.get('type'))
                    items_to_remove_keys.add(item_key)
                    print(f"[OVERLAP FIX] Marking {current.get('type')} for removal (lower priority, {current_priority} < {next_priority})")
            else:
                # Same priority - remove later one (next_item)
                item_key = (next_item.get('start_time'), next_item.get('end_time'), next_item.get('type'))
                items_to_remove_keys.add(item_key)
                print(f"[OVERLAP FIX] Marking {next_item.get('type')} for removal (same priority, removing later item)")
    
    # Remove conflicting items from fixed_plan
    if items_to_remove_keys:
        original_count = len(fixed_plan)
        fixed_plan = [
            item for item in fixed_plan 
            if (item.get('start_time'), item.get('end_time'), item.get('type')) not in items_to_remove_keys
        ]
        removed_count = original_count - len(fixed_plan)
        print(f"[OVERLAP FIX] Removed {removed_count} conflicting items from plan")
        
        # FIX #22 (03.05.2026 - CLIENT FEEDBACK Round 2 - Problem #1): Rebuild timed_items after removal
        # Root cause: last_item = timed_items[-1] uses OLD list before overlap removal
        # After removing overlapping items, timed_items[-1] may NOT be the actual last item
        # Solution: Rebuild timed_items from fixed_plan after removal
        timed_items = []
        for item in fixed_plan:
            if "start_time" in item and "end_time" in item:
                item_copy = dict(item)
                item_copy["start_min"] = time_to_minutes(item["start_time"])
                item_copy["end_min"] = time_to_minutes(item["end_time"])
                timed_items.append(item_copy)
        timed_items.sort(key=lambda x: x["start_min"])

    # FIX B (02.06.2026): Apply meal reschedulings — shift meals to their new start times.
    # These meals overlapped a higher-priority item; instead of removal, we move them forward.
    if items_to_reschedule:
        new_fixed_plan = []
        for item in fixed_plan:
            item_key = (item.get('start_time'), item.get('end_time'), item.get('type'))
            if item_key in items_to_reschedule:
                new_start_min, duration_min = items_to_reschedule[item_key]
                if new_start_min + duration_min <= day_end_min:  # Meal fits within day
                    new_item = dict(item)
                    new_item['start_time'] = minutes_to_time(new_start_min)
                    new_item['end_time'] = minutes_to_time(new_start_min + duration_min)
                    new_item['duration_min'] = duration_min
                    new_fixed_plan.append(new_item)
                    print(f"[FIX B] Rescheduled {new_item['type']}: {item['start_time']}-{item['end_time']} → {new_item['start_time']}-{new_item['end_time']}")
                else:
                    # Day is too full to fit the meal — skip it (last resort)
                    print(f"[FIX B] {item.get('type')} at {item.get('start_time')} skipped — no room after {minutes_to_time(new_start_min)}")
            else:
                new_fixed_plan.append(item)
        fixed_plan = new_fixed_plan
        # Rebuild timed_items after rescheduling
        timed_items = []
        for item in fixed_plan:
            if "start_time" in item and "end_time" in item:
                item_copy = dict(item)
                item_copy["start_min"] = time_to_minutes(item["start_time"])
                item_copy["end_min"] = time_to_minutes(item["end_time"])
                timed_items.append(item_copy)
        timed_items.sort(key=lambda x: x["start_min"])

    # Check 2: Last item vs day_end
    # FIX #22: Use timed_items[-1] from REBUILT list after overlap removal
    if not timed_items:
        # All items were removed - plan is empty, cannot add free_time
        return True, issues, fixed_plan
    
    last_item = timed_items[-1]
    gap_to_day_end = day_end_min - last_item["end_min"]
    
    # DEBUG: Show ALL timed_items when checking gap to day_end
    print(f"[VALIDATION CHECK GAP] day_end={day_end_str} ({day_end_min} min), gap_to_day_end={gap_to_day_end} min")
    print(f"[VALIDATION CHECK GAP] timed_items count: {len(timed_items)}")
    for idx, ti in enumerate(timed_items[-5:] if len(timed_items) > 5 else timed_items):  # Show last 5 items
        real_idx = idx if len(timed_items) <= 5 else len(timed_items) - 5 + idx
        item_type = ti.get("type", "?")
        item_start = ti.get("start_time", "?")
        item_end = ti.get("end_time", "?")
        print(f"  [{real_idx}] {item_type:15} {item_start}-{item_end}")
    
    # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Change threshold 30→60 min
    if gap_to_day_end > 60:
        # Significant time left until day_end - add free_time with smart label
        free_start = last_item["end_time"]
        free_start_min = time_to_minutes(free_start)
        
        # DEBUG: Log last_item details
        last_item_type = last_item.get("type", "UNKNOWN")
        last_item_start = last_item.get("start_time", "N/A")
        last_item_end = last_item.get("end_time", "N/A")
        print(f"[VALIDATION FREE_TIME] last_item: {last_item_type} {last_item_start}-{last_item_end}, gap_to_day_end={gap_to_day_end} min")
        
        # CRITICAL FIX (01.05.2026): Cap free_duration at 60 min (CLIENT FEEDBACK - Problem #7)
        # Client requirement: All free_time blocks must be ≤60 min
        # Original bug: free_duration = gap_to_day_end (uncapped, could be 120+ min)
        free_duration = min(60, gap_to_day_end)  # Cap at 60 min
        
        # FIX #20 (03.05.2026 - CLIENT FEEDBACK Round 2 - Problem #1): Calculate free_end from duration
        # Root cause: free_end = day_end_str creates mismatch (duration=60 but end_time=19:00 = 116 min)
        # This causes overlaps when engine adds items in "unused" time (17:04 + 60min = 18:04, not 19:00)
        # Solution: Use free_duration to calculate free_end instead of day_end_str
        free_end = minutes_to_time(free_start_min + free_duration)
        
        print(f"[VALIDATION FREE_TIME] Calculated: free_start={free_start}, free_duration={free_duration}, free_end={free_end}")
        
        # Check if free_time doesn't overlap with existing items
        overlaps, _ = _check_time_overlap(fixed_plan, free_start, free_end)
        
        if not overlaps:
            # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Smart label for validation-added free_time
            free_start_min = time_to_minutes(free_start)
            smart_label = _get_free_time_label(fixed_plan, free_start_min, free_duration, day_end_min)
            
            free_time_item = {
                "type": "free_time",
                "start_time": free_start,
                "end_time": free_end,
                "duration_min": free_duration,
                "description": smart_label
            }
            
            # Insert before accommodation_end (last item in plan)
            insert_index = len(fixed_plan) - 1
            fixed_plan.insert(insert_index, free_time_item)
            
            print(f"[TIME CONTINUITY] Auto-added free_time {free_start}-{free_end} ({free_duration} min): {smart_label.encode('ascii', errors='ignore').decode('ascii')}")
        else:
            issues.append(f"GAP TO DAY_END: {gap_to_day_end} min after last activity (cannot add free_time - overlap)")
    
    elif gap_to_day_end < -10:
        # Last item exceeds day_end
        issues.append(
            f"EXCEEDS DAY_END: Last item ends at {last_item['end_time']}, "
            f"but day_end is {day_end_str} ({abs(gap_to_day_end)} min over)"
        )
        print(f"[TIME CONTINUITY] WARNING: Plan exceeds day_end by {abs(gap_to_day_end)} min")
    
    # Validation result
    is_valid = len([i for i in issues if "OVERLAP" in i or "EXCEEDS" in i]) == 0
    
    return is_valid, issues, fixed_plan


# =========================
# Config
# =========================

DAY_START = "09:00"
DAY_END = "19:00"

LUNCH_TARGET = "13:00"
LUNCH_EARLIEST = "12:00"
LUNCH_LATEST = "14:30"
LUNCH_DURATION_MIN = 40

DINNER_TARGET = "19:00"
DINNER_EARLIEST = "18:00"
DINNER_LATEST = "20:00"
DINNER_DURATION_MIN = 90

MIN_TRANSFER_MIN = 5

# FIX #98 (28.05.2026): Walking vs car threshold for haversine auto-detection
# Distances below this are treated as walkable (no need to drive 300m)
WALK_THRESHOLD_KM = 1.2

# FIX #131 (XX.06.2026): Lower walk threshold for mountain/trail POIs.
# Mountain terrain is steep — 0.8 km GPS distance can mean a significant uphill climb.
WALK_THRESHOLD_MOUNTAIN_KM = 0.6

# FIX #131: POI types and tags that qualify as "mountain" for the lower walk threshold.
_MOUNTAIN_POI_TYPES = {"trail"}
_MOUNTAIN_POI_TAGS = {
    "nature_immersion", "easy_walk", "family_friendly_trail", "viewpoint_trail",
    "forest_trails", "alpine_valley", "mountain_viewpoint", "panoramic_view",
    "scenic_viewpoint",
}

# FIX #111 (06.06.2026): Inter-city transfer threshold
# Distances above this are treated as inter-city (different city within a cluster)
INTER_CITY_THRESHOLD_KM = 8.0

# FIX #111 (06.06.2026): Cluster-aware road speeds for travel time calculation
# Each cluster type has realistic road conditions that differ from mountain defaults
CLUSTER_ROAD_SPEEDS_KMH = {
    "urban_organism":   60.0,  # Trójmiasto: urban expressways / SKM corridor (S6/S7)
    "regional_cluster": 50.0,  # Kotlina Kłodzka: regional roads, moderate terrain
    "radius_based":     40.0,  # Karkonosze: narrow mountain roads, hairpin bends
    "standalone_city":  45.0,  # Default: mountain city roads (unchanged from FIX #98)
}

# FIX #102 (29.05.2026): Zakopane city center coordinates (used for return transit after trail)
ZAKOPANE_CENTER_LAT = 49.2992
ZAKOPANE_CENTER_LNG = 19.9496

GROUP_LIMITS = {
    "solo": 5,
    "couples": 5,
    "friends": 6,
    "family_kids": 8,
    "seniors": 5,
}

GROUP_DAILY_ENERGY = {
    "solo": 70,
    "couples": 65,
    "friends": 75,
    "family_kids": 60,  # FIX #124 (30.05.2026): Reduced from 90 → 60; toddler modifier applied in build_day
    "seniors": 55,
}

# FIX #7 (02.02.2026): Attraction limits per target_group
# Client requirements:
# - family_kids: 4-6 attractions (max 7), 1-2 core, 2-3 light, 1 long
# - seniors: 3-5 attractions (max 5), 1 must-see, 2-3 calm
# - solo: 5-7 attractions (max 8), 2 core, 3-4 secondary
# - couples: 5-6 attractions (max 6), 1-2 must-see, 2-3 scenic
# - friends: 6-8 attractions (max 8), 2 core, 3-4 active, 1-2 evening
#
# FIX #13 (23.02.2026 - TEST-06 CRITICAL FIX):
# SENIORS LIMIT TOO LOW: hard=5 caused Day 1 to fill 5 POIs and stop, leaving Days 2-3 empty.
# Problem: TEST-06 has 8-hour days (10:00-18:00) but seniors hit hard limit after ~3 hours.
# Result: 10% budget usage, Day 3 practically empty (1 POI + 6h free time).
# Solution: Increase seniors to soft=5, hard=7 (matching couples) to allow proper day filling.
# FIX #Problem12 (15.05.2026 - CLIENT FEEDBACK Round 2): Reduce POI limits for seniors/family_kids
# Problem: Seniors+relax get 5 POI per day (too intensive)
# Solution: seniors=3, family_kids=4, relax modifier=-1 applied later
GROUP_ATTRACTION_LIMITS = {
    "family_kids": {
        "soft": 3,  # Start penalty after 3
        "hard": 4,  # Absolute max (was 7)
        "core_min": 1,  # Minimum core POI
        "core_max": 2,  # Maximum core POI
    },
    "seniors": {
        "soft": 4,  # FIX #34 (18.05.2026): 4 (was 2 - days 2-3 empty with relax modifier dropping to 1)
        "hard": 5,  # FIX #34 (18.05.2026): 5 (was 3 - too restrictive for 8h days)
        "core_min": 1,
        "core_max": 2,
    },
    "solo": {
        "soft": 7,
        "hard": 8,
        "core_min": 2,
        "core_max": 2,
    },
    "couples": {
        "soft": 6,
        "hard": 6,
        "core_min": 1,
        "core_max": 2,
    },
    "friends": {
        "soft": 8,
        "hard": 8,
        "core_min": 2,
        "core_max": 2,
    },
}


# =========================
# Safe casting
# =========================


def _is_nan(x):
    try:
        return isinstance(x, float) and math.isnan(x)
    except (TypeError, ValueError):
        return False


def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if _is_nan(x):
            return default
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


def is_kids_focused_poi(poi):
    """
    Check if POI is kids-focused (target_groups + tags analysis).
    
    CLIENT REQUIREMENT (04.02.2026): Kids-focused POI should have daily limit
    for non-family groups (max 1 per day).
    
    UAT FIX (18.02.2026 - Problem #2): Enhanced detection via tags
    - Original logic: ONLY family_kids in target_groups
    - New logic: Also check for kids-related tags
    
    Args:
        poi: POI dict
        
    Returns:
        bool: True if POI is kids-focused
    """
    # Method 1: ONLY family_kids in target_groups (strictest)
    target_groups = poi.get("target_groups") or []
    if target_groups:
        tg = set([str(x).strip().lower() for x in target_groups])
        if len(tg) == 1 and "family_kids" in tg:
            return True
    
    # Method 2: UAT FIX - Check for kids-specific tags
    # If POI has multiple kids-related tags → likely kids-focused
    poi_tags = poi.get("tags") or []
    tags_str = ",".join([str(t).lower() for t in poi_tags])
    
    kids_indicators = [
        "kids", "children", "playground", "interactive_exhibition_kids",
        "petting_zoo", "farm_animals", "feeding_experience",
        "miniature_world", "fairytale_world", "illusion_kids",
        "aquatic_playground", "adventure_playground", "trampoline_park",
        "family_entertainment_kids", "zoo", "aquarium_kids"
    ]
    
    kids_tag_count = sum(1 for indicator in kids_indicators if indicator in tags_str)
    
    # If POI has 2+ kids indicators → treat as kids-focused
    if kids_tag_count >= 2:
        return True
    
    # Method 3: UAT FIX - Check POI name for obvious kids attractions
    poi_name = str(poi.get("name", "")).lower()
    name_indicators = [
        "mini zoo", "podwodny świat", "dom do góry nogami",
        "myszogród", "playground", "kids park", "children",
        "papugarnia"  # FIX #19 HOTFIX (29.04.2026): Client explicitly mentioned Papugarnia in couples plans
    ]
    
    for indicator in name_indicators:
        if indicator in poi_name:
            return True
    
    return False


def is_termy_spa(poi):
    """
    Check if POI is a termy/spa/thermal bath.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9):
    Max 1 termy/spa per day for seniors to avoid exhaustion.
    
    BUGFIX (30.04.2026 - CRITICAL): Case-insensitive matching
    Problem: "termy" != "Terma" or "Termy" (case-sensitive)
    Solution: Convert to lowercase before matching
    
    Args:
        poi: POI dict
        
    Returns:
        bool: True if POI is termy/spa/thermal bath
    """
    name = safe_str(poi.get("name", "")).lower()
    poi_type = safe_str(poi.get("type", "")).lower()
    tags = poi.get("tags") or []
    tags_str = ",".join([safe_str(x) for x in tags]).lower() if tags else ""
    
    # Check name, type, or tags for termy/spa/thermal keywords (case-insensitive)
    # FIX #152: Removed "relax" from tag check — it matched quiet_relax_spot, relaxation,
    # relax_zone, etc., causing waterfalls/meadows/viewpoints to be wrongly counted as termy/spa
    # and blocked by the 1-per-day limit.  Only actual thermal/spa tags remain.
    return (
        any(keyword in name for keyword in ["term", "spa", "thermal", "basen termalny", "sauna"]) or
        any(keyword in poi_type for keyword in ["term", "spa", "thermal", "wellness"]) or
        any(keyword in tags_str for keyword in ["spa", "thermal", "wellness"])
    )


def should_exclude_kids_poi_for_adults(poi, user):
    """
    Check if POI should be excluded for adult groups (friends/couples/seniors/solo).
    
    FIX #10.4 (22.02.2026 - UAT Round 3, TEST-03 FINAL FIX):
    CRITICAL BUGFIX: FIX #10 was only applied in main POI selection loop (line 1546),
    but variety logic (line 1823), core rotation (line 1730), and soft fallback (line 1927)
    bypass this filter, allowing kids POIs to appear in adult plans.
    
    Root cause: poi_15 (Termy Zakopańskie) has type='kids_attractions' but appeared in 
    TEST-03 (friends, adventure) plan because variety logic re-scanned without FIX #10.
    
    Solution: Extract FIX #10 logic to reusable function, apply to ALL POI selection paths.
    
    FIX #10.5 (22.02.2026 - UAT Round 3, TEST-04 DEBUG):
    Added comprehensive logging to diagnose poi_2 (Zoo) appearing for solo travelers.
    
    FIX #10.6 (22.02.2026 - TEST-04 DEBUG v2):
    Added ALWAYS-ON logging to verify filter is being called at all.
    
    FIX #12 (23.02.2026 - TEST-06 CRITICAL FIX):
    MULTI-PURPOSE POI EXCEPTION: Don't exclude POIs that serve both kids AND adults.
    Problem: poi_15 (Termy Zakopańskie) has type='kids_attractions, relaxation' and
    includes 'seniors' in target_groups, pero was blocked for seniors with relaxation preference.
    Solution: Allow POI if it has BOTH kids type AND adult-appropriate types (relaxation, water_attractions, spa)
    AND explicitly includes requesting group in target_groups.
    
    Args:
        poi: POI dict with tags and type
        user: User dict with group type
        
    Returns:
        bool: True if POI should be EXCLUDED (hard block for kids POI in adult plans)
    """
    poi_id = poi.get("id", "unknown")
    poi_name = poi.get("name", "unknown")
    poi_name_safe = str(poi_name).encode('ascii', errors='ignore').decode('ascii')
    
    # FIX #10.6 + FIX #15: ALWAYS print when filter is called
    print(f"\n[FIX #15 FILTER CALLED] {poi_id} - {poi_name_safe}")
    
    poi_tags = set(poi.get("tags", []))
    poi_type_str = str(poi.get("type", "")).lower()
    poi_type_list = [t.strip() for t in poi_type_str.split(",") if t.strip()]
    
    print(f"   Type string: '{poi_type_str}'")
    print(f"   Type list: {poi_type_list}")
    print(f"   Tags: {poi_tags}")
    
    group_type = user.get("group", {}).get("type", "") if isinstance(user.get("group"), dict) else user.get("target_group", "")
    adult_groups = ["friends", "couples", "couple", "seniors", "solo", "adults"]
    
    if group_type not in adult_groups:
        return False  # Not adult group - no exclusion
    
    # Kids-only POI identifiers
    # FIX #15 (23.02.2026): Added zoo_other to block Zoo for adults
    kids_only_tags = {"kids_attractions", "petting_zoo", "fairytale_world", 
                     "miniature_world", "children_playground", "playground"}
    kids_only_types = {"kids_attractions", "zoo_other", "petting_zoo", "playground", "zoo"}
    
    print(f"   kids_only_types: {kids_only_types}")
    
    # Check BOTH tags AND type fields (FIX #10.2/10.3)
    has_kids_tag = bool(kids_only_tags & poi_tags)
    has_kids_type = any(t in kids_only_types for t in poi_type_list)
    
    print(f"   has_kids_tag: {has_kids_tag} (matched: {kids_only_tags & poi_tags})")
    print(f"   has_kids_type: {has_kids_type} (matched types: {[t for t in poi_type_list if t in kids_only_types]})")
    
    # FIX #12: Multi-purpose POI exception - Check if POI serves adults too
    # Adult-appropriate types that override kids_attractions filtering
    adult_appropriate_types = {"relaxation", "spa", "wellness", "water_attractions", 
                              "thermal_baths", "hot_springs", "casino", "nightlife"}
    adult_appropriate_tags = {"thermal_baths", "spa_pools", "sauna_zone", "wellness_center",
                             "hot_springs", "relaxation_zone"}
    
    has_adult_type = any(t in adult_appropriate_types for t in poi_type_list)
    has_adult_tag = bool(adult_appropriate_tags & poi_tags)
    print(f"   has_adult_type: {has_adult_type} (matched: {[t for t in poi_type_list if t in adult_appropriate_types]})")
    print(f"   has_adult_tag: {has_adult_tag} (matched: {adult_appropriate_tags & poi_tags})")
    
    # Check if POI explicitly includes current group in target_groups
    # FIX #15 (23.02.2026 - TEST-06): Handle both string and list formats
    poi_target_groups = poi.get("target_groups", [])
    print(f"   poi_target_groups RAW: {poi_target_groups} (type: {type(poi_target_groups)})")
    
    if poi_target_groups:
        # Handle both "solo, couples, seniors" (string) and ["solo", "couples", "seniors"] (list)
        if isinstance(poi_target_groups, str):
            target_groups_list = [tg.strip().lower() for tg in poi_target_groups.split(',')]
        else:
            target_groups_list = [str(tg).strip().lower() for tg in poi_target_groups]
        explicitly_targets_group = group_type.lower() in target_groups_list
        print(f"   target_groups_list: {target_groups_list}")
        print(f"   group_type: '{group_type}' -> explicitly_targets: {explicitly_targets_group}")
    else:
        explicitly_targets_group = False
        print(f"   target_groups EMPTY -> explicitly_targets: False")
    
    # EXCEPTION: Don't exclude if POI serves BOTH kids AND adults
    # Conditions: (has_kids_type OR has_kids_tag) AND (has_adult_type OR has_adult_tag) AND explicitly_targets_group
    is_multi_purpose = (has_kids_type or has_kids_tag) and (has_adult_type or has_adult_tag) and explicitly_targets_group
    print(f"   is_multi_purpose: {is_multi_purpose} = ({has_kids_type or has_kids_tag}) AND ({has_adult_type or has_adult_tag}) AND ({explicitly_targets_group})")
    
    # FIX #19 HOTFIX 2 (29.04.2026): Also check is_kids_focused_poi() for name-based detection
    # Problem: Papugarnia has no kids tags/types but is kids-focused (detected by name "papugarnia")
    # Solution: Add name-based detection to hard block (not just penalty)
    is_kids_by_name = is_kids_focused_poi(poi)
    
    if is_multi_purpose:
        # Multi-purpose POI (e.g., Termy with both kids and adult facilities) - ALLOW
        should_exclude = False
        print(f"   [FIX #12] DECISION: ALLOW - Multi-purpose POI for {group_type}")
    elif is_kids_by_name:
        # FIX #19 HOTFIX 2: Kids-focused by name (even without kids tags/types) - EXCLUDE for adults
        should_exclude = True
        print(f"   [FIX #19 HOTFIX 2] DECISION: EXCLUDE - Kids-focused POI by name for {group_type}")
    else:
        # Pure kids POI - EXCLUDE for adults
        should_exclude = has_kids_tag or has_kids_type
        if should_exclude:
            print(f"   [KIDS FILTER] DECISION: EXCLUDE - Kids-only POI for adult group")
        else:
            print(f"   DECISION: ALLOW - Not a kids POI")
    
    return should_exclude


def safe_int(x, default=0):
    return int(round(safe_float(x, default)))


def safe_str(x):
    return str(x).strip().lower() if x is not None else ""


# =========================
# Geo helpers
# =========================


def _is_mountain_poi(poi):
    """FIX #131: Return True if POI is mountain/trail type (uses lower walk threshold)."""
    if not poi:
        return False
    if poi.get("type") in _MOUNTAIN_POI_TYPES:
        return True
    return bool(_MOUNTAIN_POI_TAGS & set(poi.get("tags", []) or []))


def _walk_threshold(a=None, b=None):
    """FIX #131: Return effective walk threshold km, lowered when either POI is mountain."""
    if _is_mountain_poi(a) or _is_mountain_poi(b):
        return WALK_THRESHOLD_MOUNTAIN_KM
    return WALK_THRESHOLD_KM


def distance_km(a, b):
    R = 6371
    lat1, lon1 = math.radians(a["lat"]), math.radians(a["lng"])
    lat2, lon2 = math.radians(b["lat"]), math.radians(b["lng"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(x))


def travel_time_minutes(a, b, context):
    """Calculate travel time between two POIs.

    FIX #98 (28.05.2026): Auto-selects walking or car mode based on GPS distance.
    - distance < WALK_THRESHOLD_KM  → walking  (~5 km/h, no parking, min 5 min)
    - distance >= WALK_THRESHOLD_KM → car      (cluster-aware speed + 5 min parking, min 10 min)

    FIX #111 (06.06.2026): Cluster-aware road speed for car travel.
    Speed is selected based on cluster_type from context["signals"]:
    - urban_organism (Trójmiasto): 60 km/h — urban expressways / SKM corridor
    - regional_cluster (Kotlina):  50 km/h — regional roads, moderate terrain
    - radius_based (Karkonosze):   40 km/h — narrow mountain roads
    - standalone_city (Zakopane):  45 km/h — mountain city roads (unchanged)
    Return type stays int (minutes) – fully backward compatible.
    """
    if not a or not b:
        return 0

    has_car = context.get("has_car", True)
    if not has_car:
        return 0

    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")

    if not all([lat1, lng1, lat2, lng2]):
        return 10  # fallback – no GPS coords

    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    _walk_thresh = _walk_threshold(a, b)  # FIX #131: mountain-aware threshold

    if distance_km < _walk_thresh:
        # Walking: 5 km/h, no parking overhead, minimum 5 min
        walk_time = (distance_km / 5.0) * 60
        return max(int(walk_time), 5)
    else:
        # FIX #111: Car speed depends on cluster type (road conditions vary per region)
        cluster_type = context.get("signals", {}).get("cluster_type", "standalone_city")
        speed_kmh = CLUSTER_ROAD_SPEEDS_KMH.get(cluster_type, 45.0)
        drive_time = (distance_km / speed_kmh) * 60 + 5
        return max(int(drive_time), 10)


def get_transport_mode(a, b):
    """Return transport mode between two POIs: 'walking' or 'car'.

    FIX #98 (28.05.2026): Pure helper – no side effects. Uses same
    WALK_THRESHOLD_KM as travel_time_minutes so mode is always consistent.
    Returns 'car' as safe fallback when GPS coords are missing.
    """
    if not a or not b:
        return "car"
    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    if not all([lat1, lng1, lat2, lng2]):
        return "car"
    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    return "walking" if distance_km < _walk_threshold(a, b) else "car"  # FIX #131


# =========================
# Context helpers
# =========================


def _get_context(context):
    if not isinstance(context, dict):
        context = {}

    season = safe_str(context.get("season")) or None
    region_type = safe_str(context.get("region_type")) or None
    weather = context.get("weather") or {}

    return {
        "season": season,
        "region_type": region_type,
        "temp": safe_float(weather.get("temp"), 15),
        "precip": bool(weather.get("precip", False)),
        "wind": safe_float(weather.get("wind"), 0),
        "transport": safe_str(context.get("transport")) or "car",
        "daylight_end": context.get("daylight_end"),
        "date": context.get("date"),  # CRITICAL FIX: Add date for opening_hours validation
    }


# =========================
# Distance calculation
# =========================


def haversine_distance(lat1, lng1, lat2, lng2):
    """
    Calculate distance in km between two GPS points using Haversine formula.
    """
    R = 6371  # Earth radius in km
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


def calculate_drive_time(poi_from, poi_to, has_car=True):
    """
    Calculate driving time between two POIs in minutes.
    
    Args:
        poi_from: POI dict with lat/lng
        poi_to: POI dict with lat/lng
        has_car: Whether user has car
    
    Returns:
        Driving time in minutes (minimum 10 min for nearby, +5 for parking)
    """
    if not has_car:
        return 0
    
    lat1 = poi_from.get('lat')
    lng1 = poi_from.get('lng')
    lat2 = poi_to.get('lat')
    lng2 = poi_to.get('lng')
    
    if not all([lat1, lng1, lat2, lng2]):
        return 10  # Default if no coordinates
    
    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    
    # 45 km/h average speed in mountains + 5 min parking
    drive_time = (distance_km / 45) * 60 + 5
    
    return max(int(drive_time), 10)  # Minimum 10 min


# =========================
# POI helpers
# =========================


def poi_id(p):
    return p.get("id", "")


def poi_name(p):
    return p.get("name", "Unnamed")


# PHASE 8 FEATURE #7 (27.04.2026): POI classifier (main vs filler)
# Formula: weight = time(40%) + priority(30%) + popularity(20%) + type(10%)
# If weight ≥ 6.0 → main attraction (główna atrakcja dnia)
# If weight < 6.0 → filler (wypełniacz)
def classify_poi_weight(p):
    """
    Classify POI as 'main' or 'filler' based on weighted formula.
    
    Weight components:
    - Time: 40% weight, scaled 0-3.0 (60min=1.0, 90min=1.5, 180min=3.0)
    - Priority: 30% weight (core=3.0, recommended=2.0, optional=1.0)
    - Popularity: 20% weight, scaled 0-2.0 (popularity 0.0-1.0 → 0.0-2.0)
    - Type: 10% weight (monument/castle=0.7, museum=0.6, viewpoint=0.4, playground=0.3)
    
    Returns:
        (classification, weight, breakdown) where:
        - classification: "main" or "filler"
        - weight: float (0-10 range, threshold 6.0)
        - breakdown: dict with component scores
    """
    # Component 1: Time (max 3.0 points) - 40% weight
    # Scaling: 60min=1.0, 90min=1.5, 120min=2.0, 180min=3.0
    time_min = safe_int(p.get("time_min", 60), 60)
    time_score = min(3.0, time_min / 60.0)
    
    # Component 2: Priority (max 3.0 points) - 30% weight
    # core=3.0, recommended=2.0, optional=1.0
    priority_str = safe_str(p.get("priority", "optional")).lower()
    if "core" in priority_str:
        priority_score = 3.0
    elif "recommend" in priority_str:
        priority_score = 2.0
    else:
        priority_score = 1.0
    
    # Component 3: Popularity (max 2.0 points) - 20% weight
    # Scaling: 0.0-1.0 → 0.0-2.0
    popularity = safe_float(p.get("popularity", 0.0))
    popularity_score = popularity * 2.0
    
    # Component 4: Type (max 1.0 point) - 10% weight
    # monument/castle=0.7, museum=0.6, park=0.5, viewpoint=0.4, playground=0.3
    poi_type = safe_str(p.get("type", "")).lower()
    type_weights = {
        "castle": 0.7, "zamek": 0.7,
        "monument": 0.7, "pomnik": 0.7,
        "cathedral": 0.65, "katedra": 0.65,
        "museum": 0.6, "muzeum": 0.6,
        "palace": 0.6, "pałac": 0.6,
        "park": 0.5,
        "viewpoint": 0.4, "punkt_widokowy": 0.4,
        "restaurant": 0.3, "restauracja": 0.3,
        "playground": 0.3, "plac_zabaw": 0.3,
        "parking": 0.2,
    }
    type_score = 0.4  # default
    for type_key, type_value in type_weights.items():
        if type_key in poi_type:
            type_score = type_value
            break
    
    # Total weight (0-9.0 max: 3.0 + 3.0 + 2.0 + 1.0)
    total_weight = time_score + priority_score + popularity_score + type_score
    
    # Classification threshold: ≥6.0 = main, <6.0 = filler
    classification = "main" if total_weight >= 6.0 else "filler"
    
    breakdown = {
        "time": time_score,
        "priority": priority_score,
        "popularity": popularity_score,
        "type": type_score,
    }
    
    return (classification, total_weight, breakdown)


def is_culture(p):
    t = safe_str(p.get("type"))
    return any(
        k in t
        for k in [
            "museum",
            "muzeum",
            "gallery",
            "galeria",
            "exhibition",
            "wystaw",
        ]
    )


def is_finale(p):
    return p.get("experience_role") == "finale"


# =========================
# Opening hours
# =========================


def is_open(p, now, duration, season, context=None):
    """
    Check if POI is open at given time.
    
    NEW FORMAT (30.01.2026) - Uses opening_hours_parser to validate:
    - opening_hours: JSON dict {"mon": "08:00-16:00", ...}
    - opening_hours_seasonal: JSON dict {"date_from": "05-01", "date_to": "09-30"}
    
    Args:
        p: POI dict with "opening_hours" and "opening_hours_seasonal" fields
        now: Start time in minutes since midnight
        duration: Visit duration in minutes
        season: Season string (unused, kept for compatibility)
        context: Context dict with "date" = (year, month, day, weekday)
    
    Returns:
        True if POI is open and visit fits within hours
        False otherwise (including off-season)
    """
    oh = p.get("opening_hours")
    oh_seasonal = p.get("opening_hours_seasonal")
    
    # FIX #33 (18.05.2026): Only skip validation when BOTH opening_hours and seasonal are absent.
    # Previously: `if not oh: return True` — this incorrectly ignored oh_seasonal!
    # Example: KULIGI has oh=None but oh_seasonal=[{winter hours}] → must check seasonal.
    if not oh and not oh_seasonal:
        return True
    
    # Extract date info from context
    if not context or "date" not in context:
        # No date context - use legacy simple validation
        print(f"[is_open DEBUG] No date context - using legacy validation for {p.get('Name', 'UNKNOWN')}")
        day_start = time_to_minutes("09:00")
        day_end = time_to_minutes("20:00")
        return (now >= day_start) and (now < day_end)
    
    # Parse context date - handle datetime objects, tuples, and strings
    date_obj = context["date"]
    if hasattr(date_obj, 'year'):
        # It's a datetime object
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        weekday = date_obj.weekday()
    elif isinstance(date_obj, str):
        # It's a string "YYYY-MM-DD"
        from datetime import datetime
        dt = datetime.strptime(date_obj, "%Y-%m-%d")
        year, month, day = dt.year, dt.month, dt.day
        weekday = dt.weekday()
    else:
        # It's a tuple (year, month, day, weekday)
        year, month, day, weekday = date_obj
    
    current_date = (year, month, day)
    
    # CLIENT FEEDBACK (30.01.2026 - Requirements #2-3): Debug opening_hours validation
    poi_name = p.get("Name", "UNKNOWN")
    print(f"[is_open DEBUG] {poi_name}: date={current_date}, weekday={weekday}, now={now}min, duration={duration}min")
    
    # Use opening_hours_parser for proper validation
    result = is_poi_open_at_time(
        opening_hours=oh,
        opening_hours_seasonal=oh_seasonal,
        current_date=current_date,
        weekday=weekday,
        start_time_minutes=now,
        duration_minutes=duration
    )
    
    if not result:
        print(f"[is_open DEBUG] {poi_name}: CLOSED (validation failed)")
    
    return result


# =========================
# Energy
# =========================


def energy_cost(p, duration, context):
    base = max(15, duration) / 10
    if p.get("intensity") == "high":
        base *= 1.5
    if p.get("space") == "outdoor":
        base *= 1.2
    if _get_context(context)["region_type"] == "mountain":
        base *= 1.2
    return base


# =========================
# Duration
# =========================


def choose_duration(p, now, end, lunch_done, user=None):
    tmin = safe_int(p.get("time_min"), 30)
    tmax = safe_int(p.get("time_max"), 60)

    # FIX #Problem13 (15.05.2026 - Round 2): TYPE-BASED minimum duration enforcement
    # Safeguard: Even if Excel has low time_min, enforce type-specific minimums
    # to prevent unreasonably short visits (e.g., museum with 5 min)
    MIN_DURATION_BY_TYPE = {
        "museum": 30,
        "gallery": 20,
        "church": 15,
        "viewpoint": 15,
        "trail": 60,
    }
    
    # Identify POI type category from "type" field or name keywords
    poi_name = safe_str(p.get("name", "")).lower()
    poi_type_str = safe_str(p.get("type", "")).lower()
    
    # Check for type-specific minimum duration requirement
    type_min_duration = 0
    if "museum" in poi_type_str or "muzeum" in poi_name:
        type_min_duration = MIN_DURATION_BY_TYPE["museum"]
    elif "gallery" in poi_type_str or "galeria" in poi_name:
        type_min_duration = MIN_DURATION_BY_TYPE["gallery"]
    elif "church" in poi_type_str or "kaplica" in poi_name or "kościół" in poi_name:
        type_min_duration = MIN_DURATION_BY_TYPE["church"]
    elif "viewpoint" in poi_type_str or "punkt widokowy" in poi_name:
        type_min_duration = MIN_DURATION_BY_TYPE["viewpoint"]
    elif "trail" in poi_type_str or "szlak" in poi_name:
        type_min_duration = MIN_DURATION_BY_TYPE["trail"]
    
    # Use the HIGHER of: POI's time_min OR type-based minimum
    # This ensures Excel data can set higher requirements, but types enforce floor
    effective_min = max(tmin, type_min_duration)
    
    if end - now < effective_min:
        if type_min_duration > 0:
            print(f"[DURATION] Skipping {p.get('name', 'unknown')} - insufficient time ({end - now} min < {effective_min} min type-based minimum)")
        return 0

    # Legacy check (now redundant but kept for clarity)
    if end - now < tmin:
        return 0

    # FIX #Problem9 (13.05.2026 - Round 2): Use group-specific lunch timing
    # If user is provided, compute group-specific timing; otherwise use defaults
    # BUGFIX: trip_mapper.py maps group.type → user["target_group"], NOT user["group"]["type"]
    if user:
        group_type = user.get("target_group")
        
        if group_type == "family_kids":
            lunch_target = time_to_minutes("12:30")
            lunch_latest = time_to_minutes("13:30")
        elif group_type == "seniors":
            lunch_target = time_to_minutes("12:45")
            lunch_latest = time_to_minutes("13:30")
        else:
            lunch_target = time_to_minutes(LUNCH_TARGET)
            lunch_latest = time_to_minutes(LUNCH_LATEST)
    else:
        lunch_target = time_to_minutes(LUNCH_TARGET)
        lunch_latest = time_to_minutes(LUNCH_LATEST)

    # FIX #45 (20.05.2026 - Issue F root fix): Trails span the entire day including lunch.
    # Mountain trails are 90min-13h activities that naturally cross lunch time.
    # Blocking trails by max_before_lunch eliminates ALL trails with tmin > ~220min,
    # leaving only 1-2 short trails for the entire 7-day trip.
    # Solution: Skip the lunch pre-filter entirely for trail type POIs.
    is_trail_poi = p.get("type") == "trail"

    # jesli lunch nie zrobiony, sprawdź czy POI zmieści tmin przed lunchem
    if not is_trail_poi and not lunch_done and now < lunch_latest:
        max_before_lunch = (
            lunch_target - now if now < lunch_target else lunch_latest - now
        )
        # BLOCK POI jeśli jego tmin przekroczyłby lunch
        if max_before_lunch < tmin:
            return 0

    # Wybierz rozsądny duration: około 70% zakresu (tmin → tmax)
    # Przykład: tmin=60, tmax=150 → preferred = 60 + 0.7*(90) = 123
    # To daje bardziej realistyczne czasy niż zawsze max
    preferred_duration = tmin + int(0.7 * (tmax - tmin))
    
    # FIX #Problem9 (14.05.2026): CAP duration at max_before_lunch to prevent pushing lunch late
    # BUG: Even if POI is allowed (tmin < max_before_lunch), preferred_duration could be much longer
    #      Example: now=10:00, lunch_target=12:30, tmin=60, preferred=150 → POI ends at 12:30 (150min)
    #               This pushes lunch to 12:30+, then POST-POI CHECK inserts it late (14:48)
    # Solution: Cap duration at max_before_lunch to ensure POI ends BEFORE lunch time
    # BUGFIX (14.05.2026): Only apply cap if max_before_lunch > 0 to avoid negative durations
    # FIX #45: Trails skip the lunch cap — they span the entire day including lunch
    if not is_trail_poi and not lunch_done and now < lunch_latest:
        # max_before_lunch is already calculated above
        # Cap duration only if we have positive time before lunch
        if max_before_lunch > 0:
            return min(preferred_duration, end - now, max_before_lunch)
        else:
            # This shouldn't happen (POI would be blocked above), but safety check
            return 0
    else:
        return min(preferred_duration, end - now)


# =========================
# Scoring
# =========================


def score_poi(
    p,
    user,
    fatigue,
    used,
    now,
    energy_left,
    context,
    culture_streak,
    body_state,
    finale_done,
    daily_cost=0,  # FIX #14: Added for budget utilization boost
    daily_limit=None,  # FIX #14: Added for budget utilization boost
    active_streak=0,  # FIX #99E: track consecutive active/outdoor POIs for friends
):
    score = 0.0
    
    # ETAP 3 PHASE 5 (27.04.2026): Get scoring_weights from router for POI scoring
    # Router calculates trip-level multipliers (cultural_bonus, convenience_bonus, must_see_bonus)
    # These weights customize scoring based on trip type (city_tourism vs mountain_hiking)
    # Phase 4 applied weights to trail scoring, Phase 5 applies to POI scoring
    scoring_weights = context.get("scoring_weights", {})

    # UAT FIX (18.02.2026 - Problem #10): Must_see conditional scoring
    # Tests 03, 06, 07, 08, 09: Wielka Krokiew appears in every plan
    # Problem: must_see * 2.0 bonus (20 points for Krokiew) dominates all other scoring
    # Solution: Full bonus only when POI matches user preferences
    # This keeps must_see important but not overwhelming when user wants different experiences
    
    # First calculate if POI matches user preferences (check tag bonus)
    user_preferences = user.get("preferences", [])
    poi_matches_preferences = False
    tag_bonus = 0
    
    if user_preferences:
        # Calculate tag-based preference bonus
        tag_bonus = calculate_tag_preference_score(p, user_preferences)
        poi_matches_preferences = (tag_bonus > 0)
    
    # Apply conditional must_see bonus
    # PHASE 5: Apply must_see_bonus multiplier from router (city_tourism gets 1.5x)
    must_see_value = safe_float(p.get("must_see"))
    must_see_multiplier = scoring_weights.get("must_see_bonus", 1.0)
    
    if poi_matches_preferences or not user_preferences:
        # Full bonus when: preferences match OR user has no preferences
        must_see_boost = must_see_value * 2.0 * must_see_multiplier  # 2.0 → 3.0 for city_tourism
        score += must_see_boost
    else:
        # Reduced bonus when: user has preferences but POI doesn't match
        must_see_boost = must_see_value * 1.0 * must_see_multiplier  # 1.0 → 1.5 for city_tourism
        score += must_see_boost
        if must_see_value > 5:  # Log for high must_see POI
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [MUST_SEE REDUCED] {poi_name_safe}: {must_see_boost:.1f} (no preference match, user wants: {user_preferences}, must_see_bonus={must_see_multiplier})")
    
    # FIX #Problem6 (CLIENT FEEDBACK 03.05.2026 - Round 2): Conditional priority bonus
    # Tests 03, 07, 09, 10: High-priority generic POI (museums, viewpoints) dominate plans
    # Problem: priority_level bonus (+12 for poi_20 Wielka Krokiew) applied unconditionally
    # Test-10: water_attractions user gets poi_20 (viewpoint, priority 12) instead of termy (priority 6, matching tags)
    # Solution: Like must_see, reduce priority bonus when POI doesn't match user preferences
    priority_value = safe_float(p.get("priority"))
    
    if poi_matches_preferences or not user_preferences:
        # Full priority bonus when preferences match OR user has no preferences
        priority_boost = priority_value
        score += priority_boost
    else:
        # Reduced priority bonus (50%) when user has preferences but POI doesn't match
        priority_boost = priority_value * 0.5
        score += priority_boost
        if priority_value >= 10:  # Log for high-priority POI
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [PRIORITY REDUCED] {poi_name_safe}: {priority_boost:.1f} (no preference match, user wants: {user_preferences}, raw priority={priority_value})")

    # dopasowanie - existing modules
    score += calculate_family_score(p, user)
    
    # FIX #73 (03.06.2026): Profile-aware scoring for family_kids.
    # Bug: museum/history/heritage POIs over-weighted for family_kids+outdoor preferences.
    # Fix: Penalty for inappropriate family content; boost for family-friendly content.
    _target_group_73 = user.get("target_group", "")
    if _target_group_73 == "family_kids":
        _poi_tags_73 = set(str(t).lower() for t in p.get("tags", []))
        _FAMILY_PENALIZED_TAGS = {
            "religious_museum", "heavy_history", "adult_heritage", "political_museum",
            "long_static_exhibition", "war_history", "historical_artifacts"
        }
        _FAMILY_BOOSTED_TAGS = {
            "family", "family_friendly", "interactive", "outdoor", "nature", "animals",
            "playground", "science", "activity", "water_activity", "kids_attractions",
            "amusement_park", "zoo", "aquarium"
        }
        _fam_penalty_tags = _FAMILY_PENALIZED_TAGS & _poi_tags_73
        _fam_boost_tags = _FAMILY_BOOSTED_TAGS & _poi_tags_73
        if _fam_penalty_tags:
            _fam_penalty = -25.0
            score += _fam_penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [FAMILY_KIDS PENALTY] {poi_name_safe}: {_fam_penalty:.1f} (inappropriate tags: {_fam_penalty_tags})")
        if _fam_boost_tags:
            _fam_boost = 15.0
            score += _fam_boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [FAMILY_KIDS BOOST] {poi_name_safe}: +{_fam_boost:.1f} (family-friendly tags: {_fam_boost_tags})")

    score += calculate_budget_score(p, user)
    score += calculate_premium_penalty(p, user)  # CLIENT REQUIREMENT (08.02.2026): Premium experience penalty at budget/standard levels

    # FIX #28 (17.05.2026): Poor value-for-time penalty at budget_level=1
    # Issue: "Figury Woskowe" (30min, 45 PLN) appears at budget_level=1 - bad value ratio
    # Rule: cost_per_min > 1.2 PLN/min AND budget_level <= 1 → heavy penalty
    _budget_level = safe_int(user.get("budget_level", 2), 2)
    _ticket_normal = float(p.get("ticket_normal") or 0)
    _time_min_poi = float(p.get("time_min") or 60)
    if _budget_level <= 1 and _time_min_poi > 0 and _ticket_normal > 0:
        _cost_per_min = _ticket_normal / _time_min_poi
        if _cost_per_min > 1.2:  # > 1.2 PLN/min at budget level = poor value
            _poor_value_penalty = -35.0
            score += _poor_value_penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [POOR VALUE PENALTY] {poi_name_safe}: {_poor_value_penalty} (cost_per_min={_cost_per_min:.2f} PLN/min at budget_level={_budget_level})")

    # FIX #49 (20.05.2026): Budget level 3 premium boost
    # Issue: budget_level=3 (900 PLN/day) users not getting premium restaurants/spa
    # Zakopane premium POIs: Terma Bania (~190 PLN), Termy Gorący Potok (~236 PLN)
    # Solution: Boost expensive POIs (+60) and penalize cheap ones (-30) for premium travelers
    if _budget_level >= 3:
        if _ticket_normal >= 100:  # Premium experience (100+ PLN/person)
            _premium_boost = 60.0
            score += _premium_boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [PREMIUM BOOST] {poi_name_safe}: +{_premium_boost:.1f} (ticket={_ticket_normal:.0f} PLN, budget_level={_budget_level})")
        elif _ticket_normal > 0 and _ticket_normal <= 20:  # Cheap POI at premium budget = mismatch
            _cheap_penalty = -30.0
            score += _cheap_penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [CHEAP PENALTY] {poi_name_safe}: {_cheap_penalty:.1f} (ticket={_ticket_normal:.0f} PLN too cheap for budget_level={_budget_level})")

    score += calculate_crowd_score(p, user, current_time_minutes=now)  # Added current_time for peak_hours
    
    # BUGFIX (19.02.2026 - UAT Round 2, Issue #6): Crowd_tolerance penalty using crowd_level
    # Tests 04, 05, 06, 08: crowd_tolerance=1 users get popular POI with "Low-crowd" label
    # Problem: Used popularity_score (must-see value), not crowd_level (actual crowding)
    # Examples: Morskie Oko, Krokiew, Krupówki marked as "Low-crowd" despite high crowds
    # Solution: Use crowd_level (1=low, 2=medium, 3=high) for penalty, stronger weights
    # FIX #90 (28.05.2026): Force crowd_level=3 for known high-crowd landmarks regardless of Excel data.
    # These places are always extremely crowded — wrong Excel value causes misleading "peaceful" tags.
    _KNOWN_HIGH_CROWD = {
        "morskie oko", "krupówki", "krupowki", "gubałówka", "gubalowka",
        "kasprowy wierch", "czarny staw", "dolina kościeliska", "dolina koscieliska",
        "dolina chochołowska", "dolina chocholowska", "siklawa",
    }
    _poi_name_lower_crowd = str(p.get("name", "")).lower()
    if any(_known in _poi_name_lower_crowd for _known in _KNOWN_HIGH_CROWD):
        crowd_level_str = "3"  # Override to high-crowd
    else:
        crowd_level_str = str(p.get("crowd_level", "")).strip()
    crowd_tolerance = safe_int(user.get("crowd_tolerance", 1), 1)
    
    # Parse crowd_level to int (may be "1", "2", "3" or empty)
    try:
        crowd_level = int(crowd_level_str) if crowd_level_str else 0
    except (ValueError, TypeError):
        crowd_level = 0
    
    if crowd_tolerance <= 1:  # Low tolerance users
        if crowd_level >= 3:  # High crowd POI
            # Strong penalty (70% reduction) - client suggested *= 0.3
            # Using additive: -40 points (more than priority_bonus)
            penalty = -40.0
            score += penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [CROWD PENALTY] {poi_name_safe}: {penalty} (crowd_level={crowd_level}, tolerance={crowd_tolerance})")
        elif crowd_level == 2:  # Medium crowd POI
            # Moderate penalty (30% reduction)
            penalty = -20.0
            score += penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [CROWD PENALTY] {poi_name_safe}: {penalty} (crowd_level={crowd_level}, tolerance={crowd_tolerance})")

    # ETAP 1 ROZSZERZONY - preferences + travel_style
    score += calculate_preference_score(p, user)
    score += calculate_travel_style_score(p, user)
    
    # FIX #Problem6 (CLIENT FEEDBACK 03.05.2026 - Round 2): Strong preference boost + mismatch penalty
    # Tests 03, 07, 09, 10: Generic high-priority POI dominate despite strong user preferences
    # Test-03: active_sport+mountain_trails gets museums (poi_22, poi_24, poi_26) instead of szlaki
    # Test-07: underground preference gets szlaki instead of underground POI
    # Test-09: nature_landscape+relaxation gets museums/kulig instead of termy
    # Test-10: water_attractions+relaxation gets poi_20 (Wielka Krokiew) instead of termy
    # Problem: Existing preference scoring (+15-30 pts) insufficient to overcome priority bonus (+12)
    # Solution: Strong boost when matching (+50-100 pts), penalty when mismatching (-30 pts)
    
    # Calculate top 3 user preferences (highest priority)
    top_3_preferences = set(user_preferences[:3]) if user_preferences else set()
    poi_tags_set = set(p.get("tags", []))
    travel_style = user.get("travel_style", "")
    
    # DEBUG: Log values for troubleshooting
    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
    print(f"[PREF DEBUG] POI={poi_name_safe} | user_prefs={user_preferences} | top_3={top_3_preferences} | poi_tags={poi_tags_set}")
    
    # Check if POI matches ANY of top 3 preferences
    if top_3_preferences and poi_tags_set:
        # Check for tag overlap between user preferences and POI tags
        # USER_PREFERENCES_TO_TAGS maps preferences to expected tags
        # Import needed for special case detection
        from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
        
        # Check each top 3 preference
        strong_match = False
        match_count = 0
        
        for pref in top_3_preferences:
            pref_mapping = USER_PREFERENCES_TO_TAGS.get(pref, {})
            expected_tags = set(pref_mapping.get("tags", []))
            
            # Check if POI has ANY of the expected tags
            if expected_tags & poi_tags_set:
                match_count += 1
                strong_match = True
        
        if strong_match:
            # Strong preference boost: +50 pts base, +25 pts per additional matching preference
            preference_boost = 50.0 + (match_count - 1) * 25.0
            score += preference_boost
            
            # SPECIAL HANDLERS - extra boosts for specific preference combinations
            
            # 1. water_attractions: Termy should dominate (thermal_baths tags)
            if "water_attractions" in top_3_preferences:
                if "thermal_baths" in poi_tags_set or "hot_springs" in poi_tags_set:
                    extra_boost = 30.0
                    score += extra_boost
                    print(f"    [WATER EXTRA] {poi_name_safe}: +{extra_boost:.1f} (thermal_baths match)")
            
            # 2. active_sport + mountain_trails: Szlaki should dominate over museums
            if ("active_sport" in top_3_preferences or "mountain_trails" in top_3_preferences):
                if "hiking" in poi_tags_set or "mountain_trails" in poi_tags_set or "alpine_activities" in poi_tags_set:
                    extra_boost = 30.0
                    score += extra_boost
                    print(f"    [ACTIVE EXTRA] {poi_name_safe}: +{extra_boost:.1f} (mountain activity match)")
            
            # 3. relaxation + relax style: Low-intensity activities prioritized
            if "relaxation" in top_3_preferences and travel_style == "relax":
                if "low_intensity_activity" in poi_tags_set or "thermal_relax_focus" in poi_tags_set or "relax_zone" in poi_tags_set:
                    extra_boost = 30.0
                    score += extra_boost
                    print(f"    [RELAX EXTRA] {poi_name_safe}: +{extra_boost:.1f} (low-intensity relax match)")
        
        elif user_preferences:  # User has preferences but POI doesn't match ANY
            # Mismatch penalty: User wants specific experiences, POI provides something else
            # Apply penalty for high-priority generic POI (museums, galleries, viewpoints, landmarks)
            poi_type = str(p.get("type_of_attraction", "")).lower()
            generic_types = ["museum", "gallery", "historic_building", "viewpoint"]
            
            # FIX #Problem6 (Round 2): Extend tag check to cover viewpoints/landmarks
            is_generic = any(t in poi_type for t in generic_types) or \
                         any(t in str(p.get("tags", [])).lower() for t in [
                             "museum", "gallery", "architecture_heritage", 
                             "viewpoint", "scenic_spot", "landmark", "photo_spot"
                         ])
            
            if is_generic and priority_value >= 6:  # Generic high-priority POI
                mismatch_penalty = -30.0
                score += mismatch_penalty
    
    # FIX #17 (24.02.2026 - TEST-06 COMPREHENSIVE FIX): Enhanced budget utilization boost
    # Problem: FIX #14 (+30 pts at <30%) insufficient for high daily_limit (500 zł/day).
    # TEST-06 results: Budget utilization 10.3% (154/1500 zł), engine selecting cheap museums over premium POI.
    # Root cause: +30 pts boost cannot overcome ~45pt gap between museums (~73 pts) and Termy (~25 pts).
    # Solution: Stronger progressive boost (60-80 pts), higher threshold (50%), severity-based scaling.
    if daily_limit is not None:
        utilization = daily_cost / daily_limit if daily_limit > 0 else 0
        poi_cost = calculate_poi_cost_for_group(p, user)
        
        if utilization < 0.5 and poi_cost > 0:  # Under 50% utilized (was 30%)
            # Progressive boost based on underutilization severity
            if utilization < 0.2:  # Severe underutilization (<20%)
                boost_multiplier = 80.0  # Was 30.0 - strong incentive for premium POI
            elif utilization < 0.35:  # Moderate underutilization (<35%)
                boost_multiplier = 60.0
            else:  # Mild underutilization (<50%)
                boost_multiplier = 40.0
            
            budget_boost = (poi_cost / daily_limit) * boost_multiplier
            score += budget_boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [BUDGET BOOST] {poi_name_safe}: +{budget_boost:.1f} (utilization={utilization*100:.0f}%, POI cost={poi_cost:.0f} PLN)")
    
    # FIX #Problem8 (13.05.2026 - Round 2): Budget overflow penalty
    # Problem: test-10 budget level 1 (200 PLN/day), first POI = Terma Bania 190 PLN (95% of limit)
    # Issue: First attraction consumes almost entire daily budget, leaving no room for variety
    # Solution: Heavy penalty for POI costing >70% of daily_limit when budget barely used
    if daily_limit is not None and daily_limit > 0:
        poi_cost = calculate_poi_cost_for_group(p, user)
        cost_ratio = poi_cost / daily_limit  # What % of daily budget this POI consumes
        utilization = daily_cost / daily_limit  # What % of budget already spent
        
        # Only penalize expensive POI when budget is still mostly available (utilization < 50%)
        # This prevents expensive POI from being selected first, but allows them later if needed
        if cost_ratio > 0.70 and utilization < 0.50:
            # Penalty scales with how expensive the POI is relative to budget
            # 70% cost → -50 points, 80% cost → -60 points, 95% cost → -80 points
            overflow_penalty = -50 * (cost_ratio / 0.70)
            score += overflow_penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [BUDGET OVERFLOW PENALTY] {poi_name_safe}: {overflow_penalty:.1f} (cost={poi_cost:.0f} PLN = {cost_ratio*100:.0f}% of {daily_limit} PLN limit)")
    
    # BUGFIX (19.02.2026 - UAT Round 2, Issue #5): Travel style preference boost
    # Problem: Tests 03, 05, 06, 09 show travel_style not properly boosting matching preferences
    # Test 03: friends+adventure gets museums instead of trails (active_sport ignored)
    # Test 05, 06, 09: relax style gets museums instead of spa/termy (relaxation ignored)
    # Solution: Boost score when travel_style aligns with POI tags + user preferences
    travel_style = user.get("travel_style", "")
    poi_tags = set(p.get("tags", []))
    
    if travel_style == "relax":
        # Boost relaxation POI for relax travelers
        relax_tags = {"relaxation", "spa", "termy", "wellness", "hot_springs", "water_attractions"}
        if relax_tags & poi_tags:
            boost = score * 0.5  # 50% boost
            score += boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [RELAX BOOST] {poi_name_safe}: +{boost:.1f} (relax style + relaxation tags)")
        
        # Penalty for active POI for relax travelers
        # FIX #154: Skip penalty if POI actually matches a user preference
        # (e.g., travel_style=relax but user explicitly picked hiking preference)
        active_tags = {"active_sport", "hiking", "climbing", "mountain_trails"}
        if active_tags & poi_tags and not poi_matches_preferences:
            penalty = score * 0.3  # 30% penalty
            score -= penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [RELAX PENALTY] {poi_name_safe}: -{penalty:.1f} (relax style conflicts with active)")

        # FIX #48 (20.05.2026): Museum penalty for relax/water users without museum preference
        # Issue: Muzeum Tatrzańskie appears for water_attractions/relax users (test-10) as filler
        # Adventure already has 55% museum penalty; relax users with no museum pref need similar protection
        _museum_tags_48 = {
            "museums", "museum_heritage", "culture",
            "themed_museum", "regional_heritage", "mountain_culture",
            "multimedia_exhibition", "interactive_exhibits", "interactive_exhibit",
            "local_history", "architecture_heritage", "historic_building",
            "composer_artist_house", "intimate_small_museum", "ethnographic_museum",
            "art_gallery", "temporary_exhibitions"
        }
        _user_prefs_48 = user.get("preferences", [])
        # FIX #153: Also skip penalty if POI actually matches any user preference.
        # Example: family_kids+relaxation user has Iluzja Park (interactive_exhibits tag) —
        # interactive_exhibits is a museum tag BUT the POI serves kids_attractions preference.
        # poi_matches_preferences is already computed earlier in score_poi, reuse it here.
        if _museum_tags_48 & poi_tags and "museum_heritage" not in _user_prefs_48 and not poi_matches_preferences:
            _museum_relax_penalty = score * 0.35  # 35% penalty for relax users with no museum preference
            score -= _museum_relax_penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [RELAX MUSEUM PENALTY] {poi_name_safe}: -{_museum_relax_penalty:.1f} (relax style + no museum_heritage pref)")

    elif travel_style == "adventure":
        # FIX #36 (19.05.2026): Gate active/mountain boosts on user having outdoor preferences.
        # Bug: JSON 7 (underground+history+museum + adventure) had Kopieniec mountain trail selected
        # because the 50%+100% adventure boost applied to ALL adventure plans regardless of preferences.
        # Fix: Only apply active/mountain boosts when user preferences include at least one outdoor pref.
        outdoor_preference_keys = {"hiking", "outdoor", "nature", "mountain_trails", "trekking", "active_sport", "climbing"}
        user_has_outdoor_prefs = bool(outdoor_preference_keys & set(user_preferences))
        
        if user_has_outdoor_prefs:
            # Boost active POI for adventure travelers with outdoor preferences
            # Includes both generic tags AND Zakopane-specific trail tags
            active_tags = {
                "active_sport", "hiking", "climbing", "mountain_trails", "outdoor", "sports",
                # Zakopane actual trail tags
                "easy_walk", "moderate_hike", "forest_trails", "nature_immersion",
            }
            poi_type_str = str(p.get("type", "")).lower()
            if (active_tags & poi_tags) or poi_type_str == "trail":
                boost = score * 0.5  # 50% boost
                score += boost
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"    [ADVENTURE BOOST] {poi_name_safe}: +{boost:.1f} (adventure style + active tags + outdoor prefs)")
            
            # FIX #11 (22.02.2026 - UAT Round 3, TEST-03 HYBRID Solution):
            # CRITICAL: Mountain POI boost for adventure + mountain_trails preference
            # Problem: TEST-03 (adventure + mountain_trails) gets museums > hiking trails
            # Only 1/11 POIs was hiking (9%), 6/11 were museums (54%)
            # Solution: Strong boost (100%) for mountain/hiking POIs to prioritize over indoor attractions
            mountain_tags = {
                "hiking", "mountain_trail", "scenic_viewpoint", "cable_car",
                "funicular", "mountain_lake", "alpine", "trekking", "peak",
                # Zakopane actual mountain/trail tags
                "viewpoint_trail", "panoramic_route", "peak_summit", "cable_car_option",
                "scenic_ridge_walk", "mountain_views", "tatra_viewpoint", "panoramic_mountain_views",
                "waterfall_trail", "out_and_back",
            }
            if mountain_tags & poi_tags:
                boost = score * 1.0  # 100% boost (DOUBLE score for mountain POIs)
                score += boost
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"    [MOUNTAIN BOOST] {poi_name_safe}: +{boost:.1f} (adventure + mountain tags)")

        # FIX #53 (20.05.2026): Boost group activities / escape rooms / kulig for adventure travelers
        # Issue: Friends+adventure (test-03) gets museums/galleries instead of escape rooms, kulig
        # These are indoor group activities that don't require outdoor prefs but ARE adventure-appropriate
        _group_activity_tags = {"escape_room", "kulig", "group_activity", "winter_sports",
                                 "active_entertainment", "team_activity", "horror_attraction"}
        if _group_activity_tags & poi_tags:
            _ga_target = user.get("target_group", "")
            if _ga_target in ("friends", "solo", "couples"):
                _ga_boost = score * 0.8  # 80% boost (strong preference for group activities)
                score += _ga_boost
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"    [GROUP ACTIVITY BOOST] {poi_name_safe}: +{_ga_boost:.1f} (adventure + group activity tags + {_ga_target})")

        else:
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [ADVENTURE BOOST] {poi_name_safe}: skipped active/mountain boost (no outdoor preferences)")
        
        # FIX #8 (22.02.2026 - UAT Round 3, TEST-03 Issue):
        # CRITICAL: Hard penalty for relaxation/wellness/spa POI for adventure travelers
        # Problem (TEST-03): Termy Gorący Potok (236 zł, 62% of budget) selected for adventure group
        # Solution: Strong penalty for relaxing/wellness POI (like relax→active penalty)
        # Client feedback: "active_sport" preference completely unmet, got thermal pools instead
        relax_tags = {"relaxation", "spa", "termy", "wellness", "hot_springs", "thermal_baths", "water_wellness"}
        # FIX #154: Skip penalty if POI matches a user preference (e.g., adventure + relaxation pref)
        if relax_tags & poi_tags and not poi_matches_preferences:
            penalty = score * 0.5  # 50% penalty (strong, matching relax→active penalty)
            score -= penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [ADVENTURE PENALTY] {poi_name_safe}: -{penalty:.1f} (adventure style conflicts with spa/wellness)")
        
        # FIX #8.2 (22.02.2026): Penalty for family attractions for adventure travelers
        # Problem (TEST-03): Tatrzańskie Mini Zoo (160 zł, 41% of budget) selected for adventure group
        # Family attractions don't match adventure/active_sport preferences
        # Note: 40% penalty is OPTIMAL - increasing to 50% caused catastrophic regression (90→55 score)
        family_tags = {"kids_attractions", "family_friendly", "zoo", "aquarium", "children"}
        if family_tags & poi_tags:
            penalty = score * 0.4  # 40% penalty (KEEP THIS VALUE - validated working)
            score -= penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [ADVENTURE PENALTY] {poi_name_safe}: -{penalty:.1f} (adventure style conflicts with family attractions)")
        
        # FIX #27 (17.05.2026): Museum penalty for adventure travelers.
        # Bug: old set {museums, museum_heritage, culture} didn't match actual Zakopane tags
        # (themed_museum, regional_heritage, multimedia_exhibition, etc.) → penalty never applied!
        # Fix: Expanded to cover actual tag values used in POI data.
        museum_tags = {
            "museums", "museum_heritage", "culture",  # legacy tags
            "themed_museum", "regional_heritage", "mountain_culture",  # Zakopane actual
            "multimedia_exhibition", "interactive_exhibits", "interactive_exhibit",
            "local_history", "architecture_heritage", "historic_building",
            "composer_artist_house", "intimate_small_museum", "ethnographic_museum",
            "art_gallery", "temporary_exhibitions"
        }
        # FIX #154: Skip museum penalty if user explicitly wants museum_heritage or the POI
        # matches any user preference — preferences are the primary signal, travel_style is secondary.
        if museum_tags & poi_tags and not poi_matches_preferences:
            penalty = score * 0.55  # FIX #31 (18.05.2026): 55% penalty (was 35% - still too many museums in adventure plans)
            score -= penalty
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [ADVENTURE PENALTY] {poi_name_safe}: -{penalty:.1f} (adventure style prefers active over culture)")
    
    # ETAP 3 PHASE 5 (27.04.2026): CULTURAL BONUS for city tourism
    # City tourism trips boost museums, cultural sites, historical attractions
    # Router calculates cultural_bonus=1.5 for city_tourism trip type
    cultural_multiplier = scoring_weights.get("cultural_bonus", 1.0)
    if cultural_multiplier > 1.0:
        cultural_tags = {"museums", "museum_heritage", "culture", "history", "historical_sites", 
                        "cultural_attractions", "art", "architecture"}
        poi_tags = set(p.get("tags", []))
        if cultural_tags & poi_tags:
            # Apply cultural boost (multiplicative on current score)
            cultural_boost = score * (cultural_multiplier - 1.0)  # 50% boost for city_tourism
            score += cultural_boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [CULTURAL BOOST] {poi_name_safe}: +{cultural_boost:.1f} (city tourism + cultural tags, cultural_bonus={cultural_multiplier})")
    
    # ETAP 3 PHASE 5 (27.04.2026): CONVENIENCE BONUS for city tourism
    # City tourism prioritizes accessible POI (low crowd_level, good location, easy access)
    # Router calculates convenience_bonus=1.2 for city_tourism trip type
    convenience_multiplier = scoring_weights.get("convenience_bonus", 1.0)
    if convenience_multiplier > 1.0:
        # Convenience indicators: low crowd_level (1-2), indoor space (weather-independent)
        crowd_level_str = str(p.get("crowd_level", "")).strip()
        try:
            crowd_level = int(crowd_level_str) if crowd_level_str else 999
        except (ValueError, TypeError):
            crowd_level = 999
        
        space = p.get("space", "")
        is_convenient = (crowd_level <= 2) or (space == "indoor")
        
        if is_convenient:
            # Apply convenience boost (multiplicative on current score)
            convenience_boost = score * (convenience_multiplier - 1.0)  # 20% boost for city_tourism
            score += convenience_boost
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            convenience_reason = "low crowd" if crowd_level <= 2 else "indoor space"
            print(f"    [CONVENIENCE BOOST] {poi_name_safe}: +{convenience_boost:.1f} (city tourism + {convenience_reason}, convenience_bonus={convenience_multiplier})")
    
    # FIX #16 (24.02.2026 - TEST-06 COMPREHENSIVE FIX): Explicit Termy boost for relaxation preference
    # CRITICAL: Termy are premium relaxation experiences that should DOMINATE when user wants relaxation.
    # Problem: TEST-06 (relaxation preference + relax style) got 0% Termy, 75% museums (6/8 POI museums, 0 Termy).
    # Root cause: 
    #   - Relaxation is 3rd preference (weaker than museum_heritage 1st)
    #   - Termy expensive (~150 zł) → premium penalty (-20 pts)
    #   - Existing relax boost (+50% multiplicative) insufficient for low base scores
    #   - Museums score ~73 pts (must_see + preference), Termy score ~25 pts → 48pt gap
    # Solution: 
    #   - Strong additive +60 pts boost when Termy + relaxation preference (overcome museum dominance)
    #   - Additional +30 pts if relax travel_style matches (total +90 pts)
    #   - Negate premium penalty for Termy (justified expense for relaxation goal)
    # Expected impact: Termy 25 + 60 + 30 + 20 = 135 pts > Museums 73 pts [OK]
    user_preferences = user.get("preferences", [])
    if "relaxation" in user_preferences and is_termy_spa(p):
        # Base Termy boost for having relaxation preference
        termy_boost = 60.0  # Strong boost to compete with museums (~70 pts baseline)
        score += termy_boost
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        print(f"    [TERMY BOOST] {poi_name_safe}: +{termy_boost:.1f} (relaxation preference, combat museum dominance)")
        
        # Additional boost if relax travel_style matches (reinforces intent)
        if user.get("travel_style") == "relax":
            style_boost = 30.0
            score += style_boost
            print(f"    [TERMY BOOST] {poi_name_safe}: +{style_boost:.1f} (relax style match)")
        
        # Negate premium penalty for Termy (justified expense for relaxation goal)
        # Premium penalty already applied earlier (~-20 pts), add it back
        penalty_negation = 20.0
        score += penalty_negation
        print(f"    [TERMY BOOST] {poi_name_safe}: +{penalty_negation:.1f} (premium penalty negated - justified expense)")
    
    # FIX #19 (29.04.2026 - CLIENT FEEDBACK): Penalty for kids-focused POI for non-family groups
    # Problem: JSON 2 (couples + cultural + relaxation) has too many family attractions
    #          Dom do góry nogami, Papugarnia appear in couples+cultural plan
    # Requirement: Couples+cultural should get museums, galleries, termy, cultural sites
    #             NOT kids attractions (aquarium, playground, upside-down house)
    # Solution: Strong penalty for kids-focused POI when target_group != family_kids
    #          Extra penalty if user has cultural/relaxation preferences (clear mismatch)
    target_group = user.get("target_group", "solo")
    if target_group != "family_kids" and is_kids_focused_poi(p):
        # Base penalty: Kids POI inappropriate for non-family groups
        kids_penalty = -80.0
        score += kids_penalty
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        print(f"    [KIDS PENALTY] {poi_name_safe}: {kids_penalty:.1f} (target_group={target_group}, kids-focused POI inappropriate)")
        
        # Extra penalty if user has cultural/relaxation preferences
        # These profiles CLEARLY don't want kids attractions
        user_preferences = user.get("preferences", [])
        if "cultural" in user_preferences or "relaxation" in user_preferences:
            extra_penalty = -40.0  # Total -120 penalty for strong mismatch
            score += extra_penalty
            print(f"    [KIDS PENALTY] {poi_name_safe}: {extra_penalty:.1f} (cultural/relaxation preference conflicts with kids POI)")
    
    # FIX #6 (02.02.2026): Priority_level bonus (core: +25, secondary: +10, optional: 0)
    score += calculate_priority_bonus(p, user)
    
    # FEEDBACK KLIENTKI (03.02.2026): Intensity soft scoring
    score += calculate_intensity_score(p, user)
    
    # CLIENT DATA UPDATE (05.02.2026): Tag-based preference scoring
    # NOTE: tag_bonus already calculated above in must_see conditional logic
    # Add the bonus to score here with logging
    if tag_bonus > 0:
        score += tag_bonus
        # ASCII-safe print for Windows terminal (polish characters)
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        print(f"    [TAG BONUS] {poi_name_safe}: +{tag_bonus} from preferences {user_preferences}")
    
    # ETAP 1 ENHANCEMENT (29.01.2026) - New scoring modules
    score += calculate_space_score(p, user, context)  # indoor/outdoor vs weather
    score += calculate_weather_dependency_score(p, user, context)  # weather dependency
    score += calculate_type_matching_score(p, user, context)  # type + group/style matching
    score += calculate_time_of_day_score(p, user, context, now)  # recommended_time_of_day

    # POI ROLE LOGIC
    role = p.get("poi_role", "FILLER")

    # prime time dnia (10:00–15:00)
    if 600 <= now <= 900:
        if role == "FILLER":
            score -= 15.0
        if role == "BUFFER":
            score -= 5.0
        if role == "RELAX":
            score += 6.0

    # po 15:00 chcemy RELAX albo FINALE
    if now >= 900:
        if role == "RELAX":
            score += 10.0
        if role == "FILLER":
            score -= 10.0

    # FIX #87 (28.05.2026): Evening energy arc — penalize demanding activities after 16:00.
    # After a full day of sightseeing/hiking, evenings should wind down: termy → café → dinner.
    # Prevents: museums at 17:00, outdoor viewpoints at 16:30, trails at 16:00.
    if now >= 960:  # After 16:00
        _evening_museum_tags = {
            "themed_museum", "regional_heritage", "museum_heritage", "museums",
            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
            "interactive_exhibit", "local_history", "architecture_heritage",
            "historic_building", "composer_artist_house", "intimate_small_museum",
            "ethnographic_museum", "art_gallery", "temporary_exhibitions",
        }
        _poi_tags_eve = set(p.get("tags", []))
        if _evening_museum_tags & _poi_tags_eve:
            score -= 25.0  # Museums feel heavy in the evening
        if p.get("type") == "trail":
            score -= 40.0  # Trails after 16:00 = darkness risk / exhaustion
        _evening_relax_tags = {"relaxation", "spa", "termy", "wellness", "hot_springs", "swimming_pool"}
        if _evening_relax_tags & _poi_tags_eve:
            score += 15.0  # Boost termy/spa in the evening — perfect wind-down
    if now >= 1020:  # After 17:00: even stronger wind-down signal
        _evening_viewpoint_tags = {"scenic_viewpoint"}
        if _evening_viewpoint_tags & set(p.get("tags", [])):
            score -= 20.0  # Viewpoints lose appeal after dark

    # zmeczenie
    score -= float(fatigue)

    # FIX #133 (31.05.2026): Consecutive short POI penalty — discourage 3rd+ short POI in a row
    # When 2+ short POIs (≤35 min) have been added already and THIS candidate is also short,
    # apply an additional -10 penalty to push longer/richer alternatives.
    _f133_time_min = int(p.get("time_min") or 0)
    if _f133_time_min > 0 and _f133_time_min <= 35:
        _f133_consec = (context or {}).get("consecutive_short_count", 0)
        if _f133_consec >= 2:
            score -= 10.0  # 3rd+ consecutive short POI is undesirable

    # FIX #134 (31.05.2026): End-of-day experience lock
    # When < 90 min remain before day end, intensive activities get a penalty.
    # Prevents: museum at 18:30, trail at 18:00 (already covered by FIX #87 but this strengthens
    # the signal for any intensive POI near the end, regardless of exact time-of-day).
    # Complements FIX #87 (which uses absolute clock time); FIX #134 uses remaining day budget.
    _f134_day_end = (context or {}).get("day_end_mins")
    if _f134_day_end is not None:
        _f134_remaining = _f134_day_end - now
        if _f134_remaining < 90:
            _f134_poi_tags = set(p.get("tags", []))
            _f134_intensive = {
                "themed_museum", "regional_heritage", "museum_heritage", "museums",
                "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                "interactive_exhibit", "local_history", "architecture_heritage",
                "art_gallery", "temporary_exhibitions", "composer_artist_house",
                "intimate_small_museum", "ethnographic_museum",
                "scenic_viewpoint", "viewpoint", "panorama",
            }
            if _f134_intensive & _f134_poi_tags:
                score -= 15.0  # Intensive culture/viewpoints feel wrong in last 90 min

    ctx = _get_context(context)

    # pogoda: deszcz + outdoor
    if ctx["precip"] and p.get("space") == "outdoor":
        score -= 5.0

    # FIX #99A: culture streak penalty - group-aware (friends hate consecutive culture more)
    if is_culture(p):
        _target_group_A = str(user.get("target_group", "")).lower()
        if _target_group_A == "friends" and culture_streak >= 1:
            score -= 30.0  # friends: strong penalty after 1st consecutive culture POI
        elif culture_streak >= 2:
            score -= 20.0  # universal: penalty after 2 consecutive culture POIs

    # FIX #99E: active_streak boost for friends (reward consecutive active/outdoor POIs)
    if active_streak >= 1 and str(user.get("target_group", "")).lower() == "friends":
        _ACTIVE_TAGS_99E = {
            "active_sport", "hiking", "climbing", "mountain_trails", "outdoor",
            "sports", "water_activity", "winter_sports", "active_entertainment",
            "kulig", "zipline", "quad_atv", "horse_riding", "cave_tour",
        }
        _poi_type_99E = str(p.get("type", "")).lower()
        _poi_tags_99E = set(p.get("tags", []))
        _is_active_99E = bool(_ACTIVE_TAGS_99E & _poi_tags_99E) or _poi_type_99E in {
            "trail", "active_sport", "adventure_sport", "nature_outdoor",
        }
        if _is_active_99E:
            score += 10.0  # reward continuing active/outdoor streak for friends

    # body state transitions
    score += calculate_body_transition_score(p, body_state)

    # RELAX kiedy cialo tego potrzebuje
    if body_state == "cold" and role == "RELAX":
        score += 12.0

    if body_state == "warm" and role == "BUFFER":
        score += 4.0

    # final dnia
    if is_finale(p):
        if finale_done:
            score -= 100.0  # nie dokladamy drugiego finalu
        else:
            if now >= time_to_minutes("15:00"):
                score += 18.0
            else:
                score -= 25.0  # przed 15:00 final nie ma sensu

    # =============================================================================
    # ETAP 3 PHASE 3 (27.04.2026): TRAIL-SPECIFIC SCORING
    # =============================================================================
    # Trails have different characteristics than POI/restaurants
    # - difficulty_level: easy/moderate/hard/extreme (affects family_kids groups)
    # - exposure_level: low/medium/high/extreme (safety risk)
    # - scenic_score: 0-10 (visual appeal, boost beautiful trails)
    # - family_friendly: bool (pre-vetted safety)
    # =============================================================================
    
    poi_type = p.get("type", "poi")  # NEW: type discrimination (trail|poi|restaurant)
    
    if poi_type == "trail":
        # ETAP 3 PHASE 4 (27.04.2026): Get scoring_weights from router
        # Router calculates trip-level multipliers (scenic_bonus, elevation_bonus, family_safety)
        # These weights customize scoring based on trip type (mountain_hiking vs city_tourism)
        scoring_weights = context.get("scoring_weights", {})
        
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        
        # 1. DIFFICULTY MATCHING (CRITICAL for family_kids safety)
        # Family groups should ONLY get easy/moderate trails
        # Hard/extreme trails get strong penalty (effectively exclude)
        difficulty_level = str(p.get("difficulty_level", "")).lower()
        target_group = user.get("target_group", "")
        
        if target_group == "family_kids":
            if difficulty_level in ["hard", "extreme"]:
                # HARD EXCLUSION: -200 pts (effectively remove from consideration)
                # PHASE 4: Apply family_safety multiplier from router
                family_safety_multiplier = scoring_weights.get("family_safety", 1.0)
                difficulty_penalty = -200.0 * family_safety_multiplier
                score += difficulty_penalty
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: {difficulty_penalty:.1f} (family_kids cannot do {difficulty_level} trails, family_safety={family_safety_multiplier})")
            
            elif difficulty_level == "moderate":
                # CAUTION: Small penalty for moderate trails (prefer easy)
                difficulty_penalty = -15.0
                score += difficulty_penalty
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: {difficulty_penalty:.1f} (family_kids: moderate trail caution)")
            
            elif difficulty_level == "easy":
                # BOOST: Reward easy trails for families
                difficulty_boost = 20.0
                score += difficulty_boost
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: +{difficulty_boost:.1f} (family_kids: perfect easy trail)")
        
        elif target_group == "seniors":
            # PHASE 8 FEATURE #3 (27.04.2026): Elastic trail rules for seniors
            # Default: Only easy trails
            # Moderate allowed ONLY if ALL: elevation ≤200m, length ≤4km, duration ≤120min, exposure=low
            
            if difficulty_level in ["hard", "extreme"]:
                # STRICT: Block hard/extreme trails
                difficulty_penalty = -150.0
                score += difficulty_penalty
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: {difficulty_penalty:.1f} (seniors cannot do {difficulty_level} trails)")
            
            elif difficulty_level == "moderate":
                # PHASE 8 FEATURE #3: Elastic moderate rules
                # Check if trail meets ALL relaxed criteria
                elevation_gain = p.get("elevation_gain_m", 0)
                length_km = p.get("length_km", 0.0)
                duration_min = p.get("duration_min", 0)
                exposure = str(p.get("exposure_level", "low")).lower()
                
                meets_elevation = elevation_gain <= 200  # ≤200m climb
                meets_length = length_km <= 4.0  # ≤4km distance
                meets_duration = duration_min <= 120  # ≤2h time
                meets_exposure = exposure == "low"  # Low exposure only
                
                if meets_elevation and meets_length and meets_duration and meets_exposure:
                    # ALLOW: Moderate trail meets all relaxed criteria
                    difficulty_boost = 5.0  # Small boost (less than easy)
                    score += difficulty_boost
                    print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: +{difficulty_boost:.1f} "
                          f"(seniors: moderate trail ALLOWED - relaxed criteria met: "
                          f"elevation={elevation_gain}m≤200, length={length_km:.1f}km≤4, "
                          f"duration={duration_min}min≤120, exposure={exposure})")
                else:
                    # BLOCK: Moderate trail too demanding
                    difficulty_penalty = -80.0  # Strong penalty
                    score += difficulty_penalty
                    failed_criteria = []
                    if not meets_elevation: failed_criteria.append(f"elevation={elevation_gain}m>200")
                    if not meets_length: failed_criteria.append(f"length={length_km:.1f}km>4")
                    if not meets_duration: failed_criteria.append(f"duration={duration_min}min>120")
                    if not meets_exposure: failed_criteria.append(f"exposure={exposure}≠low")
                    
                    print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: {difficulty_penalty:.1f} "
                          f"(seniors: moderate trail too demanding - failed: {', '.join(failed_criteria)})")
            
            elif difficulty_level == "easy":
                # BOOST: Reward easy trails for seniors
                difficulty_boost = 15.0
                score += difficulty_boost
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: +{difficulty_boost:.1f} (seniors: perfect easy trail)")
        
        elif target_group in ["friends", "couples"]:
            # Friends/couples: boost moderate/hard trails (challenge seekers)
            if difficulty_level in ["moderate", "hard"]:
                difficulty_boost = 15.0
                score += difficulty_boost
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: +{difficulty_boost:.1f} ({target_group}: {difficulty_level} trail bonus)")
            
            elif difficulty_level == "extreme":
                # Even for friends, extreme gets caution penalty (safety)
                difficulty_penalty = -25.0
                score += difficulty_penalty
                print(f"    [TRAIL DIFFICULTY] {poi_name_safe}: {difficulty_penalty:.1f} ({target_group}: extreme trail caution)")
        
        # 2. EXPOSURE LEVEL PENALTY (safety risk - cliffs, ridges, steep slopes)
        # High exposure = dangerous (falls risk), especially for families
        exposure_level = str(p.get("exposure_level", "low")).lower()
        
        if exposure_level in ["high", "extreme"]:
            if target_group == "family_kids":
                # CRITICAL: Hard exclusion for families (safety priority)
                # PHASE 4: Apply exposure_penalty multiplier from router
                exposure_multiplier = scoring_weights.get("exposure_penalty", 1.0)
                exposure_penalty = -150.0 * exposure_multiplier
                score += exposure_penalty
                print(f"    [TRAIL EXPOSURE] {poi_name_safe}: {exposure_penalty:.1f} (family_kids: {exposure_level} exposure UNSAFE, exposure_penalty={exposure_multiplier})")
            
            elif target_group == "seniors":
                # Strong penalty for seniors (balance/mobility concerns)
                exposure_penalty = -100.0
                score += exposure_penalty
                print(f"    [TRAIL EXPOSURE] {poi_name_safe}: {exposure_penalty:.1f} (seniors: {exposure_level} exposure risky)")
            
            else:
                # Moderate penalty for other groups (still risky)
                exposure_penalty = -30.0
                score += exposure_penalty
                print(f"    [TRAIL EXPOSURE] {poi_name_safe}: {exposure_penalty:.1f} ({target_group}: {exposure_level} exposure caution)")
        
        elif exposure_level == "medium":
            if target_group in ["family_kids", "seniors"]:
                # Mild penalty for medium exposure (caution)
                exposure_penalty = -20.0
                score += exposure_penalty
                print(f"    [TRAIL EXPOSURE] {poi_name_safe}: {exposure_penalty:.1f} ({target_group}: medium exposure caution)")
        
        # Low exposure = bonus (safe trails)
        elif exposure_level == "low":
            if target_group in ["family_kids", "seniors"]:
                exposure_boost = 15.0
                score += exposure_boost
                print(f"    [TRAIL EXPOSURE] {poi_name_safe}: +{exposure_boost:.1f} ({target_group}: low exposure safe)")
        
        # 3. SCENIC SCORE BONUS (boost beautiful trails - main appeal of hiking)
        # Trails are chosen for views, not just exercise
        # scenic_score: 0-10 scale (0=unremarkable, 10=breathtaking)
        # PHASE 4: Apply scenic_bonus multiplier from router (mountain_hiking gets 1.5x)
        scenic_score = safe_float(p.get("scenic_score", 0))
        scenic_multiplier = scoring_weights.get("scenic_bonus", 1.0)
        
        if scenic_score >= 8.0:
            # Exceptional views (8-10): strong boost
            scenic_boost = scenic_score * 8.0 * scenic_multiplier  # 64-80 points (96-120 for mountain_hiking)
            score += scenic_boost
            print(f"    [TRAIL SCENIC] {poi_name_safe}: +{scenic_boost:.1f} (exceptional views: {scenic_score}/10, scenic_bonus={scenic_multiplier})")
        
        elif scenic_score >= 6.0:
            # Good views (6-7): moderate boost
            scenic_boost = scenic_score * 5.0 * scenic_multiplier  # 30-35 points (45-52.5 for mountain_hiking)
            score += scenic_boost
            print(f"    [TRAIL SCENIC] {poi_name_safe}: +{scenic_boost:.1f} (good views: {scenic_score}/10, scenic_bonus={scenic_multiplier})")
        
        elif scenic_score >= 4.0:
            # Decent views (4-5): mild boost
            scenic_boost = scenic_score * 3.0 * scenic_multiplier  # 12-15 points (18-22.5 for mountain_hiking)
            score += scenic_boost
            print(f"    [TRAIL SCENIC] {poi_name_safe}: +{scenic_boost:.1f} (decent views: {scenic_score}/10, scenic_bonus={scenic_multiplier})")
        
        # Below 4.0: no bonus (unremarkable trail)
        
        # 4. FAMILY-FRIENDLY PRE-VETTING (additional safety check)
        # family_friendly field = manually vetted safe trails
        # This is SEPARATE from difficulty/exposure (expert curation)
        family_friendly = p.get("family_friendly", False)
        
        if target_group == "family_kids":
            if family_friendly:
                # BOOST: Expert-vetted family trail
                family_boost = 30.0
                score += family_boost
                print(f"    [TRAIL FAMILY] {poi_name_safe}: +{family_boost:.1f} (expert-vetted family trail)")
            else:
                # PENALTY: Not vetted for families (caution)
                family_penalty = -40.0
                score += family_penalty
                print(f"    [TRAIL FAMILY] {poi_name_safe}: {family_penalty:.1f} (not vetted for families)")
        
        # 5. DURATION MATCHING (shorter trails for families/seniors)
        # Families/seniors prefer shorter trails (less fatigue)
        duration_min = safe_int(p.get("duration_min", 0), 0)
        duration_max = safe_int(p.get("duration_max", 0), 0)
        avg_duration = (duration_min + duration_max) / 2 if duration_max > 0 else duration_min
        
        if target_group in ["family_kids", "seniors"]:
            if avg_duration <= 120:  # ≤2 hours: short trail
                duration_boost = 20.0
                score += duration_boost
                print(f"    [TRAIL DURATION] {poi_name_safe}: +{duration_boost:.1f} ({target_group}: short trail {avg_duration:.0f}min)")
            
            elif avg_duration > 240:  # >4 hours: long trail
                duration_penalty = -30.0
                score += duration_penalty
                print(f"    [TRAIL DURATION] {poi_name_safe}: {duration_penalty:.1f} ({target_group}: too long {avg_duration:.0f}min)")
        
        elif target_group == "friends":
            # Friends prefer longer, more challenging trails
            if avg_duration >= 180:  # ≥3 hours: substantial hike
                duration_boost = 15.0
                score += duration_boost
                print(f"    [TRAIL DURATION] {poi_name_safe}: +{duration_boost:.1f} (friends: substantial hike {avg_duration:.0f}min)")
        
        # 6. TRAIL TYPE BOOST (match user preferences)
        # If user wants hiking/outdoor, boost ALL trails
        user_preferences = user.get("preferences", [])
        outdoor_prefs = {"hiking", "outdoor", "nature", "mountain_trails", "trekking"}
        
        if outdoor_prefs & set(user_preferences):
            # User explicitly wants outdoor activities - boost trails
            pref_boost = 25.0
            score += pref_boost
            print(f"    [TRAIL PREFERENCE] {poi_name_safe}: +{pref_boost:.1f} (user wants hiking/outdoor)")
        
        # 7. ELEVATION GAIN PENALTY (steep climbs hard for families/seniors)
        elevation_gain = safe_int(p.get("elevation_gain_m", 0), 0)
        
        if target_group in ["family_kids", "seniors"]:
            if elevation_gain > 400:  # >400m: steep climb
                elevation_penalty = -35.0
                score += elevation_penalty
                print(f"    [TRAIL ELEVATION] {poi_name_safe}: {elevation_penalty:.1f} ({target_group}: steep climb {elevation_gain}m)")
            
            elif elevation_gain < 150:  # <150m: gentle trail
                elevation_boost = 15.0
                score += elevation_boost
                print(f"    [TRAIL ELEVATION] {poi_name_safe}: +{elevation_boost:.1f} ({target_group}: gentle trail {elevation_gain}m)")
        
        elif target_group == "friends":
            # Friends/couples like elevation gain (challenge)
            # PHASE 4: Apply elevation_bonus multiplier from router (mountain_hiking gets 1.2x)
            if elevation_gain > 300:
                elevation_multiplier = scoring_weights.get("elevation_bonus", 1.0)
                elevation_boost = 12.0 * elevation_multiplier
                score += elevation_boost
                print(f"    [TRAIL ELEVATION] {poi_name_safe}: +{elevation_boost:.1f} (friends: challenging climb {elevation_gain}m, elevation_bonus={elevation_multiplier})")
    
    # PHASE 8 FEATURE #6 (27.04.2026): 3-tier POI fallback system
    # Problem: Small cities (Sopot, Kudowa) have few POI matching ALL user preferences
    # Solution: Apply tier-based multiplier based on preference match percentage
    #   Tier 1: Target + ALL preferences (100% match) → score × 1.0 (no change)
    #   Tier 2: Target + ≥50% preferences → score × 0.8
    #   Tier 3: Only target, <50% preferences → score × 0.6
    # This ensures small cities still get POI, but preference-matching POI ranked higher
    
    # FIX #Problem6 (CLIENT FEEDBACK 03.05.2026): 3-TIER FALLBACK must use USER_PREFERENCES_TO_TAGS mapping
    # BUG: Original code compared user_preferences (preference NAMES) vs poi_tags (tag NAMES) directly
    #      ['water_attractions'] vs ['thermal_baths'] → no intersection → 0% match
    # FIX: Use tag_preferences.py mapping to convert preferences to tags before comparison
    
    user_preferences = user.get("preferences", [])
    
    if user_preferences:
        from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
        
        # Calculate preference match percentage using proper tag mapping
        poi_tags = set(p.get("tags", []))
        matched_preferences = set()
        
        for pref in user_preferences:
            pref_mapping = USER_PREFERENCES_TO_TAGS.get(pref, {})
            expected_tags = set(pref_mapping.get("tags", []))
            # Check if POI has ANY of the expected tags for this preference
            if expected_tags & poi_tags:
                matched_preferences.add(pref)
        
        match_percentage = len(matched_preferences) / len(user_preferences) if user_preferences else 0.0
        
        # Determine tier and apply multiplier
        if match_percentage >= 1.0:
            # Tier 1: ALL preferences match
            tier = 1
            multiplier = 1.0
            tier_name = "TIER 1 (100% match)"
        elif match_percentage >= 0.5:
            # Tier 2: ≥50% preferences match
            tier = 2
            multiplier = 0.8
            tier_name = f"TIER 2 ({match_percentage*100:.0f}% match)"
        else:
            # Tier 3: <50% preferences match (only target group matches)
            tier = 3
            multiplier = 0.6
            tier_name = f"TIER 3 ({match_percentage*100:.0f}% match)"
        
        # Apply tier multiplier
        if multiplier < 1.0:
            original_score = score
            score *= multiplier

    # FIX #89 (28.05.2026): Cross-day type diversity penalty for long trips.
    # After day 3+, penalise POI types (via tags) that have already appeared on >= 2 previous days.
    # Prevents: museum every day, viewpoint every day in 7-day trips.
    # FIX #121 (29.05.2026): Stronger day-scaling penalty for days 5+.
    # Problem: On 7-day trips, penalty -10/-20 wasn't strong enough to prevent tag repetition.
    # FIX #135 (31.05.2026): For solo profile, diversity kicks in from day 2 (not day 4).
    # Solo travellers explore intensively and repeat types feel stale much sooner.
    _global_type_tracking = (context or {}).get("global_type_tracking")
    _current_day = (context or {}).get("current_day_num", 1)
    _is_solo_135 = str(user.get("target_group", "")).lower() == "solo"
    _diversity_threshold = 2 if _is_solo_135 else 4
    if _global_type_tracking and _current_day >= _diversity_threshold:
        _poi_tags_variety = set(p.get("tags", []))
        # Only penalize category-level tags (not every tag)
        _diversity_tag_types = {
            "themed_museum", "regional_heritage", "museum_heritage", "museums",
            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
            "scenic_viewpoint", "viewpoint", "panorama",
            "rope_park", "adventure_park", "snow_tubing",
            "relaxation", "spa", "termy", "wellness",
            # FIX #121: Additional common over-represented types
            "nature_landscape", "nature_immersion", "valley_landscape",
            "local_food", "food_market", "local_food_experience",
            "cultural_heritage", "history_mystery", "historical_site",
        }
        # FIX #121: Scale penalty with day number — later days need stronger push toward variety
        # FIX #135: For solo, scale starts earlier — day2=0.5×, day3+=1.0×, day5+=1.5×
        if _is_solo_135:
            _day_scale = 0.5 if _current_day < 3 else (1.0 if _current_day < 5 else 1.5)
        else:
            _day_scale = 1.0 if _current_day < 5 else (1.5 if _current_day < 7 else 2.0)
        for _tag in _poi_tags_variety & _diversity_tag_types:
            _tag_days_used = _global_type_tracking.get(_tag, 0)
            if _tag_days_used >= 4:
                score -= 35.0 * _day_scale  # FIX #121: Very heavy for 4+ repeats
            elif _tag_days_used >= 3:
                score -= 20.0 * _day_scale  # Scaled heavy penalty: 3+ days with this type
            elif _tag_days_used >= 2:
                score -= 10.0 * _day_scale  # Scaled mild penalty: already seen on 2 days

    return score


# =========================
# Multi-day Planner
# =========================


def plan_multiple_days(pois, user, contexts, day_start, day_end, warnings_out=None, pois_per_day=None):
    """
    Build multi-day plan with cross-day POI tracking and core POI distribution.
    
    ETAP 2 - DAY 3 (15.02.2026): Multi-day planning core.
    
    Key features:
    - Cross-day POI tracking: No duplicate POIs across days
    - Core POI distribution: Spread core attractions across days (not all on Day 1)
    - Day-to-day energy continuity: Reset energy each day but track usage patterns
    
    Args:
        pois: List of POI dicts (fallback if pois_per_day not provided)
        user: User dict (preferences, target_group, etc.)
        contexts: List of context dicts (one per day - season, date, weather, etc.)
        day_start: Start time string "HH:MM"
        day_end: End time string "HH:MM"
        pois_per_day: Optional list[list] — per-day POI pool override (FIX #113: zone system)
    
    Returns:
        List of day plans (list of dicts, one per day)
    """
    print(f"[PLAN_MULTIPLE_DAYS CALLED] num_days={len(contexts)}")
    num_days = len(contexts)
    
    # Global tracking across ALL days
    global_used_pois = set()
    
    # UAT FIX (18.02.2026 - Problem #6): Track termy/spa count across all days
    # Test 08: 5 termy in 7 days is too much
    # Limit: max 2-3 termy in 7+ day plans (1 termy per 2-3 days)
    
    # FIX #15 (29.04.2026 - CLIENT FEEDBACK): Reduce termy limits
    # Problem: JSON 2 had 3 termy in 3 days (Chochołowskie, Bukovina, Bania) - too much
    # Requirement: Max 1-2 termy for 3 days (not 3)
    # Solution: More restrictive limit (1 termy per 3 days), boost if relaxation priority
    
    # Base limit: 1 termy per 3 days
    # 3-day: 1 termy, 5-day: 1 termy, 7-day: 2 termy, 9-day: 3 termy
    max_termy_total = max(1, num_days // 3)
    
    # FIX #Problem6 (Round 2 - 11.05.2026): Expand boost for water_attractions preference
    # Problem: Test-10 (2 days, water_attractions + relaxation) limited to 1 termy, user expects 2
    # Root cause: Boost only triggered by relaxation in TOP 2, and cap was num_days // 2 (blocks 2-day boost)
    # Solution: Trigger boost if water_attractions OR relaxation in TOP 3, remove restrictive cap
    # Boost limit if relaxation OR water_attractions in TOP 3 preferences
    # Rationale: Both preferences strongly indicate user wants termy/spa experiences
    user_prefs = user.get("preferences", [])
    if "relaxation" in user_prefs[:3] or "water_attractions" in user_prefs[:3]:
        # Allow +1 termy, capped at num_days (max 1 termy per day for strong preference)
        max_termy_total = min(max_termy_total + 1, num_days)
        print(f"[MULTI-DAY] Termy limit BOOSTED (water/relax top-3): {max_termy_total} for {num_days} days")
    else:
        print(f"[MULTI-DAY] Termy limit (base): {max_termy_total} for {num_days} days")
    
    global_termy_tracking = {"count": 0, "max": max_termy_total}
    
    print(f"[MULTI-DAY] Final termy limit: max {max_termy_total} termy for {num_days} days")
    
    # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #5): Track trail count across all days
    # Problem: No limits on trails per trip (could have 5 trails in 3 days)
    # Solution: Limit based on trip duration
    #   - 2-3 days → max 1 trail
    #   - 4-5 days → max 2 trails
    #   - 6-7 days → max 3 trails
    
    # FIX #12 (29.04.2026 - CLIENT FEEDBACK): Adjust trail limits per target_group
    # Problem: family_kids got 3 trails in 3 days (Nosal, Wielki Kopieniec, Sarnia Skała)
    # Requirement: Max 1 trail for family_kids in 3-day plan
    # Solution: More restrictive limits for family/seniors, standard for friends/solo
    
    # Base limit by trip length
    if num_days <= 3:
        base_max_trails = 1
    elif num_days <= 5:
        base_max_trails = 2
    else:
        base_max_trails = 3
    
    # Adjust for target_group
    target_group = user.get("target_group", "solo")
    
    if target_group == "family_kids":
        # Family: VERY conservative (1 trail per 3-4 days)
        # 3-day: 1 trail, 5-day: 1 trail, 7-day: 1 trail, 8-day: 2 trails
        max_trails_total = max(1, num_days // 4)
        print(f"[MULTI-DAY] Trail limit for family_kids: VERY conservative ({max_trails_total} trails for {num_days} days)")
    
    elif target_group == "seniors":
        # Seniors: conservative (1 trail per 2-3 days)
        # 3-day: 1 trail, 5-day: 1 trail, 7-day: 2 trails
        max_trails_total = max(1, num_days // 3)
        print(f"[MULTI-DAY] Trail limit for seniors: conservative ({max_trails_total} trails for {num_days} days)")
    
    elif target_group in ["friends", "solo"]:
        # Friends/solo: allow more trails (base limit)
        # 3-day: 1 trail, 5-day: 2 trails, 7-day: 3 trails
        max_trails_total = base_max_trails
        print(f"[MULTI-DAY] Trail limit for {target_group}: standard ({max_trails_total} trails for {num_days} days)")
    
    else:  # couples
        # Couples: moderate (prefer variety, not just hiking)
        # 3-day: 1 trail, 5-day: 1 trail, 7-day: 2 trails
        max_trails_total = max(1, base_max_trails - 1)
        print(f"[MULTI-DAY] Trail limit for couples: moderate ({max_trails_total} trails for {num_days} days)")

    # FIX #43 (20.05.2026 - Issue F complement): Boost trail limit for mountain_trails preference.
    # Problem: 7-day mountain_trails trip (test-08, couples) only gets 2 trail slots.
    # After 2 trail days + 2 termy days, only ~11 culture POIs remain for 3 days → Days 6-7 empty.
    # Root cause: TrailDB has 10+ trails available but global_trail_limit blocks all after Day 2.
    # Solution: When mountain_trails is a top-3 preference, add extra trail slots so TrailDB
    # trails fill the mountain days rather than exhausting the small culture POI pool.
    # Mountain_trails trip → couples wanting trails, not just city museums!
    # FIX #93 (29.05.2026): Also boost for "hiking" preference and "adventure" travel_style.
    # Problem: 3-day friends+adventure+hiking gets limit=1 → Days 2+ are all free_time.
    # "hiking" is a valid trail preference that should behave like mountain_trails.
    user_prefs_top3 = user.get("preferences", [])[:3]
    travel_style = user.get("travel_style", "balanced")
    _trail_boost_reason = []
    if "mountain_trails" in user_prefs_top3:
        _trail_boost_reason.append("mountain_trails pref")
    if "hiking" in user_prefs_top3:
        _trail_boost_reason.append("hiking pref")
    if travel_style == "adventure":
        _trail_boost_reason.append("adventure style")
    if _trail_boost_reason:
        boost = max(1, num_days // 3)  # 3-day: +1, 5-day: +1, 7-day: +2
        old_limit = max_trails_total
        # For adventure/hiking: one trail per day is expected — set hard floor of num_days
        # For others: leave 2 non-trail days for variety
        if travel_style == "adventure" or "hiking" in user_prefs_top3 or "mountain_trails" in user_prefs_top3:
            max_trails_total = num_days  # Allow a trail on every day
        else:
            max_trails_total = min(num_days - 2, max_trails_total + boost)
        max_trails_total = max(max_trails_total, 1)  # Always allow at least 1
        print(f"[MULTI-DAY] Trail limit BOOSTED ({', '.join(_trail_boost_reason)}): {old_limit} → {max_trails_total}")

    global_trail_tracking = {"count": 0, "max": max_trails_total}

    print(f"[MULTI-DAY] Final trail limit: max {max_trails_total} trails for {num_days} days (target_group={target_group})")
    
    # Core POI distribution strategy
    # Get all core POIs (priority_level == 12)
    core_pois = [p for p in pois if is_core_poi(p)]
    
    print(f"[MULTI-DAY] Planning {num_days} days with {len(core_pois)} core POIs available")
    print(f"[MULTI-DAY] Core POI IDs: {[p.get('poi_id', 'unknown') for p in core_pois]}")
    
    # Get core limits for this target group
    target_group = user.get("target_group", "solo")
    limits = GROUP_ATTRACTION_LIMITS.get(target_group, {
        "soft": 7,
        "hard": 8,
        "core_min": 1,
        "core_max": 2,
    })
    
    # Calculate core POIs to distribute
    # Each day wants core_min (usually 1), but we have limited core POIs
    # Distribute fairly: min(total_core_pois, num_days * core_min)
    total_core_needed = num_days * limits.get("core_min", 1)
    total_core_available = len(core_pois)
    
    # If we have more core POIs than needed, great!
    # If we have fewer, distribute what we have
    cores_to_distribute = min(total_core_available, total_core_needed)
    
    print(f"[MULTI-DAY] Distributing {cores_to_distribute} core POIs across {num_days} days (need {total_core_needed}, have {total_core_available})")
    
    # Build each day with cross-day tracking
    all_day_plans = []

    # FIX #50+#51 (20.05.2026): Consecutive-day protection flags
    # FIX #50: Prevent termy on two consecutive days (rest-day logic)
    # FIX #51: Force recovery day (no trails) after heavy trail (>=240 min)
    _prev_day_had_termy = False
    _prev_day_had_heavy_trail = False

    # FIX #89 (28.05.2026): Cross-day type diversity tracking for long trips (7+ days).
    # Problem: Same POI types (museum, viewpoint, cable car) repeat every day.
    # Solution: Track type usage across days and penalize repetition in score_poi.
    # Format: {"museum_heritage": 2, "scenic_viewpoint": 3, ...}
    global_type_tracking = {}  # tag -> number of days this tag type was represented

    # FIX D (02.06.2026): Sliding-window dedup for long trips (>=5 days, day 6+).
    # Problem: global_used_pois grows to exhaust entire POI pool by day 6-7,
    # leaving late days with no activities ("dead days").
    # Solution: Track per-day POI usage and for day 6+, only block POIs from
    # the last 3 days instead of all previous days.
    _FIX_D_WINDOW = 3   # days to keep blocked (recency window)
    daily_used_sets: list = []  # per-day lists of POI IDs added that day

    for day_num in range(num_days):
        context = contexts[day_num]
        
        print(f"\n[MULTI-DAY] === Building Day {day_num + 1}/{num_days} ===")
        print(f"[MULTI-DAY] Global used POIs so far: {len(global_used_pois)}")

        # FIX #50: Temporarily block termy on this day if previous day had termy
        _termy_count_save = None
        if _prev_day_had_termy and num_days > 1:
            _termy_count_save = global_termy_tracking["count"]
            global_termy_tracking["count"] = global_termy_tracking["max"]
            print(f"[FIX #50] Day {day_num + 1}: Blocking termy (consecutive-day restriction)")

        # FIX #51: Temporarily block trails on this day if previous day had heavy trail
        # FIX #93 (29.05.2026): Skip recovery day restriction for adventure/hiking profiles.
        # Reason: adventure+hiking users hike every day; recovery makes Day 2 empty (no non-trail POIs).
        _trail_count_save = None
        _user_travel_style = user.get("travel_style", "balanced")
        _user_prefs_top3_51 = user.get("preferences", [])[:3]
        _skip_recovery = (_user_travel_style == "adventure" or "hiking" in _user_prefs_top3_51 or "mountain_trails" in _user_prefs_top3_51)
        if _prev_day_had_heavy_trail and num_days > 1 and not _skip_recovery:
            _trail_count_save = global_trail_tracking["count"]
            global_trail_tracking["count"] = global_trail_tracking["max"]
            print(f"[FIX #51] Day {day_num + 1}: Recovery day - blocking all trails")
        elif _prev_day_had_heavy_trail and _skip_recovery:
            print(f"[FIX #51] Day {day_num + 1}: Heavy trail yesterday but skipping recovery (adventure/hiking profile)")

        # Build day with global tracking
        # The global_used set will be updated inside build_day()
        # UAT FIX (18.02.2026 - Problem #6): Pass termy tracking dict
        # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #5): Pass trail tracking dict
        # FIX #89 (28.05.2026): Inject global_type_tracking into context so score_poi can penalise repetition.
        context["global_type_tracking"] = global_type_tracking
        context["current_day_num"] = day_num + 1  # 1-based day number (used for variety penalty threshold)
        context["num_days"] = num_days  # FIX D: total trip length (for late-trip pool-exhaustion softening)
        _day_warnings: list = []  # FIX #130: collect per-day engine warnings
        # FIX #113 (07.06.2026): Use per-day POI pool if provided (zone system)
        _pois_for_day = pois_per_day[day_num] if pois_per_day is not None else pois

        # FIX D (02.06.2026): For day 6+ in a 5+ day trip, pass only a RECENT WINDOW of used POIs.
        # This lets the engine re-consider POIs from early days (days 1-2) so late days aren't empty.
        _fixd_use_window = (num_days >= 5 and day_num >= 5)
        if _fixd_use_window:
            _window_used: set = set()
            for _prev_set in daily_used_sets[-_FIX_D_WINDOW:]:
                _window_used |= _prev_set
            _global_used_before_day = frozenset(_window_used)
            _global_used_for_day = _window_used
            print(f"[FIX D] Day {day_num + 1}: Using windowed used set ({len(_window_used)} vs {len(global_used_pois)} full)")
        else:
            _global_used_before_day = frozenset(global_used_pois)
            _global_used_for_day = global_used_pois

        day_plan = build_day(
            pois=_pois_for_day,
            user=user,
            context=context,
            day_start=day_start,
            day_end=day_end,
            global_used=_global_used_for_day,  # FIX D: windowed or full
            global_termy_tracking=global_termy_tracking,  # Pass termy limit tracker
            global_trail_tracking=global_trail_tracking,  # Pass trail limit tracker
            warnings_out=_day_warnings,  # FIX #130: collect warnings
            fallback_pois=pois,  # FIX #159: full pool for sparse-day cross-zone backfill
        )

        # FIX #158 (PHASE 1) + FIX #160 (PHASE 3) — CLIENT FEEDBACK: full-pool recovery for
        # under-filled days. A day restricted to a small per-day zone pool (FIX #113) can
        # come back EMPTY or with 1-2 short attractions + multi-hour free_time once cross-day
        # dedup (global_used) exhausts that zone, even though attractive, still-eligible POIs
        # remain in OTHER zones (client JSON1/2/8/9). We retry the day ONCE with the FULL
        # POI pool so the MAIN selection loop (not just gap-fill) can draw from every zone,
        # and ADOPT the retry only if it is strictly better filled (more attractions, or the
        # same attractions with less free_time). This guarantees a day is never made worse.
        #
        # Zero-regression guards:
        #   * only runs when zone pools are active AND this day's pool is a strict subset of
        #     the full pool (single-zone cities / no-zone cities are untouched);
        #   * only runs for under-filled days (0-1 attractions, or > 3h free_time) — well
        #     filled days are byte-identical to before;
        #   * trackers (global_used / termy / trail) are reconciled with explicit deltas so a
        #     rejected retry leaves NO trace and an accepted retry is counted exactly once
        #     (no duplicate POIs, no phantom termy/trail consumption across days).
        def _f160_fill_metric(_items):
            _a = sum(1 for _it in _items if _it.get("type") == "attraction")
            _fr = sum((_it.get("duration_min", 0) or 0)
                      for _it in _items if _it.get("type") == "free_time")
            return _a, _fr

        _f160_attr, _f160_free = _f160_fill_metric(day_plan)
        _f160_underfilled = (_f160_attr < 2) or (_f160_free > 180)
        if _f160_underfilled and pois_per_day is not None and _pois_for_day is not pois:
            print(f"[FIX #160] Day {day_num + 1}: under-filled ({_f160_attr} attractions, "
                  f"{_f160_free}min free) from zone pool ({len(_pois_for_day)} POIs) → "
                  f"retrying with full pool ({len(pois)} POIs)")
            # --- capture the ORIGINAL build's contribution so we can undo/redo cleanly ---
            _f160_gu_added = set(_global_used_for_day) - set(_global_used_before_day)
            _f160_termy_added = sum(1 for _it in day_plan
                                    if _it.get("type") == "attraction" and is_termy_spa(_it.get("poi") or {}))
            _f160_trail_added = sum(1 for _it in day_plan
                                    if _it.get("type") == "attraction"
                                    and (_it.get("poi") or {}).get("type") == "trail")
            # undo ORIGINAL from the shared trackers so the retry starts from a clean slate
            for _pid in _f160_gu_added:
                _global_used_for_day.discard(_pid)
            if global_termy_tracking is not None:
                global_termy_tracking["count"] -= _f160_termy_added
            if global_trail_tracking is not None:
                global_trail_tracking["count"] -= _f160_trail_added
            # snapshot the clean (pre-retry) tracker state for a possible rollback
            _f160_gu_snap = set(_global_used_for_day)
            _f160_tc_snap = global_termy_tracking["count"] if global_termy_tracking is not None else None
            _f160_trc_snap = global_trail_tracking["count"] if global_trail_tracking is not None else None

            _f160_warnings: list = []
            _f160_retry = build_day(
                pois=pois,
                user=user,
                context=context,
                day_start=day_start,
                day_end=day_end,
                global_used=_global_used_for_day,  # clean dedup set → no POI reuse
                global_termy_tracking=global_termy_tracking,
                global_trail_tracking=global_trail_tracking,
                warnings_out=_f160_warnings,
            )
            _f160_rattr, _f160_rfree = _f160_fill_metric(_f160_retry)
            _f160_better = (_f160_rattr > _f160_attr) or (
                _f160_rattr == _f160_attr and _f160_rfree < _f160_free)
            if _f160_better:
                print(f"[FIX #160] Day {day_num + 1}: adopted full-pool plan "
                      f"({_f160_rattr} attractions, {_f160_rfree}min free) — better filled")
                day_plan = _f160_retry
                _day_warnings = _f160_warnings
                # trackers already reflect ONLY the retry (original was undone) — correct.
            else:
                print(f"[FIX #160] Day {day_num + 1}: kept original plan "
                      f"(retry {_f160_rattr} attractions / {_f160_rfree}min free was not better)")
                # roll back the retry's mutations, then re-apply the ORIGINAL's contribution
                _global_used_for_day.clear()
                _global_used_for_day |= _f160_gu_snap
                if global_termy_tracking is not None:
                    global_termy_tracking["count"] = _f160_tc_snap
                if global_trail_tracking is not None:
                    global_trail_tracking["count"] = _f160_trc_snap
                _global_used_for_day |= _f160_gu_added
                if global_termy_tracking is not None:
                    global_termy_tracking["count"] += _f160_termy_added
                if global_trail_tracking is not None:
                    global_trail_tracking["count"] += _f160_trail_added

        # FIX D: Capture POIs added by build_day this day and sync back to global_used_pois
        _day_pois_used = _global_used_for_day - _global_used_before_day
        daily_used_sets.append(_day_pois_used)
        if _fixd_use_window:
            # Sync newly selected POIs back into the full history set
            global_used_pois |= _day_pois_used
        # (Non-FIX-D days: global_used_pois was modified in-place by build_day already)
        # FIX #130: propagate per-day warnings tagged with day number
        if warnings_out is not None:
            for _w in _day_warnings:
                warnings_out.append({**_w, "day": day_num + 1})

        # FIX #50+#51: Restore counts (restriction was temporary; day didn't consume those slots)
        if _termy_count_save is not None:
            global_termy_tracking["count"] = _termy_count_save
        if _trail_count_save is not None:
            global_trail_tracking["count"] = _trail_count_save

        # FIX #50: Check if today had termy (to block termy tomorrow)
        _prev_day_had_termy = any(
            item.get("type") == "attraction" and is_termy_spa(item.get("poi") or {})
            for item in day_plan
        )
        # FIX #51: Check if today had a heavy trail (to force recovery day tomorrow)
        _prev_day_had_heavy_trail = any(
            item.get("type") == "attraction" and
            item.get("poi", {}).get("type") == "trail" and
            item.get("poi", {}).get("duration_min", 0) >= 240
            for item in day_plan
        )
        if _prev_day_had_termy:
            print(f"[FIX #50] Day {day_num + 1} had termy - next day will skip termy")
        if _prev_day_had_heavy_trail:
            print(f"[FIX #51] Day {day_num + 1} had heavy trail (>=240min) - next day is recovery")

        # FIX #89 (28.05.2026): Update global_type_tracking with tags from today's POI.
        # Each unique category tag used today increments its counter once.
        _day_tags_seen = set()
        for item in day_plan:
            if item.get("type") == "attraction" and item.get("poi"):
                for _tag in item["poi"].get("tags", []):
                    _day_tags_seen.add(_tag)
        for _tag in _day_tags_seen:
            global_type_tracking[_tag] = global_type_tracking.get(_tag, 0) + 1
        print(f"[FIX #89] Day {day_num + 1} type tracking updated: {len(global_type_tracking)} tracked tags")
        
        # Count POIs used in this day
        day_poi_count = 0
        day_core_count = 0
        for item in day_plan:
            if item.get("type") == "attraction" and item.get("poi"):
                day_poi_count += 1
                if is_core_poi(item["poi"]):
                    day_core_count += 1
        
        print(f"[MULTI-DAY] Day {day_num + 1} complete: {day_poi_count} POIs ({day_core_count} core)")
        print(f"[MULTI-DAY] Global used POIs after Day {day_num + 1}: {len(global_used_pois)}")
        print(f"[MULTI-DAY] Global termy count after Day {day_num + 1}: {global_termy_tracking['count']}/{global_termy_tracking['max']}")
        print(f"[MULTI-DAY] Global trail count after Day {day_num + 1}: {global_trail_tracking['count']}/{global_trail_tracking['max']}")
        
        all_day_plans.append(day_plan)
    
    return all_day_plans


# =========================
# Single-day Planner
# =========================


def build_day(pois, user, context, day_start=None, day_end=None, global_used=None, global_termy_tracking=None, global_trail_tracking=None, warnings_out=None, fallback_pois=None):
    """
    Build daily plan from POIs.
    
    Args:
        pois: List of POI dicts
        user: User dict (preferences, target_group, etc.)
        context: Context dict (season, date, weather, etc.)
        day_start: Start time string "HH:MM" (default: DAY_START global)
        day_end: End time string "HH:MM" (default: DAY_END global)
        global_used: Optional set of POI IDs already used in previous days (for multi-day planning)
        global_termy_tracking: Optional dict {"count": int, "max": int} for tracking termy/spa across all days
    """
    print("[BUILD_DAY CALLED] Starting build_day")
    ctx = _get_context(context)
    
    # SEASONALITY HARD FILTER (ETAP 1 enhancement - 29.01.2026)
    # Exclude POI outside current season BEFORE scoring
    current_date = context.get("date")
    if current_date:
        pois = filter_by_season(pois, current_date)

    # FIX #122 (30.05.2026): Evening scarcity detection
    # Count how many POI in the (post-seasonal-filter) pool include "evening" in their
    # recommended_time_of_day.  When fewer than 3 are available the time-of-day scorer
    # uses a relaxed tiered penalty so that afternoon/midday POI can fill evening slots
    # without tanking the plan quality (affects cities like Warszawa, Jelenia Góra, etc.).
    _ev_pool_count = sum(
        1 for _p in pois
        if "evening" in str(_p.get("recommended_time_of_day", "") or "").lower()
    )
    ctx["evening_scarcity"] = _ev_pool_count < 3
    if ctx["evening_scarcity"]:
        print(
            f"[FIX #122] Evening scarcity: only {_ev_pool_count} evening POI in pool — "
            f"evening fallback ACTIVE (afternoon/midday penalties relaxed for evening slots)"
        )

    # Use user-provided times or fallback to global defaults
    start_time_str = day_start or DAY_START
    end_time_str = day_end or DAY_END
    
    now = time_to_minutes(start_time_str)
    end = time_to_minutes(end_time_str)

    if ctx["daylight_end"]:
        end = min(end, time_to_minutes(ctx["daylight_end"]))

    # FIX #134 (31.05.2026): Inject day_end_mins so score_poi can compute remaining time
    ctx["day_end_mins"] = end

    # FIX #Problem9 DEBUG: Simple print to verify execution
    print(f"🔥🔥🔥 build_day() CALLED: target_group={user.get('target_group')} 🔥🔥🔥", flush=True)
    
    # FIX #Problem9 DEBUG: Marker to confirm function execution
    with open(r"C:\Users\matte\Desktop\build_day_called.txt", "a", encoding="utf-8") as f:
        f.write(f"build_day called: target_group={user.get('target_group')}\n")
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #10):
    # Standardize all items to use start_time/end_time (not "time")
    plan = [{
        "type": "accommodation_start",
        "start_time": start_time_str,
        "end_time": start_time_str  # Point-in-time event
    }]

    energy = GROUP_DAILY_ENERGY[user["target_group"]]
    # FIX #124 (30.05.2026): family_kids energy capped further for very small children (<= 6y)
    if user.get("target_group") == "family_kids":
        _ca_energy = user.get("children_age")
        if isinstance(_ca_energy, (int, float)) and _ca_energy <= 6:
            energy = min(energy, 50)
            print(f"[FAMILY ENERGY FIX#124] children_age={_ca_energy} → energy capped to {energy}")
    fatigue = 0
    
    # ETAP 2 - DAY 3 (15.02.2026): Multi-day cross-day POI tracking
    # Initialize used set from global_used (if provided) to avoid duplicates across days
    # FIX #11 (29.04.2026 - CLIENT FEEDBACK): Use reference, not copy
    # CRITICAL: set(global_used) creates COPY → changes don't propagate back
    # Using direct reference ensures POI added in Day 1 are visible in Day 2/3
    used = global_used if global_used is not None else set()
    
    last_poi = None

    # FIX #7 (02.02.2026): Track attraction counts for limits
    attraction_count = 0
    core_attraction_count = 0
    
    # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #4): Track trail day mode
    # Problem: Trails treated like regular POI (trail + 5 POI + lunch + dinner)
    # Solution: Trail = main activity, limit subsequent POI based on trail duration
    # PHASE 8 FEATURE #2 (27.04.2026): Elastic trail day rules based on difficulty
    #   - Heavy trail (hard/extreme, 4-5h): ONLY trail (max_poi_after = 0)
    #   - Moderate trail (moderate, 3-4h): trail + max 1 light POI (max_poi_after = 1)
    #   - Light trail (easy, <3h): trail + max 2 light POI (max_poi_after = 2)
    trail_day_mode = False  # True after first trail added
    trail_duration = 0      # Duration of trail in minutes
    trail_difficulty = ""   # Difficulty level: easy, moderate, hard, extreme (PHASE 8 #2)
    max_poi_after_trail = 0  # Dynamic limit based on difficulty (PHASE 8 #2)
    post_trail_poi_count = 0  # Count POI added after trail
    
    # PHASE 8 FEATURE #5 (27.04.2026): Driving time limits per cluster type
    # Limits prevent excessive driving time (users don't want 3+ hours/day in car)
    total_drive_time = 0  # Total driving minutes for this day
    
    # Get cluster type from context signals (set by router) or default to standalone_city
    signals = context.get("signals", {})
    cluster_type = signals.get("cluster_type", "standalone_city")
    
    # Define limits based on cluster type
    # FIX #111 (06.06.2026): Recalibrated for realistic inter-city cluster drives
    # - urban_organism (Trójmiasto): max ~25km at 60 km/h ≈ 30 min → single=35 with margin
    # - regional_cluster (Kotlina):  max ~25km at 50 km/h ≈ 35 min → single=45 with margin
    # - radius_based (Karkonosze):   max ~35km at 40 km/h ≈ 57 min → single=60 with margin
    # - standalone_city (Zakopane):  short drives only → single=25 UNCHANGED
    DRIVE_LIMITS = {
        "urban_organism":   {"daily": 90,  "single": 35},  # Trójmiasto: fast urban roads/SKM
        "regional_cluster": {"daily": 120, "single": 45},  # Kotlina: regional roads <25km
        "radius_based":     {"daily": 130, "single": 60},  # Karkonosze: up to 35km mountain roads
        "standalone_city":  {"daily": 60,  "single": 25}   # Zakopane: UNCHANGED
    }
    
    # Get limits for current cluster (default to standalone_city if unknown)
    limits = DRIVE_LIMITS.get(cluster_type, DRIVE_LIMITS["standalone_city"])
    max_daily_drive = limits["daily"]
    max_single_drive = limits["single"]
    
    # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING FIX #9):
    # CRITICAL: Relax drive limits for mountain_hiking to allow distant trailheads
    # Problem: Heavy mountain trails (4-5h) need 26-40min drive from city center,
    #          but standalone_city limits (max 25min single) exclude them all
    # Solution: For mountain_hiking trips, use regional_cluster limits (40min single)
    #          to allow access to major trailheads (Morskie Oko, Kościelisko, etc.)
    # Rationale: Users booking mountain_hiking EXPECT longer drives to trailheads
    trip_type = context.get("trip_type", "")
    if trip_type == "mountain_hiking":
        max_daily_drive = DRIVE_LIMITS["regional_cluster"]["daily"]  # 120min daily
        max_single_drive = DRIVE_LIMITS["regional_cluster"]["single"]  # 40min single
    
    print(f"[DRIVE LIMITS] Cluster: {cluster_type}, max daily: {max_daily_drive}min, max single: {max_single_drive}min")
    post_trail_poi_count = 0  # Count POI added after trail
    
    # CLIENT REQUIREMENT (04.02.2026): Track kids-focused POI for daily limit
    kids_focused_count = 0  # Max 1/day for non-family groups
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Track termy/spa for daily limit
    # FIX #Problem10 (14.05.2026): Max 1/day for ALL groups (not just seniors)
    termy_count = 0  # Max 1 termy/spa per day

    # FIX #58 (21.05.2026): Track museums per day for adventure profile (hard cap = 1)
    daily_museum_count = 0
    # FIX #99D: Track museums per day for friends profile (hard cap = 1)
    friends_museum_today = 0
    # FIX #127 (30.05.2026): Track museums per day for solo profile (hard cap = 2)
    solo_museum_today = 0
    # FIX #132 (31.05.2026): Track museums per day for couples profile (hard cap = 2)
    couples_museum_today = 0

    # FIX #133 (31.05.2026): Track consecutive short POIs (time_min <= 35) per day
    # Short POIs back-to-back create a "checklist tourist" feel — penalise the 3rd+
    consecutive_short_count = 0

    # FIX #64 (22.05.2026): Track experience-type dedup to prevent same-type POI on the same day
    # Problem: Iluzja Park + Dom do góry nogami both have illusion_kids tag → boring same-experience day
    # Solution: tags in UNIQUE_EXPERIENCE_TAGS can appear at most once per day
    UNIQUE_EXPERIENCE_TAGS = {
        "illusion_kids", "escape_room", "ice_rink", "bowling", "wax_figures",
        "cave_tour", "zipline", "quad_atv", "horse_riding", "kulig",
    }
    daily_used_experience_tags: set = set()  # experience tags already used today

    # FIX #5 (UAT Round 3 - 19.02.2026): Track preference coverage for top 3 preferences
    # Client feedback: "Część atrakcji jest zoo/rozrywka mimo prefs museum_heritage + cultural"
    # Goal: Enforce at least 1 attraction per top 3 user preference per day
    covered_preferences = set()  # Track which of top 3 preferences have been covered
    
    limits = GROUP_ATTRACTION_LIMITS.get(user["target_group"], {
        "soft": 7,
        "hard": 8,
        "core_min": 1,
        "core_max": 2,
    })
    
    # FIX #Problem12 (15.05.2026 - CLIENT FEEDBACK Round 2): Travel style modifier
    # Problem: Relax style should reduce POI count further
    # Solution: relax=-1 soft, -2 hard (FIX #74: more aggressive than original -1/-1)
    # FIX #117 (29.05.2026): Adventure style modifier — adventure users want max activity;
    # +1 soft/hard but capped at 8/9 to avoid scheduling impossibility.
    travel_style = user.get("travel_style", "")
    if travel_style == "relax":
        limits["soft"] = max(2, limits["soft"] - 1)  # Prevent going below 2
        limits["hard"] = max(3, limits["hard"] - 2)  # FIX #74: -2 hard (was -1); min 3 to avoid empty days
        print(f"[LIMITS] Travel style 'relax' modifier applied: soft={limits['soft']}, hard={limits['hard']}")
    elif travel_style == "adventure":
        limits["soft"] = min(8, limits["soft"] + 1)  # Cap at 8 (9 POI/day too dense)
        limits["hard"] = min(9, limits["hard"] + 1)  # Cap at 9 absolute max
        print(f"[LIMITS] Travel style 'adventure' modifier applied: soft={limits['soft']}, hard={limits['hard']}")

    # FIX #123 (30.05.2026): Solo progressive daily limits — fewer POIs as trip continues
    # Prevents POI exhaustion on compact destinations (e.g. Zakopane ~15 high-priority POIs)
    # Day 1-2: standard hard=7, Day 3-4: hard=5, Day 5+: hard=4
    if user.get("target_group") == "solo":
        _solo_day = context.get("current_day_num", 1)
        if _solo_day >= 5:
            limits["soft"] = min(limits["soft"], 4)
            limits["hard"] = min(limits["hard"], 4)
        elif _solo_day >= 3:
            limits["soft"] = min(limits["soft"], 5)
            limits["hard"] = min(limits["hard"], 5)
        # days 1-2: keep standard limits
        print(f"[SOLO FATIGUE FIX#123] Day {_solo_day}: soft={limits['soft']}, hard={limits['hard']}")

    # HUMAN STATE
    culture_streak = 0
    active_streak = 0  # FIX #99E: consecutive active/outdoor POIs counter
    body_state = "neutral"
    finale_done = False
    lunch_done = False
    dinner_done = False  # UAT Problem #11: Track dinner_break
    
    # BUDGET TRACKING (FIX 07.02.2026)
    # Track daily cost to enforce daily_limit hard constraint
    daily_cost = 0  # Sum of ticket_price for all POI added today
    
    # UAT FIX (18.02.2026 - Problem #5): Enhanced daily_limit detection
    # Check multiple possible locations for daily_limit in user dict
    daily_limit = user.get("daily_limit")  # Direct: user.daily_limit
    
    if daily_limit is None:
        # Try user.budget.daily_limit
        budget_dict = user.get("budget", {})
        if isinstance(budget_dict, dict):
            daily_limit = budget_dict.get("daily_limit")
    
    if daily_limit is None:
        # Try user.group.daily_limit
        group_dict = user.get("group", {})
        if isinstance(group_dict, dict):
            daily_limit = group_dict.get("daily_limit")
    
    # Convert to int if string
    if daily_limit is not None:
        try:
            daily_limit = int(daily_limit)
            print(f"[BUDGET] Daily limit detected: {daily_limit} PLN")
        except (ValueError, TypeError):
            daily_limit = None
            print(f"[BUDGET] WARNING: Invalid daily_limit value: {user.get('daily_limit')}")
    else:
        print(f"[BUDGET] No daily_limit set - budget tracking disabled")

    while now < end:
        # FEEDBACK KLIENTKI (03.02.2026): Enforce core_min POI
        # If we're in second half of day and no core POI yet, boost core POI heavily
        half_day = (end + time_to_minutes(start_time_str)) // 2
        if now > half_day and core_attraction_count < limits.get("core_min", 1):
            print(f"[CORE POI] Mid-day checkpoint: {core_attraction_count} core POI, boosting core attractions")
        
        
        # === LUNCH CHECKPOINT ===
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #8):
        # Enforce strict lunch time window (12:00-14:30)
        # - Insert lunch as soon as we reach 12:00
        # - If passed 14:30, insert lunch immediately with warning
        
        # FIX #14 (29.04.2026 - CLIENT FEEDBACK): Force lunch by LUNCH_TARGET (13:00), not LUNCH_EARLIEST
        # Problem: Lunch scheduled at 15:41-16:31, 15:47-16:37 (way too late - should be 12:00-14:30)
        # Root cause: Code waits until now >= 12:00 (lunch_earliest) but doesn't FORCE lunch
        #             If POI before lunch runs until 15:41, lunch will be at 15:41 with warning
        # Solution: Force lunch insertion when now >= LUNCH_TARGET (13:00) to stay within 12:00-14:30 window
        # Rationale: Better to have lunch slightly early (12:30-13:30) than very late (15:41)
        
        # FIX #Problem9 (13.05.2026 - Round 2): Group-specific lunch timing
        # Problem: test-05 (family_kids) and test-06 (seniors) get lunch at 14:48-15:28 (too late)
        # Issue: Children and seniors need earlier lunch than general travelers
        # Solution: Adjust lunch timing based on target_group
        # BUGFIX: trip_mapper.py maps group.type → user["target_group"], NOT user["group"]["type"]
        if not lunch_done:
            # Get group type from user["target_group"] (mapped by trip_mapper.py)
            group_type = user.get("target_group")
            
            # Set lunch timing based on group type
            if group_type == "family_kids":
                # Families with kids: lunch 12:30-13:30 (preferred 12:30)
                lunch_earliest = time_to_minutes("12:00")  # Allow from 12:00
                lunch_target = time_to_minutes("12:30")    # Target 12:30
                lunch_latest = time_to_minutes("13:30")    # Latest 13:30
                print(f"[LUNCH TIMING] family_kids: target 12:30, latest 13:30")
            elif group_type == "seniors":
                # Seniors: lunch 12:45-13:30 (preferred 12:45)
                lunch_earliest = time_to_minutes("12:00")  # Allow from 12:00
                lunch_target = time_to_minutes("12:45")    # Target 12:45
                lunch_latest = time_to_minutes("13:30")    # Latest 13:30
                print(f"[LUNCH TIMING] seniors: target 12:45, latest 13:30")
            else:
                # Default: lunch 13:00-14:30 (preferred 13:00)
                lunch_earliest = time_to_minutes(LUNCH_EARLIEST)  # 12:00
                lunch_target = time_to_minutes(LUNCH_TARGET)      # 13:00
                lunch_latest = time_to_minutes(LUNCH_LATEST)      # 14:30
                print(f"[LUNCH TIMING] default: target 13:00, latest 14:30")

            should_insert_lunch = False
            is_late_lunch = False
            
            # FIX #14: Change trigger from lunch_earliest (12:00) to lunch_target (13:00)
            # This ensures lunch happens by 13:00-14:00, not delayed to 15:41
            # Case 1: We've reached TARGET lunch time (13:00) - force lunch NOW
            if now >= lunch_target:
                should_insert_lunch = True
                
                # Case 1a: Already past latest lunch time (14:30) - late lunch!
                if now > lunch_latest:
                    is_late_lunch = True
                    print(f"[LUNCH] WARNING: Late lunch scheduled at {minutes_to_time(now)} (should be by {LUNCH_LATEST})")
                    # FIX #144 (01.06.2026): Pre-build late_lunch warning removed.
                    # FIX #139 (post-build) generates accurate timing-based warnings from real plan.
            
            # Case 2: We're past earliest (12:00) and approaching target (13:00)
            # If adding another POI would push lunch past 14:00, insert lunch NOW
            elif now >= lunch_earliest:
                # Estimate next POI duration (conservative: 90 min)
                estimated_next_poi_duration = 90
                if now + estimated_next_poi_duration > lunch_latest - 30:  # Would push lunch past 14:00
                    should_insert_lunch = True
                    print(f"[LUNCH] PROACTIVE: Inserting lunch at {minutes_to_time(now)} to avoid late lunch (next POI would push past 14:00)")
            
            if should_insert_lunch:
                lunch_start_time = minutes_to_time(now)
                lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding lunch
                overlaps, conflict = _check_time_overlap(plan, lunch_start_time, lunch_end_time)
                if overlaps:
                    print(f"[OVERLAP DETECTED] lunch_break {lunch_start_time}-{lunch_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                    # Adjust lunch time - move to after conflicting item
                    conflict_end_min = time_to_minutes(conflict.get('end_time', lunch_start_time))
                    now = conflict_end_min
                    lunch_start_time = minutes_to_time(now)
                    lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                # BUGFIX (19.02.2026 - UAT Round 2, Bug #2): Calculate actual duration
                # If lunch is shortened by day_end, duration_min should reflect actual time
                lunch_start_min = time_to_minutes(lunch_start_time)
                lunch_end_min = time_to_minutes(lunch_end_time)
                actual_lunch_duration = lunch_end_min - lunch_start_min
                
                # ETAP 3 PHASE 3 (27.04.2026): Intelligent lunch suggestions from RestaurantRepository
                # Use context["restaurants_available"] to find nearby lunch spots
                # Fallback to generic suggestions if no restaurants available
                lunch_suggestions = ["Lunch", "Restauracja", "Odpoczynek"]  # Default fallback

                restaurants_available = context.get("restaurants_available", [])
                if restaurants_available:
                    # FIX #65 (22.05.2026): meal_type can be comma-separated e.g. "lunch,dinner"
                    # Use "in" check instead of exact equality
                    lunch_restaurants = [
                        r for r in restaurants_available
                        if "lunch" in (r.get("meal_type") or "").lower()
                    ]

                    # FIX #59 (22.05.2026): Cuisine filter for local_food_experience preference
                    # Problem: Giga Buła (burgers/american) suggested to users who prefer local cuisine
                    # Solution: If user has local_food_experience preference, exclude fast-food/foreign
                    #           cuisines and prefer polish/regional restaurants
                    # FIX #145 (01.06.2026): Also boost restaurants with regional tags from Excel
                    user_prefs_for_lunch = user.get("preferences", [])
                    if "local_food_experience" in user_prefs_for_lunch:
                        NON_LOCAL_CUISINES = {"american", "burgers", "street_food", "fast_food", "italian", "asian"}
                        regional_restaurants = [
                            r for r in lunch_restaurants
                            if not (set(
                                [c.strip().lower() for c in (r.get("cuisine_type") or "").split(",")]
                            ) & NON_LOCAL_CUISINES)
                        ]
                        if regional_restaurants:
                            lunch_restaurants = regional_restaurants
                            print(f"[LUNCH FIX#59] local_food_experience: filtered to {len(lunch_restaurants)} regional/polish restaurants")
                        else:
                            print(f"[LUNCH FIX#59] local_food_experience: no regional-only restaurants found, using all")
                        
                        # FIX #145: Sort remaining candidates so tagged regional restaurants appear first
                        # Tags that signal authentic local experience
                        _REGIONAL_TAGS = {"regional", "traditional_food", "local", "highlander", "mountain_food", "bacowka"}
                        def _regional_sort_key(r):
                            r_tags = set(t.lower() for t in (r.get("tags") or []))
                            has_regional = bool(r_tags & _REGIONAL_TAGS)
                            return (0 if has_regional else 1, r.get("_distance", 999.0))
                        lunch_restaurants.sort(key=_regional_sort_key)
                        _tagged = sum(1 for r in lunch_restaurants if set(t.lower() for t in (r.get("tags") or [])) & _REGIONAL_TAGS)
                        print(f"[LUNCH FIX#145] local_food_experience: {_tagged} restaurants have regional tags (sorted first)")

                    # If we have current location (last attraction), sort by proximity
                    if plan:
                        # Find last attraction for location context
                        last_attraction = None
                        for item in reversed(plan):
                            if item.get("type") == "attraction" and item.get("poi"):
                                last_attraction = item.get("poi")
                                break
                        
                        if last_attraction and last_attraction.get("lat") and last_attraction.get("lng"):
                            current_lat = last_attraction.get("lat")
                            current_lng = last_attraction.get("lng")
                            
                            # Calculate distance to each restaurant
                            for r in lunch_restaurants:
                                r_lat = r.get("lat", 0)
                                r_lng = r.get("lng", 0)
                                if r_lat and r_lng:
                                    distance = haversine_distance(current_lat, current_lng, r_lat, r_lng)
                                    r["_distance"] = distance
                                else:
                                    r["_distance"] = 999.0  # Unknown location = far away
                            
                            # Sort by proximity
                            lunch_restaurants.sort(key=lambda r: r.get("_distance", 999.0))
                            print(f"[LUNCH] Sorted {len(lunch_restaurants)} lunch spots by proximity to {last_attraction.get('name', 'current location')}")

                            # FIX #141 (31.05.2026): Hard 2km geo filter — only show nearby restaurants.
                            # Prevents "lunch teleport" where suggestions are far from actual position.
                            _LUNCH_MAX_DIST_KM = 2.0
                            _nearby_lunch141 = [r for r in lunch_restaurants if r.get("_distance", 999.0) <= _LUNCH_MAX_DIST_KM]
                            if _nearby_lunch141:
                                lunch_restaurants = _nearby_lunch141
                                print(f"[LUNCH FIX#141] Filtered to {len(lunch_restaurants)} restaurants within {_LUNCH_MAX_DIST_KM}km")
                            else:
                                print(f"[LUNCH FIX#141] No restaurant within {_LUNCH_MAX_DIST_KM}km — keeping sorted fallback list")
                    
                    # Take top 3 nearest restaurants
                    if lunch_restaurants:
                        lunch_suggestions = [r["name"] for r in lunch_restaurants[:3]]
                        print(f"[LUNCH] Intelligent suggestions: {lunch_suggestions}")
                    else:
                        # No lunch restaurants available, try any restaurants
                        any_restaurants = [r for r in restaurants_available if r.get("name")]
                        if any_restaurants:
                            lunch_suggestions = [r["name"] for r in any_restaurants[:3]]
                            print(f"[LUNCH] Fallback suggestions (no lunch-specific): {lunch_suggestions}")
                
                # FIX #Problem9 DEBUG: Log lunch insertion with group_type
                group_type_debug = user.get("target_group")
                print(f"[DEBUG #Problem9] INSERTING LUNCH: time={lunch_start_time}-{lunch_end_time}, group_type={group_type_debug}, lunch_target={lunch_target}, lunch_latest={lunch_latest}")
                
                # FIX #129 (XX.06.2026): Generalize FIX #102 — add return transit to city before lunch
                # for ANY POI type that is far from centrum (not just trails).
                # Prevents "lunch teleport" regardless of attraction type (cable-car, zoo, etc.).
                _lunch_location_context = "centrum"
                # FIX #156 (04.06.2026): Gate the ZAKOPANE-hardcoded return-to-centrum block to
                # Zakopane trips only (mirrors FIX #37/#69 in plan_service). For other cities the
                # hardcoded ZAKOPANE_CENTER would compute a bogus distance to a foreign centre.
                # Default True preserves existing behavior for build_day callers that omit the flag.
                if last_poi and last_poi.get("type") != "city_center" and context.get("is_zakopane_trip", True):
                    _lp_lat = last_poi.get("lat")
                    _lp_lng = last_poi.get("lng")
                    if _lp_lat and _lp_lng:
                        _dist_to_city = haversine_distance(_lp_lat, _lp_lng, ZAKOPANE_CENTER_LAT, ZAKOPANE_CENTER_LNG)
                    else:
                        _dist_to_city = 0.0
                    if _dist_to_city > WALK_THRESHOLD_KM:
                        _return_min = max(5, int((_dist_to_city / 45) * 60 + 5))
                        if now + _return_min + 30 <= end:
                            _from_name_lunch = poi_name(last_poi)  # save before updating last_poi
                            # FIX #147: Skip if already transferred to Zakopane centrum recently (lookback-8)
                            _skip_lunch_tr = any(
                                it.get("type") == "transfer" and it.get("to") == "Zakopane centrum"
                                for it in plan[-8:]
                            )
                            if not _skip_lunch_tr:
                                plan.append({
                                    "type": "transfer",
                                    "from": _from_name_lunch,
                                    "to": "Zakopane centrum",
                                    "duration_min": _return_min,
                                    "distance_km": round(_dist_to_city, 3),
                                    "transport_mode": "car",
                                })
                                now += _return_min
                            else:
                                print(f"[FIX #147] Skipped duplicate lunch return transit to Zakopane centrum")
                            # FIX #118 pattern: Update last_poi to city center to prevent duplicate transit
                            last_poi = {
                                "lat": ZAKOPANE_CENTER_LAT,
                                "lng": ZAKOPANE_CENTER_LNG,
                                "name": "Zakopane centrum",
                                "poi_id": "__city_center__",
                                "type": "city_center",
                            }
                            lunch_start_time = minutes_to_time(now)
                            lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                            lunch_start_min = time_to_minutes(lunch_start_time)
                            lunch_end_min = time_to_minutes(lunch_end_time)
                            actual_lunch_duration = lunch_end_min - lunch_start_min
                            print(f"[FIX #129] Added return transit from {_from_name_lunch} to Zakopane centrum: {_return_min}min ({_dist_to_city:.1f}km)")
                        else:
                            print(f"[FIX #129] Skipped return transit (not enough time): {_return_min}min + 30min lunch > day_end")
                            _lunch_location_context = "przy_atrakcji"
                
                plan.append(
                    {
                        "type": "lunch_break",
                        "start_time": lunch_start_time,
                        "end_time": lunch_end_time,
                        "duration_min": actual_lunch_duration,  # Use actual duration, not constant
                        "suggestions": lunch_suggestions,  # ETAP 3: Intelligent suggestions
                        "location_context": _lunch_location_context,  # FIX #102/#103
                    }
                )
                # FIX #3: Update 'now' with actual lunch duration (not constant)
                # Ensures 'now' respects day_end if lunch was truncated
                now = lunch_end_min  # Use actual end time, not now + LUNCH_DURATION_MIN
                lunch_done = True
                fatigue = max(0, fatigue - 2)
                print(f"[LUNCH] Inserted lunch at {lunch_start_time}-{lunch_end_time} (duration: {actual_lunch_duration} min)")
                continue

        # UAT Problem #11: DINNER_BREAK
        # Add dinner break if:
        # - NOT done yet
        # - Current time >= DINNER_EARLIEST (18:00)
        # - Enough time left in day (at least 90 min before day_end)
        # FIX #3 (22.02.2026): Respect user day_end - don't schedule dinner beyond it
        if not dinner_done:
            dinner_earliest = time_to_minutes(DINNER_EARLIEST)  # 18:00
            dinner_target = time_to_minutes(DINNER_TARGET)      # 19:00
            # FIX #3: Use min of hardcoded DINNER_LATEST and actual day_end
            dinner_latest = min(time_to_minutes(DINNER_LATEST), end)  # Respect user day_end
            should_insert_dinner = False
            is_late_dinner = False
            
           # Case 1: We've reached earliest dinner time (18:00)
            # FIX #3: Also check if there's enough time left for dinner (min 40 min)
            if now >= dinner_earliest and now + 40 <= end:
                should_insert_dinner = True
                
                # Case 1a: Already past latest dinner time - late dinner!
                if now > dinner_latest:
                    is_late_dinner = True
                    print(f"[DINNER] WARNING: Late dinner scheduled at {minutes_to_time(now)} (should be by {minutes_to_time(dinner_latest)})")
                    if warnings_out is not None:  # FIX #130
                        warnings_out.append({"type": "late_dinner", "severity": "warning",
                            "message": f"Late dinner scheduled at {minutes_to_time(now)} (should be by {minutes_to_time(dinner_latest)})"})
            
            if should_insert_dinner:
                dinner_start_time = minutes_to_time(now)
                # FIX #3: Calculate dinner_end_time respecting day_end
                dinner_end_min = min(end, now + DINNER_DURATION_MIN)
                dinner_end_time = minutes_to_time(dinner_end_min)
                
                # Check overlap before adding dinner
                overlaps, conflict = _check_time_overlap(plan, dinner_start_time, dinner_end_time)
                if overlaps:
                    print(f"[OVERLAP DETECTED] dinner_break {dinner_start_time}-{dinner_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                    # Adjust dinner time - move to after conflicting item
                    conflict_end_min = time_to_minutes(conflict.get('end_time', dinner_start_time))
                    now = conflict_end_min
                    dinner_start_time = minutes_to_time(now)
                    dinner_end_time = minutes_to_time(min(end, now + DINNER_DURATION_MIN))
                
                # BUGFIX (19.02.2026 - UAT Round 2, Bug #2): Calculate actual duration
                # If dinner is shortened by day_end, duration_min should reflect actual time
                dinner_start_min = time_to_minutes(dinner_start_time)
                dinner_end_min = time_to_minutes(dinner_end_time)
                actual_dinner_duration = dinner_end_min - dinner_start_min

                # FIX #80 (27.05.2026): Don't insert dinner shorter than 40 min
                # Happens when a conflict shifts dinner start very close to day_end.
                # The initial guard (now + 40 <= end) may have been valid BEFORE the shift.
                MIN_DINNER_DURATION = 40
                if actual_dinner_duration < MIN_DINNER_DURATION:
                    print(f"[DINNER] FIX #80: Skipping dinner — only {actual_dinner_duration}min available after conflict shift (min {MIN_DINNER_DURATION}min required). Dinner cancelled.")
                    dinner_done = True  # Prevent infinite retry; day is ending
                    continue
                
                # ETAP 3 PHASE 3 (27.04.2026): Intelligent dinner suggestions from RestaurantRepository
                # Use context["restaurants_available"] to find nearby dinner spots
                # Fallback to generic suggestions if no restaurants available
                dinner_suggestions = ["Regionalna restauracja", "Bacówka", "Karcma góralska"]  # Default fallback
                
                restaurants_available = context.get("restaurants_available", [])
                if restaurants_available:
                    # FIX #65 (22.05.2026): meal_type can be comma-separated e.g. "lunch,dinner"
                    # Use "in" check instead of exact equality
                    dinner_restaurants = [
                        r for r in restaurants_available
                        if "dinner" in (r.get("meal_type") or "").lower()
                    ]
                    
                    # If we have current location (last attraction), sort by proximity
                    if plan:
                        # Find last attraction for location context
                        last_attraction = None
                        for item in reversed(plan):
                            if item.get("type") == "attraction" and item.get("poi"):
                                last_attraction = item.get("poi")
                                break
                        
                        if last_attraction and last_attraction.get("lat") and last_attraction.get("lng"):
                            current_lat = last_attraction.get("lat")
                            current_lng = last_attraction.get("lng")
                            
                            # Calculate distance to each restaurant
                            for r in dinner_restaurants:
                                r_lat = r.get("lat", 0)
                                r_lng = r.get("lng", 0)
                                if r_lat and r_lng:
                                    distance = haversine_distance(current_lat, current_lng, r_lat, r_lng)
                                    r["_distance"] = distance
                                else:
                                    r["_distance"] = 999.0  # Unknown location = far away
                            
                            # Sort by proximity
                            dinner_restaurants.sort(key=lambda r: r.get("_distance", 999.0))
                            print(f"[DINNER] Sorted {len(dinner_restaurants)} dinner spots by proximity to {last_attraction.get('name', 'current location')}")
                    
                    # Boost local food restaurants if user wants local_food_experience
                    if "local_food_experience" in user.get("preferences", []):
                        # Re-sort to prioritize regional cuisine
                        regional_tags = {"regional_cuisine", "local_food", "traditional", "góralska"}
                        for r in dinner_restaurants:
                            r_tags = set(r.get("tags", []))
                            if regional_tags & r_tags:
                                r["_distance"] = r.get("_distance", 999.0) * 0.5  # 50% distance reduction = priority boost
                        
                        dinner_restaurants.sort(key=lambda r: r.get("_distance", 999.0))
                        print(f"[DINNER] Boosted regional cuisine restaurants (local_food_experience preference)")
                    
                    # Take top 3 nearest/best restaurants
                    if dinner_restaurants:
                        dinner_suggestions = [r["name"] for r in dinner_restaurants[:3]]
                        print(f"[DINNER] Intelligent suggestions: {dinner_suggestions}")
                    else:
                        # No dinner restaurants available, try any restaurants
                        any_restaurants = [r for r in restaurants_available if r.get("name")]
                        if any_restaurants:
                            dinner_suggestions = [r["name"] for r in any_restaurants[:3]]
                            print(f"[DINNER] Fallback suggestions (no dinner-specific): {dinner_suggestions}")
                
                plan.append(
                    {
                        "type": "dinner_break",
                        "start_time": dinner_start_time,
                        "end_time": dinner_end_time,
                        "duration_min": actual_dinner_duration,  # Use actual duration, not constant
                        "suggestions": dinner_suggestions,  # ETAP 3: Intelligent suggestions
                    }
                )
                # FIX #3: Update 'now' with actual dinner duration (not constant)
                # Ensures 'now' respects day_end if dinner was truncated
                now = dinner_end_min  # Use actual end time, not now + DINNER_DURATION_MIN
                dinner_done = True
                fatigue = max(0, fatigue - 2)
                print(f"[DINNER] Inserted dinner at {dinner_start_time}-{dinner_end_time} (duration: {actual_dinner_duration} min)")
                continue

        # swiety final
        if finale_done:
            break
        
        # FIX #7 (02.02.2026): Hard stop if attraction limit reached
        if attraction_count >= limits["hard"]:
            print(f"[LIMITS] Hard stop: {attraction_count}/{limits['hard']} attractions reached")
            break

        best = None
        best_score = -9999
        best_travel = 0
        best_duration = 0

        for p in pois:
            if poi_id(p) in used:
                continue
            
            # FIX #10/10.2/10.3/10.4 (22.02.2026 - UAT Round 3, TEST-03 FINAL FIX):
            # CRITICAL: Hard block kids-only POIs for adult groups (friends/couples/seniors/solo)
            # Problem: TEST-03 (friends, adventure) gets kids POIs (zoo, termy with kids_attractions type)
            # Root cause: 40% family_tags penalty insufficient - kids POIs still competitive
            # Solution: HARD BLOCK (not penalty) - kids POIs should NEVER appear in adult plans
            # FIX #10.4: Extracted to reusable function to prevent bypass via variety/core/soft paths
            if should_exclude_kids_poi_for_adults(p, user):
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"[FILTER] HARD BLOCK kids POI for adult group: {poi_name_safe}")
                continue  # SKIP entirely - not applicable for adult groups

            # FIX #57 (21.05.2026): Skip POIs where parking walk is too long for family_kids/seniors
            # Issue: walk_time_min=25 (e.g. Nosal) unacceptable for family with small children/seniors
            _walk_min = int(p.get("parking_walk_time_min", 0) or 0)
            if _walk_min > 0:
                _tg_57 = user.get("target_group", "")
                if _tg_57 == "family_kids" and _walk_min > 15:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[WALK FILTER] EXCLUDED: {poi_name_safe} - parking walk {_walk_min}min > 15 (family_kids limit)")
                    continue
                elif _tg_57 == "seniors" and _walk_min > 20:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[WALK FILTER] EXCLUDED: {poi_name_safe} - parking walk {_walk_min}min > 20 (seniors limit)")
                    continue

            # FIX #58 (21.05.2026): Hard cap: max 1 museum per day for adventure profile
            # Issue: Adventure plans fill with museums after trails/active POIs are exhausted
            if travel_style == "adventure" and daily_museum_count >= 1:
                _mus_tags_58 = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                "interactive_exhibit", "local_history", "architecture_heritage",
                                "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                "intimate_small_museum", "ethnographic_museum"}
                if _mus_tags_58 & set(p.get("tags", [])):
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[MUSEUM CAP] EXCLUDED: {poi_name_safe} - max 1 museum/day for adventure (daily_museum_count={daily_museum_count})")
                    continue

            # FIX #99D: Hard cap: max 1 museum per day for friends profile
            if user.get("target_group") == "friends" and friends_museum_today >= 1:
                _mus_tags_99d = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                 "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                 "interactive_exhibit", "local_history", "architecture_heritage",
                                 "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                 "intimate_small_museum", "ethnographic_museum"}
                if _mus_tags_99d & set(p.get("tags", [])):
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[MUSEUM CAP] EXCLUDED: {poi_name_safe} - max 1 museum/day for friends (friends_museum_today={friends_museum_today})")
                    continue

            # FIX #127 (30.05.2026): Hard cap: max 2 museums per day for solo profile
            if user.get("target_group") == "solo" and solo_museum_today >= 2:
                _mus_tags_127 = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                 "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                 "interactive_exhibit", "local_history", "architecture_heritage",
                                 "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                 "intimate_small_museum", "ethnographic_museum"}
                if _mus_tags_127 & set(p.get("tags", [])):
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[MUSEUM CAP] EXCLUDED: {poi_name_safe} - max 2 museums/day for solo (solo_museum_today={solo_museum_today})")
                    continue

            # FIX #132 (31.05.2026): Hard cap: max 2 museums per day for couples profile
            if user.get("target_group") == "couples" and couples_museum_today >= 2:
                _mus_tags_132 = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                 "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                 "interactive_exhibit", "local_history", "architecture_heritage",
                                 "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                 "intimate_small_museum", "ethnographic_museum"}
                if _mus_tags_132 & set(p.get("tags", [])):
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[MUSEUM CAP] EXCLUDED: {poi_name_safe} - max 2 museums/day for couples (couples_museum_today={couples_museum_today})")
                    continue

            # FIX #125 (30.05.2026): Block long activities for toddlers (children_age <= 5)
            _ca_f125 = user.get("children_age")
            if (user.get("target_group") == "family_kids"
                    and isinstance(_ca_f125, (int, float)) and _ca_f125 <= 5):
                _poi_dur_f125 = int(p.get("time_min", 0) or 0)
                if _poi_dur_f125 > 90:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[DURATION FILTER FIX#125] EXCLUDED: {poi_name_safe} - duration {_poi_dur_f125}min > 90 for children_age={_ca_f125}")
                    continue

            # FIX #64 (22.05.2026): Experience-type dedup (max 1 per day per unique experience tag)
            # Problem: Iluzja Park + Dom do góry nogami both have illusion_kids → same experience twice
            _poi_exp_tags = UNIQUE_EXPERIENCE_TAGS & set(p.get("tags", []))
            if _poi_exp_tags & daily_used_experience_tags:
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"[DEDUP FIX#64] EXCLUDED: {poi_name_safe} - experience tags {_poi_exp_tags} already used today")
                continue

            # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #5): Trail limit per trip
            # CRITICAL: Limit trails based on trip duration (prevent trail overload)
            # Problem: No limits on trails (could have 5 trails in 3-day trip)
            # Solution: Check global trail counter before allowing trail
            #   - 2-3 days → max 1 trail
            #   - 4-5 days → max 2 trails  
            #   - 6-7 days → max 3 trails
            #
            if p.get("type") == "trail" and global_trail_tracking is not None:
                trails_remaining = global_trail_tracking["max"] - global_trail_tracking["count"]
                if trails_remaining <= 0:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL LIMIT] EXCLUDED trail: {poi_name_safe} - global limit reached "
                          f"({global_trail_tracking['count']}/{global_trail_tracking['max']} trails used)")
                    continue  # SKIP - trail limit reached for entire trip

            # FIX #61 (22.05.2026): Extra safety - block high-exposure trails in winter for seniors/relax
            # This supplements FIX #60 (seasonality field in to_dict).
            # Edge case: if best_season="all_year" but trail is actually dangerous in winter
            # (e.g. high exposure), enforce additional block.
            # Rules:
            #   - exposure_level="high" in winter months [12,1,2] → block for ALL users
            #   - exposure_level in ["medium","high"] in winter → block for seniors
            #   - exposure_level="high" in shoulder months [3,11] → block for seniors
            if p.get("type") == "trail":
                _trail_date = context.get("date")
                if _trail_date:
                    _trail_month = _trail_date[1]
                    _trail_exposure = (p.get("exposure_level") or "").lower()
                    _trail_target = user.get("target_group", "")
                    _is_winter = _trail_month in (12, 1, 2)
                    _is_shoulder = _trail_month in (3, 11)
                    _block_trail = False
                    if _is_winter and _trail_exposure == "high":
                        _block_trail = True  # No high-exposure in winter for anyone
                    elif _is_winter and _trail_exposure in ("medium", "high") and _trail_target == "seniors":
                        _block_trail = True  # No medium/high exposure in winter for seniors
                    elif _is_shoulder and _trail_exposure == "high" and _trail_target == "seniors":
                        _block_trail = True  # No high-exposure in shoulder months for seniors
                    if _block_trail:
                        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                        print(f"[TRAIL SAFETY FIX#61] EXCLUDED trail: {poi_name_safe} - "
                              f"exposure={_trail_exposure}, month={_trail_month}, group={_trail_target}")
                        continue

            # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #7): Trail timing - morning only
            # CRITICAL: Trails must start early (08:00-10:00) to avoid afternoon/evening starts
            # Problem: Trails scheduled at wrong times (trail start 14:00, 16:00)
            # Solution: HARD FILTER trails by time-of-day (block if now >= 10:00 AM)
            #
            # Rationale:
            #   - Mountain trails require daylight and safe descent time
            #   - Starting after 10 AM risks finishing in darkness (trails are 3-13h long)
            #   - Weather safety: early starts avoid afternoon storms in mountains
            #
            if p.get("type") == "trail":
                TRAIL_CUTOFF_TIME = 600  # 10:00 AM in minutes (08:00=480, 10:00=600)
                if now >= TRAIL_CUTOFF_TIME:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL TIMING] EXCLUDED trail: {poi_name_safe} - too late in day "
                          f"(now={minutes_to_time(now)}, cutoff=10:00)")
                    continue  # SKIP - trails must start before 10:00 AM
            
            # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #6): Trail preference filtering
            # CRITICAL: Trails should ONLY be included if user has hiking/mountain preferences
            # Problem: Trails added to plans even for culture/food-focused travelers
            # Solution: HARD FILTER trails by user preferences (not just scoring penalty)
            #
            # Trails are ONLY allowed if user has ANY of:
            #   - "mountain_trails" preference
            #   - "hiking" preference
            #   - "active_sport" preference
            #   - "outdoor" preference (weak match)
            # OR target_group = "adventure_seekers" (hiking assumed)
            #
            if p.get("type") == "trail":
                user_prefs = user.get("preferences", [])
                target_group = user.get("target_group", "")
                
                # Required preferences for trails (strong matches)
                strong_hiking_prefs = {"mountain_trails", "hiking", "active_sport"}
                
                # Weak preferences (outdoor alone is not enough unless adventure_seekers)
                weak_hiking_prefs = {"outdoor", "nature"}
                
                has_strong_pref = bool(set(user_prefs) & strong_hiking_prefs)
                has_weak_pref = bool(set(user_prefs) & weak_hiking_prefs)
                is_adventure_group = target_group == "adventure_seekers"
                
                # Trail filtering logic:
                # - Strong pref → always allow
                # - Adventure_seekers + weak pref → allow (assume hiking interest)
                # - Adventure_seekers alone → allow (group type implies hiking)
                # - Weak pref alone → block (outdoor != mountain hiking)
                # - No prefs → block
                
                trail_allowed = has_strong_pref or is_adventure_group
                
                if not trail_allowed:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL FILTER] EXCLUDED trail: {poi_name_safe} - no hiking preferences "
                          f"(user_prefs={user_prefs}, group={target_group})")
                    continue  # SKIP - user not interested in mountain trails
            
            # FIX #47 (20.05.2026): Trail intensity matching to travel_style
            # Problem: Relax users (Json9) and seniors (Json6) got heavy 360+min trails
            # Solution: Hard-cap trail duration based on travel_style + target_group
            #   - travel_style == "relax" → max 180min trails (Sarnia, Kopieniec)
            #   - target_group == "seniors" → max 150min trails (Nosal, Kopieniec only)
            if p.get("type") == "trail":
                trail_dur = p.get("duration_min", 0)
                travel_style_val = user.get("travel_style", "")
                target_group_val = user.get("target_group", "")
                max_trail_dur = None
                if target_group_val == "seniors":
                    max_trail_dur = 150  # FIX #54: seniors only get short trails
                elif travel_style_val == "relax":
                    max_trail_dur = 180  # FIX #47: relax users get at most 3h trails
                elif travel_style_val == "balanced":
                    max_trail_dur = 240  # FIX #56: balanced users get at most 4h trails (Hala Gasienicowa max)
                if max_trail_dur is not None and trail_dur > max_trail_dur:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL INTENSITY] EXCLUDED trail: {poi_name_safe} - duration {trail_dur}min > "
                          f"max {max_trail_dur}min for style={travel_style_val}/group={target_group_val}")
                    continue  # SKIP - trail too demanding for this user

            # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #4): Trail day restrictions
            # PHASE 8 FEATURE #2 (27.04.2026): Elastic trail day rules based on difficulty
            # CRITICAL: After trail added, restrict remaining POI based on trail difficulty + duration
            # Solution:
            #   - Max 1 trail per day (skip additional trails)
            #   - Heavy trail (hard/extreme, 4-5h) → NO more POI (only lunch/dinner)
            #   - Moderate trail (moderate, 3-4h) → max 1 LIGHT POI (<=60min)
            #   - Light trail (easy, <3h) → max 2 LIGHT POI (<=60min each)
            #
            if trail_day_mode:
                # Rule 1: Only 1 trail per day
                if p.get("type") == "trail":
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL DAY] EXCLUDED additional trail: {poi_name_safe} - already have trail today")
                    continue
                
                # PHASE 8 FEATURE #2: Rule 2 - Dynamic POI limit based on trail difficulty
                # Heavy trail (max_poi_after_trail = 0) → NO more POI
                if max_poi_after_trail == 0:
                    poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TRAIL DAY] EXCLUDED POI: {poi_name_safe} - heavy trail "
                          f"(difficulty={trail_difficulty}, {minutes_to_time(trail_duration)}) allows no additional attractions")
                    continue
                
                # PHASE 8 FEATURE #2: Rule 3 - Moderate/Light trail → max 1-2 light POI (<=60min)
                if max_poi_after_trail > 0:
                    # Get RAW POI duration (not choose_duration which may shorten it)
                    # Trail day requires NATURALLY SHORT POI (<=60min base duration)
                    # FIX #105 (28.05.2026): Use time_min as duration check — czas_zwiedzania_min
                    # doesn't exist in POI data (always 0 → filter was broken/no-op).
                    # Termy/spa exempt: valid recovery activity after trail (client spec Phase 8).
                    if p.get("type") == "trail":
                        p_raw_duration = p.get("duration_min", 0)
                    else:
                        p_raw_duration = safe_int(p.get("time_min"), 0)
                    
                    # Skip long POI (>60min minimum visit) — termy/spa always exempt
                    if p_raw_duration > 60 and not is_termy_spa(p):
                        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                        print(f"[TRAIL DAY] EXCLUDED POI: {poi_name_safe} - minimum visit too long "
                              f"({p_raw_duration}min > 60min) for trail day")
                        continue
                    
                    # FIX #81 (27.05.2026): After long/hard trail, block high-energy POIs.
                    # All non-trail POIs have type='poi', so we use TAG-based blocklist.
                    # FIX #85 (28.05.2026): Extended blocklist for VERY heavy trails (>=240min or hard/extreme).
                    # After Morskie Oko (5-6h), museums and viewpoints are also inappropriate.
                    # Only termy/spa/café are allowed after the hardest trails.
                    if trail_duration >= 180 or trail_difficulty in ["hard", "extreme"]:
                        _ACTIVE_TAGS_F81 = {
                            "rope_park", "adventure_park", "medium_intensity_activity",
                            "family_theme_park", "kids_zone", "snow_tubing",
                            "water_rides", "adrenaline_attractions", "zip_line", "luge"
                        }
                        # FIX #85: For very heavy trails, also block cultural/passive POI
                        # After Morskie Oko (6h walk), a museum or viewpoint is NOT recovery
                        if trail_duration >= 240 or trail_difficulty in ["hard", "extreme"]:
                            _ACTIVE_TAGS_F81 |= {
                                "themed_museum", "regional_heritage", "museum_heritage", "museums",
                                "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                "interactive_exhibit", "local_history", "architecture_heritage",
                                "historic_building", "composer_artist_house", "intimate_small_museum",
                                "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                                "scenic_viewpoint",  # requires standing/walking — not recovery
                            }
                        _p81_tags = set(p.get("tags") or [])
                        if _ACTIVE_TAGS_F81 & _p81_tags:
                            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                            print(f"[FIX #81/#85] EXCLUDED POI after {trail_duration}min {trail_difficulty} trail: "
                                  f"{poi_name_safe} (blocked_tags={_ACTIVE_TAGS_F81 & _p81_tags})")
                            continue
                    
                    # PHASE 8 FEATURE #2: Limit to max_poi_after_trail (1 for moderate, 2 for light)
                    if post_trail_poi_count >= max_poi_after_trail:
                        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                        print(f"[TRAIL DAY] EXCLUDED POI: {poi_name_safe} - already have "
                              f"{post_trail_poi_count}/{max_poi_after_trail} light POI after {trail_difficulty} trail")
                        continue
            
            # FEEDBACK KLIENTKI (03.02.2026) - HARD FILTERS
            # STEP 1: Target group hard filter
            if should_exclude_by_target_group(p, user):
                poi_name_safe = str(p.get('Name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"[FILTER] EXCLUDED by target_group: {poi_name_safe} (poi_id={poi_id(p)}) - user={user.get('target_group')}, poi_groups={p.get('target_groups', [])}, kids_only={p.get('kids_only', False)}")
                continue  # EXCLUDE - target group mismatch
            
            # STEP 2: Intensity hard filter
            if should_exclude_by_intensity(p, user):
                poi_name_safe = str(p.get('Name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"[FILTER] EXCLUDED by intensity: {poi_name_safe} (poi_id={poi_id(p)}) - user={user.get('target_group')}, poi_intensity={p.get('intensity', 'unknown')}")
                continue  # EXCLUDE - intensity conflict
            
            # FIX #7: Check core POI limit
            is_core = is_core_poi(p)
            if is_core and core_attraction_count >= limits["core_max"]:
                continue  # Skip - too many core POI already
            
            # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
            user_group = user.get("target_group", "")
            if user_group in ['solo', 'couples', 'friends', 'seniors']:
                if is_kids_focused_poi(p) and kids_focused_count >= 1:
                    print(f"[LIMITS] Skip kids-focused POI ID: {poi_id(p)} (already have {kids_focused_count}/1)")
                    continue  # Skip - already have 1 kids-focused POI today
            
            # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Max 1 termy/spa per day for seniors
            # FIX #Problem10 (14.05.2026): Apply to ALL groups (not just seniors)
            # FIX #44 (20.05.2026 - Issue F): Defer termy/spa before noon when trail slots remain
            # When mountain_trails is a top-3 preference and trail slots are still open,
            # block termy/spa before 12:00 — mornings should be reserved for trail activities.
            if is_termy_spa(p) and global_trail_tracking is not None and not trail_day_mode:
                _trails_remaining_f44 = global_trail_tracking["max"] - global_trail_tracking["count"]
                _user_prefs_f44 = user.get("preferences", [])[:3]
                _TERMY_MORNING_BLOCK = 720  # 12:00 PM in minutes
                if _trails_remaining_f44 > 0 and "mountain_trails" in _user_prefs_f44 and now < _TERMY_MORNING_BLOCK:
                    _poi_name_f44 = str(p.get('Name', p.get('name', 'Unknown'))).encode('ascii', errors='ignore').decode('ascii')
                    print(f"[TERMY DEFER] Deferring {_poi_name_f44} — trail slots remain "
                          f"({global_trail_tracking['count']}/{global_trail_tracking['max']}), "
                          f"morning reserved for trails (now={minutes_to_time(now)} < 12:00)")
                    continue
            if is_termy_spa(p) and termy_count >= 1:
                print(f"[LIMITS] Skip termy/spa POI ID: {poi_id(p)} (already have {termy_count}/1 termy per day)")
                continue  # Skip - already have 1 termy/spa today
            
            # UAT FIX (18.02.2026 - Problem #6): Global termy limit across all days
            # Test 08: 5 termy in 7 days is too much (max 2-3)
            if global_termy_tracking is not None and is_termy_spa(p):
                if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                    print(f"[LIMITS] Skip termy/spa POI ID: {poi_id(p)} (global limit {global_termy_tracking['count']}/{global_termy_tracking['max']})")
                    continue  # Skip - global termy limit reached
            
            # STEP 3: Budget hard filter (FIX 07.02.2026)
            # FIX #2 (22.02.2026): Use unified cost calculation (matches plan_service)
            if daily_limit is not None:
                poi_cost_total = calculate_poi_cost_for_group(p, user)
                potential_cost = daily_cost + poi_cost_total
                if potential_cost > daily_limit:
                    print(f"[FILTER] EXCLUDED by budget: POI_ID={poi_id(p)} (cost={poi_cost_total:.0f} PLN, current={daily_cost:.0f}/{daily_limit} PLN)")
                    continue  # EXCLUDE - would exceed daily budget limit

            travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
            
            # BUGFIX: For first POI with car, add parking (15 min) + walk_time
            if not last_poi and ctx.get("has_car", True):
                parking_duration = 15
                walk_time = p.get("parking_walk_time_min", 5)
                travel = parking_duration + walk_time
            
            start_time = now + travel

            # jezeli po transferze nie ma juz czasu – pomijamy POI
            if start_time >= end:
                continue

            duration = choose_duration(p, start_time, end, lunch_done, user)
            if duration <= 0:
                continue

            # CLIENT FEEDBACK (30.01.2026 - Requirement #6): Seasonal hard filter
            # Problem: Out-of-season POI inserted (Zjazd pontonem in February)
            # Solution: Explicitly check date range BEFORE is_open() validation
            # This is defensive backup - is_open() should already do this, but double-check
            from app.domain.planner.opening_hours_parser import find_current_season
            
            seasonal_data = p.get("opening_hours_seasonal")
            if seasonal_data:
                # Get current date from context
                current_date_tuple = ctx.get("date")  # (year, month, day)
                if current_date_tuple:
                    # Check if POI is in season
                    current_season = find_current_season(current_date_tuple, seasonal_data)
                    if current_season is None:
                        # Out of season - SKIP this POI
                        poi_name_debug = p.get("Name", "UNKNOWN")
                        month = current_date_tuple[1]
                        print(f"[SEASONAL FILTER] SKIP {poi_name_debug} - out of season (month: {month})")
                        continue

            if not is_open(p, start_time, duration, ctx["season"], ctx):
                continue

            poi_id_debug = p.get("id", "unknown")
            print(f"[BEFORE SCORE_POI] About to score poi_id={poi_id_debug}")
            # FIX #133: inject current consecutive-short count for scoring
            ctx["consecutive_short_count"] = consecutive_short_count
            score = score_poi(
                p=p,
                user=user,
                fatigue=fatigue,
                used=used,
                now=start_time,
                energy_left=energy,
                context=ctx,
                culture_streak=culture_streak,
                body_state=body_state,
                finale_done=finale_done,
                daily_cost=daily_cost,  # FIX #14
                daily_limit=daily_limit,  # FIX #14
                active_streak=active_streak,  # FIX #99E
            )
            
            poi_name_debug = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"[AFTER SCORE_POI] poi_id={poi_id_debug} ({poi_name_debug}): score={score:.1f}, best_so_far={best_score:.1f}")
            
            # FEEDBACK KLIENTKI (03.02.2026): Boost core POI if core_min not met
            # If we need core POI and this is core, add massive bonus
            if core_attraction_count < limits.get("core_min", 1) and is_core:
                score += 50  # Huge bonus to ensure core POI gets selected
                print(f"[CORE POI] Boosting {p.get('Name')} (core) by +50 to meet core_min")

            # BUGFIX (31.01.2026 - Problem #7): Increased travel penalty from 0.1 to 0.5
            # Prefer closer POI - e.g., Termy Zakopiańskie (closer) over Gorący Potok (farther)
            # Old: 22 min = -2.2 penalty (too weak)
            # New: 22 min = -11 penalty (strong preference for nearby)
            score -= travel * 0.5
            
            # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING): Trail priority boost for mountain_hiking
            # CRITICAL: Trails must be selected BEFORE cutoff time (10:00 AM)
            # Problem: Engine selects high-scoring POI (termy, zoo) first, then `now` exceeds 10:00
            #          Trail cutoff filter blocks all trails → 0 trails in plan
            # Solution: Massive boost for trails in mountain_hiking BEFORE cutoff time
            #          Ensures trails selected first (early morning) before other POI
            trip_type = context.get("trip_type", "")
            is_trail = p.get("type") == "trail"
            TRAIL_CUTOFF = 600  # 10:00 AM in minutes
            
            if is_trail and trip_type == "mountain_hiking" and now < TRAIL_CUTOFF:
                trail_early_boost = 300  # PHASE 8 FIX #5: Increased 150->300 to beat variety randomness
                score += trail_early_boost
                poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                print(f"[TRAIL PRIORITY] +{trail_early_boost} boost for trail: {poi_name_safe} "
                      f"(mountain_hiking mode, now={minutes_to_time(now)} < 10:00)")
            
            # FIX #7 (02.02.2026): Soft limit penalty
            # After soft limit, heavily penalize additional attractions
            if attraction_count >= limits["soft"]:
                score -= 50  # Strong penalty to discourage exceeding soft limit
                print(f"[LIMITS] Soft limit penalty: {attraction_count}/{limits['soft']} attractions, -50 score")
            
            # FIX #5 (UAT Round 3 - 19.02.2026): PREFERENCE COVERAGE BOOST
            # Client feedback: "Część atrakcji jest zoo/rozrywka mimo prefs museum_heritage + cultural"
            # After 2 attractions added, massively boost POI matching uncovered top 3 preferences
            if attraction_count >= 2:
                user_prefs = user.get("preferences", [])
                top_3_prefs = user_prefs[:3]  # Top 3 preferences only
                uncovered = set(top_3_prefs) - covered_preferences
                
                if uncovered:
                    # Check if this POI matches any uncovered preference
                    from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
                    
                    poi_type = p.get("type", "")
                    poi_tags = set(p.get("tags", []))
                    
                    matched_uncovered_prefs = set()
                    for pref in uncovered:
                        pref_config = USER_PREFERENCES_TO_TAGS.get(pref, {})
                        type_matches = pref_config.get("type_match", [])
                        tag_matches = set(pref_config.get("tags", []))
                        
                        # Check if POI matches this preference
                        if poi_type in type_matches or poi_tags & tag_matches:
                            matched_uncovered_prefs.add(pref)
                    
                    # Apply massive boost for uncovered preferences
                    if matched_uncovered_prefs:
                        boost = len(matched_uncovered_prefs) * 75  # +75 per uncovered preference
                        score += boost
                        print(f"[PREFERENCE COVERAGE] +{boost} boost for uncovered prefs: {matched_uncovered_prefs} (POI: {poi_name(p)})")

            # CLIENT REQUIREMENT (04.02.2026): Collect candidates within 1% of best score for variety
            # This prevents always selecting same POI, adds diversity to plans
            if score > best_score:
                best = p
                best_score = score
                best_travel = travel
                best_duration = duration
        
        # CLIENT REQUIREMENT (08.02.2026): CORE POI ROTATION
        # Special handling when we need core POI: collect ALL viable core candidates
        # (not just 1% threshold) to enable rotation among top core POI
        # This prevents always selecting same high-scoring core (e.g., Morskie Oko)
        if best:
            # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING FIX #4):
            # CRITICAL: Skip core rotation for mountain_hiking to allow trails in main loop
            # Problem: Core rotation selects museums/termy FIRST (priority_level=12), 
            #          trails never selected because they lack core status
            # Solution: For mountain_hiking trips, skip core rotation → trails compete 
            #          in main loop where they have +150 boost → higher selection chance
            # Rationale: Trails should be PRIMARY attraction for mountain_hiking, not museums
            trip_type = context.get("trip_type", "")
            skip_core_rotation = (trip_type == "mountain_hiking")
            
            # Check if we need to select a core POI
            if core_attraction_count < limits.get("core_min", 1) and not skip_core_rotation:
                # CORE POI ROTATION LOGIC
                # Collect ALL viable core POI candidates to enable rotation
                core_candidates = []
                
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # Only collect core POI for rotation
                    is_core = is_core_poi(p)
                    if not is_core:
                        continue
                    
                    # Apply same filters as main loop
                    # FIX #10.4: Apply kids POI filter to core rotation path
                    if should_exclude_kids_poi_for_adults(p, user):
                        continue
                    
                    if should_exclude_by_target_group(p, user):
                        continue
                    if should_exclude_by_intensity(p, user):
                        continue
                    
                    # BUGFIX (30.04.2026 - CRITICAL): Trail limit enforcement in core rotation
                    # Problem: Core rotation rescans POI without applying trail limit filter
                    # Solution: Apply same trail limit check as main loop (lines 2510-2517)
                    if p.get("type") == "trail" and global_trail_tracking is not None:
                        trails_remaining = global_trail_tracking["max"] - global_trail_tracking["count"]
                        if trails_remaining <= 0:
                            continue  # SKIP - trail limit reached for entire trip
                    
                    # FIX #40 (CLIENT FEEDBACK): Trail per-day enforcement in core rotation
                    # Same fix as variety logic - core rotation also lacked trail_day_mode check
                    if p.get("type") == "trail" and trail_day_mode:
                        continue  # SKIP - already have 1 trail today (per-day trail limit)
                    
                    # FIX #73 (25.05.2026): Apply full post-trail limit in core rotation
                    # Previously only blocked extra trails; now also blocks non-trail POI when limit reached
                    if trail_day_mode and max_poi_after_trail == 0:
                        continue  # Heavy trail day - no POI allowed after trail (not even core)
                    if trail_day_mode and post_trail_poi_count >= max_poi_after_trail:
                        continue  # Post-trail POI count limit reached
                    
                    # FIX #47/#54 (20.05.2026): Trail intensity filter in core rotation
                    if p.get("type") == "trail":
                        _cr_trail_dur = p.get("duration_min", 0)
                        _cr_style = user.get("travel_style", "")
                        _cr_group = user.get("target_group", "")
                        _cr_max = 150 if _cr_group == "seniors" else (180 if _cr_style == "relax" else (240 if _cr_style == "balanced" else None))  # FIX #56
                        if _cr_max and _cr_trail_dur > _cr_max:
                            continue  # SKIP - trail too demanding

                    # BUGFIX (30.04.2026 - CRITICAL): Termy limit enforcement in core rotation
                    # Problem: Core rotation rescans POI without applying termy limit filter
                    # Solution: Apply same termy limit check as main loop (lines 2657-2660)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # SKIP - termy limit reached for entire trip
                    
                    if is_core and core_attraction_count >= limits["core_max"]:
                        continue
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue
                    
                    # FIX #70 (23.05.2026): Apply termy/spa daily limit to ALL groups (not just seniors)
                    # Root cause: Problem #10 fix only applied to main loop; sub-loops still seniors-only.
                    if is_termy_spa(p) and termy_count >= 1:
                        continue
                    
                    # BUDGET HARD FILTER
                    # FIX #2 (22.02.2026): Use unified cost calculation
                    if daily_limit is not None:
                        poi_cost_total = calculate_poi_cost_for_group(p, user)
                        if daily_cost + poi_cost_total > daily_limit:
                            continue
                    
                    travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        travel = parking_duration + walk_time
                    
                    start_time = now + travel
                    if start_time >= end:
                        continue
                    
                    duration = choose_duration(p, start_time, end, lunch_done, user)
                    if duration <= 0:
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Calculate score with core boost
                    score = score_poi(
                        p=p, user=user, fatigue=fatigue, used=used, now=start_time,
                        energy_left=energy, context=ctx, culture_streak=culture_streak,
                        body_state=body_state, finale_done=finale_done,
                        daily_cost=daily_cost, daily_limit=daily_limit,  # FIX #14
                        active_streak=active_streak,  # FIX #99E
                    )
                    
                    # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING): Trail priority boost in core rotation
                    # CRITICAL: Apply same trail boost here as in main selection loop
                    trip_type = ctx.get("trip_type", "")
                    is_trail = p.get("type") == "trail"
                    TRAIL_CUTOFF = 600  # 10:00 AM
                    
                    if is_trail and trip_type == "mountain_hiking" and start_time < TRAIL_CUTOFF:
                        trail_early_boost = 300  # PHASE 8 FIX #5: Same as main loop (150->300)
                        score += trail_early_boost
                        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                        print(f"[CORE ROTATION TRAIL] +{trail_early_boost} boost for trail: {poi_name_safe}")
                    
                    score += 50  # Core boost (same as main loop)
                    score -= travel * 0.5
                    
                    if attraction_count >= limits["soft"]:
                        score -= 50
                    
                    core_candidates.append({
                        "poi": p,
                        "score": score,
                        "travel": travel,
                        "duration": duration
                    })
                
                # Sort by score and select randomly from top 4-5 core POI
                if core_candidates:
                    core_candidates.sort(key=lambda x: x["score"], reverse=True)
                    top_core = core_candidates[:5]  # Top 5 core POI
                    
                    # Random selection from top core POI for variety
                    selected = random.choice(top_core)
                    best = selected["poi"]
                    best_score = selected["score"]
                    best_travel = selected["travel"]
                    best_duration = selected["duration"]
                    print(f"[CORE ROTATION] Selected from {len(top_core)} top core POI: POI_ID={poi_id(best)} (score={best_score:.1f})")
            
            else:
                # NORMAL VARIETY LOGIC (when core_min already met or for non-core POI)
                # CLIENT REQUIREMENT (04.02.2026): Randomize within 1% of top score
                threshold = best_score * 0.99  # 1% tolerance
                candidates = []
                
                # Re-scan to find all POI within 1% of best score
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # Apply same filters as before
                    # FIX #10.4: Apply kids POI filter to variety logic path (CRITICAL!)
                    # This was the root cause of poi_15 (termy with kids_attractions) appearing
                    if should_exclude_kids_poi_for_adults(p, user):
                        continue
                    
                    if should_exclude_by_target_group(p, user):
                        continue
                    if should_exclude_by_intensity(p, user):
                        continue
                    
                    is_core = is_core_poi(p)
                    if is_core and core_attraction_count >= limits["core_max"]:
                        continue
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue
                    
                    # BUGFIX (30.04.2026 - CRITICAL): Trail limit enforcement in variety logic
                    # Problem: Variety logic rescans POI without applying trail limit filter
                    # Solution: Apply same trail limit check as main loop (lines 2510-2517)
                    if p.get("type") == "trail" and global_trail_tracking is not None:
                        trails_remaining = global_trail_tracking["max"] - global_trail_tracking["count"]
                        if trails_remaining <= 0:
                            continue  # SKIP - trail limit reached for entire trip
                    
                    # FIX #40 (CLIENT FEEDBACK): Trail per-day enforcement in variety rescan
                    # Problem: trail_day_mode check only existed in main scoring loop (~line 2929)
                    #          Variety logic re-scanned POIs without this check → trail snuck into
                    #          candidates even when trail_day_mode=True. FIX #7 then FORCED selection.
                    # Solution: Apply trail_day_mode check here too.
                    if p.get("type") == "trail" and trail_day_mode:
                        continue  # SKIP - already have 1 trail today (per-day trail limit)
                    
                    # FIX #73 (25.05.2026): Apply full post-trail limit in variety rescan
                    if trail_day_mode and max_poi_after_trail == 0:
                        continue  # Heavy trail day - no POI allowed after trail
                    if trail_day_mode and post_trail_poi_count >= max_poi_after_trail:
                        continue  # Post-trail POI count limit reached
                    
                    # FIX #47/#54 (20.05.2026): Trail intensity filter in variety loop
                    if p.get("type") == "trail":
                        _var_trail_dur = p.get("duration_min", 0)
                        _var_style = user.get("travel_style", "")
                        _var_group = user.get("target_group", "")
                        _var_max = 150 if _var_group == "seniors" else (180 if _var_style == "relax" else (240 if _var_style == "balanced" else None))  # FIX #56
                        if _var_max and _var_trail_dur > _var_max:
                            continue  # SKIP - trail too demanding

                    # BUGFIX (30.04.2026 - CRITICAL): Termy limit enforcement in variety logic
                    # Problem: Variety logic rescans POI without applying termy limit filter
                    # Solution: Apply same termy limit check as main loop (lines 2657-2660)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # SKIP - termy limit reached for entire trip
                    
                    # FIX #70 (23.05.2026): Apply termy/spa daily limit to ALL groups (not just seniors)
                    if is_termy_spa(p) and termy_count >= 1:
                        continue
                    
                    # BUDGET HARD FILTER (FIX 07.02.2026): Apply to candidate collection
                    # FIX #2 (22.02.2026): Use unified cost calculation
                    if daily_limit is not None:
                        poi_cost_total = calculate_poi_cost_for_group(p, user)
                        if daily_cost + poi_cost_total > daily_limit:
                            continue  # EXCLUDE - would exceed daily budget limit
                    
                    travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        travel = parking_duration + walk_time
                    
                    start_time = now + travel
                    if start_time >= end:
                        continue
                    
                    duration = choose_duration(p, start_time, end, lunch_done, user)
                    if duration <= 0:
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Calculate same score
                    score = score_poi(
                        p=p, user=user, fatigue=fatigue, used=used, now=start_time,
                        energy_left=energy, context=ctx, culture_streak=culture_streak,
                        body_state=body_state, finale_done=finale_done,
                        daily_cost=daily_cost, daily_limit=daily_limit,  # FIX #14
                        active_streak=active_streak,  # FIX #99E
                    )
                    
                    if core_attraction_count < limits.get("core_min", 1) and is_core:
                        score += 50
                    
                    score -= travel * 0.5
                    
                    # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING FIX #6):
                    # CRITICAL: Apply trail boost in variety logic (else branch)
                    # Problem: When core rotation skipped (mountain_hiking), variety logic
                    #          recalculates scores WITHOUT trail boost → trails lose advantage
                    # Solution: Add same trail boost here as in main loop (+300)
                    trip_type_variety = context.get("trip_type", "")  # Use 'context', not 'ctx'
                    is_trail_variety = p.get("type") == "trail"
                    TRAIL_CUTOFF_VARIETY = 600  # 10:00 AM
                    
                    if is_trail_variety and trip_type_variety == "mountain_hiking" and start_time < TRAIL_CUTOFF_VARIETY:
                        trail_early_boost = 300  # Same as main loop and core rotation
                        score += trail_early_boost
                        # Debug print removed to avoid spam - already printed in main loop
                    
                    if attraction_count >= limits["soft"]:
                        score -= 50
                    
                    # Collect candidates within 1% threshold
                    if score >= threshold:
                        candidates.append({
                            "poi": p,
                            "score": score,
                            "travel": travel,
                            "duration": duration
                        })
                
                # Randomize selection from top candidates
                if len(candidates) > 1:
                    # BUGFIX (28.04.2026 - PHASE 8 TRAIL ROUTING FIX #7):
                    # CRITICAL: Don't randomize if trails have highest score
                    # Problem: Trails get +300 boost → highest score, but random.choice()
                    #          picks random candidate (may be non-trail with low score)
                    # Solution: For mountain_hiking, if top candidate is trail, select it
                    #          (disable variety randomness for trails)
                    trip_type_selection = context.get("trip_type", "")
                    trail_count_in_candidates = sum(1 for c in candidates if c["poi"].get("type") == "trail")
                    
                    # DEBUG (28.04.2026): Verify Fix #7 executing
                    print(f"[FIX #7 CHECK] trip_type='{trip_type_selection}', trails={trail_count_in_candidates}/{len(candidates)}")
                    
                    if trip_type_selection == "mountain_hiking" and trail_count_in_candidates > 0:
                        # Sort by score descending and check if top is trail
                        sorted_candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
                        top_candidate = sorted_candidates[0]
                        top_is_trail = top_candidate["poi"].get("type") == "trail"
                        print(f"[FIX #7 CHECK] Top POI type={top_candidate['poi'].get('type')}, is_trail={top_is_trail}, score={top_candidate['score']:.1f}")
                        
                        if top_is_trail:
                            # Top is trail → select it (no randomness)
                            selected = top_candidate
                            poi_name_safe = str(top_candidate["poi"].get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
                            print(f"[TRAIL FORCED] Top is trail → selected at now={minutes_to_time(now)}: {poi_name_safe} (score={top_candidate['score']:.1f})")
                        else:
                            # Top is not trail → normal randomness
                            selected = random.choice(candidates)
                            print(f"[VARIETY] Top NOT trail → random selection")
                    else:
                        # Normal randomness for non-mountain or no trails
                        selected = random.choice(candidates)
                    
                    best = selected["poi"]
                    best_score = selected["score"]
                    best_travel = selected["travel"]
                    best_duration = selected["duration"]
                    print(f"[VARIETY] Selected from {len(candidates)} candidates within 1% of top score: POI_ID={poi_id(best)} (score={best_score:.1f})")
                elif len(candidates) == 1:
                    # Only one candidate, use it (same as before)
                    best = candidates[0]["poi"]
                    best_score = candidates[0]["score"]
                    best_travel = candidates[0]["travel"]
                    best_duration = candidates[0]["duration"]
        
        # Check if POI was selected

        if not best:
            # FALLBACK for gaps >60 min: Try soft POI or add free_time
            # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Change threshold 20→60 min
            # Client feedback: 8/10 tests have 1-3h gaps unexplained
            # Client requirement: gaps >60 min should have soft POI or free_time
            
            remaining_time = end - now
            
            if remaining_time >= 60:  # Only handle gaps >60 min (UAT Round 2 fix)
                # Try to find soft POI: low intensity, short duration, low must_see
                soft_best = None
                soft_score = -9999
                soft_duration = 0

                # FIX #81 (27.05.2026): Soft POI loop must respect trail_day_mode limits.
                # ROOT CAUSE: Without this guard the soft loop bypassed post-trail limit →
                # post_trail_poi_count reached 2-3 with max=1 (e.g. after moderate trail).
                _soft_poi_candidates = (
                    [] if (trail_day_mode and (max_poi_after_trail == 0 or
                           post_trail_poi_count >= max_poi_after_trail))
                    else pois
                )

                for p in _soft_poi_candidates:
                    if poi_id(p) in used:
                        continue
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    # FIX #10.4: Apply kids POI filter to soft POI fallback path
                    if should_exclude_kids_poi_for_adults(p, user):
                        continue  # EXCLUDE - kids POI for adult groups
                    
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue  # Skip - already have 1 kids-focused POI today
                    
                    # BUDGET HARD FILTER (FIX 07.02.2026): Apply to soft POI too
                    # FIX #2 (22.02.2026): Use unified cost calculation
                    if daily_limit is not None:
                        poi_cost_total = calculate_poi_cost_for_group(p, user)
                        if daily_cost + poi_cost_total > daily_limit:
                            continue  # EXCLUDE - would exceed daily budget limit
                    
                    # UAT FIX (18.02.2026 - Problem #6): Check global termy limit (fallback soft POI)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # Skip - global termy limit reached
                    
                    # FIX #81 (27.05.2026): After long/hard trail, block high-energy POIs in soft fallback.
                    # Tag-based blocklist (same as main loop — type='poi' for all non-trail POIs).
                    # FIX #85 (28.05.2026): Extended blocklist for very heavy trails.
                    if trail_day_mode and (trail_duration >= 180 or trail_difficulty in ["hard", "extreme"]):
                        _ACTIVE_TAGS_F81_SOFT = {
                            "rope_park", "adventure_park", "medium_intensity_activity",
                            "family_theme_park", "kids_zone", "snow_tubing",
                            "water_rides", "adrenaline_attractions", "zip_line", "luge"
                        }
                        if trail_duration >= 240 or trail_difficulty in ["hard", "extreme"]:
                            _ACTIVE_TAGS_F81_SOFT |= {
                                "themed_museum", "regional_heritage", "museum_heritage", "museums",
                                "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                "interactive_exhibit", "local_history", "architecture_heritage",
                                "historic_building", "composer_artist_house", "intimate_small_museum",
                                "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                                "scenic_viewpoint",
                            }
                        _p81s_tags = set(p.get("tags") or [])
                        if _ACTIVE_TAGS_F81_SOFT & _p81s_tags:
                            continue  # Skip high-energy/cultural POIs after heavy trail

                    # FIX #88 (28.05.2026): Adventure profile museum cap in soft fallback loop too.
                    if travel_style == "adventure" and daily_museum_count >= 1:
                        _adv_museum_soft_tags = {
                            "themed_museum", "regional_heritage", "museum_heritage", "museums",
                            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                            "interactive_exhibit", "local_history", "architecture_heritage",
                            "historic_building", "composer_artist_house", "intimate_small_museum",
                            "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                        }
                        if _adv_museum_soft_tags & set(p.get("tags", [])):
                            continue  # Adventure already has a museum today

                    # FIX #99D: Friends profile museum cap in soft fallback loop too.
                    if user.get("target_group") == "friends" and friends_museum_today >= 1:
                        _friends_museum_soft_tags = {
                            "themed_museum", "regional_heritage", "museum_heritage", "museums",
                            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                            "interactive_exhibit", "local_history", "architecture_heritage",
                            "historic_building", "composer_artist_house", "intimate_small_museum",
                            "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                        }
                        if _friends_museum_soft_tags & set(p.get("tags", [])):
                            continue  # Friends already has a museum today

                    # FIX #127 (30.05.2026): Solo museum cap in soft fallback loop too (max 2/day).
                    if user.get("target_group") == "solo" and solo_museum_today >= 2:
                        _solo_museum_soft_tags = {
                            "themed_museum", "regional_heritage", "museum_heritage", "museums",
                            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                            "interactive_exhibit", "local_history", "architecture_heritage",
                            "historic_building", "composer_artist_house", "intimate_small_museum",
                            "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                        }
                        if _solo_museum_soft_tags & set(p.get("tags", [])):
                            continue  # Solo already has 2 museums today

                    # FIX #132 (31.05.2026): Couples museum cap in soft fallback loop too (max 2/day).
                    if user.get("target_group") == "couples" and couples_museum_today >= 2:
                        _couples_museum_soft_tags = {
                            "themed_museum", "regional_heritage", "museum_heritage", "museums",
                            "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                            "interactive_exhibit", "local_history", "architecture_heritage",
                            "historic_building", "composer_artist_house", "intimate_small_museum",
                            "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                        }
                        if _couples_museum_soft_tags & set(p.get("tags", [])):
                            continue  # Couples already has 2 museums today

                    # Soft POI criteria (client requirements)
                    # Since all Zakopane POI have intensity='medium', accept medium intensity
                    # Focus on: short duration (10-30 min) + low must_see_score (0-2)
                    
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:  # 10-30 min range
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    # Calculate travel time
                    soft_travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    
                    # For first soft POI with car, add parking + walk
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        soft_travel = parking_duration + walk_time
                    
                    start_time = now + soft_travel
                    
                    if start_time >= end:
                        continue
                    
                    duration = min(time_min, remaining_time - soft_travel)
                    if duration < 10:  # Too short
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Simple scoring for soft POI (prefer nearby, quick visits)
                    score = 10 - soft_travel * 0.5 + (30 - time_min) * 0.2
                    
                    if score > soft_score:
                        soft_best = p
                        soft_score = score
                        soft_duration = duration
                        soft_travel_time = soft_travel  # Store travel time
                
                if soft_best:
                    # Found soft POI - add it
                    best = soft_best
                    best_score = soft_score
                    best_travel = soft_travel_time  # Use stored travel time
                    best_duration = soft_duration
                else:
                    # No soft POI - add free_time with smart label
                    # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Remove 40 min limit, use smart labels
                    # Client feedback: 2-3h gaps need longer free_time, context-aware descriptions
                    # FIX #3 (22.02.2026): Also cap at day_end to prevent violations
                    # CRITICAL FIX (01.05.2026): Changed cap from 120 to 60 min (CLIENT FEEDBACK - Problem #7)
                    # FIX #86 (28.05.2026): After 15:00 create ONE big evening block (no 60-min cap).
                    # Prevents multiple 60-min blocks — client wants "Wieczorny relaks" single block.
                    if now >= 900:  # After 15:00 → one big "Wieczorny relaks" block
                        free_duration = min(remaining_time, end - now)
                    else:
                        free_duration = min(60, remaining_time, end - now)  # Max 60 min before afternoon
                    free_start_time = minutes_to_time(now)
                    free_end_time = minutes_to_time(now + free_duration)
                    
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                    if overlaps:
                        print(f"[OVERLAP DETECTED] free_time {free_start_time}-{free_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                        # Skip this free_time, continue loop
                        now += 15
                        continue
                    
                    # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Smart label based on context
                    smart_label = _get_free_time_label(plan, now, free_duration, end, profile=user.get("target_group"))
                    
                    plan.append({
                        "type": "free_time",
                        "start_time": free_start_time,
                        "end_time": free_end_time,
                        "duration_min": free_duration,
                        "description": smart_label
                    })
                    
                    print(f"[GAP FILL] Added free_time ({free_duration}min) with label: {smart_label.encode('ascii', errors='ignore').decode('ascii')}")
                    now += free_duration
                    continue
            else:
                # Gap <60 min or not enough time - just advance time
                # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Updated comment to reflect 60 min threshold
                now += 15
                if now + 30 >= end:
                    break
                continue
        
        # POI selected (either normal or soft) - add to plan
        if not best:
            continue

        transfer_time = (
            max(best_travel, MIN_TRANSFER_MIN) if last_poi else 0
        )
        
        # PHASE 8 FEATURE #5 (27.04.2026): Check driving time limits BEFORE adding transfer
        # Prevent excessive driving time (users don't want 3+ hours/day in car)
        if last_poi and transfer_time >= 10:  # Only count car drives (>=10 min)
            # Check single drive limit
            if transfer_time > max_single_drive:
                poi_name_safe = str(poi_name(best)).encode('ascii', errors='ignore').decode('ascii')
                print(f"[DRIVE LIMIT] EXCLUDED POI: {poi_name_safe} - single drive too long "
                      f"({transfer_time}min > {max_single_drive}min limit for {cluster_type})")
                # BUGFIX (28.04.2026 - PHASE 8 INFINITE LOOP FIX #8):
                # CRITICAL: Mark POI as used before continue to prevent retry loop
                used.add(poi_id(best))
                continue
            
            # Check daily drive limit
            if total_drive_time + transfer_time > max_daily_drive:
                poi_name_safe = str(poi_name(best)).encode('ascii', errors='ignore').decode('ascii')
                print(f"[DRIVE LIMIT] EXCLUDED POI: {poi_name_safe} - would exceed daily drive limit "
                      f"({total_drive_time + transfer_time}min > {max_daily_drive}min for {cluster_type})")
                # BUGFIX (28.04.2026 - PHASE 8 INFINITE LOOP FIX #8):
                # CRITICAL: Mark POI as used before continue to prevent retry loop
                used.add(poi_id(best))
                continue

        # BUGFIX (17.02.2026): Check if POI + buffers would exceed day_end
        # Estimate buffer time: parking_walk (~5 min) + restroom (~5-10 min) + photo_stop (~10 min) = ~20-25 min
        # Add 30 min safety margin to account for buffers
        estimated_buffer_time = 30
        if now + transfer_time + best_duration + estimated_buffer_time > end:
            poi_name_safe = str(poi_name(best)).encode('ascii', errors='ignore').decode('ascii')
            print(f"[POI SKIP] POI {poi_name_safe} would exceed day_end with buffers ({minutes_to_time(now + transfer_time + best_duration + estimated_buffer_time)} > {minutes_to_time(end)})")
            break

        if last_poi:
            transfer_time = max(best_travel, MIN_TRANSFER_MIN)

            # FIX #77 (27.05.2026): Compute GPS distance so plan_service can skip transit for close POIs
            _t77_lat1, _t77_lng1 = last_poi.get("lat"), last_poi.get("lng")
            _t77_lat2, _t77_lng2 = best.get("lat"), best.get("lng")
            _t77_dist_km = haversine_distance(_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2) if all([_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2]) else 999.0

            # FIX #131: mountain-aware walk threshold
            _is_walking = _t77_dist_km < _walk_threshold(last_poi, best)
            # FIX #111 (06.06.2026): Mark inter-city transfers (distance > INTER_CITY_THRESHOLD_KM)
            _is_inter_city = _t77_dist_km >= INTER_CITY_THRESHOLD_KM

            # FIX #128: Skip zero-distance or duplicate transfer (same location → no transit needed)
            _skip_transfer = (
                _t77_dist_km < 0.05
                or (plan and plan[-1].get("type") == "transfer"
                    and plan[-1].get("to") == poi_name(best))
                # FIX #142 (31.05.2026): Skip transfer when recent plan items show we're already
                # at the same destination — prevents transit→lunch→transit→same_place patterns.
                # FIX #144 (01.06.2026): Extended lookback from 3 to 8 to catch more duplicate patterns.
                or (len(plan) >= 2
                    and any(it.get("type") == "transfer" and it.get("to") == poi_name(best)
                            for it in plan[-8:]))
            )
            if not _skip_transfer:
                plan.append(
                    {
                        "type": "transfer",
                        "from": poi_name(last_poi),
                        "to": poi_name(best),
                        "duration_min": transfer_time,
                        "distance_km": round(_t77_dist_km, 3),  # FIX #77
                        "transport_mode": "walking" if _is_walking else "car",  # FIX #98/#131
                        "inter_city": _is_inter_city,  # FIX #111
                    }
                )

                now += transfer_time

                # PHASE 8 FEATURE #5 (27.04.2026): Track total drive time for daily limit
                # FIX #98 (28.05.2026): Only count car transfers, not walking
                if transfer_time >= 10 and not _is_walking:
                    total_drive_time += transfer_time
                    print(f"[DRIVE TRACKING] Added {transfer_time}min drive, total today: {total_drive_time}min / {max_daily_drive}min")

                # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add parking_walk buffer after car transfer
                # Client requirement: "Oś czasu ma dziury" - dodaj buffer parking_walk po transfer
                # FIX #98 (28.05.2026): Skip parking_walk for walking transfers – no car, no parking
                if ctx.get("has_car", True) and not _is_walking:
                    parking_walk_duration = best.get("parking_walk_time_min", 5)
                    # Ensure reasonable range: 5-15 min
                    parking_walk_duration = max(5, min(15, int(parking_walk_duration)))
                    now = _add_buffer_item(
                        plan,
                        now,
                        "parking_walk",
                        parking_walk_duration,
                        reason_context={"poi_name": poi_name(best)},
                        day_end=end
                    )
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add tickets_queue buffer for popular attractions
        # Client requirement: Add buffer for waiting in line at popular places
        popularity_score = best.get("popularity_score", 0)
        if popularity_score >= 7:  # Popular attractions (score 7-10)
            # Queue time: 5-20 min based on popularity
            queue_duration = int(5 + (popularity_score - 7) * 5)  # 7→5min, 8→10min, 9→15min, 10→20min
            queue_duration = max(5, min(20, queue_duration))
            now = _add_buffer_item(
                plan,
                now,
                "tickets_queue",
                queue_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )

        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding attraction
        attraction_start_time = minutes_to_time(now)
        attraction_end_time = minutes_to_time(now + best_duration)
        
        overlaps, conflict = _check_time_overlap(plan, attraction_start_time, attraction_end_time)
        if overlaps:
            print(f"[OVERLAP DETECTED] attraction {poi_name(best)} {attraction_start_time}-{attraction_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
            # FIX #62 (22.05.2026): Phantom transfer prevention
            # If we already appended a transfer/parking_walk to plan for this POI, remove them
            # before continuing, otherwise plan will have a transfer without a destination POI.
            while plan and plan[-1].get("type") in ("transfer", "parking_walk", "buffer"):
                removed = plan.pop()
                now -= removed.get("duration_min", 0)
                # Also rollback drive tracking if it was a car transfer
                # FIX #98 (28.05.2026): Use transport_mode field instead of duration proxy
                if removed.get("type") == "transfer" and removed.get("transport_mode", "car") == "car" and removed.get("duration_min", 0) >= 10:
                    total_drive_time = max(0, total_drive_time - removed.get("duration_min", 0))
                print(f"[FIX#62] Rolled back phantom {removed.get('type')} ({removed.get('duration_min',0)}min)")
            # Skip this POI, mark as used to avoid retry, continue loop
            used.add(poi_id(best))
            now += 15  # Advance time slightly
            continue
        
        # PHASE 8 FEATURE #7 (27.04.2026): Classify POI as main/filler
        poi_classification, poi_weight, poi_weight_breakdown = classify_poi_weight(best)

        plan.append(
            {
                "type": "attraction",
                "poi": best,  # Całe POI dla PlanService
                "name": poi_name(best),
                "start_time": attraction_start_time,
                "end_time": attraction_end_time,
                "meta": {
                    "experience_role": best.get("experience_role"),
                    "is_culture": bool(is_culture(best)),
                    "body_state_after": get_next_body_state(best, body_state),
                    "poi_class": poi_classification,  # PHASE 8 FEATURE #7: "main" or "filler"
                    "poi_weight": round(poi_weight, 2),  # PHASE 8 FEATURE #7: classification weight
                },
            }
        )
        
        # PHASE 8 FEATURE #7: Log POI classification
        poi_name_safe = str(poi_name(best)).encode('ascii', errors='ignore').decode('ascii')
        print(f"[POI CLASS] {poi_name_safe}: {poi_classification.upper()} "
              f"(weight={poi_weight:.1f}, "
              f"time={poi_weight_breakdown['time']:.1f}, "
              f"priority={poi_weight_breakdown['priority']:.1f}, "
              f"popularity={poi_weight_breakdown['popularity']:.1f}, "
              f"type={poi_weight_breakdown['type']:.1f})")

        # HOTFIX #10.7: Debug logging - track which POI engine adds
        print(f"[ENGINE SELECTION] ADDED POI: id={poi_id(best)}, time={minutes_to_time(now)}")
        
        # BUDGET TRACKING (FIX 07.02.2026): Update daily cost
        # FIX #2 (22.02.2026): Use unified cost calculation (matches plan_service)
        poi_cost_total = calculate_poi_cost_for_group(best, user)
        daily_cost += poi_cost_total
        if daily_limit is not None:
            print(f"[BUDGET] POI cost: {poi_cost_total:.0f} PLN, daily total: {daily_cost:.0f}/{daily_limit} PLN")

        # DEBUG #Problem9 (14.05.2026): Track now update to diagnose overlap
        old_now = now
        now += best_duration
        if minutes_to_time(old_now) >= "18:00":
            print(f"[PROBLEM9 DEBUG] EVENING POI: {poi_name(best)}, start={minutes_to_time(old_now)}, duration={best_duration}, new_now={minutes_to_time(now)}, end={minutes_to_time(old_now + best_duration)}")
        energy -= energy_cost(best, best_duration, ctx)
        fatigue += 1
        # FIX #133 (31.05.2026): Track consecutive short POIs — short POI = time_min <= 35 min
        # Extra fatigue accumulated when short POIs pile up (handled via score_poi penalty)
        _best_time_min = int(best.get("time_min") or 0)
        if _best_time_min > 0 and _best_time_min <= 35:
            consecutive_short_count += 1
        else:
            consecutive_short_count = 0  # reset on any non-short POI
        used.add(poi_id(best))
        
        # ETAP 2 - DAY 3 (15.02.2026): Update global_used for cross-day tracking
        if global_used is not None:
            global_used.add(poi_id(best))
        
        # CRITICAL FIX (30.04.2026): Increment trail counter BEFORE any continue statements!
        # BUG: Lunch post-POI check (line ~3420) does continue BEFORE reaching trail counter increment
        #      This caused trails to be added without incrementing counter → limit never enforced
        # Solution: Move trail counter increment HERE (immediately after adding POI, before lunch check)
        if best.get("type") == "trail" and global_trail_tracking is not None:
            global_trail_tracking["count"] += 1
            print(f"[TRAIL LIMIT] Trail added - Global count: {global_trail_tracking['count']}/{global_trail_tracking['max']}")
        
        # FIX #46 (20.05.2026 - CRITICAL BUG): Set trail_day_mode HERE before any continue statement
        # ROOT CAUSE: post-POI lunch check at ~line 3836 has `continue` that jumps back to while loop
        #             SKIPPING the trail_day_mode = True at line ~3947 → trail_day_mode never set!
        #             This allowed a SECOND trail to be added on the same day (Bug #1 from client)
        # Solution: Set trail_day_mode + max_poi_after_trail HERE, before lunch post-POI check
        if best.get("type") == "trail" and not trail_day_mode:
            trail_day_mode = True
            # FIX #72 (25.05.2026): Excel trails use time_min, not duration_min (same bug as FIX #69)
            # DB trails map time_min→duration_min in to_dict(). Excel trails keep time_min.
            _trail_raw_dur_early = best.get("duration_min") or best.get("time_min") or 0
            _trail_diff_early = best.get("difficulty_level", "moderate").lower()
            # FIX #81 (27.05.2026): Set trail_duration/trail_difficulty early so the type-restriction
            # filter works correctly even when the lunch post-POI `continue` fires and prevents the
            # main trail-set block (~line 4287) from running.
            trail_duration = _trail_raw_dur_early
            trail_difficulty = _trail_diff_early
            if _trail_diff_early in ["hard", "extreme"] or _trail_raw_dur_early >= 240:
                max_poi_after_trail = 1  # FIX #81 (27.05.2026): was 0 — allow 1 calm POI after hard trail
            elif _trail_diff_early == "moderate" or _trail_raw_dur_early >= 180:
                max_poi_after_trail = 1
            else:
                max_poi_after_trail = 2
            print(f"[FIX #46] trail_day_mode=True set early (before lunch check) - max_poi_after_trail={max_poi_after_trail}")

        # CRITICAL FIX (30.04.2026 - FIX #15): Increment termy counter BEFORE any continue statements!
        # BUG: Same as trail counter bug - continue statement at line ~3420 (lunch post-POI check)
        #      prevents termy increment code at line ~3575 from executing
        # Solution: Move termy counter increment HERE (immediately after trail increment, before continue)
        if global_termy_tracking is not None and is_termy_spa(best):
            old_count = global_termy_tracking["count"]
            global_termy_tracking["count"] += 1
            best_name = safe_str(best.get('name', 'UNKNOWN'))
            print(f"[TERMY LIMIT] Termy added: {best_name} - Global count: {old_count} → {global_termy_tracking['count']}/{global_termy_tracking['max']}")

        # FIX #155 (REGRESSION FIX): Set last_poi BEFORE lunch post-POI check.
        # ROOT CAUSE: The lunch post-POI check (below) has a `continue` statement that jumps
        #             back to the while loop, SKIPPING `last_poi = best` at line ~5060+.
        #             This caused the NEXT iteration to see last_poi=None (or stale), so the
        #             `if last_poi:` transit block was skipped → MISSING TRANSIT between
        #             distant consecutive attractions (e.g. Gubałówka → Polana Głodówka, 12.48km).
        # Same class of bug as FIX #46 (trail_day_mode) and FIX #15 (termy counter).
        last_poi = best

        # FIX #14 (29.04.2026 - CLIENT FEEDBACK): CRITICAL LUNCH CHECK AFTER POI
        # Problem: POI duration can push 'now' past lunch_target (e.g., 12:30 + 2.5h = 15:00)
        #          If we only check at loop start, lunch gets scheduled at 15:00+ (too late!)
        # Solution: Check IMMEDIATELY after updating 'now' - if we're past lunch_target and
        #          lunch not done, FORCE lunch insertion NOW before continuing
        # This ensures lunch happens 12:00-14:30, never 15:41+
        
        # FIX #Problem9 (13.05.2026 - Round 2): Apply group-specific lunch timing to POST-POI CHECK
        # This is the SECOND lunch insertion point - must use same timing rules as main loop
        # BUGFIX: trip_mapper.py maps group.type → user["target_group"], NOT user["group"]["type"]
        if not lunch_done:
            # Get group type from user["target_group"] (mapped by trip_mapper.py)
            group_type = user.get("target_group")
            
            # Set lunch timing based on group type (SAME as main lunch checkpoint)
            if group_type == "family_kids":
                lunch_target = time_to_minutes("12:30")    # Target 12:30
                lunch_latest = time_to_minutes("13:30")    # Latest 13:30
            elif group_type == "seniors":
                lunch_target = time_to_minutes("12:45")    # Target 12:45
                lunch_latest = time_to_minutes("13:30")    # Latest 13:30
            else:
                lunch_target = time_to_minutes(LUNCH_TARGET)  # 13:00
                lunch_latest = time_to_minutes(LUNCH_LATEST)  # 14:30
            
            # Check if POI pushed us past lunch time
            if now >= lunch_target:
                print(f"[LUNCH POST-POI CHECK] POI pushed now to {minutes_to_time(now)} (>= target {lunch_target}) - FORCING lunch NOW")
                
                # FIX #129 (XX.06.2026): Generalize FIX #102 — add return transit to city before lunch
                # for ANY POI type that is far from centrum (not just trails).
                # Prevents "lunch teleport" regardless of attraction type (cable-car, zoo, etc.).
                _lunch_location_context = "centrum"
                # FIX #156 (04.06.2026): see matching block above — gate the ZAKOPANE-hardcoded
                # return-to-centrum to Zakopane trips only (default True keeps build_day behavior).
                if best and best.get("type") != "city_center" and context.get("is_zakopane_trip", True):
                    _bp_lat = best.get("lat")
                    _bp_lng = best.get("lng")
                    if _bp_lat and _bp_lng:
                        _dist_to_city = haversine_distance(_bp_lat, _bp_lng, ZAKOPANE_CENTER_LAT, ZAKOPANE_CENTER_LNG)
                    else:
                        _dist_to_city = 0.0
                    if _dist_to_city > WALK_THRESHOLD_KM:
                        _return_min = max(5, int((_dist_to_city / 45) * 60 + 5))
                        # Only add return transit if it fits within day_end
                        if now + _return_min + 30 <= end:  # 30 min minimum for lunch
                            # FIX #147: Skip if already transferred to Zakopane centrum recently (lookback-8)
                            _skip_lunch_tr2 = any(
                                it.get("type") == "transfer" and it.get("to") == "Zakopane centrum"
                                for it in plan[-8:]
                            )
                            if not _skip_lunch_tr2:
                                plan.append({
                                    "type": "transfer",
                                    "from": poi_name(best),
                                    "to": "Zakopane centrum",
                                    "duration_min": _return_min,
                                    "distance_km": round(_dist_to_city, 3),
                                    "transport_mode": "car",
                                })
                                now += _return_min
                                print(f"[FIX #129] Added return transit from {poi_name(best)} to Zakopane centrum: {_return_min}min ({_dist_to_city:.1f}km)")
                            else:
                                print(f"[FIX #147] Skipped duplicate post-POI lunch return transit to Zakopane centrum")
                        else:
                            print(f"[FIX #129] Skipped return transit (not enough time): {_return_min}min + 30min lunch > day_end")
                            _lunch_location_context = "przy_atrakcji"
                
                # Insert lunch immediately
                lunch_start_time = minutes_to_time(now)
                lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                # Check overlap before adding lunch
                overlaps, conflict = _check_time_overlap(plan, lunch_start_time, lunch_end_time)
                if overlaps:
                    print(f"[OVERLAP DETECTED] lunch_break {lunch_start_time}-{lunch_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                    # Adjust lunch time - move to after conflicting item
                    conflict_end_min = time_to_minutes(conflict.get('end_time', lunch_start_time))
                    now = conflict_end_min
                    lunch_start_time = minutes_to_time(now)
                    lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                # Calculate actual duration
                lunch_start_min = time_to_minutes(lunch_start_time)
                lunch_end_min = time_to_minutes(lunch_end_time)
                actual_lunch_duration = lunch_end_min - lunch_start_min
                
                # Get lunch suggestions (same logic as main lunch block)
                lunch_suggestions = ["Lunch", "Restauracja", "Odpoczynek"]
                restaurants_available = context.get("restaurants_available", [])
                if restaurants_available:
                    lunch_restaurants = [r for r in restaurants_available if r.get("meal_type") == "lunch"]
                    if lunch_restaurants and plan:
                        # Find last attraction for proximity
                        last_attraction = None
                        for item in reversed(plan):
                            if item.get("type") == "attraction" and item.get("poi"):
                                last_attraction = item.get("poi")
                                break
                        
                        if last_attraction and last_attraction.get("lat") and last_attraction.get("lng"):
                            current_lat = last_attraction.get("lat")
                            current_lng = last_attraction.get("lng")
                            for r in lunch_restaurants:
                                r_lat = r.get("lat", 0)
                                r_lng = r.get("lng", 0)
                                if r_lat and r_lng:
                                    distance = haversine_distance(current_lat, current_lng, r_lat, r_lng)
                                    r["_distance"] = distance
                                else:
                                    r["_distance"] = 999.0
                            lunch_restaurants.sort(key=lambda r: r.get("_distance", 999.0))
                            # FIX #141 (31.05.2026): Hard 2km geo filter (post-POI lunch path)
                            _nearby_lunch141b = [r for r in lunch_restaurants if r.get("_distance", 999.0) <= 2.0]
                            if _nearby_lunch141b:
                                lunch_restaurants = _nearby_lunch141b
                        
                        if lunch_restaurants:
                            lunch_suggestions = [r["name"] for r in lunch_restaurants[:3]]
                
                plan.append({
                    "type": "lunch_break",
                    "start_time": lunch_start_time,
                    "end_time": lunch_end_time,
                    "duration_min": actual_lunch_duration,
                    "suggestions": lunch_suggestions,
                    "location_context": _lunch_location_context,  # FIX #102/#103
                })
                
                now = lunch_end_min
                lunch_done = True
                fatigue = max(0, fatigue - 2)
                
                if now > lunch_latest:
                    print(f"[LUNCH POST-POI] WARNING: Late lunch at {lunch_start_time} (should be by {LUNCH_LATEST})")
                    # FIX #144 (01.06.2026): Pre-build late_lunch warning removed.
                    # FIX #139 (post-build) generates accurate timing-based warnings from real plan.
                else:
                    print(f"[LUNCH POST-POI] Lunch inserted at {lunch_start_time}-{lunch_end_time} (duration: {actual_lunch_duration} min)")
                
                # Continue to next iteration - don't add more POI until after lunch
                continue
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add restroom buffer after long attractions
        # Client requirement: Add realistic buffers for bathroom breaks
        if best_duration >= 60:  # Long attraction (60+ min)
            restroom_duration = min(10, max(5, int(best_duration / 60) * 5))  # 5-10 min based on duration
            now = _add_buffer_item(
                plan,
                now,
                "restroom",
                restroom_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add photo_stop buffer at scenic locations
        # Client requirement: Add buffer for photo opportunities at viewpoints
        poi_tags = best.get("tags", []) or []
        tag_list = [str(t).lower() for t in poi_tags if t]
        is_scenic = any(tag in tag_list for tag in ["viewpoint", "scenic", "panorama", "mountain_view"])
        
        if is_scenic:
            photo_duration = 10  # Standard 10 min for photo stop
            now = _add_buffer_item(
                plan,
                now,
                "photo_stop",
                photo_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )
        
        last_poi = best
        
        # FIX #7 (02.02.2026): Update attraction counters
        attraction_count += 1
        is_core_attraction = is_core_poi(best)
        if is_core_attraction:
            core_attraction_count += 1
        print(f"[LIMITS] Added attraction: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")
        
        # BUGFIX (27.04.2026 - CLIENT FEEDBACK Bug #4): Trail day logic
        # PHASE 8 FEATURE #2 (27.04.2026): Elastic trail day rules based on difficulty
        # If trail added, set trail_day_mode and limit subsequent POI
        if best.get("type") == "trail":
            trail_day_mode = True
            
            # Use RAW trail duration for rule logic (not shortened choose_duration result)
            # choose_duration may shorten long trail to fit schedule, but we need
            # to know the REAL trail duration to apply correct restrictions
            # FIX #72 (25.05.2026): Excel trails use time_min, DB trails map to duration_min
            trail_raw_duration = best.get("duration_min") or best.get("time_min") or 0
            trail_duration = trail_raw_duration  # Use RAW for rules, not best_duration
            
            # PHASE 8 FEATURE #2: Get trail difficulty for elastic rules
            trail_difficulty = best.get("difficulty_level", "moderate").lower()
            
            # PHASE 8 FEATURE #2: Determine max POI after trail based on difficulty + duration
            # Heavy trail (hard/extreme, 4-5h): ONLY trail (0 POI after)
            # Moderate trail (moderate, 3-4h): trail + max 1 light POI
            # Light trail (easy, <3h): trail + max 2 light POI
            if trail_difficulty in ["hard", "extreme"] or trail_raw_duration >= 240:
                max_poi_after_trail = 1  # FIX #81 (27.05.2026): was 0 — allow 1 calm POI after hard trail
                trail_category = "heavy"
            elif trail_difficulty == "moderate" or trail_raw_duration >= 180:
                max_poi_after_trail = 1  # Max 1 POI after moderate trails
                trail_category = "moderate"
            else:  # easy or <3h
                max_poi_after_trail = 2  # Max 2 POI after light trails
                trail_category = "light"
            
            print(f"[TRAIL DAY] Trail added (difficulty={trail_difficulty}, RAW duration: {minutes_to_time(trail_raw_duration)}, "
                  f"allocated: {minutes_to_time(best_duration)}, category={trail_category}) - "
                  f"limiting subsequent POI: max {max_poi_after_trail} light attractions")
            
            # NOTE: Trail counter increment moved BEFORE lunch check (line ~3360) to avoid continue statement bug
        else:
            # If trail_day_mode active and adding non-trail POI, increment counter
            if trail_day_mode:
                post_trail_poi_count += 1
                print(f"[TRAIL DAY] Added light POI after {trail_difficulty} trail: {post_trail_poi_count}/{max_poi_after_trail}")
        
        # CLIENT REQUIREMENT (04.02.2026): Increment kids-focused counter for non-family
        user_group = user.get("target_group", "")
        if user_group in ['solo', 'couples', 'friends', 'seniors']:
            if is_kids_focused_poi(best):
                kids_focused_count += 1
                print(f"[LIMITS] Kids-focused POI added: {kids_focused_count}/1 for today")
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Increment termy counter
        # FIX #Problem10 (14.05.2026): Apply to ALL groups (not just seniors)
        if is_termy_spa(best):
            termy_count += 1
            print(f"[LIMITS] Termy/spa POI added: {termy_count}/1 per day")

        # FIX #58: Increment daily museum counter for adventure profile
        if travel_style == "adventure":
            _mus_cnt_tags = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                             "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                             "interactive_exhibit", "local_history", "architecture_heritage",
                             "art_gallery", "temporary_exhibitions", "composer_artist_house",
                             "intimate_small_museum", "ethnographic_museum"}
            if _mus_cnt_tags & set(best.get("tags", [])):
                daily_museum_count += 1
                print(f"[MUSEUM CAP] Museum added today: {daily_museum_count}/1 (adventure)")

        # FIX #99D: Increment daily museum counter for friends profile
        if user.get("target_group") == "friends":
            _mus_friends_tags = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                 "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                 "interactive_exhibit", "local_history", "architecture_heritage",
                                 "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                 "intimate_small_museum", "ethnographic_museum"}
            if _mus_friends_tags & set(best.get("tags", [])):
                friends_museum_today += 1
                print(f"[MUSEUM CAP] Museum added today: {friends_museum_today}/1 (friends)")

        # FIX #127 (30.05.2026): Increment daily museum counter for solo profile
        if user.get("target_group") == "solo":
            _mus_solo_tags = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                              "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                              "interactive_exhibit", "local_history", "architecture_heritage",
                              "art_gallery", "temporary_exhibitions", "composer_artist_house",
                              "intimate_small_museum", "ethnographic_museum"}
            if _mus_solo_tags & set(best.get("tags", [])):
                solo_museum_today += 1
                print(f"[MUSEUM CAP] Museum added today: {solo_museum_today}/2 (solo)")

        # FIX #132 (31.05.2026): Increment daily museum counter for couples profile
        if user.get("target_group") == "couples":
            _mus_couples_tags = {"themed_museum", "regional_heritage", "museum_heritage", "museums",
                                 "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                                 "interactive_exhibit", "local_history", "architecture_heritage",
                                 "art_gallery", "temporary_exhibitions", "composer_artist_house",
                                 "intimate_small_museum", "ethnographic_museum"}
            if _mus_couples_tags & set(best.get("tags", [])):
                couples_museum_today += 1
                print(f"[MUSEUM CAP] Museum added today: {couples_museum_today}/2 (couples)")

        # FIX #64: Track used experience tags for dedup
        _added_exp_tags = UNIQUE_EXPERIENCE_TAGS & set(best.get("tags", []))
        if _added_exp_tags:
            daily_used_experience_tags.update(_added_exp_tags)
            print(f"[DEDUP FIX#64] Registered experience tags: {_added_exp_tags}")
        
        # FIX #5 (UAT Round 3 - 19.02.2026): Update preference coverage tracking
        # Track which of top 3 preferences have been covered by this POI
        user_prefs = user.get("preferences", [])
        top_3_prefs = user_prefs[:3]
        
        if top_3_prefs:
            from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
            
            poi_type = best.get("type", "")
            poi_tags = set(best.get("tags", []))
            
            for pref in top_3_prefs:
                if pref not in covered_preferences:
                    pref_config = USER_PREFERENCES_TO_TAGS.get(pref, {})
                    type_matches = pref_config.get("type_match", [])
                    tag_matches = set(pref_config.get("tags", []))
                    
                    # Check if POI matches this preference
                    if poi_type in type_matches or poi_tags & tag_matches:
                        covered_preferences.add(pref)
                        print(f"[PREFERENCE COVERAGE] [OK] Covered preference '{pref}' with {poi_name(best)}")
            
            # Log coverage status
            uncovered = set(top_3_prefs) - covered_preferences
            if uncovered:
                print(f"[PREFERENCE COVERAGE] Still uncovered: {uncovered}")
            else:
                print(f"[PREFERENCE COVERAGE] [OK] All top 3 preferences covered!")

        # update kultur
        if is_culture(best):
            culture_streak += 1
        
        # GAP FILLING: Check if next POI creates gap >20 min
        # Look ahead to see when next POI would start
        remaining = end - now
        if remaining > 20:  # Only if enough time left
            # Try to find next POI to calculate potential gap
            next_poi_time = None
            next_best_travel = 999
            
            for p in pois:
                if poi_id(p) in used:
                    continue
                
                travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                test_start = now + travel
                
                if test_start >= end:
                    continue
                
                test_duration = choose_duration(p, test_start, end, lunch_done, user)
                if test_duration <= 0:
                    continue
                
                if not is_open(p, test_start, test_duration, ctx["season"], ctx):
                    continue
                
                # Found potential next POI
                if travel < next_best_travel:
                    next_best_travel = travel
                    next_poi_time = test_start
                    break  # Use first viable POI for gap check
            
            # Check if there's a gap before next POI
            if next_poi_time and (next_poi_time - now) > 20:
                gap_duration = next_poi_time - now
                
                # Try to fill gap with soft POI
                soft_filled = False
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # FIX #10.7 (22.02.2026 - TEST-04 CRITICAL FIX): Add kids POI filter to gap filling
                    # ROOT CAUSE: poi_2 (Zoo) appeared for solo traveler because gap filling logic
                    # was missing should_exclude_kids_poi_for_adults check (only had target_group + intensity)
                    if should_exclude_kids_poi_for_adults(p, user):
                        continue  # EXCLUDE - kids POI for adult groups
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue  # Skip - already have 1 kids-focused POI today
                    
                    # FIX #70 (23.05.2026): Apply termy/spa daily limit to ALL groups (not just seniors)
                    if is_termy_spa(p) and termy_count >= 1:
                        continue  # Skip - already have 1 termy/spa today (all groups)
                    
                    # UAT FIX (18.02.2026 - Problem #6): Check global termy limit
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # Skip - global termy limit reached
                    
                    # FIX #7 (02.02.2026): Check hard limit before adding soft POI
                    if attraction_count >= limits["hard"]:
                        break  # Stop gap filling if limit reached
                    
                    # Soft POI criteria
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    soft_travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    soft_start = now + soft_travel
                    
                    if soft_start >= next_poi_time or soft_start >= end:
                        continue
                    
                    soft_duration = min(time_min, gap_duration - soft_travel, next_poi_time - soft_start)
                    if soft_duration < 10:
                        continue
                    
                    if not is_open(p, soft_start, soft_duration, ctx["season"], ctx):
                        continue
                    
                    # Add soft POI to fill gap
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    soft_start_time = minutes_to_time(now + soft_travel)
                    soft_end_time = minutes_to_time(now + soft_travel + soft_duration)
                    
                    overlaps, conflict = _check_time_overlap(plan, soft_start_time, soft_end_time)
                    if overlaps:
                        print(f"[OVERLAP DETECTED] soft POI {poi_name(p)} {soft_start_time}-{soft_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                        continue  # Skip this soft POI
                    
                    if soft_travel > 0:
                        # FIX #77 (27.05.2026): Compute GPS distance for close-POI detection
                        _t77_lat1, _t77_lng1 = last_poi.get("lat"), last_poi.get("lng")
                        _t77_lat2, _t77_lng2 = p.get("lat"), p.get("lng")
                        _t77_dist_km = haversine_distance(_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2) if all([_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2]) else 999.0
                        # FIX #128: Skip zero-distance or duplicate transfer
                        _skip_soft_tr = (
                            _t77_dist_km < 0.05
                            or (plan and plan[-1].get("type") == "transfer"
                                and plan[-1].get("to") == poi_name(p))
                            # FIX #147: Also check recent 8 items (mirror of main loop FIX #142/144)
                            or (len(plan) >= 2
                                and any(it.get("type") == "transfer" and it.get("to") == poi_name(p)
                                        for it in plan[-8:]))
                        )
                        if not _skip_soft_tr:
                            plan.append({
                                "type": "transfer",
                                "from": poi_name(last_poi),
                                "to": poi_name(p),
                                "duration_min": soft_travel,
                                "distance_km": round(_t77_dist_km, 3),  # FIX #77
                                "transport_mode": "walking" if _t77_dist_km < _walk_threshold(last_poi, p) else "car",  # FIX #98/#131
                                "inter_city": _t77_dist_km >= INTER_CITY_THRESHOLD_KM,  # FIX #111
                            })
                            now += soft_travel
                    
                    plan.append({
                        "type": "attraction",
                        "poi": p,
                        "name": poi_name(p),
                        "start_time": minutes_to_time(now),
                        "end_time": minutes_to_time(now + soft_duration),
                        "meta": {
                            "experience_role": "filler",  # Mark as gap filler
                            "is_culture": bool(is_culture(p)),
                            "body_state_after": get_next_body_state(p, body_state),
                        },
                    })
                    
                    now += soft_duration
                    used.add(poi_id(p))
                    last_poi = p
                    
                    # FIX #7 (02.02.2026): Update counters for soft POI too
                    attraction_count += 1
                    is_core_soft = is_core_poi(p)
                    if is_core_soft:
                        core_attraction_count += 1
                    print(f"[LIMITS] Added soft POI: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")
                    
                    # CLIENT REQUIREMENT (04.02.2026): Increment kids-focused counter for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p):
                            kids_focused_count += 1
                            print(f"[LIMITS] Kids-focused POI added (soft): {kids_focused_count}/1 for today")
                    
                    # BUGFIX (16.02.2026 - Problem #9): Increment termy counter for seniors (soft POI)
                    # FIX #Problem10 (14.05.2026): Apply to ALL groups (not just seniors)
                    if is_termy_spa(p):
                        termy_count += 1
                        print(f"[LIMITS] Termy/spa POI added (soft): {termy_count}/1 per day")
                    
                    # UAT FIX (18.02.2026 - Problem #6): Increment global termy counter (gap filler)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        global_termy_tracking["count"] += 1
                        print(f"[LIMITS] Global termy count (gap filler): {global_termy_tracking['count']}/{global_termy_tracking['max']}")
                    
                    # FIX #5 (UAT Round 3 - 19.02.2026): Update preference coverage for soft POI too
                    user_prefs = user.get("preferences", [])
                    top_3_prefs = user_prefs[:3]
                    
                    if top_3_prefs:
                        from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
                        
                        poi_type = p.get("type", "")
                        poi_tags = set(p.get("tags", []))
                        
                        for pref in top_3_prefs:
                            if pref not in covered_preferences:
                                pref_config = USER_PREFERENCES_TO_TAGS.get(pref, {})
                                type_matches = pref_config.get("type_match", [])
                                tag_matches = set(pref_config.get("tags", []))
                                
                                # Check if POI matches this preference
                                if poi_type in type_matches or poi_tags & tag_matches:
                                    covered_preferences.add(pref)
                                    print(f"[PREFERENCE COVERAGE] [OK] Covered preference '{pref}' with soft POI {poi_name(p)}")
                    
                    soft_filled = True
                    break  # Fill one soft POI per gap
                
                # If no soft POI fits, add free_time with smart label
                # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Change threshold 20→60, remove limit, smart labels
                if not soft_filled and gap_duration > 60:
                    # FIX #3 (22.02.2026): Also cap at day_end to prevent violations
                    # CRITICAL FIX (01.05.2026): Changed cap from 120 to 60 min (CLIENT FEEDBACK - Problem #7)
                    # FIX #86 (28.05.2026): After 15:00 create ONE big block — avoids 60-min×3 pattern.
                    if now >= 900:  # After 15:00 → wieczorny relaks territory
                        free_duration = min(gap_duration, end - now)
                    else:
                        free_duration = min(60, gap_duration, end - now)  # Max 60 min before afternoon
                    free_start_time = minutes_to_time(now)
                    free_end_time = minutes_to_time(now + free_duration)
                    
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                    if not overlaps:
                        # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Smart label based on context
                        smart_label = _get_free_time_label(plan, now, free_duration, end, profile=user.get("target_group"))
                        
                        plan.append({
                            "type": "free_time",
                            "start_time": free_start_time,
                            "end_time": free_end_time,
                            "duration_min": free_duration,
                            "description": smart_label
                        })
                        print(f"[GAP FILL] Added free_time after culture ({free_duration}min): {smart_label.encode('ascii', errors='ignore').decode('ascii')}")
                        now += free_duration
                    else:
                        print(f"[OVERLAP DETECTED] gap-fill free_time {free_start_time}-{free_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
        else:
            culture_streak = 0

        # FIX #99E: Update active_streak (consecutive active/outdoor POIs)
        _ACTIVE_TAGS_99E_INC = {
            "active_sport", "hiking", "climbing", "mountain_trails", "outdoor",
            "sports", "water_activity", "winter_sports", "active_entertainment",
            "kulig", "zipline", "quad_atv", "horse_riding", "cave_tour",
        }
        _best_type_99E = str(best.get("type", "")).lower()
        _best_tags_99E = set(best.get("tags", []))
        _is_active_best_99E = bool(_ACTIVE_TAGS_99E_INC & _best_tags_99E) or _best_type_99E in {
            "trail", "active_sport", "adventure_sport", "nature_outdoor",
        }
        if _is_active_best_99E:
            active_streak += 1
        else:
            active_streak = 0

        # update body
        body_state = get_next_body_state(best, body_state)

        # finale lock
        if is_finale(best):
            finale_done = True

    # UAT FIX (18.02.2026 - Problem #4): Fill massive time gaps before day_end
    # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Change threshold 180→60 min
    # Client feedback: 8/10 tests have 1-3h end-of-day gaps
    # Tests 03, 06, 07, 08, 09: Days end early, leaving 1.5-4.5h gaps
    # Solution: If (day_end - current_time) > 60min, add light activities or free_time
    remaining_to_end = end - now

    # FIX #143 (31.05.2026): Sparse day early close.
    # When a day ends up with very few attractions and no trail, skip aggressive gap-fill
    # and close with a single free_time block. Prevents adding noise-level fillers to a
    # structurally sparse day (e.g. when zone pool is limited or budget is very tight).
    _f143_real_attractions = [
        it for it in plan
        if it.get("type") == "attraction"
        and it.get("poi", {}).get("type") != "trail"  # Trails count as full-day activities
    ]
    _f143_has_trail = any(it.get("type") == "attraction" and it.get("poi", {}).get("type") == "trail"
                          for it in plan)
    # FIX #159 (05.06.2026 - CLIENT FEEDBACK / PHASE 3): Anti-sparse substantial backfill.
    # OLD FIX #143 closed a structurally-sparse day immediately with one big free_time
    # block (set remaining_to_end = 0 → skipped gap-fill). The client reported the
    # OPPOSITE need: days with 0-1 attractions and HOURS of free_time, while attractive,
    # still-eligible POIs remain unused (JSON1 D2/D3, JSON2 D2/D3, JSON4 D3/D5, JSON7 D1,
    # JSON8, JSON9). So instead of early-closing we now let the end gap-fill below run in
    # SPARSE MODE (see _f159_sparse_mode), which is allowed to pull SUBSTANTIAL, higher-
    # quality POIs (longer duration + higher must_see + uncovered-preference bias) to reach
    # a sensible minimum of ~2 attractions/day. If nothing eligible fits, the gap-fill
    # itself closes the day with free_time — exactly the same graceful fallback as before.
    if (not _f143_has_trail
            and len(_f143_real_attractions) < 1
            and remaining_to_end > 120):
        print(f"[FIX #159] Sparse day ({len(_f143_real_attractions)} non-trail attractions, "
              f"{remaining_to_end}min free) → attempting substantial backfill before free_time close")
        # Deliberately do NOT add free_time or zero remaining_to_end here — the sparse-aware
        # gap-fill below handles both filling and the graceful free_time close.

    if remaining_to_end > 60:  # 1+ hour remaining (UAT Round 2 fix)
        print(f"[GAP FILL END] Gap remaining: {remaining_to_end}min ({minutes_to_time(now)} → {minutes_to_time(end)})")
        
        # Try to add 1-2 light activities to fill the gap
        gap_fill_attempts = 0
        # FIX #60 (21.05.2026): More attempts for large gaps or family_kids (reduces free_time blocks)
        _is_large_gap = remaining_to_end > 180
        _is_family = user.get("target_group") == "family_kids"
        max_gap_fill = 4 if (_is_large_gap or _is_family) else 2

        # FIX #159 (PHASE 3): if the day is under-filled (< 2 attractions) OR still has a big
        # free block (> 3h), allow more gap-fill attempts so the sparse-mode backfill can add
        # substantial POIs instead of leaving multi-hour free_time.
        if attraction_count < 2 or remaining_to_end > 180:
            max_gap_fill = max(max_gap_fill, 4)

        # FIX D (02.06.2026): Soften quality gates on late days of long trips (>=5 days, day 6+).
        # When the sliding-window dedup (FIX D part 1) re-opens the early-day POI pool,
        # the quality gates (FIX #136, #138) can still block them. Relax the thresholds
        # so the re-opened pool can actually contribute.
        _fixd_num_days = context.get("num_days", 1)
        _fixd_current_day = context.get("current_day_num", 1)
        _fixd_is_late_trip = (_fixd_num_days >= 5 and _fixd_current_day >= 5)
        if _fixd_is_late_trip:
            print(f"[FIX D] Day {_fixd_current_day}/{_fixd_num_days}: Late-trip quality gates softened")
        
        while remaining_to_end > 90 and gap_fill_attempts < max_gap_fill:
            # FIX #159 (PHASE 3): recompute "sparse" each pass. While the day has < 2
            # attractions OR still has a big free block (> 3h), we relax the gap-fill
            # quality/duration ceilings (below) so a SUBSTANTIAL POI can be added; once the
            # day has >= 2 attractions AND the remaining gap is < 3h we revert to the
            # original light-filler behaviour (zero regression for already-filled days).
            _f159_sparse_mode = (attraction_count < 2 or remaining_to_end > 180)
            _f159_uncovered_prefs = (
                [pp for pp in user.get("preferences", [])[:3] if pp not in covered_preferences]
                if _f159_sparse_mode else []
            )
            # FIX #52 (20.05.2026): Block gap fill culture/activity POIs on heavy trail days
            # Heavy trail (max_poi_after_trail=0) should end with free_time only, not culture visits
            # This prevents e.g. gallery/church after 7h Giewont trek
            if trail_day_mode and max_poi_after_trail == 0:
                print(f"[FIX #52] Gap fill blocked: heavy trail day (trail_day_mode + max_poi_after_trail=0)")
                break
            # FIX #73 (25.05.2026): Block gap fill when post-trail POI limit reached (moderate trails)
            if trail_day_mode and post_trail_poi_count >= max_poi_after_trail:
                print(f"[FIX #73] Gap fill blocked: post-trail POI limit ({post_trail_poi_count}/{max_poi_after_trail})")
                break

            # Find soft POI (light activity: 30-60 min, low must_see)
            soft_best = None
            soft_score = -9999
            soft_duration = 0
            soft_travel = 0

            # FIX #159 (PHASE 3): in sparse mode, widen the candidate pool with the FULL
            # POI set (other zones) so a day whose own zone pool is exhausted by cross-day
            # dedup can still be filled from attractive, unused POIs elsewhere. Purely
            # additive — every candidate still passes the same hard filters / dedup / caps
            # below, so no duplicates and no cap violations. Normal (non-sparse) mode and
            # callers that pass no fallback_pois are unchanged (zero regression).
            _gf_candidates = pois
            if _f159_sparse_mode and fallback_pois is not None:
                _gf_seen_ids = {poi_id(_pp) for _pp in pois}
                _gf_extra = [_pp for _pp in fallback_pois if poi_id(_pp) not in _gf_seen_ids]
                if _gf_extra:
                    _gf_candidates = list(pois) + _gf_extra

            for p in _gf_candidates:
                if poi_id(p) in used:
                    continue
                
                # Apply hard filters
                if should_exclude_by_target_group(p, user):
                    continue
                if should_exclude_by_intensity(p, user):
                    continue
                
                # FIX #15.2 (23.02.2026 - TEST-06): Add kids filter to gap filling
                # CRITICAL BUG: Gap filling was adding Zoo for seniors because kids filter was missing
                # This is why poi_2 appeared despite FIX #15 blocking it in main engine
                if should_exclude_kids_poi_for_adults(p, user):
                    print(f"   [GAP FILL] Excluded kids POI: {poi_name(p)}")
                    continue
                
                # Limits
                user_group = user.get("target_group", "")
                if user_group in ['solo', 'couples', 'friends', 'seniors']:
                    if is_kids_focused_poi(p) and kids_focused_count >= 1:
                        continue
                # FIX #70 (23.05.2026): Apply termy/spa daily limit to ALL groups (not just seniors)
                if is_termy_spa(p) and termy_count >= 1:
                    continue
                # FIX #88 (28.05.2026): Adventure profile — museum cap in gap-fill loop.
                # Main loop checks daily_museum_count for adventure, gap-fill loop was missing this.
                # Prevents: museum at 16:00 for adventure/friends profile (museum_count already 1).
                if travel_style == "adventure" and daily_museum_count >= 1:
                    _adv_museum_gf_tags = {
                        "themed_museum", "regional_heritage", "museum_heritage", "museums",
                        "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                        "interactive_exhibit", "local_history", "architecture_heritage",
                        "historic_building", "composer_artist_house", "intimate_small_museum",
                        "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                    }
                    if _adv_museum_gf_tags & set(p.get("tags", [])):
                        continue  # Adventure already has a museum today — skip in gap-fill

                # FIX #99D: Friends profile — museum cap in gap-fill loop.
                if user.get("target_group") == "friends" and friends_museum_today >= 1:
                    _friends_museum_gf_tags = {
                        "themed_museum", "regional_heritage", "museum_heritage", "museums",
                        "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                        "interactive_exhibit", "local_history", "architecture_heritage",
                        "historic_building", "composer_artist_house", "intimate_small_museum",
                        "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                    }
                    if _friends_museum_gf_tags & set(p.get("tags", [])):
                        continue  # Friends already has a museum today — skip in gap-fill

                # FIX #127 (30.05.2026): Solo profile — museum cap in gap-fill loop (max 2/day).
                if user.get("target_group") == "solo" and solo_museum_today >= 2:
                    _solo_museum_gf_tags = {
                        "themed_museum", "regional_heritage", "museum_heritage", "museums",
                        "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                        "interactive_exhibit", "local_history", "architecture_heritage",
                        "historic_building", "composer_artist_house", "intimate_small_museum",
                        "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                    }
                    if _solo_museum_gf_tags & set(p.get("tags", [])):
                        continue  # Solo already has 2 museums today — skip in gap-fill

                # FIX #132 (31.05.2026): Couples profile — museum cap in gap-fill loop (max 2/day).
                if user.get("target_group") == "couples" and couples_museum_today >= 2:
                    _couples_museum_gf_tags = {
                        "themed_museum", "regional_heritage", "museum_heritage", "museums",
                        "mountain_culture", "multimedia_exhibition", "interactive_exhibits",
                        "interactive_exhibit", "local_history", "architecture_heritage",
                        "historic_building", "composer_artist_house", "intimate_small_museum",
                        "ethnographic_museum", "art_gallery", "temporary_exhibitions",
                    }
                    if _couples_museum_gf_tags & set(p.get("tags", [])):
                        continue  # Couples already has 2 museums today — skip in gap-fill

                # FIX #136 (31.05.2026): Solo filler quality gate
                # Skip low-quality fillers (must_see < 4) when day is already well-filled (>=3 POIs)
                # and there is still significant time left (>60 min) — prevents padding with noise.
                # FIX D: Softened to must_see < 2.5 and attraction_count >= 2 on late long-trip days.
                if user.get("target_group") == "solo":
                    _gf136_must_see = p.get("must_see", p.get("must_see_score", 5))
                    try:
                        _gf136_must_see = float(_gf136_must_see)
                    except (TypeError, ValueError):
                        _gf136_must_see = 5.0
                    _gf136_threshold = 2.5 if _fixd_is_late_trip else 4.0
                    _gf136_count = 2 if _fixd_is_late_trip else 4
                    if _gf136_must_see < _gf136_threshold and attraction_count >= _gf136_count and remaining_to_end > 60:
                        continue  # Solo: skip low-quality fillers when day is already well-filled

                # FIX #138 (31.05.2026): Global filler quality gate — ALL profiles
                # Skip noise-level fillers (must_see < 3) when day already has >=3 attractions
                # and >45 min remain. Lower thresholds than FIX #136 (solo-only) — global floor.
                # FIX D: Softened to attraction_count >= 2 on late long-trip days.
                _gf138_must_see = p.get("must_see", p.get("must_see_score", 5))
                try:
                    _gf138_must_see = float(_gf138_must_see)
                except (TypeError, ValueError):
                    _gf138_must_see = 5.0
                _gf138_count = 2 if _fixd_is_late_trip else 4
                if _gf138_must_see < 2.0 and attraction_count >= _gf138_count and remaining_to_end > 45:
                    continue  # Global: skip noise-level fillers on already well-filled days

                # FIX #125 (30.05.2026): Block long activities for toddlers in gap-fill (children_age <= 5)
                _ca_gf_125 = user.get("children_age")
                if (user.get("target_group") == "family_kids"
                        and isinstance(_ca_gf_125, (int, float)) and _ca_gf_125 <= 5):
                    _poi_dur_gf = int(p.get("time_min", 0) or 0)
                    if _poi_dur_gf > 90:
                        continue  # Too long for a toddler — skip in gap-fill

                if attraction_count >= limits["hard"]:
                    break
                
                # Budget filter
                # FIX #2 (22.02.2026): Use unified cost calculation
                if daily_limit is not None:
                    poi_cost_total = calculate_poi_cost_for_group(p, user)
                    if daily_cost + poi_cost_total > daily_limit:
                        continue
                
                # Soft POI criteria: 15-60 min, must_see <= 7
                # FIX #55 (20.05.2026): Raised min from 10 to 15 min (block 8-min Kaplica fillers)
                # FIX #60 (21.05.2026): Allow up to 90min POIs when gap > 180min (reduce free_time)
                time_min = p.get("time_min", 60)
                _gap_max_time = 90 if remaining_to_end > 180 else 60
                # FIX #159: on under-filled days allow SUBSTANTIAL POIs (cap at remaining
                # time, max ~240 min) instead of only short fillers.
                if _f159_sparse_mode:
                    _gap_max_time = min(max(remaining_to_end - 15, 90), 240)
                if time_min < 15 or time_min > _gap_max_time:
                    continue
                must_see_score = p.get("must_see", p.get("must_see_score", 10))
                _gap_must_see_limit = 8 if remaining_to_end > 180 else 7
                # FIX #159: on under-filled days also accept high-quality POIs (the best
                # fillers) — normal mode keeps fillers light (<=7/8) to avoid padding.
                if _f159_sparse_mode:
                    _gap_must_see_limit = 10
                if must_see_score > _gap_must_see_limit:
                    continue
                
                # Calculate travel + duration
                travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                start_time = now + travel
                if start_time >= end:
                    continue
                
                duration = min(time_min, remaining_to_end - travel)
                if duration < 10:
                    continue
                
                if not is_open(p, start_time, duration, ctx["season"], ctx):
                    continue
                
                # Simple scoring: prefer nearby, quick visits
                score = 10 - travel * 0.5

                # FIX #159 (PHASE 3): on under-filled days pick the BEST available POI first
                # (quality + preference coverage), not merely the nearest tiny filler. This
                # is what turns "1 attraction + 6h free_time" into a sensibly filled day and
                # surfaces secondary preferences (museum_heritage/history_mystery/underground)
                # that the main loop missed (client JSON7/JSON8).
                if _f159_sparse_mode:
                    try:
                        _f159_ms = float(must_see_score)
                    except (TypeError, ValueError):
                        _f159_ms = 5.0
                    score = _f159_ms * 10 - travel * 0.5
                    if _f159_uncovered_prefs:
                        from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
                        _f159_ptags = set(p.get("tags", []))
                        _f159_ptype = p.get("type", "")
                        for _f159_pref in _f159_uncovered_prefs:
                            _f159_cfg = USER_PREFERENCES_TO_TAGS.get(_f159_pref, {})
                            if (_f159_ptype in _f159_cfg.get("type_match", [])
                                    or _f159_ptags & set(_f159_cfg.get("tags", []))):
                                score += 200.0  # strongly prefer covering a missing preference
                                break

                if score > soft_score:
                    soft_best = p
                    soft_score = score
                    soft_duration = duration
                    soft_travel = travel
            
            if soft_best:
                # Add soft POI to fill gap
                if soft_travel > 0:
                    # FIX #77 (27.05.2026): Compute GPS distance for close-POI detection
                    _t77_lp = last_poi if last_poi else {}
                    _t77_lat1, _t77_lng1 = _t77_lp.get("lat"), _t77_lp.get("lng")
                    _t77_lat2, _t77_lng2 = soft_best.get("lat"), soft_best.get("lng")
                    _t77_dist_km = haversine_distance(_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2) if all([_t77_lat1, _t77_lng1, _t77_lat2, _t77_lng2]) else 999.0
                    # FIX #128: Skip zero-distance or duplicate transfer
                    _skip_gap_tr = (
                        _t77_dist_km < 0.05
                        or (plan and plan[-1].get("type") == "transfer"
                            and plan[-1].get("to") == poi_name(soft_best))
                        # FIX #142 (31.05.2026): Skip if already moved to this destination recently
                        # FIX #144 (01.06.2026): Extended lookback from 3 to 8.
                        or (len(plan) >= 2
                            and any(it.get("type") == "transfer" and it.get("to") == poi_name(soft_best)
                                    for it in plan[-8:]))
                    )
                    if not _skip_gap_tr:
                        plan.append({
                            "type": "transfer",
                            "from": poi_name(last_poi) if last_poi else "start",
                            "to": poi_name(soft_best),
                            "duration_min": soft_travel,
                            "distance_km": round(_t77_dist_km, 3),  # FIX #77
                            "transport_mode": "walking" if _t77_dist_km < _walk_threshold(last_poi, soft_best) else "car",  # FIX #98/#131
                            "inter_city": _t77_dist_km >= INTER_CITY_THRESHOLD_KM,  # FIX #111
                        })
                        now += soft_travel
                
                plan.append({
                    "type": "attraction",
                    "poi": soft_best,
                    "name": poi_name(soft_best),
                    "start_time": minutes_to_time(now),
                    "end_time": minutes_to_time(now + soft_duration),
                    "meta": {
                        "experience_role": "gap_filler",
                        "is_culture": bool(is_culture(soft_best)),
                        "body_state_after": get_next_body_state(soft_best, body_state),
                    },
                })
                
                now += soft_duration
                used.add(poi_id(soft_best))
                if global_used is not None:
                    global_used.add(poi_id(soft_best))
                
                # Update counters
                attraction_count += 1
                if is_core_poi(soft_best):
                    core_attraction_count += 1
                if user_group in ['solo', 'couples', 'friends', 'seniors']:
                    if is_kids_focused_poi(soft_best):
                        kids_focused_count += 1
                # FIX #Problem10 (14.05.2026): Apply to ALL groups (not just seniors)
                if is_termy_spa(soft_best):
                    termy_count += 1
                
                # Update budget
                # FIX #2 (22.02.2026): Use unified cost calculation
                if daily_limit is not None:
                    poi_cost_total = calculate_poi_cost_for_group(soft_best, user)
                    daily_cost += poi_cost_total
                
                # FIX #5 (UAT Round 3 - 19.02.2026): Track preference coverage for gap filler
                user_prefs = user.get("preferences", [])
                top_3_prefs = user_prefs[:3]
                
                if top_3_prefs:
                    from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS
                    
                    poi_type = soft_best.get("type", "")
                    poi_tags = set(soft_best.get("tags", []))
                    
                    for pref in top_3_prefs:
                        if pref not in covered_preferences:
                            pref_config = USER_PREFERENCES_TO_TAGS.get(pref, {})
                            type_matches = pref_config.get("type_match", [])
                            tag_matches = set(pref_config.get("tags", []))
                            
                            if poi_type in type_matches or poi_tags & tag_matches:
                                covered_preferences.add(pref)
                                print(f"[PREFERENCE COVERAGE] [OK] Covered preference '{pref}' with gap filler {poi_name(soft_best)}")
                
                last_poi = soft_best
                remaining_to_end = end - now
                gap_fill_attempts += 1
                # FIX #73 (25.05.2026): Count gap fill POIs toward post-trail limit
                if trail_day_mode:
                    post_trail_poi_count += 1
                    print(f"[TRAIL DAY] Gap fill POI counted as post-trail: {post_trail_poi_count}/{max_poi_after_trail}")
                
                print(f"[GAP FILL END] Added light activity: {poi_name(soft_best)} ({soft_duration}min), remaining={remaining_to_end}min")
            else:
                # No soft POI available, add free_time with smart label
                # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Remove 90 min limit, use smart labels
                # FIX #3 (22.02.2026): Also cap at day_end to prevent violations
                # CRITICAL FIX (01.05.2026): Changed cap from 180 to 60 min (CLIENT FEEDBACK - Problem #7)
                # FIX #86 (28.05.2026): After 15:00 (900 min), create ONE large block instead of 60-min loop.
                # Client wants "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja" — not 3×60 min blocks.
                if now >= 900:  # After 15:00 → create ONE big "Wieczorny relaks" block
                    free_duration = min(remaining_to_end, end - now)
                else:
                    free_duration = min(60, remaining_to_end, end - now)  # Max 60 min before afternoon
                free_start_time = minutes_to_time(now)
                free_end_time = minutes_to_time(now + free_duration)
                
                # DEBUG: Log free_time calculation
                print(f"[ENGINE MAIN LOOP FREE_TIME] now={now}, remaining_to_end={remaining_to_end}, free_duration={free_duration}")
                print(f"[ENGINE MAIN LOOP FREE_TIME] Calculated: free_start={free_start_time}, free_end={free_end_time}")
                
                overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                if not overlaps:
                    # BUGFIX (19.02.2026 - UAT Round 2, Bug #3): Smart label for end-of-day gaps
                    smart_label = _get_free_time_label(plan, now, free_duration, end, profile=user.get("target_group"))
                    
                    plan.append({
                        "type": "free_time",
                        "start_time": free_start_time,
                        "end_time": free_end_time,
                        "duration_min": free_duration,
                        "description": smart_label
                    })
                    now += free_duration
                    remaining_to_end = end - now
                    print(f"[GAP FILL END] Added free_time ({free_duration}min), remaining={remaining_to_end}min, label: {smart_label.encode('ascii', errors='ignore').decode('ascii')}")
                
                break  # Exit after adding free_time (stop gap filling)

    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #10):
    # Standardize all items to use start_time/end_time (not "time")
    plan.append({
        "type": "accommodation_end",
        "start_time": minutes_to_time(end),
        "end_time": minutes_to_time(end)  # Point-in-time event
    })
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #7):
    # Validate time continuity and auto-fix gaps to day_end
    print(f"[TIME CONTINUITY] Validating plan with day_end={end_time_str}")
    is_valid, issues, fixed_plan = _validate_and_fix_time_continuity(plan, end_time_str)
    
    if issues:
        print(f"[TIME CONTINUITY] Found {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
    
    if not is_valid:
        print(f"[TIME CONTINUITY] WARNING: Plan has critical issues (overlaps or exceeds day_end)")
    else:
        print(f"[TIME CONTINUITY] Plan validated successfully")
    
    # Use fixed plan (may have auto-added free_time to day_end)
    plan = fixed_plan
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #11):
    # Detect empty/sparse days (>50% free_time) and report error
    total_minutes = end - time_to_minutes(start_time_str)
    free_time_minutes = sum(
        item.get("duration_min", 0) 
        for item in plan 
        if item.get("type") == "free_time"
    )
    
    # Count actual attractions (not buffers, transits, lunch)
    attraction_count_final = sum(
        1 for item in plan if item.get("type") == "attraction"
    )
    
    if total_minutes > 0:
        free_time_pct = (free_time_minutes / total_minutes) * 100
        
        if free_time_pct > 50 or attraction_count_final == 0:
            print(f"\n[EMPTY DAY WARNING] Day is sparse or empty:")
            print(f"  - Free time: {free_time_minutes}/{total_minutes} min ({free_time_pct:.1f}%)")
            print(f"  - Attractions: {attraction_count_final}")
            print(f"  - Suggestion: Relax filters (target_group, intensity, budget, distance)")
            if warnings_out is not None:  # FIX #130
                warnings_out.append({"type": "sparse_day", "severity": "warning",
                    "message": f"Day is sparse: {attraction_count_final} attractions, {free_time_pct:.0f}% free time. Consider relaxing filters."})
    
    # BUGFIX (19.02.2026 - UAT Round 2, Issue #5): Validate preference coverage
    # Check if day includes attractions matching top 3 user preferences
    _log_preference_coverage(plan, user)
    
    # NOTE: Gap filling moved to PlanService (after parking/transit timing adjustments)
    # This ensures gaps are detected AFTER all time shifts from parking

    # FIX #139 (31.05.2026): Post-build warning validation
    # Check actual plan items for timing anomalies after all insertions/transits are done.
    # Supplements pre-build time-estimate warnings with real-plan-based warnings.
    # FIX #144 (01.06.2026): Extended to cover late_lunch (>=14:30) and added deduplication.
    if warnings_out is not None:
        for _w139_item in plan:
            _w139_type = _w139_item.get("type", "")
            _w139_start = _w139_item.get("start_time", "")
            if _w139_type == "lunch_break" and _w139_start:
                if _w139_start >= "15:00":
                    warnings_out.append({
                        "type": "very_late_lunch",
                        "severity": "warning",
                        "message": f"Lunch scheduled very late: {_w139_start} (recommend finishing by 14:30)",
                    })
                elif _w139_start >= "14:30":
                    warnings_out.append({
                        "type": "late_lunch",
                        "severity": "warning",
                        "message": f"Late lunch: {_w139_start} (should finish by 14:30)",
                    })
            elif _w139_type == "dinner_break" and _w139_start and _w139_start < "17:00":
                warnings_out.append({
                    "type": "early_dinner",
                    "severity": "info",
                    "message": f"Dinner scheduled early: {_w139_start}",
                })
        # NEW FIX B (01.06.2026): Deduplicate warnings
        # If very_late_lunch exists, drop weaker late_lunch (stronger message covers it)
        _has_very_late_lunch = any(w.get("type") == "very_late_lunch" for w in warnings_out)
        if _has_very_late_lunch:
            warnings_out[:] = [w for w in warnings_out if w.get("type") != "late_lunch"]
        # Remove exact duplicates (same type + same message)
        _seen_warn: set = set()
        _deduped_warn = []
        for _w in warnings_out:
            _wkey = (_w.get("type", ""), _w.get("message", "")[:80])
            if _wkey not in _seen_warn:
                _seen_warn.add(_wkey)
                _deduped_warn.append(_w)
        warnings_out[:] = _deduped_warn

    # FIX #147: Post-build transfer deduplication — safety net for consecutive duplicates.
    # Removes any transfer item immediately followed by another transfer with the same (from, to).
    # Non-consecutive duplicates are prevented at insertion time (FIX #128/#142/#144/#147 above).
    _f147_clean: list = []
    for _f147_idx, _f147_item in enumerate(plan):
        if _f147_item.get("type") == "transfer":
            _f147_to = _f147_item.get("to", "")
            _f147_from = _f147_item.get("from", "")
            # Drop consecutive duplicate: same (from, to) as the previous transfer already kept
            if (_f147_clean
                    and _f147_clean[-1].get("type") == "transfer"
                    and _f147_clean[-1].get("from") == _f147_from
                    and _f147_clean[-1].get("to") == _f147_to):
                print(f"[FIX #147] Removed consecutive duplicate transfer: {_f147_from} → {_f147_to}", flush=True)
                continue
        _f147_clean.append(_f147_item)
    if len(_f147_clean) < len(plan):
        plan[:] = _f147_clean

    return plan


def fill_plan_gaps(plan, pois, used_poi_ids, ctx, user):
    """
    Post-process plan to fill gaps >20 min between attractions.
    Client requirement: gaps should be filled with soft POI or free_time (max 40 min).
    HOTFIX #10.8: Added user parameter to apply hard filters (target_group + intensity).
    """
    print(f"[GAP FILLING DEBUG] Starting with {len(plan)} items", flush=True)
    print(f"[GAP FILLING DEBUG] RAW PLAN DUMP:", flush=True)
    for i, item in enumerate(plan):
        item_type = item.get('type')
        if item_type == 'attraction':
            print(f"  {i}. {item_type}: {item.get('name')} | start={item.get('start_time')} end={item.get('end_time')}", flush=True)
        elif item_type == 'transfer':
            print(f"  {i}. {item_type}: {item.get('from')} -> {item.get('to')} | duration={item.get('duration_min')} | HAS start_time={('start_time' in item)} HAS end_time={('end_time' in item)}", flush=True)
        elif item_type in ['lunch_break', 'free_time']:
            print(f"  {i}. {item_type}: start={item.get('start_time')} end={item.get('end_time')}", flush=True)
        else:
            print(f"  {i}. {item_type}: {item.get('time', 'N/A')}", flush=True)
    
    filled_plan = []
    last_end_time = None  # Track end time of previous item for transfers
    
    for i, item in enumerate(plan):
        filled_plan.append(item)
        
        print(f"[GAP FILLING DEBUG] Item {i}: type={item['type']}", flush=True)
        
        # Check for gap before next item
        if i < len(plan) - 1:
            next_item = plan[i + 1]
            
            # Get end time of current item
            current_end = None
            if item["type"] == "accommodation_start":
                current_end = time_to_minutes(item["time"])
            elif item["type"] == "attraction":
                current_end = time_to_minutes(item["end_time"])
            elif item["type"] in ["transfer", "transit"]:
                # Transfer in raw plan has no start_time/end_time, only duration_min
                # Calculate end time from last_end_time + duration
                if "end_time" in item:
                    current_end = time_to_minutes(item["end_time"])
                elif "start_time" in item:
                    current_end = time_to_minutes(item["start_time"]) + item["duration_min"]
                elif last_end_time is not None:
                    # Raw transfer: calculate from previous item's end
                    current_end = last_end_time + item["duration_min"]
                else:
                    # Can't determine end time
                    continue
            elif item["type"] == "lunch_break":
                current_end = time_to_minutes(item["end_time"])
            elif item["type"] == "free_time":
                current_end = time_to_minutes(item["end_time"])
            
            if current_end is None:
                continue
            
            # Remember this for next transfer
            last_end_time = current_end
            
            print(f"[GAP FILLING DEBUG] current_end={current_end}, last_end_time={last_end_time}", flush=True)
            
            if current_end is None:
                continue
            
            # Get start time of next item
            next_start = None
            if next_item["type"] == "attraction":
                next_start = time_to_minutes(next_item["start_time"])
                print(f"[GAP FILLING DEBUG] next attraction at {next_start}", flush=True)
            elif next_item["type"] == "lunch_break":
                next_start = time_to_minutes(next_item["start_time"])
                print(f"[GAP FILLING DEBUG] next lunch at {next_start}", flush=True)
            elif next_item["type"] in ["transfer", "transit"]:
                # No gap before transfer/transit - they happen immediately
                print(f"[GAP FILLING DEBUG] next is transfer/transit - skipping", flush=True)
                continue
            elif next_item["type"] == "accommodation_end":
                # No gap before day end
                print(f"[GAP FILLING DEBUG] next is day_end - skipping", flush=True)
                continue
            
            if next_start is None:
                print(f"[GAP FILLING DEBUG] next_start is None - skipping", flush=True)
                continue
            
            # Calculate gap
            gap_minutes = next_start - current_end
            print(f"[GAP FILLING DEBUG] GAP DETECTED: {gap_minutes} min (current_end={current_end}, next_start={next_start})", flush=True)
            
            # Fill gaps >20 min
            if gap_minutes > 20:
                print(f"[GAP FILLING DEBUG] Gap >20 min - trying to fill...", flush=True)
                # Try to find soft POI to fill gap
                soft_filled = False
                for p in pois:
                    if poi_id(p) in used_poi_ids:
                        continue
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    # Note: fill_plan_gaps doesn't have kids_focused_count, so this check is approximate
                    # (will be enforced in main loop, this is additional safety)
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p):
                            # Check if plan already has kids-focused POI
                            has_kids_focused = any(
                                is_kids_focused_poi(item.get("poi", {}))
                                for item in filled_plan
                                if item.get("type") == "attraction"
                            )
                            if has_kids_focused:
                                continue  # Skip - already have kids-focused POI
                    
                    # Soft POI criteria
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    # Check if POI fits in gap
                    # Soft POI duration should fit in gap
                    available_time = gap_minutes
                    if time_min > available_time:
                        continue
                    
                    # Check opening hours at current_end time
                    season = ctx.get("season")
                    date_ctx = ctx  # Full context for opening_hours
                    if not is_open(p, current_end, time_min, season, date_ctx):
                        continue
                    
                    # Add soft POI
                    filled_plan.append({
                        "type": "attraction",
                        "poi": p,
                        "name": poi_name(p),
                        "start_time": minutes_to_time(current_end),
                        "end_time": minutes_to_time(current_end + time_min),
                        "meta": {
                            "experience_role": "gap_filler",
                            "is_culture": bool(is_culture(p)),
                        },
                    })
                    
                    used_poi_ids.add(poi_id(p))
                    current_end += time_min
                    gap_minutes = next_start - current_end
                    soft_filled = True
                    break  # Fill one soft POI per gap
                
                # If still gap >20 min and no soft POI, add free_time (max 40 min)
                if not soft_filled and gap_minutes > 20:
                    free_duration = min(40, gap_minutes)
                    print(f"[GAP FILLING DEBUG] No soft POI - adding free_time ({free_duration} min)", flush=True)
                    filled_plan.append({
                        "type": "free_time",
                        "start_time": minutes_to_time(current_end),
                        "end_time": minutes_to_time(current_end + free_duration),
                        "duration_min": free_duration,
                        "description": "Czas wolny: spacer, kawa, odpoczynek"
                    })
                else:
                    print(f"[GAP FILLING DEBUG] Gap filled with soft POI or gap now <20 min", flush=True)
    
    print(f"[GAP FILLING DEBUG] Finished - returning {len(filled_plan)} items", flush=True)
    return filled_plan
