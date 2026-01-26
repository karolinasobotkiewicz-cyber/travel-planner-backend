# type: ignore
"""Time conversion utils"""


def time_to_minutes(t):
    """HH:MM -> minutes from midnight"""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(m):
    """minutes -> HH:MM format"""
    m = int(round(m))
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"
