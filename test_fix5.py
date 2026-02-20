"""
Quick test script for FIX #5 - Preference Coverage Hard Constraints.
Runs plan_service directly and analyzes preference coverage per day.
"""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.application.services.plan_service import PlanService
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.models.trip_input import TripInput
from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS


def check_poi_preferences(poi, preferences):
    """Check which preferences a POI matches."""
    poi_type = poi.get("type", "")
    poi_tags = set(poi.get("tags", []))
    
    matched_prefs = []
    
    for pref in preferences:
        pref_config = USER_PREFERENCES_TO_TAGS.get(pref, {})
        type_matches = pref_config.get("type_match", [])
        tag_matches = set(pref_config.get("tags", []))
        
        # Check if POI matches this preference
        if poi_type in type_matches or poi_tags & tag_matches:
            matched_prefs.append(pref)
    
    return matched_prefs


def analyze_preference_coverage(day_items, user_preferences, poi_repo):
    """Analyze which of top 3 user preferences are covered by attractions."""
    top_3_prefs = user_preferences[:3] if len(user_preferences) >= 3 else user_preferences
    
    covered_prefs = set()
    pref_attractions = {pref: [] for pref in top_3_prefs}
    total_attractions = 0
    
    for item in day_items:
        item_dict = item.dict() if hasattr(item, 'dict') else item
        
        if item_dict['type'] == 'attraction':
            total_attractions += 1
            
            # Get POI data using poi_id from repository
            poi_id = item_dict.get('poi_id')
            if not poi_id:
                continue
            
            # Load POI from repository
            poi = None
            for p in poi_repo.get_all():
                # Convert POI model to dict
                p_dict = p.dict() if hasattr(p, 'dict') else p
                # POI uses "id" field, not "poi_id" - match against item's poi_id
                # Items use "poi_id" format from plan_service (e.g., "poi_35")
                # POI records use "id" format from Excel (e.g., "poi_35" or just index)
                p_id = p_dict.get("id") or p_dict.get("poi_id")
                if p_id == poi_id or f"poi_{p_id}" == poi_id:
                    poi = p_dict
                    break
            
            if not poi:
                if total_attractions == 1:  # Debug first attraction only
                    print(f"[DEBUG] POI not found: {poi_id}")
                    print(f"[DEBUG] First 3 POI IDs in repo: {[(p.dict() if hasattr(p, 'dict') else p).get('id') for p in list(poi_repo.get_all())[:3]]}")
                continue
            
            if total_attractions == 1:  # Debug first POI match
                print(f"[DEBUG] First POI found: {poi.get('Name')}")
                print(f"  type: {poi.get('type')}")
                print(f"  tags: {poi.get('tags', [])[:5]}")  # First 5 tags
            
            matched = check_poi_preferences(poi, top_3_prefs)
            
            if total_attractions == 1 and not matched:
                print(f"[DEBUG] No preferences matched for first POI")
                print(f"  Checking against: {top_3_prefs}")
            
            for pref in matched:
                if pref not in covered_prefs:
                    covered_prefs.add(pref)
                pref_attractions[pref].append(poi.get('Name', 'Unknown'))
    
    uncovered = set(top_3_prefs) - covered_prefs
    
    return {
        'top_3_prefs': top_3_prefs,
        'covered': list(covered_prefs),
        'uncovered': list(uncovered),
        'pref_attractions': pref_attractions,
        'total_attractions': total_attractions,
        'coverage_pct': (len(covered_prefs) / len(top_3_prefs) * 100) if top_3_prefs else 0
    }


def main():
    # Load test-01.json
    test_file = Path(__file__).parent.parent / "Testy_Klientki" / "test-01.json"
    
    print(f"\n{'='*80}")
    print(f"FIX #5 TEST - Preference Coverage Hard Constraints")
    print(f"{'='*80}\n")
    
    print(f"[*] Loading: {test_file}")
    
    with open(test_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    # Parse TripInput
    trip_input = TripInput(**test_data)
    user_prefs = trip_input.preferences if hasattr(trip_input, 'preferences') else []
    
    print(f"[USER] Preferences: {user_prefs}")
    print(f"[USER] Top 3: {user_prefs[:3]}")
    
    # Create plan service
    poi_repo = POIRepository(excel_path="data/zakopane.xlsx")
    plan_service = PlanService(poi_repository=poi_repo)
    
    # Generate plan
    print("\n[*] Generating plan with FIX #5...\n")
    plan_response = plan_service.generate_plan(trip_input)
    
    print(f"[OK] Plan generated: {len(plan_response.days)} days\n")
    
    # Analyze each day
    coverage_results = []
    
    for day in plan_response.days:
        print(f"\n{'─'*80}")
        print(f"[DAY] Day {day.day}")
        print(f"{'─'*80}")
        
        coverage = analyze_preference_coverage(day.items, user_prefs, poi_repo)
        coverage_results.append(coverage)
        
        print(f"\n[PREFERENCES] Top 3: {coverage['top_3_prefs']}")
        print(f"[COVERAGE] {len(coverage['covered'])}/{len(coverage['top_3_prefs'])} covered ({coverage['coverage_pct']:.0f}%)")
        
        if coverage['covered']:
            print(f"\n[✓] COVERED:")
            for pref in coverage['covered']:
                attractions = coverage['pref_attractions'][pref]
                print(f"   • {pref}: {len(attractions)} attraction(s)")
                for att in attractions[:3]:  # Show first 3
                    print(f"      - {att}")
        
        if coverage['uncovered']:
            print(f"\n[✗] UNCOVERED:")
            for pref in coverage['uncovered']:
                print(f"   • {pref}: NO matching attractions")
        
        print(f"\n[STATS] Total attractions: {coverage['total_attractions']}")
    
    print(f"\n{'='*80}")
    print(f"FIX #5 TEST COMPLETE")
    print(f"{'='*80}\n")
    
    # Overall summary
    total_days = len(coverage_results)
    days_with_full_coverage = sum(1 for c in coverage_results if len(c['uncovered']) == 0)
    avg_coverage = sum(c['coverage_pct'] for c in coverage_results) / total_days if total_days > 0 else 0
    
    print(f"[SUMMARY]:")
    print(f"   • Total days: {total_days}")
    print(f"   • Days with 100% coverage: {days_with_full_coverage}/{total_days}")
    print(f"   • Average coverage: {avg_coverage:.1f}%")
    print(f"   • Boost threshold: After 2 attractions")
    print(f"   • Boost strength: +75 per uncovered preference")
    
    if days_with_full_coverage == total_days:
        print(f"\n[SUCCESS] ✓ All days have 100% preference coverage!")
    else:
        print(f"\n[WARNING] Some days missing preference coverage")


if __name__ == "__main__":
    main()
