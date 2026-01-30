# 🧪 PLAN TESTÓW KOMPLETNY - ETAP 1

**Data utworzenia:** 26.01.2026  
**Cel:** 80%+ coverage + pełna walidacja funkcjonalności  
**Status:** 📋 DO WYKONANIA

================================================================================

## 📊 OBECNY STAN TESTÓW

### Istniejące testy (16 testów):
1. **test_api_part1.py** - 7 testów API endpoints ✅
2. **test_repositories_part2.py** - 3 testy repositories ✅
3. **test_business_logic_part3.py** - 2 testy business logic ✅
4. **test_content_images_part4.py** - 4 testy content & images ✅
5. **tests/unit/domain/test_scoring.py** - 22 testy scoring modules ✅
6. **tests/unit/domain/test_time_utils.py** - ??? testy (do sprawdzenia)

**TOTAL:** 38+ testów już istniejących

### Lukі do wypełnienia:
- ❌ Integration tests (end-to-end scenarios)
- ❌ PlanService unit tests (isolated)
- ❌ Engine tests (isolated z mockami)
- ❌ Error handling tests
- ❌ Edge cases (boundary conditions)
- ❌ Validation tests (Pydantic models)
- ❌ Configuration tests
- ❌ Graceful degradation tests

================================================================================

## 🎯 STRATEGIA TESTOWANIA

### 1. UNIT TESTS (izolowane komponenty)
**Cel:** Test każdej funkcji/metody w izolacji z mockami

#### 1.1 PlanService Tests
- `test_generate_plan_success` - happy path
- `test_generate_plan_empty_pois` - brak POI
- `test_generate_plan_invalid_dates` - złe daty
- `test_generate_parking_item_car_mode` - parking dla car
- `test_generate_parking_item_walk_mode` - brak parkingu dla walk
- `test_estimate_cost_family_kids` - koszt dla rodziny (2×normal + 2×reduced)
- `test_estimate_cost_free_entry` - darmowe wejście
- `test_estimate_cost_solo` - baseline dla solo
- `test_generate_attraction_item_with_all_fields` - pełna atrakcja
- `test_convert_engine_result_all_item_types` - wszystkie 7 typów
- `test_convert_engine_result_lunch_always_present` - 🚨 CRITICAL: lunch ZAWSZE
- `test_convert_engine_result_no_lunch_from_engine` - wymuszenie lunchu

#### 1.2 Engine Tests (domain/planner/engine.py)
- `test_build_day_basic` - prosty dzień
- `test_build_day_no_pois` - brak POI → empty schedule
- `test_build_day_family_kids` - energia 90, limity
- `test_build_day_seniors` - energia 55, mniejsze limity
- `test_attraction_item_structure` - czy zawiera "poi" key
- `test_lunch_break_timing` - lunch między 12:00-14:30
- `test_transfer_items_generation` - transit między POI
- `test_scoring_integration` - czy używa scoring modules

#### 1.3 Repository Tests (rozszerzenie istniejących)
- `test_poi_repository_excel_loading_success` - załaduj zakopane.xlsx
- `test_poi_repository_excel_missing_graceful_fallback` - mock gdy brak
- `test_poi_repository_cache_persistence` - czy cache działa
- `test_plan_repository_concurrent_saves` - wiele planów równocześnie
- `test_destinations_repository_json_invalid` - złe JSON

#### 1.4 Model Validation Tests
- `test_trip_input_validation_success` - prawidłowy TripInput
- `test_trip_input_validation_missing_fields` - brakujące pola
- `test_trip_input_validation_invalid_dates` - złe daty
- `test_trip_input_validation_negative_budget` - ujemny budget
- `test_plan_response_serialization` - JSON serialization
- `test_poi_model_image_key_field` - nowe pole image_key
- `test_lunch_break_item_duration` - duration_min = 90

#### 1.5 Scoring Tests (rozszerzenie)
- Już są w test_scoring.py (22 testy) ✅
- TODO: Dodać edge cases jeśli brakuje

#### 1.6 Time Utils Tests
- Sprawdzić test_time_utils.py co już jest ✅
- Dodać edge cases jeśli brakuje

### 2. INTEGRATION TESTS (komponenty współpracują)
**Cel:** Test współpracy komponentów bez mocków (lub minimalnych)

#### 2.1 Full Flow Tests
- `test_full_plan_generation_family_kids_car` - pełny flow z car
- `test_full_plan_generation_couple_walk` - pełny flow z walk
- `test_full_plan_generation_solo_public_transport` - public transport
- `test_full_plan_generation_with_real_zakopane_data` - z zakopane.xlsx

#### 2.2 API Integration Tests
- `test_preview_then_payment_then_retrieve` - cały lifecycle planu
- `test_concurrent_plan_previews` - wiele równocześnie
- `test_content_home_with_poi_details` - GET home → GET poi/{id}

