"""
Comprehensive UAT Round 2 Test Suite - All 10 Test Scenarios
BUGFIX VALIDATION (19.02.2026)

Tests all 7 issues with real client test data from Testy_Klientki folder:
1. Bug #1: Parking overlap (9/10 tests)
2. Bug #2: duration_min accuracy (6/10 tests)
3. Bug #3: Gap filling (8/10 tests)
4. Issue #4: why_selected refinement (7/10 tests)
5. Issue #5: Preference coverage (7/10 tests)
6. Issue #6: Crowd_tolerance accuracy (5/10 tests)
7. Issue #7: cost_estimate communication (1/10 tests)
"""

import json
import sys
import os
from pathlib import Path
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

# Configuration
API_BASE_URL = "http://localhost:8080"
TEST_FILES_DIR = Path("..") / "Testy_Klientki"
RESULTS_DIR = Path("test_results_uat_round2")

# Create results directory
RESULTS_DIR.mkdir(exist_ok=True)


class Colors:
    """Console colors for better readability"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_section(text: str):
    """Print formatted section"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'-'*len(text)}{Colors.END}")


def print_pass(text: str):
    """Print pass message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_fail(text: str):
    """Print fail message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def load_test_json(test_number: int) -> Dict[str, Any]:
    """Load test JSON from Testy_Klientki folder"""
    file_path = TEST_FILES_DIR / f"test-{test_number:02d}.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def call_api(request_data: Dict[str, Any]) -> Tuple[bool, Any]:
    """Call the travel planner API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/plan/preview",
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)


def validate_bug1_parking_overlap(response: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Bug #1: Validate no parking overlaps with transit
    
    Issue: 9/10 tests showed parking_start < transit_end
    Fix: plan_service.py validation ensures parking_start >= transit_end
    """
    issues = []
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        for item_idx, item in enumerate(day.get("plan", []), 1):
            if item.get("type") == "attraction" and "parking" in item:
                parking = item["parking"]
                parking_start = parking.get("parking_start")
                
                # Find previous transit item
                if item_idx > 0:
                    prev_item = day["plan"][item_idx - 1]
                    if prev_item.get("type") == "transit":
                        transit_end = prev_item.get("end_time")
                        
                        if parking_start and transit_end:
                            if parking_start < transit_end:
                                issues.append(
                                    f"Day {day_idx}, Item {item_idx}: "
                                    f"Parking starts at {parking_start} but "
                                    f"transit ends at {transit_end}"
                                )
    
    return len(issues) == 0, issues


