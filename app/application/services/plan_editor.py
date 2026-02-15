"""
Plan Editor - editing logic for day plans (ETAP 2 Day 6).

Handles remove, replace, and reflow operations on existing plans.
"""
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

from app.domain.models.plan import (
    DayPlan, PlanItem, AttractionItem, TransitItem, 
    FreeTimeItem, ItemType
)
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.engine import travel_time_minutes, is_open


class PlanEditor:
    """
    Service for editing day plans.
    
    ETAP 2 Day 6: Core editing logic (remove, replace, reflow).
    NOT API endpoints (that's Day 7).
    """
    
    def __init__(self, poi_repository):
        """
        Initialize editor with POI repository.
        
        Args:
            poi_repository: POIRepository for finding replacement POIs
        """
        self.poi_repo = poi_repository
    
    def remove_item(
        self,
        day_plan: DayPlan,
        item_id: str,
        all_pois: List[Dict[str, Any]],
        context: Dict[str, Any],
        user: Dict[str, Any],
        avoid_cooldown_hours: int = 24
    ) -> DayPlan:
        """
        Remove item from day plan and attempt gap fill.
        
        Args:
            day_plan: DayPlan to edit
            item_id: ID of item to remove (poi_id for attractions)
            all_pois: List of all available POIs
            context: Context dict (season, weather, transport, etc.)
            user: User preferences dict
            avoid_cooldown_hours: Hours to avoid reinserting removed POI (default 24)
            
        Returns:
            Updated DayPlan with item removed, gap potentially filled, times recalculated
            
        Logic:
        1. Find and remove target item
        2. Calculate gap (start time, duration)
        3. Attempt to fill gap with new POI (avoid recently removed)
        4. Recalculate all times (full reflow)
        """
        # Convert DayPlan items to mutable list
        items = [item.model_dump() if hasattr(item, 'model_dump') else item 
                 for item in day_plan.items]
        
        # Find item to remove
        item_index = None
        removed_item = None
        
        for i, item in enumerate(items):
            # Match by poi_id for attractions, or by index for others
            if item.get("type") == "attraction" and item.get("poi_id") == item_id:
                item_index = i
                removed_item = item
                break
        
        if item_index is None:
            # Item not found, return unmodified
            return day_plan
        
        # Don't allow removing critical items (day_start, day_end, lunch_break)
        if removed_item.get("type") in ["day_start", "day_end", "lunch_break"]:
            return day_plan
        
        # Calculate gap details
        gap_start = removed_item.get("start_time")
        gap_end = removed_item.get("end_time")
        gap_duration = time_to_minutes(gap_end) - time_to_minutes(gap_start)
        
        # Remove item and adjacent transit
        items_to_remove = [item_index]
        
        # Remove transit BEFORE removed item (if exists)
        if item_index > 0 and items[item_index - 1].get("type") == "transit":
            items_to_remove.append(item_index - 1)
        
        # Remove transit AFTER removed item (if exists)
        if item_index < len(items) - 1 and items[item_index + 1].get("type") == "transit":
            items_to_remove.append(item_index + 1)
        
        # Remove items (reverse order to preserve indices)
        for idx in sorted(items_to_remove, reverse=True):
            items.pop(idx)
        
        # Attempt gap fill
        items = self._attempt_gap_fill(
            items=items,
            gap_start=gap_start,
            gap_duration=gap_duration,
            all_pois=all_pois,
            context=context,
            user=user,
            avoid_poi_ids={item_id}  # Avoid just-removed POI
        )
        
        # Recalculate times (full reflow)
        items = self._recalculate_times(items, context)
        
        # Reconstruct DayPlan
        return self._reconstruct_day_plan(day_plan.day, items, day_plan.quality_badges)
    
    def replace_item(
        self,
        day_plan: DayPlan,
        item_id: str,
        all_pois: List[Dict[str, Any]],
        context: Dict[str, Any],
        user: Dict[str, Any],
        strategy: str = "SMART_REPLACE"
    ) -> DayPlan:
        """
        Replace item with similar POI (SMART_REPLACE).
        
        Args:
            day_plan: DayPlan to edit
            item_id: ID of item to replace (poi_id for attractions)
            all_pois: List of all available POIs
            context: Context dict
            user: User preferences dict
            strategy: Replacement strategy ("SMART_REPLACE" only for now)
            
        Returns:
            Updated DayPlan with item replaced, times recalculated
            
        SMART_REPLACE Logic:
        1. Find item to replace
        2. Extract POI metadata (category, target_groups, intensity, duration)
        3. Find similar POI from candidates
        4. Scoring: category (30%), target_group (25%), intensity (20%), duration (15%), type (10%)
        5. Replace item with best match
        6. Recalculate times
        """
        # Convert items to mutable
        items = [item.model_dump() if hasattr(item, 'model_dump') else item 
                 for item in day_plan.items]
        
        # Find item to replace
        item_index = None
        target_item = None
        
        for i, item in enumerate(items):
            if item.get("type") == "attraction" and item.get("poi_id") == item_id:
                item_index = i
                target_item = item
                break
        
        if item_index is None or target_item is None:
            return day_plan
        
        # Get target POI data
        target_poi = self._find_poi_by_id(item_id, all_pois)
        if not target_poi:
            return day_plan
        
        # Get used POI IDs (to avoid duplicates)
        used_poi_ids = {
            item.get("poi_id") 
            for item in items 
            if item.get("type") == "attraction" and item.get("poi_id")
        }
        
        # Find similar POI
        similar_poi = self._find_similar_poi(
            target_poi=target_poi,
            candidates=all_pois,
            used_poi_ids=used_poi_ids,
            user=user,
            target_time=target_item.get("start_time"),
            context=context
        )
        
        if not similar_poi:
            # No similar POI found, return unmodified
            return day_plan
        
        # Replace item with new POI (keep timing for now, reflow will adjust)
        new_item = {
            "type": "attraction",
            "poi_id": similar_poi.get("ID"),
            "name": similar_poi.get("Name", ""),
            "start_time": target_item.get("start_time"),
            "end_time": target_item.get("end_time"),
            "duration_min": similar_poi.get("time_min", target_item.get("duration_min")),
            "description_short": similar_poi.get("Description_short", ""),
            "lat": similar_poi.get("Lat", 0.0),
            "lng": similar_poi.get("Lng", 0.0),
            "address": similar_poi.get("Address", ""),
            "cost_estimate": target_item.get("cost_estimate", 0),
            "ticket_info": target_item.get("ticket_info", {}),
            "parking": target_item.get("parking", {}),
            "pro_tip": similar_poi.get("Pro_tip"),
            "why_selected": target_item.get("why_selected", []),
            "quality_badges": target_item.get("quality_badges", [])
        }
        
        items[item_index] = new_item
        
        # Recalculate times (full reflow)
        items = self._recalculate_times(items, context)
        
        # Reconstruct DayPlan
        return self._reconstruct_day_plan(day_plan.day, items, day_plan.quality_badges)
    
    def regenerate_time_range(
        self,
        day_plan: DayPlan,
        from_time: str,
        to_time: str,
        pinned_items: List[str],
        all_pois: List[Dict[str, Any]],
        context: Dict[str, Any],
        user: Dict[str, Any]
    ) -> DayPlan:
        """
        Regenerate POIs in time range while keeping pinned items.
        
        Args:
            day_plan: DayPlan to edit
            from_time: Start of regeneration range (HH:MM)
            to_time: End of regeneration range (HH:MM)
            pinned_items: List of poi_ids to keep (locked)
            all_pois: List of all available POIs
            context: Context dict
            user: User preferences dict
            
        Returns:
            Updated DayPlan with regenerated range
            
        Logic:
        1. Extract items in time range
        2. Keep pinned items (mark as locked)
        3. Remove unpinned attractions from range
        4. Re-run mini planning for available time slots
        5. Merge before + new range + after
        6. Recalculate all times
        """
        # Convert to mutable (use mode='json' to serialize enums as strings)
        items = [item.model_dump(mode='json') if hasattr(item, 'model_dump') else item 
                 for item in day_plan.items]
        
        from_minutes = time_to_minutes(from_time)
        to_minutes = time_to_minutes(to_time)
        
        # Separate items into: before range, in range, after range
        before_range = []
        in_range = []
        after_range = []
        
        for item in items:
            item_start = time_to_minutes(
                item.get("start_time", item.get("time", "00:00"))
            )
            
            if item_start < from_minutes:
                before_range.append(item)
            elif item_start < to_minutes:
                in_range.append(item)
            else:
                after_range.append(item)
        
        # Collect used POI IDs (from entire day)
        used_poi_ids = {
            item.get("poi_id") 
            for item in items 
            if item.get("type") == "attraction" and item.get("poi_id")
        }
        
        # Separate in-range items: pinned vs unpinned
        pinned_set = set(pinned_items)
        kept_items = []
        removed_items = []
        
        for item in in_range:
            item_type = item.get("type")
            poi_id = item.get("poi_id")
            
            # Always keep non-attraction items (day_start, day_end, etc.)
            if item_type in ["day_start", "day_end", "lunch_break"]:
                kept_items.append(item)
                continue
            
            # Keep pinned attractions
            if item_type == "attraction" and poi_id in pinned_set:
                kept_items.append(item)
                continue
            
            # Remove unpinned attractions and adjacent transit
            if item_type in ["attraction", "transit", "parking", "free_time"]:
                removed_items.append(item)
                if poi_id:
                    used_poi_ids.discard(poi_id)  # Free up for reuse
        
        # Calculate available time slots for new POIs
        # Sort kept items by start time
        kept_items.sort(
            key=lambda x: time_to_minutes(
                x.get("start_time", x.get("time", "00:00"))
            )
        )
        
        # Build time slots: gaps between kept items
        time_slots = []
        current_slot_start = from_minutes
        
        for item in kept_items:
            item_start = time_to_minutes(
                item.get("start_time", item.get("time", "00:00"))
            )
            item_end = time_to_minutes(
                item.get("end_time", item.get("time", "00:00"))
            )
            
            # If gap before this item, add slot
            if current_slot_start < item_start:
                time_slots.append({
                    "start": current_slot_start,
                    "end": item_start,
                    "duration": item_start - current_slot_start
                })
            
            # Move to end of this item
            current_slot_start = max(current_slot_start, item_end)
        
        # Final slot: from last kept item to range end
        if current_slot_start < to_minutes:
            time_slots.append({
                "start": current_slot_start,
                "end": to_minutes,
                "duration": to_minutes - current_slot_start
            })
        
        # Fill each time slot with new POIs
        new_items = []
        
        for slot in time_slots:
            slot_items = self._fill_time_slot(
                start_time=slot["start"],
                end_time=slot["end"],
                all_pois=all_pois,
                used_poi_ids=used_poi_ids,
                context=context,
                user=user,
                last_poi=new_items[-1] if new_items else None
            )
            
            new_items.extend(slot_items)
            
            # Track used POIs
            for item in slot_items:
                if item.get("type") == "attraction" and item.get("poi_id"):
                    used_poi_ids.add(item.get("poi_id"))
        
        # Merge: before + kept (pinned) + new + after
        # Sort by start time to interleave pinned and new items
        range_items = kept_items + new_items
        range_items.sort(
            key=lambda x: time_to_minutes(
                x.get("start_time", x.get("time", "00:00"))
            )
        )
        
        merged_items = before_range + range_items + after_range
        
        # Recalculate all times (full reflow)
        merged_items = self._recalculate_times(merged_items, context)
        
        # Reconstruct DayPlan
        return self._reconstruct_day_plan(
            day_plan.day, merged_items, day_plan.quality_badges
        )
    
    def _fill_time_slot(
        self,
        start_time: int,
        end_time: int,
        all_pois: List[Dict[str, Any]],
        used_poi_ids: Set[str],
        context: Dict[str, Any],
        user: Dict[str, Any],
        last_poi: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fill time slot with POIs (mini build_day).
        
        Args:
            start_time: Start time in minutes
            end_time: End time in minutes
            all_pois: Available POIs
            used_poi_ids: Set of already used POI IDs
            context: Context dict
            user: User preferences dict
            last_poi: Previous POI (for transit calculation)
            
        Returns:
            List of items to fill slot
        """
        from app.domain.planner.engine import (
            score_poi, choose_duration, travel_time_minutes
        )
        from app.domain.scoring.family_fit import should_exclude_by_target_group
        from app.domain.scoring.intensity_scoring import should_exclude_by_intensity
        
        items = []
        current_time = start_time
        available_duration = end_time - start_time
        
        # Need at least 45 min for a POI (30 min + 15 min transit)
        if available_duration < 45:
            # Add free time if gap too small
            if available_duration >= 15:
                items.append({
                    "type": "free_time",
                    "start_time": minutes_to_time(start_time),
                    "end_time": minutes_to_time(end_time),
                    "duration_min": available_duration,
                    "label": "Czas wolny",
                    "description": "Krótka przerwa"
                })
            return items
        
        # Try to add 1-2 POIs in slot
        max_attempts = 2
        attempts = 0
        
        while current_time + 30 < end_time and attempts < max_attempts:
            attempts += 1
            
            # Find best POI for this slot
            best_poi = None
            best_score = -9999
            best_duration = 0
            best_travel = 0
            
            for poi in all_pois:
                poi_id = poi.get("ID")
                
                # Skip used POIs
                if poi_id in used_poi_ids:
                    continue
                
                # Hard filters
                if should_exclude_by_target_group(poi, user):
                    continue
                if should_exclude_by_intensity(poi, user):
                    continue
                
                # Calculate travel time
                travel = 0
                if last_poi:
                    travel = travel_time_minutes(last_poi, poi, context)
                elif context.get("has_car", True):
                    # First POI - add parking
                    travel = 15 + poi.get("parking_walk_time_min", 5)
                
                poi_start = current_time + travel
                
                # Check if fits in slot
                if poi_start >= end_time:
                    continue
                
                duration = choose_duration(
                    poi, poi_start, end_time * 60, False
                )
                if duration <= 0:
                    continue
                
                # Check opening hours
                if not is_open(poi, poi_start, duration, context.get("season", "summer"), context):
                    continue
                
                # Score POI
                score = score_poi(
                    p=poi,
                    user=user,
                    fatigue=0,  # Simplified for mini planning
                    used=used_poi_ids,
                    now=poi_start,
                    energy_left=100,  # Simplified
                    context=context,
                    culture_streak=0,
                    body_state="neutral",
                    finale_done=False
                )
                
                # Travel penalty
                score -= travel * 0.5
                
                if score > best_score:
                    best_poi = poi
                    best_score = score
                    best_duration = duration
                    best_travel = travel
            
            # If found POI, add it
            if best_poi:
                # Add transit if needed
                if best_travel > 0 and last_poi:
                    items.append({
                        "type": "transit",
                        "start_time": minutes_to_time(current_time),
                        "end_time": minutes_to_time(current_time + best_travel),
                        "duration_min": best_travel,
                        "mode": context.get("transport", "car"),
                        "from": last_poi.get("name", ""),
                        "to": best_poi.get("Name", "")
                    })
                    current_time += best_travel
                
                # Add POI
                poi_item = {
                    "type": "attraction",
                    "poi_id": best_poi.get("ID"),
                    "name": best_poi.get("Name", ""),
                    "start_time": minutes_to_time(current_time),
                    "end_time": minutes_to_time(current_time + best_duration),
                    "duration_min": best_duration,
                    "description_short": best_poi.get("Description_short", ""),
                    "lat": best_poi.get("Lat", 0.0),
                    "lng": best_poi.get("Lng", 0.0),
                    "address": best_poi.get("Address", ""),
                    "cost_estimate": 0,
                    "ticket_info": {
                        "ticket_normal": best_poi.get("ticket_price", 0),
                        "ticket_reduced": 0,
                        "free_entry": False
                    },
                    "parking": {
                        "name": best_poi.get("parking", "Brak parkingu"),
                        "walk_time_min": best_poi.get("parking_walk_time_min", 5)
                    },
                    "pro_tip": best_poi.get("Pro_tip"),
                    "why_selected": [],
                    "quality_badges": []
                }
                
                items.append(poi_item)
                current_time += best_duration
                last_poi = poi_item
                used_poi_ids.add(best_poi.get("ID"))
            else:
                # No POI found, break
                break
        
        # Fill remaining gap with free time if significant
        if current_time + 15 < end_time:
            gap_duration = end_time - current_time
            items.append({
                "type": "free_time",
                "start_time": minutes_to_time(current_time),
                "end_time": minutes_to_time(end_time),
                "duration_min": gap_duration,
                "label": "Czas wolny",
                "description": "Przerwa"
            })
        
        return items
    
    def _recalculate_times(
        self,
        items: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Recalculate all times in day plan (full reflow).
        
        Args:
            items: List of plan items
            context: Context dict (transport mode, etc.)
            
        Returns:
            Items with recalculated times
            
        Logic:
        1. Start from day_start time
        2. For each item, calculate start/end based on previous item
        3. Update transit times based on actual POI locations
        4. Ensure no overlaps
        """
        if not items:
            return items
        
        # Find day_start
        current_time = None
        for item in items:
            if item.get("type") == "day_start":
                current_time = time_to_minutes(item.get("time"))
                break
        
        if current_time is None:
            current_time = time_to_minutes("09:00")  # Default
        
        updated_items = []
        last_poi = None
        
        for item in items:
            item_type = item.get("type")
            
            # Day markers - keep original time
            if item_type in ["day_start", "day_end"]:
                updated_items.append(item)
                if item_type == "day_start":
                    current_time = time_to_minutes(item.get("time"))
                continue
            
            # Parking, lunch, free_time - use duration
            if item_type in ["parking", "lunch_break", "free_time"]:
                duration = item.get("duration_min", 0)
                item["start_time"] = minutes_to_time(current_time)
                item["end_time"] = minutes_to_time(current_time + duration)
                current_time += duration
                updated_items.append(item)
                continue
            
            # Transit - recalculate based on POI locations
            if item_type == "transit":
                # Get duration from previous calculation or default
                duration = item.get("duration_min", 15)
                item["start_time"] = minutes_to_time(current_time)
                item["end_time"] = minutes_to_time(current_time + duration)
                current_time += duration
                updated_items.append(item)
                continue
            
            # Attraction - update timing
            if item_type == "attraction":
                duration = item.get("duration_min", 60)
                item["start_time"] = minutes_to_time(current_time)
                item["end_time"] = minutes_to_time(current_time + duration)
                current_time += duration
                updated_items.append(item)
                
                # Track for transit calculation
                last_poi = {
                    "lat": item.get("lat"),
                    "lng": item.get("lng"),
                    "name": item.get("name")
                }
                continue
        
        return updated_items
    
    def _attempt_gap_fill(
        self,
        items: List[Dict[str, Any]],
        gap_start: str,
        gap_duration: int,
        all_pois: List[Dict[str, Any]],
        context: Dict[str, Any],
        user: Dict[str, Any],
        avoid_poi_ids: Set[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Attempt to fill gap with new POI.
        
        Args:
            items: Current plan items
            gap_start: Gap start time (HH:MM)
            gap_duration: Gap duration in minutes
            all_pois: All available POIs
            context: Context dict
            user: User preferences dict
            avoid_poi_ids: POI IDs to avoid (cooldown)
            
        Returns:
            Items with gap potentially filled
            
        Logic:
        1. Find POIs that fit in gap (duration-wise)
        2. Exclude already used POIs
        3. Exclude avoided POIs (cooldown)
        4. Score candidates (simple: duration fit, opening hours)
        5. Insert best POI if found, else insert free_time
        """
        if avoid_poi_ids is None:
            avoid_poi_ids = set()
        
        # Get used POI IDs
        used_poi_ids = {
            item.get("poi_id")
            for item in items
            if item.get("type") == "attraction" and item.get("poi_id")
        }
        
        # Add avoided IDs
        used_poi_ids.update(avoid_poi_ids)
        
        # Find gap location in items
        gap_start_min = time_to_minutes(gap_start)
        insert_index = None
        
        for i, item in enumerate(items):
            if item.get("type") == "attraction":
                item_start = time_to_minutes(item.get("start_time", "09:00"))
                if item_start > gap_start_min:
                    insert_index = i
                    break
        
        if insert_index is None:
            # Gap is at end of day
            insert_index = len(items) - 1  # Before day_end
        
        # Find candidate POIs
        best_poi = None
        best_score = -999
        
        for poi in all_pois:
            poi_id = poi.get("ID", "")
            
            # Skip if used or avoided
            if poi_id in used_poi_ids:
                continue
            
            # Check duration fit (POI should fit in gap)
            poi_duration = poi.get("time_min", 60)
            if poi_duration > gap_duration:
                continue
            
            # Check opening hours (if date available)
            if context.get("date"):
                season = context.get("season", "all")
                if not is_open(poi, gap_start_min, poi_duration, season, context):
                    continue
            
            # Simple scoring: prefer POIs with duration close to gap
            duration_diff = abs(poi_duration - gap_duration)
            score = 100 - duration_diff * 0.5
            
            if score > best_score:
                best_poi = poi
                best_score = score
        
        # Insert POI or free_time
        if best_poi:
            # Create attraction item
            new_item = {
                "type": "attraction",
                "poi_id": best_poi.get("ID"),
                "name": best_poi.get("Name", ""),
                "start_time": gap_start,
                "end_time": minutes_to_time(gap_start_min + best_poi.get("time_min", 60)),
                "duration_min": best_poi.get("time_min", 60),
                "description_short": best_poi.get("Description_short", ""),
                "lat": best_poi.get("Lat", 0.0),
                "lng": best_poi.get("Lng", 0.0),
                "address": best_poi.get("Address", ""),
                "cost_estimate": 0,
                "ticket_info": {
                    "ticket_normal": best_poi.get("ticket_normal", 0) or 0,
                    "ticket_reduced": best_poi.get("ticket_reduced", 0) or 0,
                    "free_entry": best_poi.get("free_entry", False) or False
                },
                "parking": {"name": "Brak parkingu", "walk_time_min": 5},
                "pro_tip": best_poi.get("Pro_tip"),
                "why_selected": [],
                "quality_badges": []
            }
            items.insert(insert_index, new_item)
        else:
            # Insert free_time
            free_duration = min(gap_duration, 40)  # Max 40 min free time
            free_item = {
                "type": "free_time",
                "start_time": gap_start,
                "end_time": minutes_to_time(gap_start_min + free_duration),
                "duration_min": free_duration,
                "label": "Czas wolny po edycji",
                "description": "Spacer, kawa, odpoczynek"
            }
            items.insert(insert_index, free_item)
        
        return items
    
    def _find_similar_poi(
        self,
        target_poi: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        used_poi_ids: Set[str],
        user: Dict[str, Any],
        target_time: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar POI for SMART_REPLACE.
        
        Args:
            target_poi: POI being replaced
            candidates: All available POIs
            used_poi_ids: Already used POI IDs
            user: User preferences
            target_time: Target time for replacement
            context: Context dict
            
        Returns:
            Best matching POI or None
            
        Scoring criteria:
        - Tags match (40%): Similar tags/keywords
        - Target group match (30%): Similar target_groups
        - Intensity match (20%): Similar intensity level
        - Duration match (10%): Similar visit duration
        """
        # Get target POI attributes (use capital keys from Excel aliases)
        target_tags_str = str(target_poi.get("Tags", "")).lower()
        target_groups_str = str(target_poi.get("target_groups", "")).lower()
        target_intensity = target_poi.get("fizyczna_intensywnosc", "").lower()
        target_duration = target_poi.get("time_min", 60)
        
        best_poi = None
        best_score = -999
        
        for poi in candidates:
            poi_id = poi.get("ID", "")
            
            # Skip if used
            if poi_id in used_poi_ids:
                continue
            
            # Skip if same as target
            if poi_id == target_poi.get("ID"):
                continue
            
            # Calculate similarity score
            score = 0
            
            # Tags match (40%) - most important for similarity
            poi_tags_str = str(poi.get("Tags", "")).lower()
            if poi_tags_str and target_tags_str:
                # Check keyword overlap
                target_keywords = set(target_tags_str.split())
                poi_keywords = set(poi_tags_str.split())
                overlap = len(target_keywords & poi_keywords)
                if overlap > 0:
                    score += 40 * (overlap / max(len(target_keywords), 1))
            
            # Target group match (30%)
            poi_groups_str = str(poi.get("target_groups", "")).lower()
            if poi_groups_str and target_groups_str:
                # Check overlap
                target_group_set = set(target_groups_str.split(","))
                poi_group_set = set(poi_groups_str.split(","))
                overlap = len(target_group_set & poi_group_set)
                if overlap > 0:
                    score += 30 * (overlap / max(len(target_group_set), 1))
            
            # Intensity match (20%)
            poi_intensity = poi.get("fizyczna_intensywnosc", "").lower()
            if poi_intensity and target_intensity:
                if poi_intensity == target_intensity:
                    score += 20
                elif self._intensity_similar(target_intensity, poi_intensity):
                    score += 10
            
            # Duration match (10%)
            poi_duration = poi.get("time_min", 60)
            duration_diff = abs(poi_duration - target_duration)
            if duration_diff <= 15:  # Within 15 min
                score += 10
            elif duration_diff <= 30:  # Within 30 min
                score += 5
            
            if score > best_score:
                best_poi = poi
                best_score = score
        
        return best_poi
    
    def _intensity_similar(self, intensity1: str, intensity2: str) -> bool:
        """Check if two intensity levels are similar."""
        intensity_map = {
            "light": 1,
            "lekka": 1,
            "moderate": 2,
            "moderowana": 2,
            "intense": 3,
            "intensywna": 3
        }
        
        level1 = intensity_map.get(intensity1, 2)
        level2 = intensity_map.get(intensity2, 2)
        
        return abs(level1 - level2) <= 1
    
    def _find_poi_by_id(
        self,
        poi_id: str,
        all_pois: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find POI by ID in list."""
        for poi in all_pois:
            if poi.get("ID") == poi_id:
                return poi
        return None
    
    def _reconstruct_day_plan(
        self,
        day_number: int,
        items: List[Dict[str, Any]],
        quality_badges: List[str]
    ) -> DayPlan:
        """
        Reconstruct DayPlan from dict items.
        
        Args:
            day_number: Day number (1-indexed)
            items: List of item dicts
            quality_badges: Quality badges for day
            
        Returns:
            DayPlan instance
        """
        # Import models
        from app.domain.models.plan import (
            DayStartItem, DayEndItem, ParkingItem, TransitItem,
            AttractionItem, LunchBreakItem, FreeTimeItem,
            TransitMode, ParkingType, TicketInfo, ParkingInfo
        )
        
        # Convert dicts to proper model instances
        plan_items = []
        
        for item in items:
            item_type = item.get("type")
            
            if item_type == "day_start":
                plan_items.append(DayStartItem(time=item.get("time")))
            
            elif item_type == "day_end":
                plan_items.append(DayEndItem(time=item.get("time")))
            
            elif item_type == "parking":
                plan_items.append(ParkingItem(
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    name=item.get("name", ""),
                    address=item.get("address", ""),
                    lat=item.get("lat", 0.0),
                    lng=item.get("lng", 0.0),
                    parking_type=ParkingType(item.get("parking_type", "paid")),
                    walk_time_min=item.get("walk_time_min", 5)
                ))
            
            elif item_type == "transit":
                plan_items.append(TransitItem(
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    duration_min=item.get("duration_min", 0),
                    mode=TransitMode(item.get("mode", "car")),
                    from_location=item.get("from", ""),
                    to_location=item.get("to", "")
                ))
            
            elif item_type == "attraction":
                # Skip attractions without poi_id
                poi_id = item.get("poi_id")
                if not poi_id:
                    continue
                
                ticket_info_dict = item.get("ticket_info", {})
                parking_dict = item.get("parking", {})
                
                plan_items.append(AttractionItem(
                    poi_id=poi_id,
                    name=item.get("name", ""),
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    duration_min=item.get("duration_min", 0),
                    description_short=item.get("description_short", ""),
                    lat=item.get("lat", 0.0),
                    lng=item.get("lng", 0.0),
                    address=item.get("address", ""),
                    cost_estimate=item.get("cost_estimate", 0),
                    ticket_info=TicketInfo(
                        ticket_normal=ticket_info_dict.get("ticket_normal", 0),
                        ticket_reduced=ticket_info_dict.get("ticket_reduced", 0),
                        free_entry=ticket_info_dict.get("free_entry", False)
                    ),
                    parking=ParkingInfo(
                        name=parking_dict.get("name", "Brak parkingu"),
                        walk_time_min=parking_dict.get("walk_time_min", 5)
                    ),
                    pro_tip=item.get("pro_tip"),
                    why_selected=item.get("why_selected", []),
                    quality_badges=item.get("quality_badges", [])
                ))
            
            elif item_type == "lunch_break":
                plan_items.append(LunchBreakItem(
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    duration_min=item.get("duration_min", 0),
                    label=item.get("label", "Lunch / przerwa regeneracyjna"),
                    suggestions=item.get("suggestions", [])
                ))
            
            elif item_type == "free_time":
                plan_items.append(FreeTimeItem(
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                    duration_min=item.get("duration_min", 0),
                    label=item.get("label", "Czas wolny"),
                    description=item.get("description", "")
                ))
        
        return DayPlan(
            day=day_number,
            items=plan_items,
            quality_badges=quality_badges
        )