#### 2.3 Repository Integration Tests
- `test_plan_save_and_retrieve_full_cycle` - zapis → odczyt → update
- `test_poi_repository_with_destinations` - POI + destinations razem

### 3. ERROR HANDLING TESTS
**Cel:** Sprawdź czy aplikacja gracefully obsługuje błędy

#### 3.1 API Error Tests
- `test_plan_preview_invalid_json` - złe JSON body
- `test_plan_preview_missing_required_fields` - brakujące pola
- `test_get_plan_nonexistent_id` - 404 dla nieistniejącego ID
- `test_payment_webhook_invalid_event` - złe event type
- `test_poi_details_invalid_id` - 404 dla nieistniejącego POI

#### 3.2 Service Error Tests
- `test_plan_service_engine_exception` - engine throws error
- `test_plan_service_repository_exception` - repository throws error
- `test_plan_service_invalid_user_data` - validation error

#### 3.3 Repository Error Tests
- `test_poi_repository_excel_corrupted` - skorumpowany Excel
- `test_destinations_repository_json_corrupted` - skorumpowany JSON

### 4. EDGE CASES & BOUNDARY TESTS
**Cel:** Test przypadków brzegowych

#### 4.1 Time Window Tests
- `test_day_start_equals_day_end` - start = end (edge case)
- `test_day_window_too_short` - < 2h (nie zmieści się nic)
- `test_lunch_at_day_start` - lunch = 09:00 (before 12:00)
- `test_lunch_at_day_end` - lunch = 18:00 (after 14:30)

#### 4.2 Group Size Tests
- `test_group_size_1` - solo (minimum)
- `test_group_size_100` - bardzo duża grupa (edge case)
- `test_children_age_0` - niemowlę
- `test_children_age_18` - już dorosły

#### 4.3 Budget Tests
- `test_budget_level_0` - darmowe
- `test_budget_level_5` - premium
- `test_all_free_entry_pois` - wszystkie POI darmowe

#### 4.4 POI Tests
- `test_single_poi_available` - tylko 1 POI
- `test_no_pois_available` - 0 POI → empty schedule
- `test_poi_without_parking` - POI bez parking_name

#### 4.5 Transport Tests
- `test_multiple_transport_modes` - ["car", "walk", "public_transport"]
- `test_no_transport_modes` - pusta lista
- `test_invalid_transport_mode` - "bicycle" (not supported)

### 5. PERFORMANCE TESTS
**Cel:** Sprawdź czy spełnia KPI (< 2s response, < 5s engine)

#### 5.1 Response Time Tests
- `test_plan_preview_response_time_under_2s` - API < 2s
- `test_engine_execution_time_under_5s` - engine < 5s
- `test_concurrent_requests_no_degradation` - 10 równoczesnych

#### 5.2 Resource Tests
- `test_poi_cache_memory_efficient` - cache nie zajmuje > 100MB
- `test_plan_repository_handles_100_plans` - 100 planów w pamięci

### 6. REGRESSION TESTS
**Cel:** Upewnij się że fixe nie zepsuły niczego

#### 6.1 Critical Fix Tests
- `test_lunch_break_always_present_short_day` - 🚨 1 atrakcja → lunch ✅
- `test_lunch_break_always_present_long_day` - 5 atrakcji → lunch ✅
- `test_lunch_break_always_12_00_to_13_30` - dokładne godziny
- `test_lunch_break_duration_90_minutes` - duration_min = 90

================================================================================

## 📁 STRUKTURA PLIKÓW TESTOWYCH

### Nowa struktura tests/:
```
tests/
├── conftest.py (fixtures + config)
├── unit/
│   ├── domain/
│   │   ├── test_scoring.py ✅ (22 tests)
│   │   ├── test_time_utils.py ✅ (check count)
│   │   └── test_engine.py ❌ NEW (12 tests)
│   ├── application/
│   │   └── test_plan_service.py ❌ NEW (15 tests)
│   ├── infrastructure/
│   │   ├── test_poi_repository_extended.py ❌ NEW (8 tests)
│   │   ├── test_plan_repository_extended.py ❌ NEW (6 tests)
│   │   └── test_destinations_repository_extended.py ❌ NEW (4 tests)
│   └── api/
│       ├── test_models_validation.py ❌ NEW (10 tests)
│       └── test_error_handling.py ❌ NEW (8 tests)
├── integration/
│   ├── test_full_flow.py ❌ NEW (4 tests)
│   ├── test_api_integration.py ❌ NEW (3 tests)
│   └── test_with_real_data.py ❌ NEW (2 tests)
├── edge_cases/
│   ├── test_time_boundaries.py ❌ NEW (4 tests)
│   ├── test_group_boundaries.py ❌ NEW (4 tests)
│   ├── test_budget_boundaries.py ❌ NEW (3 tests)
│   └── test_transport_edge_cases.py ❌ NEW (3 tests)
└── regression/
    └── test_critical_fixes.py ❌ NEW (4 tests)

Root (dla compatibility):
├── test_api_part1.py ✅ (7 tests)
├── test_repositories_part2.py ✅ (3 tests)
├── test_business_logic_part3.py ✅ (2 tests)
└── test_content_images_part4.py ✅ (4 tests)
```

