"""
Time of day scoring module.

Rewards POI that are visited at their recommended time of day.

Changelog
---------
BUGFIX  (31.01.2026 – Problem #6): Stronger enforcement; afternoon/midday no longer compatible.
FIX #5  (02.02.2026): Evening/night distinction; KULIGI-type POI penalised during day.
FIX #91 (28.05.2026): Winter outdoor dark penalty (15:00 + 14:30 thresholds).
FIX #122(30.05.2026): Multi-value recommended_time_of_day parsing + tiered evening fallback.

  Key changes in FIX #122
  ~~~~~~~~~~~~~~~~~~~~~~~~
  1. Multi-value parsing
     recommended_time_of_day is now parsed as a **frozenset** before comparison.
     "afternoon, evening" → {"afternoon", "evening"} → correctly matches either period.
     Previously the whole string was compared with ==, so "afternoon, evening" would NEVER
     match "evening" — causing a permanent mismatch even for well-tagged POI.

  2. Tiered evening fallback
     When a city has few dedicated evening POI ("evening_scarcity" context flag), the engine
     would previously produce broken or empty evening slots because every non-evening POI
     received a blanket -30 penalty.
     The new system uses graduated penalties that depend on:
       a) Which period the POI was designed for (afternoon is more forgiving than morning).
       b) How deep into the evening the slot is (18:00–18:30 < 18:30–19:30 < 19:30+).
       c) Whether evening_scarcity is True (inject from engine.py after counting pool).

  Hard rules that are UNCHANGED
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • "evening" / "night" POI during daytime → -50 (kulig without darkness is pointless).
  • "morning" / "early_morning" POI in late evening → still strongly penalised.
  • Winter outdoor dark penalty (FIX #91) applied on top of all other scores.
"""

# ---------------------------------------------------------------------------
# Period time boundaries (minutes from midnight)
# ---------------------------------------------------------------------------
_EARLY_MORNING_END = 600    # 10:00
_MORNING_END       = 720    # 12:00
_MIDDAY_END        = 900    # 15:00
_AFTERNOON_END     = 1080   # 18:00
_EVENING_END       = 1200   # 20:00

# Evening sub-zones (FIX #122)
_EARLY_EVE_END = 1110   # 18:30 — "early evening":  afternoon POI still quite acceptable
_MID_EVE_END   = 1170   # 19:30 — "mid evening":    afternoon POI soft penalty


def time_to_period(time_str) -> str:
    """
    Convert time string or minutes to a named period of the day.

    FIX #5 (02.02.2026): Added evening/night distinction.
      - evening : 18:00–20:00  (dusk, twilight)
      - night   : 20:00+       (after dark)

    Args:
        time_str: "HH:MM" string  OR  integer / float minutes from midnight.

    Returns:
        str: One of "early_morning", "morning", "midday",
             "afternoon", "evening", "night".
    """
    if isinstance(time_str, str):
        h, m = map(int, time_str.split(":"))
        minutes = h * 60 + m
    else:
        minutes = int(time_str)

    if minutes < _EARLY_MORNING_END:
        return "early_morning"
    elif minutes < _MORNING_END:
        return "morning"
    elif minutes < _MIDDAY_END:
        return "midday"
    elif minutes < _AFTERNOON_END:
        return "afternoon"
    elif minutes < _EVENING_END:
        return "evening"
    else:
        return "night"


def _parse_recommended(raw) -> frozenset:
    """
    Parse the recommended_time_of_day field into a frozenset of period names.

    FIX #122: Handles both single-value and multi-value strings.
      "evening"                          → frozenset({"evening"})
      "afternoon, evening"               → frozenset({"afternoon", "evening"})
      "morning+midday+afternoon"         → frozenset({"morning", "midday", "afternoon"})
      "morning, midday, afternoon"       → frozenset({"morning", "midday", "afternoon"})

    Accepts comma (,) and plus (+) as separators — both appear in the data.
    """
    if not raw:
        return frozenset()
    normalized = str(raw).replace("+", ",")
    return frozenset(p.strip().lower() for p in normalized.split(",") if p.strip())


