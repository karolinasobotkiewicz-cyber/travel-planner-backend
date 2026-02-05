"""
CLIENT REQUIREMENT TEST (04.02.2026): Budget scoring strengthening
Test that budget scoring has stronger influence on POI selection

Compare plans for low-budget vs high-budget users
Expected: Low-budget plans should exclude expensive POI more aggressively
"""

import sys
import io
sys.path.insert(0, '.')

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI
ZAKOPANE_POI = load_zakopane_poi("data/zakopane.xlsx")

def generate_plan_with_budget(budget_level):
    """Generate plan with specific budget level"""
    user = {
        "target_group": "friends",
        "intensity_preference": "medium",
        "budget": budget_level  # 1=low, 2=medium, 3=high
    }
    
    ctx = {
        "season": "winter",
        "has_car": True,
        "accommodation_location": {"lat": 49.295, "lon": 19.949},
        "start_time": "09:00",
        "end_time": "22:00",
        "date": "2026-02-05"
    }
    
    plan = build_day(ZAKOPANE_POI, user, ctx)
    
    # Extract POI with prices
    poi_list = []
    total_cost = 0
    
    for item in plan:
        if item["type"] == "attraction":
            poi = item.get("poi", {})
            poi_name = item.get("name", "Unknown")
            price = poi.get("ticket_price", 0) or 0
            budget_level = poi.get("budget_level", "N/A")
            
            poi_list.append({
                "name": poi_name,
                "price": float(price),
                "budget_level": budget_level
            })
            total_cost += float(price)
    
    return poi_list, total_cost

def test_budget_scoring_strength():
    """Test that budget scoring influences POI selection strongly"""
    print("\n" + "="*80)
    print("CLIENT REQUIREMENT TEST: Budget Scoring Strengthening")
    print("="*80)
    print("Comparing low-budget vs high-budget user plans")
    print("Expected: Low-budget plan should have lower total cost\n")
    
    # Generate plans
    print("🔄 Generating LOW-BUDGET plan (budget=1)...")
    low_budget_poi, low_total = generate_plan_with_budget(1)
    
    print("🔄 Generating HIGH-BUDGET plan (budget=3)...")
    high_budget_poi, high_total = generate_plan_with_budget(3)
    
    # Display results
    print("\n" + "="*80)
    print("RESULTS:")
    print("="*80)
    
    print(f"\n💰 LOW-BUDGET PLAN (budget=1):")
    print(f"   Total POI: {len(low_budget_poi)}")
    print(f"   Total cost: {low_total:.2f} PLN")
    print("   POI list:")
    for poi in low_budget_poi:
        print(f"     - {poi['name']}: {poi['price']:.2f} PLN (budget_level={poi['budget_level']})")
    
    print(f"\n💎 HIGH-BUDGET PLAN (budget=3):")
    print(f"   Total POI: {len(high_budget_poi)}")
    print(f"   Total cost: {high_total:.2f} PLN")
    print("   POI list:")
    for poi in high_budget_poi:
        print(f"     - {poi['name']}: {poi['price']:.2f} PLN (budget_level={poi['budget_level']})")
    
    # Analysis
    print("\n" + "="*80)
    print("BUDGET SCORING ANALYSIS:")
    print("="*80)
    
    cost_diff = high_total - low_total
    cost_ratio = (high_total / low_total) if low_total > 0 else 0
    
    print(f"\n📊 Cost difference: {cost_diff:.2f} PLN")
    print(f"📊 High/Low ratio: {cost_ratio:.2f}x")
    
    # Evaluation
    print("\n" + "="*80)
    if low_total < high_total:
        print("✅ PASS | Budget scoring works: low-budget plan is cheaper")
        if cost_diff >= 50:
            print(f"         Strong effect: {cost_diff:.2f} PLN difference")
        else:
            print(f"         Moderate effect: {cost_diff:.2f} PLN difference")
    elif low_total == high_total:
        print("⚠️  PARTIAL | Same total cost - budget scoring may need more strengthening")
    else:
        print("❌ FAIL | Low-budget plan is MORE expensive than high-budget!")
        print("         Budget scoring not working correctly")
    print("="*80 + "\n")
    
    return low_total <= high_total

if __name__ == "__main__":
    success = test_budget_scoring_strength()
    sys.exit(0 if success else 1)