### Nowe pliki do utworzenia:
1. `tests/unit/domain/test_engine.py` - 12 testów
2. `tests/unit/application/test_plan_service.py` - 15 testów
3. `tests/unit/infrastructure/test_poi_repository_extended.py` - 8 testów
4. `tests/unit/infrastructure/test_plan_repository_extended.py` - 6 testów
5. `tests/unit/infrastructure/test_destinations_repository_extended.py` - 4 testy
6. `tests/unit/api/test_models_validation.py` - 10 testów
7. `tests/unit/api/test_error_handling.py` - 8 testów
8. `tests/integration/test_full_flow.py` - 4 testy
9. `tests/integration/test_api_integration.py` - 3 testy
10. `tests/integration/test_with_real_data.py` - 2 testy
11. `tests/edge_cases/test_time_boundaries.py` - 4 testy
12. `tests/edge_cases/test_group_boundaries.py` - 4 testy
13. `tests/edge_cases/test_budget_boundaries.py` - 3 testy
14. `tests/edge_cases/test_transport_edge_cases.py` - 3 testy
15. `tests/regression/test_critical_fixes.py` - 4 testy

**TOTAL NEW:** 90 nowych testów

================================================================================

## 📊 SZACOWANY COVERAGE

### Obecny coverage (estymacja):
- API routes: ~70% (7 endpoint tests)
- Repositories: ~60% (3 basic tests)
- Business logic: ~40% (2 integration tests)
- Domain (scoring): ~90% (22 tests) ✅
- Models: ~30% (basic usage only)

**Estimated TOTAL:** ~55%

### Po dodaniu nowych testów:
- API routes: ~95% (+ error handling, validation)
- Repositories: ~90% (+ extended tests, edge cases)
- Business logic: ~95% (+ unit tests PlanService)
- Domain (engine): ~85% (+ isolated engine tests)
- Domain (scoring): ~90% (unchanged) ✅
- Models: ~85% (+ validation tests)

**Expected TOTAL:** ~90%+ ✅

================================================================================

## ⏰ HARMONOGRAM WYKONANIA

### Faza 1: Unit Tests (3h)
1. test_plan_service.py (15 tests) - 1h
2. test_engine.py (12 tests) - 1h
3. test_models_validation.py (10 tests) - 30min
4. test_*_extended.py repositories (18 tests) - 30min

### Faza 2: Integration Tests (2h)
5. test_full_flow.py (4 tests) - 45min
6. test_api_integration.py (3 tests) - 30min
7. test_with_real_data.py (2 tests) - 45min

### Faza 3: Edge Cases (1.5h)
8. test_time_boundaries.py (4 tests) - 20min
9. test_group_boundaries.py (4 tests) - 20min
10. test_budget_boundaries.py (3 tests) - 20min
11. test_transport_edge_cases.py (3 tests) - 20min
12. test_error_handling.py (8 tests) - 10min

### Faza 4: Regression (30min)
13. test_critical_fixes.py (4 tests) - 30min

### Faza 5: Coverage Report (30min)
14. pytest --cov=app --cov-report=html
15. Analiza report, fix lukі jeśli < 80%
16. Final run wszystkich testów

**TOTAL CZAS:** 7h 30min

================================================================================

## 🎯 KRYTERIA SUKCESU

### Must-Have:
- ✅ Coverage ≥ 80% (all modules)
- ✅ Wszystkie testy GREEN
- ✅ Lunch break regression tests PASS (critical fix)
- ✅ Integration tests z real data PASS
- ✅ Error handling tests PASS (graceful degradation)

### Nice-to-Have:
- 🎁 Coverage ≥ 90%
- 🎁 Performance tests < 2s API, < 5s engine
- 🎁 pytest.ini configuration
- 🎁 Coverage badge w README

================================================================================

## ❓ PYTANIA DO KLIENTKI (przed rozpoczęciem)

### 1. Priorytet testów:
**Pytanie:** Które obszary są najważniejsze do przetestowania?
- [ ] A) PlanService (business logic) - KRYTYCZNE
- [ ] B) Engine (algorytm planowania) - KRYTYCZNE
- [ ] C) Repositories (persistence) - ŚREDNIE
- [ ] D) API routes (endpoints) - ŚREDNIE
- [ ] E) Models (validation) - NISKIE

