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
    "cave":                    ["underground", "history_mystery", "nature_landscape"],
    "underground":             ["underground"],
    "karst-cave":              ["underground", "cave"],
    "karst_cave":              ["underground", "cave"],
    "geology":                 ["museum_heritage", "underground"],
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
    # FIX #202: common Excel hyphen variants + multi-city vocabulary
    "historic-site":           ["heritage_site", "historic_building"],
    "family-friendly":         ["family_friendly"],
    "local-food":              ["local_food", "local_cuisine"],
    "active-tourism":          ["active_sport", "hiking"],
    "theme-park":              ["theme_park", "amusement_rides"],
    "food-market":             ["food_market"],
    "street-food":             ["street_food"],
    "botanical-garden":        ["botanical_garden"],
    "industrial-heritage":     ["industrial_heritage"],
    "kids-attractions":        ["kids_attractions", "attractions_for_kids"],
    "interactive-exhibitions": ["interactive_exhibition", "interactive_exhibits"],
    "water-activity":          ["water_attractions"],
    "military-history":        ["military_history", "war_history"],
    "history-of-poland":       ["local_history", "historical_exhibits"],
    "outdoor":                 ["nature_landscape", "active_sport"],
    "gdansk":                  ["city_landmark", "historic_market_square"],
    "fortifications":          ["fortification", "historic_building"],
    "fort":                    ["fortification"],
    "gastronomy":              ["local_food_experience", "regional_cuisine"],
    "city-life":               ["city_walk"],
    "river":                   ["river_view", "nature_landscape"],
    "recreation":              ["relax_wellness", "city_walk"],
    "arboretum":               ["botanical_garden", "nature_landscape"],
    "nightlife":               ["city_walk"],
    "events":                  ["city_walk", "seasonal_activity"],
    "urban-space":             ["city_walk"],
    "social-spot":             ["city_walk"],
    "piast-dynasty":           ["local_history", "history_mystery"],
    "gniezno":                 ["local_history"],
    "zator":                   ["theme_park"],
    "local-culture":           ["regional_heritage", "local_history"],
    "warta-river":             ["river_view", "nature_landscape"],
    "sport":                   ["active_sport"],
    "underground-route":       ["underground_route", "underground"],
    "exploration":             ["underground", "nature_landscape"],
    "twierdza-poznan":         ["fortification", "historic_building"],
    "cathedral":               ["religious_site", "historic_building"],
    "religious-heritage":      ["religious_site", "cultural_heritage"],
    "archaeology":             ["archaeological_site", "museum_heritage"],
    "legend":                  ["local_legends", "history_mystery"],
    "white-lady":              ["local_legends", "history_mystery"],
    "green-space":             ["park", "nature_landscape"],
    "local-products":          ["local_food_experience", "food_market"],
    "food-hall":               ["food_market", "local_food_experience"],
    "concerts":                ["city_walk", "cultural_heritage"],
    "music":                   ["cultural_heritage"],
    "bastion":                 ["fortification"],
    "defense-system":          ["fortification", "military_history"],
    "canals":                  ["city_walk", "water_attractions"],
    "waterfront":              ["river_view", "city_walk"],
    "water-tower":             ["city_landmark", "industrial_heritage"],
    "water-reservoir":         ["lake_view", "nature_landscape"],
    "engineering":             ["industrial_heritage", "museum_heritage"],
    "hidden-gems":             ["hidden_gem", "history_mystery"],
    "science-center":          ["science_center", "museum_heritage"],
    "astronomy":               ["science", "museum_heritage"],
    "technology":              ["science", "interactive_museum"],
    "futuristic":              ["interactive_museum"],
    "alwernia":                ["local_history"],
    "amusement-park":          ["amusement_rides", "theme_park"],
    "roller-coasters":         ["amusement_rides"],
    "adrenaline":              ["adrenaline_experience"],
    "attractions":             ["city_landmark"],
    "thrill-rides":            ["amusement_rides"],
    "dinosaur-park":           ["dinosaur_park"],
    "educational-park":        ["educational_fun", "attractions_for_kids"],
    "mythology":               ["folklore", "local_legends"],
    "food":                    ["local_food_experience", "regional_cuisine"],
    "sweet_experience":        ["local_food_experience"],
    "flowers":                 ["botanical_garden"],
    "gardens":                 ["botanical_garden", "park"],
    "water-park":              ["water_park", "aquapark"],
    "thermal-pools":           ["thermal_baths"],
    "water-slides":            ["water_slides"],
    "indoor-attractions":      ["indoor", "attractions_for_kids"],
    "resort":                  ["relax_wellness", "spa_wellness"],
    "adventure-park":          ["adventure_park"],
    "rope-park":               ["rope_park"],
    "circus-heritage":         ["cultural_heritage", "folklore"],
    "playgrounds":             ["playground"],
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
        aliases = TAG_ALIASES.get(normalized)
        if aliases is None:
            aliases = TAG_ALIASES.get(normalized.replace("-", "_"), [])
        for mapped_tag in aliases or []:
            if mapped_tag not in seen:
                result.append(mapped_tag)
                seen.add(mapped_tag)

    return result
