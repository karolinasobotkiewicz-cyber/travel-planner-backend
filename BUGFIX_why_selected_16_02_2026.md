# BUGFIX: why_selected Illogical Reasons (16.02.2026)

## Problem #5 - CLIENT FEEDBACK

**Client:** Karolina  
**Date:** 16.02.2026  
**Priority:** 🔴 HIGH  

### Issue

> "`why_selected` zawiera nielogiczne argumenty niepasujące do POI."

**Examples from client feedback:**

1. **Dom do góry nogami:**
   - why_selected: `"Great for museum_heritage lovers"`
   - why_selected: `"Breathtaking mountain views"`
   - **Reality:** POI is Instagram/novelty attraction with tags `["illusion_kids", "interactive_exhibition_kids"]`
   - **Problem:** No museum/heritage tags, no viewpoint/scenic tags

2. **Wielka Krokiew (ski jump toboggan):**
   - why_selected: `"nature_landscape lovers"` (naciągane)
   - **Reality:** POI is active_sport with tags `["snow_tubing", "adrenaline_experience", "beginner_friendly"]`
   - **Problem:** No nature_landscape/hiking tags

**Client suggestion:**
> "Może słownik why_selected powinien być generowany z tagów POI? Albo dodać walidację: jeśli POI nie ma tagu nature_landscape / mountain_trails / viewpoint, to nie wolno używać argumentów o widokach górskich."

---

## Root Cause

### Issue 1: Preferences Match (Lines 64-74)

**Original Code:**
```python
# Preferences match
preferences = user.get("preferences", [])
poi_tags = str(poi.get("tags", "")).lower()
poi_type = poi.get("type", "").lower()

matched_prefs = []
for pref in preferences:
    pref_lower = pref.lower()
    if pref_lower in poi_tags or pref_lower in poi_type:  # ❌ PROBLEM
        matched_prefs.append(pref)

if matched_prefs:
    prefs_text = " and ".join(matched_prefs[:2])
    reasons.append(f"Great for {prefs_text} lovers")
```

**Problem:**
- Checks if user preference is substring of `poi_tags` OR `poi_type`
- "Dom do góry nogami" has `type: "museum_heritage"` but NO museum tags in Tags field
- User with preference "museum_heritage" gets reason "Great for museum_heritage lovers" even though POI has NO actual museum tags
- **Type can be misleading** - it's a categorization, not actual POI attributes

### Issue 2: Name-Based Logic (Lines 107-115)

**Original Code:**
```python
# Special experiences
poi_name = poi.get("name", "").lower()
if "kuligi" in poi_name:
    reasons.append("Unique winter experience you can't miss")
elif "termy" in poi_name or "spa" in poi_name:
    reasons.append("Perfect for relaxation after a day of exploring")
elif "muzeum" in poi_name:
    reasons.append("Cultural enrichment and local history")
elif "góry" in poi_name or "morskie oko" in poi_name or "kościeliska" in poi_name:  # ❌ PROBLEM
    reasons.append("Breathtaking mountain views")
```

**Problem:**
- Generates reasons based ONLY on substring matching in POI name
- "Dom do **góry** nogami" has "góry" in name → gets "Breathtaking mountain views"
- But it's NOT a viewpoint or scenic location - it's an illusion house!
- **Name-based logic is unreliable** - need tag-based validation

---

## Solution

### Fix 1: Validate Preferences Against Actual POI Tags

**New Code (Lines 64-93):**
```python
# BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #5):
# Validate preferences against POI tags (not type) to avoid illogical reasons
# Example: "Dom do góry nogami" has type "museum_heritage" but no actual museum tags

# Preferences match - validate against actual POI tags
preferences = user.get("preferences", [])
poi_tags_list = poi.get("tags", [])

# Convert tags to list if string
if isinstance(poi_tags_list, str):
    if poi_tags_list:
        poi_tags_list = [t.strip().lower() for t in poi_tags_list.split(",") if t.strip()]
    else:
        poi_tags_list = []

# Normalize POI tags to lowercase
poi_tags_normalized = [str(tag).lower() for tag in poi_tags_list]

matched_prefs = []
for pref in preferences:
    pref_lower = pref.lower()
    # Check if preference matches any POI tag (exact or substring)
    if any(pref_lower in tag or tag in pref_lower for tag in poi_tags_normalized):
        matched_prefs.append(pref)

if matched_prefs:
    # Take first 2 preferences
    prefs_text = " and ".join(matched_prefs[:2])
    reasons.append(f"Great for {prefs_text} lovers")
```

**Changes:**
- ✅ Only check `poi_tags_list` (actual POI tags), NOT `poi_type`
- ✅ Parse tags to list (handle both string and list formats)
- ✅ Match preference against normalized tags
- ✅ Ignore POI type - it's categorization, not validation

### Fix 2: Tag-Based Validation for Special Experiences

