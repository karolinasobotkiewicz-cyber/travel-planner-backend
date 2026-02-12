# ETAP 2 - Dzień 1: PostgreSQL Setup - RAPORT PROBLEMÓW

## ✅ CO ZOSTAŁO WYKONANE

### 1. Zależności i Struktura (100% ✅)
- ✅ Zainstalowano SQLAlchemy 2.0.25, psycopg2-binary 2.9.9, alembic 1.13.1
- ✅ Utworzono moduł `app/infrastructure/database/`
- ✅ Zaimplementowano connection.py (SQLAlchemy engine + session factory)
- ✅ Zaimplementowano models.py (Plan + PlanVersion ORM models)
- ✅ Skonfigurowano Alembic (init + env.py z dotenv support)

### 2. Database Models (100% ✅)
**Plan table:**
- UUID primary key
- location, group_type, days_count, budget_level
- created_at, updated_at (auto-timestamps)
- trip_metadata (JSON - flexible metadata storage)

**PlanVersion table:**
- UUID primary key
- plan_id (FK do Plan, CASCADE delete)
- version_number (unique per plan)
- created_at, change_type (initial/regenerated/edited/rollback)
- parent_version_id (self-referential FK dla version tree)
- days_json (full snapshot każdej wersji)
- change_summary (opis zmian)
- UniqueConstraint(plan_id, version_number)

### 3. Alembic Migration (95% ✅)
- ✅ Utworzono migration file: `360e3cae0377_initial_schema_plans_and_plan_versions_.py`
- ✅ Wygenerowano SQL CREATE TABLE statements
- ⚠️ **NIE WYKONANO** na bazie (problem połączenia - zobacz sekcję Problemy)

### 4. Naprawione Błędy
1. ✅ `DATABASE_URL not found` → Dodano load_dotenv() do alembic/env.py
2. ✅ `metadata is reserved keyword` → Renamed do trip_metadata
3. ✅ `__table_args__ must be tuple` → Poprawiono syntax z class na tuple
4. ✅ `ConfigParser interpolation error` → Zmieniono env.py aby nie używać set_main_option()

---

## ❌ PROBLEM: Brak połączenia IPv6 z Supabase

### Diagnoza
```
psycopg2.OperationalError: could not translate host name 
"db.usztzcigcnsyyatguxay.supabase.co" to address
```

**Przyczyna:** 
- Supabase Direct Connection (port 5432) używa **tylko IPv6**
- System Windows użytkownika: **brak działającej łączności IPv6**
- DNS resolving działa (nslookup zwraca IPv6), ale połączenie TCP fails: "Network is unreachable"

### Próby Rozwiązania
1. ❌ Direct connection (db.usztzcigcnsyyatguxay.supabase.co:5432) - tylko IPv6
2. ❌ IPv6 bezpośrednio (2a05:d018:135e:16a5:1df9:b3c6:694:ba97) - "Network unreachable"
3. ❌ Pooler connection (aws-0-eu-central-1.pooler.supabase.com:6543) - "Tenant not found"
4. ✅ **Workaround: Ręczne wykonanie SQL w Supabase SQL Editor**

---

## 🔧 ROZWIĄZANIE: Ręczna Migracja

### KRO KI DO WYKONANIA PRZEZ KLIENTKĘ/UŻYTKOWNIKA:

1. **Zaloguj się do Supabase Dashboard**
   - Adres: https://supabase.com/dashboard
   - Email: karolina.sobotkiewicz@gmail.com
   - Password: @ManTrav!97

2. **Otwórz SQL Editor**
   - W menu left sidebar kliknij "SQL Editor"
   - Kliknij "+ New query"

3. **Skopiuj i Wykonaj SQL**
   - Otwórz plik: `migration_manual.sql` (w głównym folderze projektu)
   - Zaznacz CAŁĄ zawartość i skopiuj (Ctrl+A, Ctrl+C)
   - Wklej do SQL Editor w Supabase (Ctrl+V)
   - Kliknij "Run" (lub Ctrl+Enter)

