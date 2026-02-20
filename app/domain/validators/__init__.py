"""
Domain validators for plan integrity.

This module contains validators for ensuring plan coherence and timeline integrity.
"""

from .timeline_validator import (
    validate_timeline_integrity,
    heal_timeline_overlaps,
    validate_and_heal_timeline,
    TimelineValidationError,
    TimelineOverlap,
)

__all__ = [
    "validate_timeline_integrity",
    "heal_timeline_overlaps",
    "validate_and_heal_timeline",
    "TimelineValidationError",
    "TimelineOverlap",
]
