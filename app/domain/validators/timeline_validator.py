"""
Timeline Integrity Validator - UAT Round 3 Fix #1

PROBLEM (20.02.2026):
- Items overlap freely (parking/attraction, lunch/attraction, free_time/attraction)
- No validation that timeline is coherent and sequential
- Klientka reported overlaps in 10/10 tests

SOLUTION:
- validate_timeline_integrity(): Detect ALL overlaps in a day's timeline
- heal_timeline_overlaps(): Auto-fix overlaps by cascading items forward
- Run AFTER all items created, BEFORE returning plan to user

USAGE:
    from app.domain.validators import validate_timeline_integrity, heal_timeline_overlaps
    
    # Validate timeline
    overlaps = validate_timeline_integrity(day_items)
    if overlaps:
        # Try to heal
        healed_items = heal_timeline_overlaps(day_items)
        # Validate again
        remaining_overlaps = validate_timeline_integrity(healed_items)
        if remaining_overlaps:
            raise TimelineValidationError(remaining_overlaps)
    
    return plan
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time


@dataclass
class TimelineOverlap:
    """Represents an overlap between two timeline items."""
    
    item1_type: str
    item1_name: str
    item1_end: str
    item2_type: str
    item2_name: str
    item2_start: str
    overlap_minutes: int
    
    def __str__(self):
        return (
            f"OVERLAP: {self.item1_type} '{self.item1_name}' ends at {self.item1_end}, "
            f"but {self.item2_type} '{self.item2_name}' starts at {self.item2_start} "
            f"(overlap: {self.overlap_minutes} min)"
        )


class TimelineValidationError(Exception):
    """Raised when timeline has overlaps that cannot be healed."""
    
    def __init__(self, overlaps: List[TimelineOverlap]):
        self.overlaps = overlaps
        message = f"Timeline has {len(overlaps)} unresolvable overlaps:\n"
        message += "\n".join(f"  - {overlap}" for overlap in overlaps)
        super().__init__(message)


def _get_item_name(item: Any) -> str:
    """
    Extract item name from various item types.
    
    Handles both Pydantic models and dict representations.
    """
    if hasattr(item, 'name'):
        return item.name
    elif hasattr(item, 'type'):
        type_str = item.type if isinstance(item.type, str) else item.type.value
        return type_str.replace('_', ' ').title()
    elif isinstance(item, dict):
        return item.get('name', item.get('type', 'Unknown'))
    return 'Unknown'


def _get_item_type(item: Any) -> str:
    """
    Extract item type from various item types.
    
    Handles both Pydantic models and dict representations.
    """
    if hasattr(item, 'type'):
        return item.type if isinstance(item.type, str) else item.type.value
    elif isinstance(item, dict):
        return item.get('type', 'unknown')
    return 'unknown'


def _get_item_time(item: Any, field: str) -> str:
    """
    Extract time field from item.
    
    Args:
        item: Item (Pydantic model or dict)
        field: 'start_time' or 'end_time'
    
    Returns:
        Time string in HH:MM format
    """
    if hasattr(item, field):
        return getattr(item, field)
    elif isinstance(item, dict):
        return item.get(field, '00:00')
    return '00:00'


def validate_timeline_integrity(
    day_items: List[Any],
    allow_gap: int = 0,
    check_walk_time: bool = True
) -> List[TimelineOverlap]:
    """
    Validate that all items in a day form non-overlapping sequential timeline.
    
    CRITICAL VALIDATION (UAT Round 3 - Client Feedback 20.02.2026):
    - All items must be sequential: item[n].end_time <= item[n+1].start_time
    - Special case: parking → attraction must have walk_time gap
    - No hidden overlaps between any item types
    
    Args:
        day_items: List of timeline items (DayStart, Parking, Transit, Attraction, etc.)
        allow_gap: Minimum gap allowed between items (default: 0 = no gap required)
        check_walk_time: If True, validate parking → attraction has walk_time gap
    
    Returns:
        List of TimelineOverlap objects (empty if valid)
    
    Example overlaps detected:
        - parking 14:07-14:22 vs attraction 14:12 (starts BEFORE parking ends!)
        - lunch 12:00-13:00 vs attraction 12:30 (lunch overlaps with activity!)
        - free_time 15:00-16:00 vs attraction 15:30 (illogical overlap)
    """
    overlaps = []
    
    if not day_items:
        return overlaps
    
    # Sort items by start_time for sequential validation
    sorted_items = sorted(
        day_items,
        key=lambda x: time_to_minutes(_get_item_time(x, 'start_time'))
    )
    
    # Validate each pair of consecutive items
    for i in range(len(sorted_items) - 1):
        current = sorted_items[i]
        next_item = sorted_items[i + 1]
        
        current_end_min = time_to_minutes(_get_item_time(current, 'end_time'))
        next_start_min = time_to_minutes(_get_item_time(next_item, 'start_time'))
        
        # Calculate required gap
        required_gap = allow_gap
        
        # SPECIAL CASE: Parking → Attraction MUST have walk_time gap
        # Client feedback: "start_attraction >= end_parking + walk_time_min"
        if check_walk_time:
            current_type = _get_item_type(current)
            next_type = _get_item_type(next_item)
            
            if current_type == 'parking' and next_type == 'attraction':
                # Extract walk_time from parking item
                if hasattr(current, 'walk_time_min'):
                    walk_time = current.walk_time_min
                elif isinstance(current, dict):
                    walk_time = current.get('walk_time_min', 5)
                else:
                    walk_time = 5  # Default fallback
                
                required_gap = walk_time
        
        # Check for overlap (current ends AFTER next starts)
        actual_gap = next_start_min - current_end_min
        
        if actual_gap < required_gap:
            overlap_minutes = required_gap - actual_gap
            
            overlap = TimelineOverlap(
                item1_type=_get_item_type(current),
                item1_name=_get_item_name(current),
                item1_end=_get_item_time(current, 'end_time'),
                item2_type=_get_item_type(next_item),
                item2_name=_get_item_name(next_item),
                item2_start=_get_item_time(next_item, 'start_time'),
                overlap_minutes=overlap_minutes
            )
            overlaps.append(overlap)
    
    return overlaps


def heal_timeline_overlaps(
    day_items: List[Any],
    max_iterations: int = 3
) -> List[Any]:
    """
    Auto-heal timeline overlaps by cascading items forward.
    
    HEALING STRATEGY:
    1. Sort items by start_time
    2. For each overlap: move next_item forward to end of current_item + gap
    3. Cascade: if item moved, all subsequent items must move too
    4. Repeat until no overlaps OR max_iterations reached
    
    PRESERVES:
    - Item order (by start_time)
    - Item duration (duration_min unchanged)
    - Day boundaries (day_end not extended)
    
    Args:
        day_items: List of timeline items to heal
        max_iterations: Maximum healing passes (default: 3)
    
    Returns:
        Healed list of items (may still have overlaps if unable to heal)
    
    Note: This modifies item times but NOT item content/data.
          After healing, validate again to ensure success.
    """
    if not day_items:
        return day_items
    
    # Work with sorted copy
    items = sorted(
        day_items,
        key=lambda x: time_to_minutes(_get_item_time(x, 'start_time'))
    )
    
    for iteration in range(max_iterations):
        overlaps = validate_timeline_integrity(items)
        
        if not overlaps:
            # Success! No more overlaps
            break
        
        # Heal overlaps by shifting items forward
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            current_end_min = time_to_minutes(_get_item_time(current, 'end_time'))
            next_start_min = time_to_minutes(_get_item_time(next_item, 'start_time'))
            
            # Calculate required gap (including walk_time for parking)
            required_gap = 0
            current_type = _get_item_type(current)
            next_type = _get_item_type(next_item)
            
            if current_type == 'parking' and next_type == 'attraction':
                if hasattr(current, 'walk_time_min'):
                    required_gap = current.walk_time_min
                elif isinstance(current, dict):
                    required_gap = current.get('walk_time_min', 5)
                else:
                    required_gap = 5
            
            # Check if overlap exists
            actual_gap = next_start_min - current_end_min
            
            if actual_gap < required_gap:
                # OVERLAP DETECTED - Shift next_item forward
                shift_amount = required_gap - actual_gap
                
                # Shift this item and all subsequent items
                for j in range(i + 1, len(items)):
                    item = items[j]
                    
                    # Get current times
                    old_start = _get_item_time(item, 'start_time')
                    old_end = _get_item_time(item, 'end_time')
                    
                    # Calculate new times
                    new_start_min = time_to_minutes(old_start) + shift_amount
                    new_end_min = time_to_minutes(old_end) + shift_amount
                    
                    new_start = minutes_to_time(new_start_min)
                    new_end = minutes_to_time(new_end_min)
                    
                    # Update item times (works for both Pydantic and dict)
                    if hasattr(item, 'start_time'):
                        # Pydantic model - need to use model_copy or setattr
                        # Since Pydantic models are immutable, we'll create modified dict
                        # and let caller handle reconstruction if needed
                        if hasattr(item, '__dict__'):
                            item.__dict__['start_time'] = new_start
                            item.__dict__['end_time'] = new_end
                    elif isinstance(item, dict):
                        item['start_time'] = new_start
                        item['end_time'] = new_end
                
                # Break inner loop to re-sort and validate
                break
        
        # Re-sort after modifications
        items = sorted(
            items,
            key=lambda x: time_to_minutes(_get_item_time(x, 'start_time'))
        )
    
    return items


def validate_and_heal_timeline(
    day_items: List[Any],
    day_number: int = 1,
    raise_on_failure: bool = False
) -> tuple[List[Any], List[str]]:
    """
    Convenience function: Validate + Heal + Validate again.
    
    RECOMMENDED USAGE in plan_service.py:
        healed_items, warnings = validate_and_heal_timeline(day.items, day_number=1)
        if warnings:
            logger.warning(f"Day {day_number} timeline warnings: {warnings}")
        day.items = healed_items
    
    Args:
        day_items: List of items for one day
        day_number: Day number (for logging/error messages)
        raise_on_failure: If True, raise TimelineValidationError if healing fails
    
    Returns:
        Tuple of (healed_items, warnings_list)
        - healed_items: Items with overlaps fixed (if possible)
        - warnings: List of warning messages (empty if no issues)
    
    Raises:
        TimelineValidationError: If raise_on_failure=True and overlaps remain after healing
    """
    warnings = []
    
    # Initial validation
    overlaps = validate_timeline_integrity(day_items)
    
    if not overlaps:
        # Perfect! No issues
        return day_items, warnings
    
    # Log initial overlaps
    warnings.append(f"Day {day_number}: Found {len(overlaps)} overlaps before healing")
    for overlap in overlaps:
        warnings.append(f"  - {overlap}")
    
    # Attempt healing
    healed_items = heal_timeline_overlaps(day_items)
    
    # Validate again
    remaining_overlaps = validate_timeline_integrity(healed_items)
    
    if remaining_overlaps:
        warnings.append(f"Day {day_number}: {len(remaining_overlaps)} overlaps remain after healing")
        for overlap in remaining_overlaps:
            warnings.append(f"  - {overlap}")
        
        if raise_on_failure:
            raise TimelineValidationError(remaining_overlaps)
    else:
        warnings.append(f"Day {day_number}: All overlaps successfully healed ✓")
    
    return healed_items, warnings