def calculate_time_of_day_score(poi, user, context, current_time_minutes: int) -> float:
    """
    Score a POI based on how well its recommended_time_of_day matches the current slot.

    Args:
        poi:                  POI dict.  Key field: "recommended_time_of_day".
        user:                 User dict  (reserved for future use).
        context:              Context dict.  Relevant keys:
                                "season"           → enables winter outdoor penalty (FIX #91)
                                "evening_scarcity" → bool; True when the day's POI pool
                                                     contains fewer than N evening POI.
                                                     Injected by engine.py (FIX #122).
        current_time_minutes: Slot start time in minutes from midnight.

    Returns:
        float: Score adjustment.  Positive = bonus, negative = penalty.
    """
    ctx = context if isinstance(context, dict) else {}

    # ------------------------------------------------------------------
    # 1. Parse recommended periods (FIX #122: set-based, not string ==)
    # ------------------------------------------------------------------
    recommended = _parse_recommended(poi.get("recommended_time_of_day", ""))

    if not recommended:
        return 0.0   # No preference — neutral for any time

    current_period = time_to_period(current_time_minutes)

    # ------------------------------------------------------------------
    # 2. Exact match → strong bonus
    # ------------------------------------------------------------------
    if current_period in recommended:
        score = 15.0

    # ------------------------------------------------------------------
    # 3. Adjacent / compatible pairs → smaller bonus
    #    morning ↔ early_morning   (+5)
    #    evening ↔ night           (+10, both "after dark")
    # ------------------------------------------------------------------
    elif _is_adjacent(current_period, recommended):
        score = _adjacent_bonus(current_period, recommended)

    # ------------------------------------------------------------------
    # 4. Evening/night slot but POI has no evening period (FIX #122 core)
    #    Tiered penalty based on how late it is and whether city has
    #    evening_scarcity (few dedicated evening POI in the pool).
    # ------------------------------------------------------------------
    elif current_period in ("evening", "night"):
        score = _evening_mismatch_penalty(
            recommended=recommended,
            current_time_minutes=current_time_minutes,
            evening_scarcity=ctx.get("evening_scarcity", False),
        )

    # ------------------------------------------------------------------
    # 5. Daytime slot for an evening/night POI, or other mismatches
    # ------------------------------------------------------------------
    else:
        score = _daytime_mismatch_penalty(recommended, current_period)

    # ------------------------------------------------------------------
    # 6. Winter outdoor dark penalty (FIX #91 — unchanged behaviour)
    #    In winter it gets dark ~15:00 in mountains; outdoor/trail POI
    #    scheduled past 14:30 are dangerous / unpleasant.
    # ------------------------------------------------------------------
    if ctx.get("season") == "winter":
        poi_space = str(poi.get("space", "") or "").lower()
        if poi.get("type") == "trail" or poi_space == "outdoor":
            if current_time_minutes >= 900:    # 15:00+ → dark
                score -= 50.0
            elif current_time_minutes >= 870:  # 14:30 → last light
                score -= 25.0

    return score


# ---------------------------------------------------------------------------
# Internal helpers (not part of public API)
# ---------------------------------------------------------------------------

_ADJACENT_MAP = {
    "early_morning": frozenset({"morning"}),
    "morning":       frozenset({"early_morning"}),
    "evening":       frozenset({"night"}),
    "night":         frozenset({"evening"}),
}


def _is_adjacent(current_period: str, recommended: frozenset) -> bool:
    """Return True if current_period is an accepted near-match for any recommended period."""
    return bool(_ADJACENT_MAP.get(current_period, frozenset()) & recommended)


def _adjacent_bonus(current_period: str, recommended: frozenset) -> float:
    """Score bonus for near-match compatible period pairs."""
    # evening ↔ night: both "after dark" — high compatibility
    if current_period in ("evening", "night") and bool({"evening", "night"} & recommended):
        return 10.0
    # morning ↔ early_morning: neighbours
    return 5.0


