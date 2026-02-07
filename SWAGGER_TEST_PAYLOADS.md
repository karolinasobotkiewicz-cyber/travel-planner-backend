# Swagger Test Payloads - Tag Preferences

**Swagger UI:** http://localhost:8000/docs

**Endpoint:** `POST /plan/preview`

---

## 🌊 Test 1: Water Attractions Preference

```json
{
  "user": {
    "target_group": "family_kids",
    "budget_level": 2,
    "crowd_tolerance": 2,
    "preferences": ["water_attractions"],
    "travel_style": ["relaxed"],
    "intensity_level": 2
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Termy (thermal baths) powinny mieć wysokie score (+20 type + 15-75 tag bonuses)

---

## 🎈 Test 2: Kids Attractions Preference

```json
{
  "user": {
    "target_group": "family_kids",
    "budget_level": 2,
    "crowd_tolerance": 2,
    "preferences": ["attractions_for_kids"],
    "travel_style": ["relaxed"],
    "intensity_level": 2
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Iluzja Park, DINO PARK, Myszogród - kids POI with high scores

---

## 🏔️ Test 3: Multiple Preferences (Water + Kids)

```json
{
  "user": {
    "target_group": "family_kids",
    "budget_level": 2,
    "crowd_tolerance": 2,
    "preferences": ["water_attractions", "attractions_for_kids"],
    "travel_style": ["relaxed"],
    "intensity_level": 2
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Mix - Termy z aquatic_playground + pure kids attractions

---

## ⛷️ Test 4: Active Sport Preference

```json
{
  "user": {
    "target_group": "couples",
    "budget_level": 3,
    "crowd_tolerance": 2,
    "preferences": ["active_sport"],
    "travel_style": ["adventurous"],
    "intensity_level": 3
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Kasprowy Wierch, skiing, mountain trails with high scores

---

## 🏛️ Test 5: Museums & Heritage Preference

```json
{
  "user": {
    "target_group": "couples",
    "budget_level": 2,
    "crowd_tolerance": 1,
    "preferences": ["museums_heritage"],
    "travel_style": ["cultural"],
    "intensity_level": 1
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Muzeum Tatrzańskie, Muzeum Oscypka, cultural POI prioritized

---

## ✅ Test 6: No Preferences (Backward Compat)

```json
{
  "user": {
    "target_group": "family_kids",
    "budget_level": 2,
    "crowd_tolerance": 2,
    "preferences": [],
    "travel_style": ["relaxed"],
    "intensity_level": 2
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Normal plan without tag bonuses - backward compatible

---

## 🌿 Test 7: Nature & Landscapes Preference

```json
{
  "user": {
    "target_group": "friends",
    "budget_level": 2,
    "crowd_tolerance": 2,
    "preferences": ["nature_landscapes"],
    "travel_style": ["relaxed"],
    "intensity_level": 2
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Morskie Oko, Dolina Chochołowska, mountain viewpoints

---

## 💆 Test 8: Relax & Wellness Preference

```json
{
  "user": {
    "target_group": "couples",
    "budget_level": 3,
    "crowd_tolerance": 1,
    "preferences": ["relax_wellness"],
    "travel_style": ["relaxed"],
    "intensity_level": 1
  },
  "trip": {
    "destination": "zakopane",
    "start_date": "2026-02-05",
    "end_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "18:00"
  }
}
```

**Expected:** Termy with spa/wellness tags, relaxation pools prioritized

---

## 📋 How to Test in Swagger

1. **Open Swagger UI:** http://localhost:8000/docs
2. **Find endpoint:** `POST /plan/preview`
3. **Click "Try it out"**
4. **Paste JSON** from above
5. **Click "Execute"**
6. **Check response:**
   - Look for POI names matching preference
   - Check `plan[].name` for expected attractions
   - Verify plan contains preference-matched POI

---

## 🔍 What to Look For

### With `water_attractions`:
- ✅ Termy Zakopańskie
- ✅ Chochołowskie Termy
- ✅ Termy Gorący Potok
- ✅ Terma Bania
- ✅ Termy Bukovina

### With `attractions_for_kids`:
- ✅ Iluzja Park
- ✅ DINO PARK
- ✅ Myszogród
- ✅ Papugarnia Egzotyczne
- ✅ Tatrzańskie Mini Zoo

### With `active_sport`:
- ✅ Kasprowy Wierch (skiing tags)
- ✅ Mountain trails POI
- ✅ Wielka Krokiew

### With `museums_heritage`:
- ✅ Muzeum Tatrzańskie
- ✅ Muzeum Oscypka
- ✅ Muzeum Kornela Makuszyńskiego

---

## 🎯 Success Criteria

✅ **Plan generated successfully** (status 200)
✅ **Preference-matched POI appear in plan**
✅ **Tag bonus visible in backend logs** (if debug enabled)
✅ **Backward compatible** (empty preferences works)
✅ **No errors or crashes**

---

**Commit deployed:** fc6d1a5
**System ready:** Tag-based preference scoring ✅
