"""
Mapper/Adapter for converting TripInput to engine parameters.
Konwertuje Pydantic TripInput model na parametry wymagane przez engine.py.
"""
from typing import Dict, Any
from datetime import timedelta, date
from app.domain.models.trip_input import TripInput


def trip_input_to_engine_params(
    trip_input: TripInput,
) -> Dict[str, Any]:
    """
    Konwertuje TripInput model na dict z parametrami dla engine.py.

    Args:
        trip_input: TripInput model z request

    Returns:
        Dict z parametrami dla build_day() i innych funkcji engine
    """

    # Oblicz daty dla każdego dnia
    dates = []
    for day_num in range(trip_input.trip_length.days):
        day_date = trip_input.trip_length.start_date + timedelta(days=day_num)
        dates.append(day_date.strftime("%Y-%m-%d"))

    # Context dla engine
    context = {
        "season": _get_season_from_date(trip_input.trip_length.start_date),
        "region_type": trip_input.location.region_type or "city",
        "transport": _map_transport_mode(trip_input.transport_modes),
        "daylight_end": None,  # TODO obliczać na podstawie daty
        "date": None,  # Będzie ustawiane dla każdego dnia osobno
    }

    # User profile dla engine
    user = {
        "target_group": trip_input.group.type,
        "children_age": trip_input.group.children_age,
        "crowd_tolerance": trip_input.group.crowd_tolerance,
        "budget": trip_input.budget.level,
        "preferences": trip_input.preferences or [],
        "travel_style": trip_input.travel_style or "balanced",
    }

    # Day limits
    day_start = trip_input.daily_time_window.start
    day_end = trip_input.daily_time_window.end

    return {
        "dates": dates,
        "context": context,
        "user": user,
        "day_start": day_start,
        "day_end": day_end,
        "city": trip_input.location.city,
        "country": trip_input.location.country,
        "transport_modes": trip_input.transport_modes,
        "num_days": trip_input.trip_length.days,
    }


def _get_season_from_date(date_obj: date) -> str:
    """
    Określa porę roku na podstawie daty.

    Args:
        date_obj: datetime.date object

    Returns:
        Season: spring, summer, autumn, winter
    """
    month = date_obj.month

    if month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    elif month in [9, 10, 11]:
        return "autumn"
    else:
        return "winter"


def _map_transport_mode(modes: list[str]) -> str:
    """
    Mapuje listę transport_modes na pojedynczy tryb dla engine.
    Engine używa "car", "walk", "public" - wybieramy pierwszy z listy.

    Args:
        modes: Lista trybów transportu

    Returns:
        Tryb dla engine: car, walk, public
    """
    if not modes:
        return "car"

    # Priorytet: car > public_transport > walk
    if "car" in modes:
        return "car"
    elif "public_transport" in modes:
        return "public"
    elif "walk" in modes:
        return "walk"

    return "car"