4. **Weryfikacja**
   Po wykonaniu SQL powinny być widoczne 3 tabele:
   - ✅ `alembic_version` (migration tracking)
   - ✅ `plans` (trip metadata)
   - ✅ `plan_versions` (version history)

   Możesz zweryfikować w Dashboard → Table Editor → powinny być widoczne te tabele.

---

## 🚀 ALTERNATYWNE ROZWIĄZANIE (jeśli manual nie działa)

### Opcja A: Connection Pooling (Transaction Mode) - **ZALECANE**

1. W Supabase Dashboard → Project Settings → Database → Connection String
2. Zmień mode z "Session" na "Transaction"
3. Skopiuj nowy connection string (powinien mieć port 6543)
4. Format powinien być:`postgresql://postgres.usztzcigcnsyyatguxay:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`
5. Zaktualizuj `.env` file z nowym connection string
6. **PRZETESTUJ:** `python -c "from app.infrastructure.database import test_connection; test_connection()"`

### Opcja B: IPv6 przez VPN/Proxy
Użyj VPN który wspiera IPv6 (np. Cloudflare WARP, Tailscale)

### Opcja C: Praca na innym komputerze
Użyj komputera z działającym IPv6 (większość nowoczesnych systemów/sieci)

---

## 📝 NASTĘPNE KROKI (po rozwiązaniu problemu połączenia)

### 1. Weryfikacja Lokalnie
```bash
python -c "from app.infrastructure.database import test_connection; test_connection()"
```
Oczekiwany output: `✅ Database connection OK`

### 2. Dodanie DATABASE_URL do Render
- Render Dashboard → travel-planner-backend → Environment
- Add Environment Variable:
  - Key: `DATABASE_URL`
  - Value: (connection string z .env file)
- Save → triggers auto-redeploy

### 3. Test Produkcyjny
```bash
curl https://travel-planner-backend.onrender.com/health
```
Oczekiwany output: `{"status": "ok", "database": "connected"}`

### 4. Kontynuacja Day 1 Tasks
- Repository Migration (PostgreSQL implementation)
- Multi-day Planning Core (plan_multiple_days function)
- Versioning System (PlanVersionRepository)
- Quality + Explainability modules

---

## 🔐 SECURITY CHECKLIST

- ✅ DATABASE_URL w .env (gitignored)
- ✅ Password URL-encoded (%40 = @, %21 = !)
- ✅ Brak hardcoded credentials w kodzie
- ✅ .env w .gitignore (line 48)
- ⚠️ **TODO:** Dodaj migration.sql i migration_manual.sql do .gitignore (lub usuń po wykonaniu)

---

## 📊 PROGRESS TRACKING - Dzień 1 (22 dni razem)

- [x] **PostgreSQL Setup (60%)**: Models ✅, Migration ✅, Connection ⚠️
- [ ] **Repository Migration (0%)**: PostgreSQL implementation z Plan/PlanVersion
- [ ] **Multi-day Planning Core (0%)**: plan_multiple_days() function
- [ ] **Versioning System (0%)**: save/list/get/rollback methods
- [ ] **Quality + Explainability (0%)**: quality_checker.py + explainability.py

**Estimated Time to Complete Day 1:** 
- Z manual SQL (jeśli klientka wykonała): ~2-3 godziny
- Z rozwiązaniem pooler connection: ~4-5 godzin

---

## 💡 LESSONS LEARNED

1. **IPv6 nie jest uniwersalne**: Zawsze testować połączenia na target environment
2. **Supabase pooler require specific format**: `postgres.{project_ref}` jako username
3. **ConfigParser ma issues z URL-encoded strings**: Używać create_engine() bezpośrednio
4. **SQLAlchemy reserved keywords**: metadata, query, etc. - unikać w nazwach kolumn
5. **Windows DNS może nie wspierać IPv6**: Nawet gdy nslookup działa, psycopg2 może failować

---

## 📞 SUPPORT

Jeśli po manual SQL execution nadal są problemy:
1. Screenshot Supabase SQL Editor z error message
2. Screenshot Table Editor (czy tabele są widoczne?)
3. Output z: `python -c "from app.infrastructure.database import test_connection; test_connection()"`