def _evening_mismatch_penalty(
    recommended: frozenset,
    current_time_minutes: int,
    evening_scarcity: bool,
) -> float:
    """
    Penalty for a non-evening POI scheduled during an evening/night slot.

    FIX #122 design
    ~~~~~~~~~~~~~~~
    Three time sub-zones:
      Early   18:00–18:30  → afternoon POI are still very reasonable (terraces, sunset walks).
      Mid     18:30–19:30  → light penalty; afternoon POI feel slightly off.
      Late    19:30+       → genuine evening expected; stronger penalty for day-time POI.

    evening_scarcity=True relaxes every tier by ~10 points so that cities with
    0–2 dedicated evening POI (Warszawa, Jelenia Góra, Kudowa-Zdrój, …) can still
    fill evening slots with their best available afternoon/midday attractions rather
    than producing an empty or broken schedule.

    Hard rules (NEVER relaxed)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    • morning / early_morning only POI at late evening → heavy penalty (-40 to -50).
      A "morning market" or "sunrise viewpoint" is wrong at 20:00 regardless of scarcity.
    • evening / night POI that somehow land here → return +15 (shouldn't happen, defensive).

    Penalty tables  (normal, scarcity)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Afternoon POI:
      early    →  -5,   0
      mid      → -15,  -5
      late     → -22, -10

    Midday POI:
      early    → -15,  -5
      mid      → -25, -12
      late     → -35, -18

    Morning / early_morning only:
      early    → -40, -30
      mid      → -45, -35
      late     → -50, -40
    """
    # Defensive: POI IS evening/night — shouldn't reach here, but safe-guard
    if "evening" in recommended or "night" in recommended:
        return 15.0

    # Determine sub-zone
    if current_time_minutes < _EARLY_EVE_END:      # 18:00–18:30
        sub = "early"
    elif current_time_minutes < _MID_EVE_END:      # 18:30–19:30
        sub = "mid"
    else:                                           # 19:30+
        sub = "late"

    # --- Afternoon POI at evening ---
    if "afternoon" in recommended:
        table = {
            "early": (-5.0,   0.0),
            "mid":   (-15.0, -5.0),
            "late":  (-22.0, -10.0),
        }
        normal, scarcity_val = table[sub]
        return scarcity_val if evening_scarcity else normal

    # --- Midday POI at evening ---
    if "midday" in recommended:
        table = {
            "early": (-15.0, -5.0),
            "mid":   (-25.0, -12.0),
            "late":  (-35.0, -18.0),
        }
        normal, scarcity_val = table[sub]
        return scarcity_val if evening_scarcity else normal

    # --- Morning / early_morning only POI at evening ---
    if recommended <= {"morning", "early_morning"}:
        table = {
            "early": (-40.0, -30.0),
            "mid":   (-45.0, -35.0),
            "late":  (-50.0, -40.0),
        }
        normal, scarcity_val = table[sub]
        return scarcity_val if evening_scarcity else normal

    # --- Catch-all for any other combination ---
    base = -30.0
    return base + (10.0 if evening_scarcity else 0.0)


def _daytime_mismatch_penalty(recommended: frozenset, current_period: str) -> float:
    """
    Penalty when a POI designed for a specific daytime period is misscheduled.

    Also handles the critical FIX #5 case: evening/night POI during day → -50
    (ruins the experience — kulig without darkness, fountain light show at noon).
    """
    # Evening / night POI during the day — ruins the experience (FIX #5 unchanged)
    if "evening" in recommended or "night" in recommended:
        return -50.0

    # Midday ↔ afternoon crossover (BUGFIX 31.01.2026, Problem #6: was +3, now -15)
    if ("midday" in recommended and current_period == "afternoon") or \
       ("afternoon" in recommended and current_period == "midday"):
        return -15.0

    # Afternoon at morning / early_morning — too early in the day
    if "afternoon" in recommended and current_period in ("morning", "early_morning"):
        return -30.0

    # Morning / early_morning at afternoon — slot too late
    if bool({"morning", "early_morning"} & recommended) and current_period == "afternoon":
        return -30.0

    return 0.0
