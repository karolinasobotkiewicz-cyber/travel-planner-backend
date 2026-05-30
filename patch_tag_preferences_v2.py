"""
FIX #124 patch v2: fix kids_attractions/nature_landscape key detection
+ add remaining 140 tags that were missed in first pass.
Run from travel-planner-backend/ directory.
"""
import re

# Remaining 140 tags (not yet in file) mapped to categories
ROUND2_ADDITIONS = {
    "attractions_for_kids": [
        "artistic_fun_experience","color_explosion","educational_path","educational_space",
        "entertainment_center","entertainment_zone","friends_activity","giant_brick_structures",
        "immersive_gameplay","immersive_movie_adventure","lemur_exhibit","marine_life_exhibits",
        "motion_seats_experience","precision_game","pumpkin_theme","rainy_day_attraction",
        "sensory_experience_center","small_local_zoo",
    ],
    "kids_attractions": [
        "active_family_fun","active_play","africarium","amusement_area",
        "animal_exhibits","animal_specimens","animal_training",
        "arcade_experience","arcade_games","bird_park","bowling",
        "brick_models","butterfly_exhibit_room",
        "candy_workshop","career_simulation","challenge_game",
        "children_animals","children_history",
        "cinema_theme","city_zoo","city_zoo_animals",
        "climbing_challenges","climbing_wall","competitive_fun","console_collection",
        "creative_painting","creative_splatter_art",
        "digital_floor_games","digital_playground",
        "dinosaur_models","dinosaurs","dollhouses",
        "downhill_sledge","downhill_tracks",
        "edutainment","educational_discovery","educational_exhibits",
        "educational_experience","educational_family_attraction",
        "educational_fun","educational_playground","educational_science_displays",
        "electric_gokarts","escape_room","escape_room_game",
        "fairytale_theme","fairytale_trail",
        "family_amusement_area","family_animal_park","family_attraction","family_bike_park",
        "family_boat_trip","family_building_exhibition","family_challenge","family_exhibition",
        "family_experience","family_forest_walk","family_friendly_attraction","family_friendly_route",
        "family_friendly_water","family_fun_center","family_fun_focus","family_learning_center",
        "family_playgrounds","family_relaxation","family_rides",
        "forest_adventure","forest_adventure_park","forest_challenge",
        "fun_activity","fun_experience","fun_labyrinth_challenge","fun_path",
        "games_and_fun","gaming_exhibition",
        "group_activity","group_adventure","group_fun",
        "hands_on_exhibits","hands_on_learning",
        "high_energy_fun","high_stimulation",
        "horse_riding","horse_sleigh_ride",
        "immersive_adventure","immersive_exhibition","immersive_experience","immersive_game",
        "indoor_activity","indoor_aquapark","indoor_aquapark_slides",
        "indoor_attraction","indoor_fun","indoor_inflatable_park","indoor_jump_park","indoor_play_zone",
        "interactive_aircraft_exhibits","interactive_display","interactive_experience",
        "interactive_game_arena","interactive_games","interactive_history","interactive_history_exhibit",
        "interactive_learning","interactive_mind_tricks","interactive_models","interactive_play",
        "interactive_racing","interactive_science","interactive_science_exhibits","interactive_science_garden",
        "interactive_storytelling","interactive_technology_displays","interactive_zones",
        "jumping_zone","kids_entertainment","kids_escape_room","kids_experience","kids_fun","kids_only",
        "laser_arena","laser_tag","laser_tag_arena","learning_through_play",
        "lego_construction_models","lego_exhibition","lego_fan_exhibition","lego_models_collection",
        "live_animals","live_shows","live_tropical_butterflies",
        "logic_puzzles","maze","maze_challenge","mega_theme_park",
        "mini_zoo","miniature_landmarks","miniature_models","minifigure_display","mirror_maze_experience",
        "model_exhibition","model_trains","mystery_adventure","mystery_game",
        "obstacle_courses","optical_illusion_exhibits",
        "outdoor_challenges","outdoor_experience","outdoor_fun",
        "outdoor_physics_experiments","outdoor_puzzle","parrot_house",
        "play_structures","playful_exhibit_rooms","pools_and_slides","puzzle_solving",
        "role_play_city","scenario_game","scenario_games","skill_game",
        "social_activity","soft_play_structures","spider_exhibition","storybook_figures",
        "team_activity","team_battle","team_building","team_challenge","team_game",
        "toy_collection","toy_exhibition","trampoline_arena","tree_climbing",
        "virtual_reality_cinema","vr_zone",
        "visual_illusion_walk","visual_paradox_rooms","visual_tricks",
        "wind_tunnel","zipline_challenges","zipline_routes",
        # round 2
        "artistic_fun_experience","color_explosion","educational_path","educational_space",
        "entertainment_center","entertainment_zone","friends_activity","giant_brick_structures",
        "immersive_gameplay","immersive_movie_adventure","lemur_exhibit","marine_life_exhibits",
        "motion_seats_experience","precision_game","pumpkin_theme","rainy_day_attraction",
        "sensory_experience_center","small_local_zoo",
    ],
    "theme_parks": [
        "entertainment_center","entertainment_zone","event_theme_park",
        "immersive_gameplay","immersive_movie_adventure","motion_seats_experience","pumpkin_theme",
    ],
    "active_sport": [
        "friends_activity","sports_history_exhibition",
    ],
    "museums_heritage": [
        "artisan_glass_production","business_district","central_square","ceremony",
        "changing_guard","church_tower_view","city_attraction","city_center_landmark",
        "city_events_space","city_experience","city_high_street",
        "colorful_photo_installations","cosmos_theme","creative_installations",
        "economy_basics","educational_path","educational_space","enthusiast_museum",
        "evening_attraction","evening_light_display","event_space",
        "famous_place","guided_activity","guided_only","guided_tour",
        "guided_tours_recommended","guided_visit",
        "illuminated_fountain_show","katowice_highlights","largest_medieval_square",
        "launch_site","live_production","local_culture_collection","local_events_space",
        "local_folklore_display","local_religious_landmark","local_religious_site",
        "marian_sanctuary","marine_life_exhibits","market_square_landmark",
        "modern_parish_church","modern_space","modernist_hall","monument_area",
        "national_symbol","old_market_layout","old_town_center","old_town_landmark",
        "ornate_interior","pilgrimage_site","planned_worker_district","polish_tradition",
        "rainy_day_attraction","revitalized_space","seasonal_event","sensory_experience_center",
        "sightseeing","sports_history_exhibition","street_art","tourist_attraction",
        "tourist_center","tourist_square","train_collection","unesco_city_center",
        "unesco_site","unesco_world_heritage","unique_experience","urban_attraction",
        "urban_exhibition","urban_landmark","vehicle_collection","water_show","winter_tradition",
    ],
    "museum_heritage": [
        "artisan_glass_production","business_district","central_square","ceremony",
        "changing_guard","church_tower_view","city_attraction","city_center_landmark",
        "city_events_space","city_experience","city_high_street",
        "colorful_photo_installations","cosmos_theme","creative_installations",
        "economy_basics","educational_path","educational_space","enthusiast_museum",
        "evening_attraction","evening_light_display","event_space",
        "famous_place","guided_activity","guided_only","guided_tour",
        "guided_tours_recommended","guided_visit",
        "illuminated_fountain_show","katowice_highlights","largest_medieval_square",
        "launch_site","live_production","local_culture_collection","local_events_space",
        "local_folklore_display","local_religious_landmark","local_religious_site",
        "marian_sanctuary","marine_life_exhibits","market_square_landmark",
        "modern_parish_church","modern_space","modernist_hall","monument_area",
        "national_symbol","old_market_layout","old_town_center","old_town_landmark",
        "ornate_interior","pilgrimage_site","planned_worker_district","polish_tradition",
        "rainy_day_attraction","revitalized_space","seasonal_event","sensory_experience_center",
        "sightseeing","sports_history_exhibition","street_art","tourist_attraction",
        "tourist_center","tourist_square","train_collection","unesco_city_center",
        "unesco_site","unesco_world_heritage","unique_experience","urban_attraction",
        "urban_exhibition","urban_landmark","vehicle_collection","water_show","winter_tradition",
    ],
    "nature_landscapes": [
        "active_seafront","central_location","city_center","city_life","city_viewpoint",
        "city_waterfront","cityscape_views","colorful_facades","colorful_townhouses",
        "curiosity_spot","famous_place","fun_photo_spot","iconic_waterfront",
        "lakes_rivers","lanterns_bridge","lively_public_space","local_city_life","local_spot",
        "long_distance","long_stay_possible","love_locks_bridge","meeting_spot","mermaid_statue",
        "modern_bridge","popular_evening_stroll","regional_activity","revitalized_space",
        "river_crossing","river_crossing_landmark","romantic_bridge","romantic_walks",
        "seaside_district","seaside_views","seasonal_activity",
        "sightseeing","skyline_view","street_art","sunset_photo_spot","sunset_spot",
        "tourist_attraction","tourist_promenade","urban_attraction","urban_landmark",
        "urban_life","urban_space","water_show",
    ],
    "nature_landscape": [
        "active_seafront","balancing_rock","botanical_collection","botanical_tree_collection",
        "city_park","cliff_views","cliffside_views",
        "coastal_landscape","coastal_relaxation","coastal_views","coastal_walks",
        "colorful_lakes","dam_structure",
        "dramatic_cliff_views","dramatic_rock_landscape",
        "eagle_nests_trail","easy_access_nature","environmental_learning","exotic_species",
        "famous_bend","fitness_path",
        "forest_hike","forest_hill_walk","forest_landscape","forest_nature_reserve",
        "forest_park_trails","forest_reserve","forest_setting","forested_hill_walk",
        "granite_cliffs","granite_viewpoint",
        "green_city_walk","green_fields_leisure","green_recreation_area","green_relaxation","greenhouse",
        "harbour_views","health_trail","hikers_rest_point","hiking_paths",
        "hill_viewpoint","hilltop_viewpoint",
        "iconic_hiking_destination","iconic_pier",
        "instagram_photo_spots","japanese_garden",
        "karkonosze_ecosystem","karkonosze_landmark","karkonosze_views",
        "labyrinth_rock_formations","lakeside_relax",
        "landscape_design","landscaped_gardens","landscaped_park_walks","landscaped_walks",
        "large_city_meadow","large_city_park",
        "limestone_cliffs_area","limestone_rock_pillar","memorial_hill",
        "mineral_springs","mountain_cable_car","mountain_chairlift","mountain_experience",
        "mountain_folklore","mountain_hut","mountain_lake_relaxation","mountain_rest_point",
        "mountain_river_rafting","mountain_road_curve","mountain_shelter_stop","mountain_valley",
        "mountain_waterfall",
        "national_park","national_park_attraction","national_park_education_center",
        "natural_curiosity","natural_lake_swimming",
        "nature_education","nature_exhibits","nature_picnic_spot","nature_trail",
        "observation_deck","observation_point",
        "ojcow_national_park_cave","ojcow_national_park_landmark",
        "ojcow_national_park_symbol","ojcow_valley_landmark",
        "open_green_space","open_space","oriental_garden",
        "panoramic_landscape_views","panoramic_old_town_views","panoramic_photo_spot","panoramic_valley_views",
        "park_complex","park_walk","peat_bog_reserve","pedestrian_bridge_sculpture","pergola_structure",
        "plant_exhibits","plants","popular_picnic_spot","protected_landscape",
        "quiet_beach_area","quiet_green_area","quiet_nature_walks",
        "rare_plants_collection","rare_wetland_ecosystem","relax_garden",
        "relaxing_green_space","relaxing_walks","remote_nature",
        "river_access","river_activity","river_views",
        "riverside_island","riverside_landmark","riverside_walk",
        "rock_viewpoint","rooftop_garden","sand_spit_walk",
        "sandstone_corridors","sandstone_rock_formations",
        "scenic_cliffs","scenic_drive","scenic_fortress_views","scenic_hilltop",
        "scenic_mountain_views","scenic_riverside_views","scenic_stop","scenic_stroll",
        "scenic_valley","scenic_valley_landmark","scenic_view_dining","scenic_viewpoints","scenic_views","scenic_walks",
        "sea_panorama","sea_views","small_fishing_pier",
        "stalactite_formations","stone_geological_trail",
        "summer_hotspot","summer_spot",
        "suspension_bridge",
        "table_mountains_landscape","table_mountains_nature","table_mountains_peak","table_mountains_views",
        "turquoise_limestone_lake","unique_colors","unique_landscape","unusual_nature_shapes",
        "urban_hill","urban_lake","urban_lake_beach","urban_square",
        "viewpoint_hill","viewpoint_stop",
        "vistula_photo_spot","vistula_river_walks","vistula_riverside_photo_spot",
        "walking","walking_paths",
        "water_education","water_elements","water_features","water_reservoir","water_viewpoint",
        "waterfront_views",
        "wetlands","wildlife","wildlife_exhibits","wildlife_forest_area","yacht_harbour",
        # round 2
        "central_location","city_center","city_life","city_viewpoint",
        "city_waterfront","cityscape_views","colorful_facades","colorful_townhouses",
        "curiosity_spot","famous_place","fun_photo_spot","iconic_waterfront",
        "lakes_rivers","lanterns_bridge","lively_public_space","local_city_life","local_spot",
        "long_distance","long_stay_possible","love_locks_bridge","meeting_spot","mermaid_statue",
        "modern_bridge","popular_evening_stroll","revitalized_space",
        "river_crossing","river_crossing_landmark","romantic_bridge","romantic_walks",
        "seaside_district","seaside_views","seasonal_activity",
        "sightseeing","skyline_view","street_art","sunset_photo_spot","sunset_spot",
        "tourist_attraction","tourist_promenade","urban_attraction","urban_landmark",
        "urban_life","urban_space","water_show",
    ],
    "water_attractions": [
        "active_seafront","city_waterfront","iconic_waterfront","lakes_rivers",
        "lazy_river","seaside_district","seaside_views","water_show",
    ],
    "castles_palaces": [],
    "caves_mines": [],
    "relax_wellness": [
        "couples","couples_activity","cozy_interior","evening_relax","evening_stroll",
        "friends_meeting","long_stay_possible","popular_evening_stroll",
        "regional_activity","romantic_bridge","romantic_walks","seaside_district","seaside_views",
        "seniors","tourist_promenade",
    ],
    "relaxation": [
        "couples","couples_activity","cozy_interior","evening_relax","evening_stroll",
        "friends_meeting","long_stay_possible","popular_evening_stroll",
        "regional_activity","romantic_bridge","romantic_walks","seaside_district","seaside_views",
        "seniors","tourist_promenade",
    ],
    "local_food_experience": [
        "city_high_street","city_life","evening_activity","friends_meeting",
        "lively_atmosphere","local_activity","meeting_spot","polish_tradition",
        "regional_activity","seasonal_event","shopping","shopping_street",
        "tourist_promenade","urban_life","winter_tradition",
    ],
    "history_mystery": [
        "changing_guard","dragon_statue","gravity_anomaly","largest_medieval_square",
        "local_religious_landmark","local_religious_site","marian_sanctuary","market_square_landmark",
        "mermaid_statue","monument_area","national_symbol","old_market_layout","old_town_landmark",
        "pilgrimage_site","planned_worker_district","tourist_square",
        "unesco_city_center","unesco_site","unesco_world_heritage",
    ],
    "mountain_trails": [
        "long_distance","seasonal_activity",
    ],
}

