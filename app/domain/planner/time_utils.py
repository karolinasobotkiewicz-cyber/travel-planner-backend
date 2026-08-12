# type: ignore
"""Time conversion utils"""


def time_to_minutes(t):
    """HH:MM -> minutes from midnight"""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(m):
    """minutes -> HH:MM format (clamped to 00:00–23:59)."""
    m = int(round(m))
    # FIX #266: never emit 24:xx — TransitItem / pydantic reject it.
    m = max(0, min(m, 23 * 60 + 59))
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"
