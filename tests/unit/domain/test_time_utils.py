"""Tests dla time utils"""
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time


def test_time_to_minutes_morning():
    assert time_to_minutes("09:00") == 540


def test_time_to_minutes_afternoon():
    assert time_to_minutes("15:30") == 930


def test_time_to_minutes_midnight():
    assert time_to_minutes("00:00") == 0


def test_minutes_to_time_simple():
    assert minutes_to_time(540) == "09:00"


def test_minutes_to_time_with_minutes():
    assert minutes_to_time(930) == "15:30"


def test_minutes_to_time_zero():
    assert minutes_to_time(0) == "00:00"


def test_round_trip_conversion():
    """Test czy konwersja tam i z powrotem działa"""
    original = "12:45"
    minutes = time_to_minutes(original)
    result = minutes_to_time(minutes)

    assert result == original
