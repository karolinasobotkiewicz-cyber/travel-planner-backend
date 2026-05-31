"""
FIX #111 — Tag Mapper (31.05.2026)

Translates tags from Excel (client-defined vocabulary) to tags understood
by tag_preferences.py (engine scoring vocabulary).

Rules:
- One Excel tag can map to MULTIPLE engine tags
- Unknown tags are preserved as-is (no data loss)
- Mapping is additive: original tags are kept + mapped tags added
- Used by load_multi_city.py and load_zakopane.py at load time

Mapping defined by client on 31.05.2026.
"""

# Excel tag -> list of engine tags (from tag_preferences.py vocabulary)
TAG_ALIASES: dict[str, list[str]] = {
    "viewpoint":               ["nature_landscape", "city_walk"],
    "interactive_exhibition":  ["museum_heritage", "attractions_for_kids"],
    "family_friendly":         ["attractions_for_kids"],
    "educational":             ["museum_heritage", "attractions_for_kids"],
    "heritage":                ["museum_heritage"],
    "landmark":                ["museum_heritage", "city_walk"],
    "history":                 ["museum_heritage"],
    "city_walk":               ["city_walk"],
    "old_town_square":         ["city_walk", "museum_heritage"],
    "science_center":          ["museum_heritage", "attractions_for_kids"],
    "interactive":             ["attractions_for_kids", "museum_heritage"],
    "wellness":                ["relax_wellness"],
    "aquapark":                ["water_attractions"],
    "boat_trip":               ["water_attractions", "city_walk"],
    "old_town":                ["city_walk", "museum_heritage"],
    "park":                    ["nature_landscape", "city_walk"],
    "adventure":               ["active_sport", "attractions_for_kids"],
    "architecture":            ["museum_heritage", "city_walk"],
    "animals":                 ["attractions_for_kids", "nature_landscape"],
    "spa":                     ["relax_wellness"],
    "entertainment":           ["attractions_for_kids", "active_sport"],
    "rope_courses":            ["active_sport", "attractions_for_kids"],
    "rope_course":             ["active_sport", "attractions_for_kids"],
    "thermal_pools":           ["water_attractions", "relax_wellness"],
    "castle":                  ["museum_heritage"],
    "craft":                   ["museum_heritage"],
    "sensory_experience":      ["attractions_for_kids", "museum_heritage"],
    "nature":                  ["nature_landscape"],
    "space":                   ["museum_heritage", "attractions_for_kids"],
    "experiments":             ["museum_heritage", "attractions_for_kids"],
    "old_town_view":           ["city_walk", "nature_landscape"],
    "swimming_spot":           ["water_attractions", "relax_wellness"],
    "water_attractions":       ["water_attractions"],
    "kids_attractions":        ["attractions_for_kids"],
    "active_sport":            ["active_sport"],
    "local_food_experience":   ["local_food_experience"],
}


def apply_tag_mapping(tags: list[str]) -> list[str]:
    """
    Takes a list of raw tags from Excel and returns an enriched list
    with all mapped engine tags added (no duplicates, original tags preserved).

    Example:
        apply_tag_mapping(["viewpoint", "heritage"])
        → ["viewpoint", "heritage", "nature_landscape", "city_walk", "museum_heritage"]
    """
    if not tags:
        return tags

    result = list(tags)
    seen = set(t.lower().strip() for t in tags)

    for tag in tags:
        normalized = tag.lower().strip()
        for mapped_tag in TAG_ALIASES.get(normalized, []):
            if mapped_tag not in seen:
                result.append(mapped_tag)
                seen.add(mapped_tag)

    return result