def patch():
    filepath = "app/domain/scoring/tag_preferences.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    total_added = 0
    skipped = 0

    for pref_key, new_tags in ROUND2_ADDITIONS.items():
        if not new_tags:
            continue

        # Find the preference key as a TOP-LEVEL dict key (4-space indent)
        m = re.search(r'^\s{4}"' + re.escape(pref_key) + r'"\s*:\s*\{', content, re.MULTILINE)
        if not m:
            print(f"WARNING: preference key '{pref_key}' not found as top-level key!")
            continue

        idx = m.start()

        # Find "tags": [ after the key
        ts = content.find('"tags": [', idx)
        if ts == -1:
            print(f"WARNING: 'tags' list not found for '{pref_key}'!")
            continue

        bracket_start = content.find('[', ts)
        depth = 0
        bracket_end = bracket_start
        for i in range(bracket_start, len(content)):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    bracket_end = i
                    break

        existing_list_str = content[bracket_start:bracket_end+1]
        tags_to_add = []
        for tag in new_tags:
            if f'"{tag}"' in existing_list_str:
                skipped += 1
            else:
                tags_to_add.append(tag)

        if not tags_to_add:
            print(f"  [{pref_key}]: all {len(new_tags)} tags already present (skipped)")
            continue

        fix_comment = f"\n            # FIX #124 round2: Remaining tags\n"
        tag_lines = "".join(f'            "{t}",\n' for t in tags_to_add)
        insertion = fix_comment + tag_lines

        content = content[:bracket_end] + insertion + "        " + content[bracket_end:]
        total_added += len(tags_to_add)
        print(f"  [{pref_key}]: added {len(tags_to_add)} tags")

    print(f"\nTotal added: {total_added}")
    print(f"Already present (skipped): {skipped}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"File updated: {filepath}")

if __name__ == "__main__":
    patch()
