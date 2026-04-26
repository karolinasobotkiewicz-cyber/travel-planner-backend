"""
Router module - Trip type detection and intelligent routing (ETAP 3 Phase 2).
"""
from .trip_type_router import TripTypeRouter, TripType, detect_trip_type

__all__ = [
    "TripTypeRouter",
    "TripType",
    "detect_trip_type",
]