**Rekomendacja:** Focus na A) i B) żeby osiągnąć 80%+ coverage szybko.

---

### 2. Real data testing:
**Pytanie:** Czy mogę używać zakopane.xlsx do testów integracyjnych?
- [ ] TAK - test z prawdziwymi danymi POI
- [ ] NIE - tylko mocki (szybsze, izolowane)

**Rekomendacja:** TAK - przynajmniej 1-2 testy z real data dla confidence.

---

### 3. Performance tests:
**Pytanie:** Czy performance tests są MUST w ETAP 1?
- [ ] TAK - sprawdź < 2s API, < 5s engine (KPI z planu)
- [ ] NIE - odłóż na ETAP 2 (monitoring produkcyjny)

**Rekomendacja:** TAK - proste performance tests (1-2), nie pełny load testing.

---

### 4. Lunch break tests:
**Pytanie:** Ile testów regression dla lunch_break fix?
- [ ] 2 testy (basic: short day, long day)
- [ ] 4 testy (extended: + timing, duration)
- [ ] 6+ testów (comprehensive: wszystkie edge cases)

**Rekomendacja:** 4 testy (extended) - pokrycie critical fix + validation.

---

### 5. Coverage target:
**Pytanie:** Jaki dokładny coverage target?
- [ ] 80% (plan minimum)
- [ ] 85% (comfortable)
- [ ] 90%+ (excellent)

**Rekomendacja:** 85% - balance jakość vs czas (90% = +2h extra).

================================================================================

## 📝 NOTATKI IMPLEMENTACYJNE

### Mock Strategy:
- **Unit tests:** Mocki dla wszystkich dependencies
- **Integration tests:** Minimalne mocki, prawdziwe komponenty
- **Real data tests:** 0 mocków, zakopane.xlsx

### Fixtures (conftest.py):
```python
@pytest.fixture
def mock_poi_repository():
    # Return repository z mock POI

@pytest.fixture
def sample_family_trip_input():
    # TripInput dla family_kids + car

@pytest.fixture
def sample_couple_trip_input():
    # TripInput dla couple + walk

@pytest.fixture
def real_zakopane_data():
    # Load zakopane.xlsx jeśli istnieje
```

### Assertions:
- **Strukturalne:** `assert 'plan_id' in response`
- **Wartościowe:** `assert lunch['start_time'] == '12:00'`
- **Typowe:** `assert isinstance(plan, PlanResponse)`
- **Biznesowe:** `assert len(parking_items) == 1  # car mode`

### Coverage Exclusions:
```python
# pragma: no cover
- __init__.py files (imports only)
- main.py startup code
- External API stubs (ETAP 1 mocks)
```

================================================================================

## 🚀 EXECUTION PLAN

### Krok 1: Przeczytaj istniejące testy (15min)
- Sprawdź test_time_utils.py ile testów
- Zrozum fixtures w conftest.py
- Identify luki w coverage

### Krok 2: Odpowiedz na 5 pytań klientki (5min)
- Przed rozpoczęciem implementacji
- Uzyskaj approval na prioritzation

### Krok 3: Implement Unit Tests (3h)
- Priorytet: PlanService, Engine, Models
- Run po każdej grupie: `pytest tests/unit/`

### Krok 4: Implement Integration Tests (2h)
- Full flow scenarios
- Run: `pytest tests/integration/`

### Krok 5: Implement Edge Cases (1.5h)
- Boundaries, error handling
- Run: `pytest tests/edge_cases/`

### Krok 6: Implement Regression (30min)
- Lunch break critical fix validation
- Run: `pytest tests/regression/`

### Krok 7: Coverage Report (30min)
- `pytest --cov=app --cov-report=html`
- Analyze gaps
- Add tests jeśli < 80%

### Krok 8: Final Validation (30min)
- Run ALL tests: `pytest`
- Verify: wszystkie GREEN
- Generate final report

### Krok 9: Documentation (30min)
- Update README (Testing section)
- Create RAPORT_TESTOW.md
- Update PLAN_DZIALANIA_ETAP1.md

**TOTAL:** 8h 30min

================================================================================

## 📄 DELIVERABLES

Po zakończeniu testów:

1. **90+ nowych testów** w tests/
2. **Coverage report HTML** (htmlcov/)
3. **RAPORT_TESTOW.md** - szczegółowy raport z wynikami
4. **pytest.ini** - configuration
5. **README.md updated** - Testing section
6. **PLAN_DZIALANIA_ETAP1.md updated** - DZIEŃ 5 część 1 completed

================================================================================

**PLAN UTWORZONY:** 26.01.2026 23:50  
**READY TO EXECUTE:** Czekam na odpowiedzi na 5 pytań  
**ESTIMATED COMPLETION:** 27.01.2026 08:00 (after 8.5h work)

================================================================================
