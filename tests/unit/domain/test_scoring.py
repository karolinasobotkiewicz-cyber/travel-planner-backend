"""Tests dla scoring modules"""

from app.domain.scoring.family_fit import calculate_family_score
from app.domain.scoring.budget import calculate_budget_score
from app.domain.scoring.crowd import calculate_crowd_score
from app.domain.scoring.body_state import (
    calculate_body_transition_score,
    get_next_body_state,
)


class TestFamilyFitScore:
    def test_non_family_group_returns_zero(self):
        """
        FIX #8 (02.02.2026): Zmiana logiki - solo vs family_kids POI = mismatch penalty (-10)
        Poprzednio: 0 (ignorowano wszystkie inne grupy)
        Teraz: -10 (penalty za mismatch target_group)
        """
        poi = {"kids_only": False, "target_groups": ["family_kids"]}
        user = {"target_group": "solo"}

        # FIX #8: solo user vs family_kids POI = mismatch = -10
        assert calculate_family_score(poi, user) == -10.0

    def test_kids_only_poi_high_score(self):
        poi = {"kids_only": True}
        user = {"target_group": "family_kids"}

        score = calculate_family_score(poi, user)
        assert score == 8.0

    def test_family_target_group_bonus(self):
        poi = {"kids_only": False, "target_groups": ["family_kids"]}
        user = {"target_group": "family_kids"}

        score = calculate_family_score(poi, user)
        assert score == 6.0  # base bonus

    def test_age_range_matching(self):
        """Test czy wiek dziecka w zakresie daje bonus"""
        poi = {
            "kids_only": False,
            "target_groups": ["family_kids"],
            "children_min": 5,
            "children_max": 12,
        }
        user = {"target_group": "family_kids", "children_age": 8}

        score = calculate_family_score(poi, user)
        assert score == 8.0  # base 6 + age bonus 2


class TestBudgetScore:
    def test_matching_budget_neutral(self):
        poi = {"budget_level": 2}
        user = {"budget": 2}

        assert calculate_budget_score(poi, user) == 0.0

    def test_expensive_poi_penalty(self):
        poi = {"budget_level": 3}
        user = {"budget": 1}

        score = calculate_budget_score(poi, user)
        assert score == -12.0  # delta=2, -6*2

    def test_cheap_poi_no_penalty(self):
        poi = {"budget_level": 1}
        user = {"budget": 3}

        score = calculate_budget_score(poi, user)
        assert score == 12.0  # delta=-2, -6*(-2)


class TestCrowdScore:
    def test_matching_crowd_neutral(self):
        poi = {"crowd_level": 1}
        user = {"crowd_tolerance": 1}

        assert calculate_crowd_score(poi, user) == 0.0

    def test_high_crowd_low_tolerance_penalty(self):
        poi = {"crowd_level": 3}
        user = {"crowd_tolerance": 0}

        score = calculate_crowd_score(poi, user)
        assert score == -15.0  # delta=3, -5*3

    # TODO: dodac testy dla edge cases (None values)


class TestBodyStateTransitions:
    def test_warm_to_cold_penalty(self):
        """Warm body state + cold experience = penalty"""
        poi = {
            "name": "Kulig w Tatrach",
            "space": "outdoor",
            "intensity": "high",
        }

        score = calculate_body_transition_score(poi, "warm")
        assert score == -10.0

    def test_cold_to_relax_bonus(self):
        """Cold body + relax POI = bonus"""
        poi = {"name": "Termy Chochołowskie", "type": "spa"}

        score = calculate_body_transition_score(poi, "cold")
        assert score == 8.0

    def test_neutral_transitions(self):
        poi = {"name": "Muzeum", "space": "indoor"}

        assert calculate_body_transition_score(poi, "neutral") == 0.0

    def test_next_state_after_relax(self):
        poi = {"name": "Termy", "type": "spa"}

        assert get_next_body_state(poi, "cold") == "warm"

    def test_next_state_after_cold_exp(self):
        poi = {"name": "Kulig", "space": "outdoor", "intensity": "high"}

        assert get_next_body_state(poi, "neutral") == "cold"

    def test_next_state_default(self):
        """Normalny POI nie zmienia stanu na konkretny"""
        poi = {"name": "Muzeum", "space": "indoor", "intensity": "low"}

        state = get_next_body_state(poi, "neutral")
        assert state == "neutral"