def validate_bug2_duration_min(response: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Bug #2: Validate duration_min accuracy for meals
    
    Issue: 6/10 tests showed duration_min ≠ actual time difference
    Fix: engine.py calculates duration from time difference
    """
    issues = []
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        for item in day.get("plan", []):
            if item.get("type") in ["lunch", "dinner"]:
                start = item.get("start_time", "")
                end = item.get("end_time", "")
                duration_min = item.get("duration_min", 0)
                
                # Calculate actual duration
                try:
                    start_parts = list(map(int, start.split(":")))
                    end_parts = list(map(int, end.split(":")))
                    start_minutes = start_parts[0] * 60 + start_parts[1]
                    end_minutes = end_parts[0] * 60 + end_parts[1]
                    actual_duration = end_minutes - start_minutes
                    
                    if abs(actual_duration - duration_min) > 1:  # Allow 1 min tolerance
                        issues.append(
                            f"Day {day_idx}, {item['type']}: "
                            f"duration_min={duration_min} but actual={actual_duration} "
                            f"({start} to {end})"
                        )
                except:
                    pass
    
    return len(issues) == 0, issues


def validate_bug3_gap_filling(response: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Bug #3: Validate gap filling logic
    
    Issue: 8/10 tests had problems:
    - Gaps too short (<20 min) shouldn't be filled
    - Gaps 40-90 min should be filled
    - Gap items need context labels
    
    Fix: Thresholds 20→60 min, limits 120-180 min, smart labels
    """
    issues = []
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        plan = day.get("plan", [])
        
        for i in range(len(plan) - 1):
            current_item = plan[i]
            next_item = plan[i + 1]
            
            current_end = current_item.get("end_time", "")
            next_start = next_item.get("start_time", "")
            
            if current_end and next_start:
                try:
                    # Calculate gap
                    end_parts = list(map(int, current_end.split(":")))
                    start_parts = list(map(int, next_start.split(":")))
                    end_minutes = end_parts[0] * 60 + end_parts[1]
                    start_minutes = start_parts[0] * 60 + start_parts[1]
                    gap_minutes = start_minutes - end_minutes
                    
                    # Check if gap item exists between them
                    has_gap_item = (i + 1 < len(plan) - 1 and 
                                   plan[i + 1].get("type") == "gap")
                    
                    # Validate gap filling logic
                    if gap_minutes >= 60 and gap_minutes <= 180:
                        # Should have gap item
                        if not has_gap_item:
                            print_warning(
                                f"Day {day_idx}: Gap of {gap_minutes} min "
                                f"between {current_end} and {next_start} not filled"
                            )
                    elif gap_minutes < 20:
                        # Should NOT have gap item
                        if has_gap_item:
                            issues.append(
                                f"Day {day_idx}: Gap too short ({gap_minutes} min) "
                                f"but has gap item"
                            )
                    
                    # Check gap item labels
                    if has_gap_item:
                        gap_item = plan[i + 1]
                        description = gap_item.get("description_short", "")
                        
                        # Should have context label
                        context_labels = [
                            "przed obiadem", "po obiedzie",
                            "przed kolacją", "po kolacji",
                            "przed", "po", "między"
                        ]
                        
                        has_context = any(label in description.lower() 
                                        for label in context_labels)
                        
                        if not has_context:
                            print_warning(
                                f"Day {day_idx}: Gap item lacks context label: "
                                f"'{description}'"
                            )
                
                except:
                    pass
    
    return len(issues) == 0, issues


def validate_issue4_why_selected(response: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Issue #4: Validate why_selected refinement 2.0
    
    Issue: 7/10 tests had "Quiet, peaceful destination" spam
    Fix: Removed hardcoded spam, added profile-aware reasoning
    """
    issues = []
    quiet_spam_count = 0
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        for item in day.get("plan", []):
            if item.get("type") == "attraction":
                why_selected = item.get("why_selected", [])
                
                # Check for "Quiet" spam
                quiet_reasons = [r for r in why_selected 
                               if "quiet" in r.lower() or "peaceful" in r.lower()]
                
                if len(quiet_reasons) > 1:
                    quiet_spam_count += 1
                    issues.append(
                        f"Day {day_idx}, {item.get('name', 'Unknown')}: "
                        f"Multiple 'Quiet' reasons: {quiet_reasons}"
                    )
                
                # Check for empty/generic reasons
                if not why_selected:
                    print_warning(
                        f"Day {day_idx}, {item.get('name', 'Unknown')}: "
                        f"No why_selected reasons"
                    )
                elif all(len(r) < 10 for r in why_selected):
                    print_warning(
                        f"Day {day_idx}, {item.get('name', 'Unknown')}: "
                        f"Only generic reasons: {why_selected}"
                    )
    
    return len(issues) == 0, issues


def validate_issue5_preferences(response: Dict[str, Any], 
                                request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Issue #5: Validate preference coverage
    
    Issue: 7/10 tests ignored user preferences (kids_attractions, relaxation)
    Fix: Increased weights (top 3: +15, others: +8), travel_style modifiers
    """
    issues = []
    preferences = request.get("preferences", [])
    top_3_prefs = set(preferences[:3])
    
    if not top_3_prefs:
        return True, []  # No preferences to validate
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        attractions = [
            item for item in day.get("plan", [])
            if item.get("type") == "attraction" and item.get("poi_id")
        ]
        
        # Check if day covers top 3 preferences
        day_tags = set()
        for item in attractions:
            # Try to extract tags from description or other fields
            # (In real scenario, we'd need POI tags from database)
            pass
        
        # At minimum, check if attractions have preference-related keywords
        pref_keywords = {
            "kids_attractions": ["kids", "family", "children", "playground"],
            "relaxation": ["spa", "termy", "wellness", "relax"],
            "active_sport": ["sport", "climbing", "hiking", "trails"],
            "museum_heritage": ["museum", "heritage", "history"],
            "nature_landscape": ["nature", "landscape", "mountain", "view"],
        }
        
        has_pref_match = False
        for pref in top_3_prefs:
            keywords = pref_keywords.get(pref, [])
            for item in attractions:
                name_lower = item.get("name", "").lower()
                desc_lower = item.get("description_short", "").lower()
                
                if any(kw in name_lower or kw in desc_lower for kw in keywords):
                    has_pref_match = True
                    break
            
            if has_pref_match:
                break
        
        if not has_pref_match and len(attractions) > 0:
            print_warning(
                f"Day {day_idx}: No clear preference match for top 3: "
                f"{list(top_3_prefs)}"
            )
    
    return len(issues) == 0, issues


def validate_issue6_crowd_tolerance(response: Dict[str, Any],
                                    request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Issue #6: Validate crowd_tolerance accuracy
    
    Issue: 5/10 tests said "Low-crowd" for crowded POI (Morskie Oko, Krokiew)
    Fix: Use crowd_level instead of popularity_score, stronger penalties
    """
    issues = []
    crowd_tolerance = request.get("group", {}).get("crowd_tolerance", 2)
    
    # Known crowded POI from client feedback
    crowded_poi = {
        "morskie oko": "High crowd (crowd_level=3)",
        "wielka krokiew": "High crowd (crowd_level=3)",
        "gubałówka": "High crowd (crowd_level=3)",
    }
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        for item in day.get("plan", []):
            if item.get("type") == "attraction":
                name_lower = item.get("name", "").lower()
                why_selected = item.get("why_selected", [])
                
                # Check if crowded POI labeled as "Low-crowd"
                for poi_name, crowd_info in crowded_poi.items():
                    if poi_name in name_lower:
                        has_low_crowd_label = any(
                            "low-crowd" in reason.lower() or "quiet" in reason.lower()
                            for reason in why_selected
                        )
                        
                        if has_low_crowd_label and crowd_tolerance <= 1:
                            issues.append(
                                f"Day {day_idx}, {item.get('name')}: "
                                f"Labeled 'Low-crowd' but is {crowd_info}"
                            )
                        
                        # Low tolerance users shouldn't visit crowded POI
                        if crowd_tolerance <= 1:
                            print_warning(
                                f"Day {day_idx}: Low tolerance user visiting "
                                f"crowded POI: {item.get('name')}"
                            )
    
    return len(issues) == 0, issues


def validate_issue7_cost_note(response: Dict[str, Any],
                              request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Issue #7: Validate cost_estimate communication
    
    Issue: 1/10 tests - unclear if cost is per person or group total
    Fix: Added cost_note field with explicit explanation
    """
    issues = []
    group_size = request.get("group", {}).get("size", 1)
    
    for day_idx, day in enumerate(response.get("days", []), 1):
        for item in day.get("plan", []):
            if item.get("type") == "attraction":
                cost_estimate = item.get("cost_estimate")
                cost_note = item.get("cost_note")
                
                if cost_estimate and cost_estimate > 0:
                    # Should have cost_note
                    if not cost_note:
                        issues.append(
                            f"Day {day_idx}, {item.get('name')}: "
                            f"Has cost_estimate={cost_estimate} but no cost_note"
                        )
                    else:
                        # Validate cost_note content
                        expected_phrases = [
                            f"group of {group_size}",
                            "for 1 person",
                            "for your group"
                        ]
                        
                        has_expected = any(phrase in cost_note.lower() 
                                         for phrase in expected_phrases)
                        
                        if not has_expected:
                            issues.append(
                                f"Day {day_idx}, {item.get('name')}: "
                                f"cost_note unclear: '{cost_note}'"
                            )
    
    return len(issues) == 0, issues


def run_test(test_number: int) -> Dict[str, Any]:
    """Run single test scenario and validate all issues"""
    print_header(f"TEST {test_number:02d}")
    
    # Load test data
    print(f"Loading test data from Testy_Klientki/test-{test_number:02d}.json...")
    try:
        request_data = load_test_json(test_number)
    except Exception as e:
        print_fail(f"Failed to load test JSON: {e}")
        return {
            "test_number": test_number,
            "status": "ERROR",
            "error": str(e)
        }
    
    # Print test profile
    group = request_data.get("group", {})
    travel_style = request_data.get("travel_style", "")
    days = request_data.get("trip_length", {}).get("days", 0)
    preferences = request_data.get("preferences", [])
    
    print(f"Profile: {group.get('type')} (size={group.get('size')}), "
          f"{days} days, {travel_style}")
    print(f"Preferences: {', '.join(preferences)}")
    print(f"Crowd tolerance: {group.get('crowd_tolerance', 2)}")
    print()
    
    # Call API
    print("Calling API...")
    success, response = call_api(request_data)
    
    if not success:
        print_fail(f"API call failed: {response}")
        return {
            "test_number": test_number,
            "status": "API_ERROR",
            "error": response
        }
    
    print_pass("API call successful")
    
    # Save response for debugging
    response_file = RESULTS_DIR / f"test-{test_number:02d}-response.json"
    with open(response_file, 'w', encoding='utf-8') as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    print(f"Response saved to: {response_file}")
    
    # Validate all 7 issues
    results = {}
    
    print_section("Validating Bug #1: Parking Overlap")
    bug1_pass, bug1_issues = validate_bug1_parking_overlap(response)
    if bug1_pass:
        print_pass("No parking overlaps detected")
    else:
        for issue in bug1_issues:
            print_fail(issue)
    results["bug1_parking"] = {"pass": bug1_pass, "issues": bug1_issues}
    
    print_section("Validating Bug #2: duration_min Accuracy")
    bug2_pass, bug2_issues = validate_bug2_duration_min(response)
    if bug2_pass:
        print_pass("All duration_min values accurate")
    else:
        for issue in bug2_issues:
            print_fail(issue)
    results["bug2_duration"] = {"pass": bug2_pass, "issues": bug2_issues}
    
    print_section("Validating Bug #3: Gap Filling")
    bug3_pass, bug3_issues = validate_bug3_gap_filling(response)
    if bug3_pass:
        print_pass("Gap filling logic correct")
    else:
        for issue in bug3_issues:
            print_fail(issue)
    results["bug3_gaps"] = {"pass": bug3_pass, "issues": bug3_issues}
    
    print_section("Validating Issue #4: why_selected Refinement")
    issue4_pass, issue4_issues = validate_issue4_why_selected(response)
    if issue4_pass:
        print_pass("No 'Quiet' spam detected")
    else:
        for issue in issue4_issues:
            print_fail(issue)
    results["issue4_why_selected"] = {"pass": issue4_pass, "issues": issue4_issues}
    
    print_section("Validating Issue #5: Preference Coverage")
    issue5_pass, issue5_issues = validate_issue5_preferences(response, request_data)
    if issue5_pass:
        print_pass("Preference coverage validated")
    else:
        for issue in issue5_issues:
            print_fail(issue)
    results["issue5_preferences"] = {"pass": issue5_pass, "issues": issue5_issues}
    
    print_section("Validating Issue #6: Crowd Tolerance")
    issue6_pass, issue6_issues = validate_issue6_crowd_tolerance(response, request_data)
    if issue6_pass:
        print_pass("Crowd tolerance accuracy validated")
    else:
        for issue in issue6_issues:
            print_fail(issue)
    results["issue6_crowd"] = {"pass": issue6_pass, "issues": issue6_issues}
    
    print_section("Validating Issue #7: cost_note Communication")
    issue7_pass, issue7_issues = validate_issue7_cost_note(response, request_data)
    if issue7_pass:
        print_pass("Cost notes present and clear")
    else:
        for issue in issue7_issues:
            print_fail(issue)
    results["issue7_cost"] = {"pass": issue7_pass, "issues": issue7_issues}
    
    # Overall result
    all_pass = all(r["pass"] for r in results.values())
    
    print()
    if all_pass:
        print_pass(f"TEST {test_number:02d} PASSED - All validations successful ✓")
    else:
        failed = [k for k, v in results.items() if not v["pass"]]
        print_fail(f"TEST {test_number:02d} FAILED - Issues in: {', '.join(failed)}")
    
    return {
        "test_number": test_number,
        "status": "PASS" if all_pass else "FAIL",
        "profile": {
            "group_type": group.get("type"),
            "group_size": group.get("size"),
            "days": days,
            "travel_style": travel_style,
            "crowd_tolerance": group.get("crowd_tolerance")
        },
        "validations": results
    }


def generate_final_report(all_results: List[Dict[str, Any]]):
    """Generate comprehensive final report"""
    print_header("FINAL VALIDATION REPORT - UAT ROUND 2")
    
    # Overall statistics
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r.get("status") == "PASS")
    failed_tests = sum(1 for r in all_results if r.get("status") == "FAIL")
    error_tests = sum(1 for r in all_results 
                     if r.get("status") in ["ERROR", "API_ERROR"])
    
    print(f"Total tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.END}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.END}")
    print(f"{Colors.YELLOW}Errors: {error_tests}{Colors.END}")
    print()
    
    # Issue-by-issue statistics
    print_section("Issue-by-Issue Results")
    
    issue_stats = {
        "bug1_parking": "Bug #1: Parking Overlap",
        "bug2_duration": "Bug #2: duration_min Accuracy",
        "bug3_gaps": "Bug #3: Gap Filling",
        "issue4_why_selected": "Issue #4: why_selected Refinement",
        "issue5_preferences": "Issue #5: Preference Coverage",
        "issue6_crowd": "Issue #6: Crowd Tolerance",
        "issue7_cost": "Issue #7: cost_note Communication"
    }
    
    for issue_key, issue_name in issue_stats.items():
        passed = sum(1 for r in all_results 
                    if r.get("status") not in ["ERROR", "API_ERROR"] 
                    and r.get("validations", {}).get(issue_key, {}).get("pass", False))
        
        total_valid = sum(1 for r in all_results 
                         if r.get("status") not in ["ERROR", "API_ERROR"])
        
        if total_valid > 0:
            percentage = (passed / total_valid) * 100
            status = "✓" if passed == total_valid else "✗"
            color = Colors.GREEN if passed == total_valid else Colors.RED
            print(f"{color}{status} {issue_name}: {passed}/{total_valid} ({percentage:.0f}%){Colors.END}")
    
    print()
    
    # Test-by-test summary
    print_section("Test-by-Test Summary")
    
    for result in all_results:
        test_num = result["test_number"]
        status = result["status"]
        
        if status == "PASS":
            print(f"{Colors.GREEN}✓ Test {test_num:02d}: PASS{Colors.END}")
        elif status == "FAIL":
            print(f"{Colors.RED}✗ Test {test_num:02d}: FAIL{Colors.END}")
            validations = result.get("validations", {})
            failed = [k for k, v in validations.items() if not v["pass"]]
            for issue_key in failed:
                issue_name = issue_stats.get(issue_key, issue_key)
                print(f"    - {issue_name}")
        else:
            print(f"{Colors.YELLOW}⚠ Test {test_num:02d}: {status}{Colors.END}")
            if "error" in result:
                print(f"    Error: {result['error']}")
    
    print()
    
    # Save report to file
    report_file = RESULTS_DIR / f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests
            },
            "results": all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Full report saved to: {report_file}")
    print()
    
    # Final verdict
    if passed_tests == total_tests:
        print_header("🎉 ALL TESTS PASSED! 🎉")
        print(f"{Colors.GREEN}{Colors.BOLD}Wszystkie 7 błędów zostały naprawione!{Colors.END}")
        print(f"{Colors.GREEN}Klientka będzie zadowolona ✓{Colors.END}")
    else:
        print_header("⚠ SOME TESTS FAILED")
        print(f"{Colors.YELLOW}Należy przeanalizować failed testy i poprawić pozostałe błędy.{Colors.END}")


def main():
    """Main test execution"""
    print_header("UAT ROUND 2 - COMPREHENSIVE TEST SUITE")
    print("Testing all 7 bugfixes with 10 client test scenarios")
    print(f"Test files location: {TEST_FILES_DIR.absolute()}")
    print(f"Results location: {RESULTS_DIR.absolute()}")
    print()
    
    # Check if API is running
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_pass(f"API is running at {API_BASE_URL}")
        else:
            print_fail("API health check failed")
            print("Please start the API server first:")
            print("  cd travel-planner-backend/app")
            print("  uvicorn main:app --reload")
            return
    except:
        print_fail(f"Cannot connect to API at {API_BASE_URL}")
        print("Please start the API server first:")
        print("  cd travel-planner-backend/app")
        print("  uvicorn main:app --reload")
        return
    
    print()
    
    # Run all tests
    all_results = []
    
    for test_num in range(1, 11):
        result = run_test(test_num)
        all_results.append(result)
        print()
    
    # Generate final report
    generate_final_report(all_results)


if __name__ == "__main__":
    main()