**New Code (Lines 103-127):**
```python
# BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #5):
# Generate special experience reasons ONLY from POI tags, not name substring matching
# Example: "Dom do góry nogami" has "góry" in name but is NOT a viewpoint

# Special experiences - validate against POI tags
poi_tags_str = ",".join(poi_tags_normalized) if poi_tags_normalized else ""
poi_type = poi.get("type", "").lower()

# Winter experiences (kuligi)
if "winter_experience" in poi_tags_str or "kulig" in poi_type:
    reasons.append("Unique winter experience you can't miss")

# Relaxation (termy/spa)
elif any(tag in poi_type for tag in ["termy", "spa", "wellness", "thermal"]):
    reasons.append("Perfect for relaxation after a day of exploring")

# Museum/cultural (validate with tags, not just name)
elif any(tag in poi_tags_str for tag in ["museum", "heritage", "cultural", "historical", "ethnographic"]):
    reasons.append("Cultural enrichment and local history")

# Mountain views (validate with tags: viewpoint/scenic/panorama)
elif any(tag in poi_tags_str for tag in ["viewpoint", "scenic", "panorama", "mountain_view", "nature_landscape"]):
    reasons.append("Breathtaking mountain views")
```

**Changes:**
- ✅ Remove name-based substring matching
- ✅ Validate against POI tags: `["viewpoint", "scenic", "panorama", "mountain_view", "nature_landscape"]`
- ✅ Only generate "mountain views" if POI actually has viewpoint/scenic tags
- ✅ Museum reasons only if POI has museum/heritage tags

---

## Test Results

**Test File:** `test_why_selected_validation.py`

### Test 1: Dom do góry nogami (Negative Test)

```
POI: Dom do góry nogami
Type: kids_attractions, museum_heritage
Tags: ['illusion_kids', 'interactive_exhibition_kids']

Generated why_selected:
  - Perfect for couples seeking romantic experiences

✅ VALIDATION:
   ✅ PASS: No museum/heritage reason (correct - POI has no museum tags)
   ✅ PASS: No mountain/views reason (correct - POI has no viewpoint tags)
```

**Result:** ✅ **PASS** - No illogical reasons generated

### Test 2: Wielka Krokiew (Negative Test)

```
POI: Zjazd pontonem ze skoczni narciarskiej Wielka Krokiew
Type: active_sport, kids_attractions
Tags: ['snow_tubing', 'adrenaline_experience', 'beginner_friendly', 'group_activity']

Generated why_selected:
  - Great for groups of friends

✅ VALIDATION:
   ✅ PASS: No nature/landscape reason (correct - POI has no nature tags)
```

**Result:** ✅ **PASS** - No nature/landscape reason for active_sport POI

### Test 3: Dolina Kościeliska (Positive Test)

```
POI: Dolina Kościeliska
Type: mountain_trails
Tags: ['must_see', 'nature_landscapes', 'hiking', 'scenic_views']

Generated why_selected:
  - Must-see attraction in Zakopane
  - Great for groups of friends
  - Great for nature_landscapes and hiking lovers

✅ VALIDATION:
   ✅ PASS: Has nature/mountain reason AND POI has matching tags
      POI tags include nature/landscape/mountain/viewpoint
```

**Result:** ✅ **PASS** - Correct nature reason for POI with actual nature tags

### Test Summary

```
================================================================================
TEST SUMMARY
================================================================================

✅ ALL CRITICAL TESTS PASSED

   Problem #5 FIXED:
   - why_selected validates against actual POI tags
   - No illogical reasons (museum/mountain views for wrong POIs)
   - Reasons match POI's real attributes
```

---

## Impact

### Before Fix

**Dom do góry nogami:**
```json
{
  "why_selected": [
    "Great for museum_heritage lovers",     ❌ POI has NO museum tags
    "Breathtaking mountain views"           ❌ POI has NO viewpoint tags
  ]
}
```

**Wielka Krokiew:**
```json
{
  "why_selected": [
    "Great for nature_landscape lovers"     ❌ POI has NO nature tags
  ]
}
```

### After Fix

**Dom do góry nogami:**
```json
{
  "why_selected": [
    "Perfect for couples seeking romantic experiences"  ✅ Matches target_group
  ]
}
```

**Wielka Krokiew:**
```json
{
  "why_selected": [
    "Great for groups of friends"           ✅ Matches target_group
  ]
}
```

**Dolina Kościeliska (with nature tags):**
```json
{
  "why_selected": [
    "Must-see attraction in Zakopane",
    "Great for groups of friends",
    "Great for nature_landscapes and hiking lovers"  ✅ Matches POI tags
  ]
}
```

**Benefits:**
- ✅ why_selected reasons validated against actual POI tags
- ✅ No illogical reasons (no "mountain views" for non-viewpoints)
- ✅ No misleading information for users
- ✅ Better trust in plan quality and recommendations
- ✅ Consistent with POI's real attributes

---

## Files Modified

1. **app/domain/planner/explainability.py**:
   - Lines 64-93: Fixed preferences match validation (tags only, not type)
   - Lines 103-127: Fixed special experiences validation (tag-based, not name-based)

2. **test_why_selected_validation.py** (NEW):
   - Comprehensive test validating both negative and positive cases
   - Tests Dom do góry nogami (no illogical reasons)
   - Tests Wielka Krokiew (no nature reason)
   - Tests Dolina Kościeliska (correct nature reason)

---

## Status

**Problem #5:** ✅ **FIXED** (16.02.2026)

**Next Steps:**
- Problem #6: Fix quality_badges consistency (MEDIUM priority)
- Problem #7: Add time continuity validator (HIGH priority)
- Problems #8-12: Remaining medium/low priority issues

---

**Date:** 16.02.2026  
**Author:** AI Agent (GitHub Copilot)  
**Reviewer:** User (requested client feedback validation)  
**Status:** ✅ IMPLEMENTED & TESTED
