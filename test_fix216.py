"""FIX #216 — register Polanica/Kotlina plain Excel tags."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.domain.scoring.tag_mapper import apply_tag_mapping
from app.domain.scoring.tag_preferences import get_all_registered_tags, calculate_tag_preference_score
from app.infrastructure.repositories.excel_validator import validate_excel

NEW_TAGS = [
    "outdoor_activity", "easy_nature", "scenic_spot", "scenic_route",
    "promenade", "rock_formation", "historic_site",
]


def test_tags_registered():
    reg = get_all_registered_tags()
    missing = [t for t in NEW_TAGS if t not in reg]
    assert not missing, f"Not registered: {missing}"


def test_tag_mapping_enriches():
    mapped = apply_tag_mapping(["scenic_spot", "easy_nature", "outdoor_activity"])
    low = {t.lower() for t in mapped}
    assert "scenic_viewpoint" in low or "scenic_photo_spot" in low
    assert "nature_landscape" in low or "easy_access_nature" in low


def test_scoring_bonus_nature():
    poi = {"tags": ["easy_nature", "scenic_route"], "type": "poi"}
    bonus = calculate_tag_preference_score(poi, ["nature_landscape"])
    assert bonus > 0, f"expected nature bonus, got {bonus}"


def test_excel_no_unknown_tag_warnings():
    rep = validate_excel(
        "data/multi_city_attractions.xlsx",
        city_name="ALL",
        sheet_name="All Cities",
    )
    bad = [
        str(w) for w in rep.warnings
        if "not in tag_preferences" and any(t in str(w) for t in NEW_TAGS)
    ]
    assert not bad, "\n".join(bad)


def test_industrial_registered():
    assert "industrial" in get_all_registered_tags()
    mapped = apply_tag_mapping(["industrial"])
    low = {t.lower() for t in mapped}
    assert "industrial_heritage" in low
    poi = {"tags": ["industrial"], "type": "poi"}
    bonus = calculate_tag_preference_score(poi, ["museum_heritage"])
    assert bonus > 0


if __name__ == "__main__":
    test_tags_registered()
    test_tag_mapping_enriches()
    test_scoring_bonus_nature()
    test_excel_no_unknown_tag_warnings()
    test_industrial_registered()
    print("FIX #216: 5/5 tests passed")
