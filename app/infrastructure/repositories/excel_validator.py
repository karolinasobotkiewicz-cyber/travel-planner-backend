# type: ignore
"""
Excel Data Validator for Travel Planner (ETAP 3)

Automatically detects data quality issues in city Excel files before they
reach the engine. Prevents the need to debug city-by-city after import.

Issues detected (mirrors bugs fixed for Zakopane):
  - TAG MISMATCH (#94, #95): POI tags not present in tag_preferences.py
  - POLISH VALUES (#97): recommended_time_of_day in Polish instead of English
  - MUST_SEE missing (#96): Must see score column present but tag not injected
  - PRIORITY unknown: priority_level values not in {core, secondary, optional}
  - MISSING COORDINATES: Lat/Lng = 0 or NaN
  - MISSING NAME: Name column empty / NaN
  - TIME ANOMALY: time_min > time_max, or unreasonable values (>480 min)
  - POI COUNT WARNING: fewer than 20 POI → risky for multi-day plans
  - OPENING HOURS '{}'/'[]': string that looks like empty dict (FIX #75)
  - TARGET GROUP unknown: values not in known set

Usage (standalone - run from repo root):
    python -m app.infrastructure.repositories.excel_validator data/krakow.xlsx

Usage (from loader - call validate_excel() before processing):
    from app.infrastructure.repositories.excel_validator import validate_excel
    report = validate_excel("data/krakow.xlsx", city_name="Kraków")
    if report.has_errors:
        print(report.summary())
        # Optionally raise, or just log warnings
"""

from __future__ import annotations

import ast
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Known-good values (mirrors tag_preferences.py + normalizer.py)
# ──────────────────────────────────────────────────────────────────────────────

# All tags that appear in USER_PREFERENCES_TO_TAGS across ALL preferences.
# Kept here (not imported) so the validator has zero side-effects on engine code.
_KNOWN_TAGS: set = {
    # attractions_for_kids / kids_attractions
    "playground", "interactive_exhibition_kids", "petting_zoo", "farm_animals",
    "feeding_experience", "miniature_world", "fairytale_world", "illusion_kids",
    "aquatic_playground", "adventure_playground", "trampoline_park",
    "family_entertainment",
    # theme_parks
    "dinosaur_park", "adventure_park", "water_park", "rope_park",
    "interactive_exhibits", "amusement_rides",
    # active_sport
    "skiing", "snowboarding", "cross_country_skiing", "sledding", "ice_skating",
    "tubing", "climbing", "via_ferrata", "hiking", "mountain_trails",
    "alpine_activities", "zipline", "off_road",
    # museums_heritage / museum_heritage
    "local_history", "mountain_culture", "regional_heritage",
    "traditional_architecture", "ethnographic_museum", "themed_museum",
    "historical_mansion", "art_gallery", "interactive_museum",
    "educational_exhibition",
    # nature_landscapes / nature_landscape
    "mountain_viewpoint", "scenic_panorama", "natural_landscape", "waterfall",
    "alpine_valley", "mountain_lake", "botanical_garden", "nature_reserve",
    "gorge", "forest_trail",
    # FIX #94/#95 actual Excel tags
    "nature_immersion", "forest_trails", "meadows_fields", "mountain_views",
    "panoramic_mountain_views", "valley_landscape", "viewpoint_trail",
    "tatra_viewpoint",
    # mountain_trails (FIX #95)
    "easy_walk", "family_friendly_trail", "out_and_back", "moderate_hike",
    "stroller_friendly",
    # water_attractions / relax_wellness / relaxation
    "thermal_baths", "hot_springs", "aquapark_slides", "geothermal_pools",
    "spa_wellness", "relaxation_pools", "waterfall_pools", "year_round",
    "massage", "sauna", "jacuzzi", "wellness_center", "relax",
    # castles_palaces
    "medieval_castle", "castle_ruins", "fortification", "renaissance_architecture",
    "gothic_architecture", "royal_residence",
    # caves_mines
    "limestone_cave", "underground_tour", "salt_mine", "mining_heritage",
    "geological_formation", "spelunking", "underground_chapel",
    "crystal_formations",
    # must_see_only (FIX #96)
    "must_see",
    # local_food_experience (FIX #67)
    "local_cuisine", "regional_food", "traditional_restaurant", "bacówka",
    "bacowka", "highlander_cuisine", "food_tasting", "local_specialties",
    "mountain_food", "oscypek", "regional_dishes", "local_food",
    "regional_cuisine", "food_market", "street_food", "local_experience",
    "traditional_food",
    # history_mystery
    "legends", "folklore", "mystery", "hidden_gem", "secret_history",
    "unexplored", "discovery",
    # generic / shared
    "family_friendly", "seasonal_activity", "group_activity",
    "beginner_friendly", "adrenaline_experience", "horse_riding",
    "snow_tubing", "interactive_exhibition",
    # water-specific
    "water_slides", "sauna_zone", "relax_zone", "family_friendly_water",
    "thermal_relax_focus", "long_stay_possible", "evening_relax",
    # scenic / nature
    "easy_access_nature", "long_distance", "trailhead_parking",
    "viewpoint", "nature_walk", "lake_view", "river_view",
    # urban / cultural
    "city_center", "old_town", "market_square", "street_art",
    "architecture_walk", "jewish_quarter", "royal_route",
    # Trójmiasto-specific
    "beach", "seaside", "pier", "amber_museum", "shipyard_history",
    "naval_history", "maritime_museum", "gdansk_old_town",
    # Karkonosze-specific
    "karkonosze_trail", "karkonosze_viewpoint", "giant_mountains",
    "schneekoppe", "waterfall_karkonosze",
    # Kotlina Kłodzka-specific
    "healing_springs", "spa_town", "sanatorium", "paper_mill",
    "fortification_kłodzko",
    # Generic accessibility/time
    "wheelchair_accessible", "dog_friendly", "night_visit", "light_show",
}

_KNOWN_TOD_EN = {"morning", "midday", "afternoon", "evening", "night", "any", ""}
_TOD_POLISH = {
    "rano", "poranek", "południe", "poludnie", "popoludnie", "popołudnie",
    "wieczor", "wieczór", "noc",
}

_KNOWN_PRIORITY = {"core", "secondary", "optional", "high", "medium", "low"}

_KNOWN_TARGET_GROUPS = {
    "all", "family", "families", "family_kids", "couples", "solo", "seniors",
    "friends", "kids", "adults", "groups",
}


def _parse_tag_list(raw) -> List[str]:
    """Parse tags/groups from both 'tag1, tag2' and "['tag1', 'tag2']" formats."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    # Handle Python list literal: "['tag1', 'tag2']" or "[tag1, tag2]"
    if s.startswith("["):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return [str(t).strip().lower() for t in parsed if str(t).strip()]
        except (ValueError, SyntaxError):
            pass
    # Fallback: plain comma-separated
    return [t.strip().lower() for t in s.split(",") if t.strip()]

# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    level: str          # "ERROR" | "WARNING" | "INFO"
    row: Optional[int]  # 1-based Excel row, or None for file-level issues
    column: str
    message: str

    def __str__(self) -> str:
        loc = f"row {self.row}" if self.row else "file"
        return f"[{self.level}] {loc} | {self.column}: {self.message}"


@dataclass
class ValidationReport:
    city: str
    excel_path: str
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == "WARNING"]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def summary(self) -> str:
        lines = [
            f"╔══ Validation: {self.city} ({self.excel_path})",
            f"║  {len(self.errors)} ERROR(s), {len(self.warnings)} WARNING(s)",
        ]
        for issue in self.issues:
            lines.append(f"║  {issue}")
        lines.append("╚" + "═" * 60)
        return "\n".join(lines)

    def print_summary(self) -> None:
        print(self.summary())


# ──────────────────────────────────────────────────────────────────────────────
# Core validator
# ──────────────────────────────────────────────────────────────────────────────

def validate_excel(
    excel_path: str,
    city_name: str = "",
    sheet_name: str = 0,
    raise_on_error: bool = False,
) -> ValidationReport:
    """
    Validate a city Excel file and return a ValidationReport.

    Args:
        excel_path:     Path to the .xlsx file.
        city_name:      Human-readable city name for the report (optional).
        sheet_name:     Sheet to read (default: first sheet).
        raise_on_error: If True, raises ValueError when any ERROR-level issue found.

    Returns:
        ValidationReport with all detected issues.
    """
    path = Path(excel_path)
    city = city_name or path.stem
    report = ValidationReport(city=city, excel_path=str(excel_path))

    # ── Load file ────────────────────────────────────────────────────────────
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except FileNotFoundError:
        report.issues.append(ValidationIssue(
            "ERROR", None, "file", f"File not found: {excel_path}"
        ))
        return report
    except Exception as exc:
        report.issues.append(ValidationIssue(
            "ERROR", None, "file", f"Cannot read Excel: {exc}"
        ))
        return report

    # Strip column whitespace (mirrors FIX from load_zakopane.py)
    df.columns = df.columns.str.strip()

    # ── File-level checks ────────────────────────────────────────────────────
    _check_poi_count(df, report)
    _check_required_columns(df, report)

    # ── Row-level checks ─────────────────────────────────────────────────────
    for excel_row, (_, row) in enumerate(df.iterrows(), start=2):  # row 1 = header
        _check_name(row, excel_row, report)
        _check_coordinates(row, excel_row, report)
        _check_priority_level(row, excel_row, report)
        _check_time_values(row, excel_row, report)
        _check_tod(row, excel_row, report)
        _check_tags(row, excel_row, report)
        _check_opening_hours_sentinel(row, excel_row, report)
        _check_target_group(row, excel_row, report)
        _check_must_see_score(row, excel_row, report)

    if raise_on_error and report.has_errors:
        raise ValueError(
            f"Excel validation failed for {city}: "
            f"{len(report.errors)} error(s). Run validate_excel() for details."
        )

    return report


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────

def _check_poi_count(df: pd.DataFrame, report: ValidationReport) -> None:
    n = len(df)
    if n == 0:
        report.issues.append(ValidationIssue("ERROR", None, "rows", "Sheet is empty (0 rows)."))
    elif n < 20:
        report.issues.append(ValidationIssue(
            "WARNING", None, "rows",
            f"Only {n} POI. Plans for 3+ days may be sparse. Consider adding more."
        ))
    else:
        report.issues.append(ValidationIssue(
            "INFO", None, "rows", f"{n} POI loaded."
        ))


def _check_required_columns(df: pd.DataFrame, report: ValidationReport) -> None:
    required = ["Name", "Lat", "Lng"]
    recommended = ["Tags", "priority_level", "time_min", "time_max",
                   "recommended_time_of_day", "Must see score"]
    cols = set(df.columns)
    for col in required:
        if col not in cols:
            report.issues.append(ValidationIssue(
                "ERROR", None, "columns", f"Required column '{col}' is missing."
            ))
    for col in recommended:
        if col not in cols:
            report.issues.append(ValidationIssue(
                "WARNING", None, "columns",
                f"Recommended column '{col}' is missing — related features will be degraded."
            ))


def _check_name(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    val = row.get("Name")
    if val is None or (isinstance(val, float) and math.isnan(val)) or str(val).strip() == "":
        report.issues.append(ValidationIssue(
            "ERROR", excel_row, "Name", "Empty or missing name."
        ))


def _check_coordinates(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    for col in ("Lat", "Lng"):
        val = row.get(col)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            report.issues.append(ValidationIssue(
                "ERROR", excel_row, col, f"{col} is missing (NaN)."
            ))
        elif float(val) == 0.0:
            report.issues.append(ValidationIssue(
                "ERROR", excel_row, col, f"{col}=0.0 — likely placeholder, not a real coordinate."
            ))


def _check_priority_level(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    val = str(row.get("priority_level", "") or "").strip().lower()
    if not val or val in ("nan", "none", ""):
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "priority_level",
            "Missing priority_level — POI treated as optional (lowest score bonus)."
        ))
    elif val not in _KNOWN_PRIORITY:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "priority_level",
            f"Unknown value '{val}'. Expected: core/secondary/optional (or high/medium/low for multi_city)."
        ))


def _check_time_values(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    raw_min = row.get("time_min")
    raw_max = row.get("time_max")

    t_min = None
    t_max = None

    if raw_min is not None and not (isinstance(raw_min, float) and math.isnan(raw_min)):
        try:
            t_min = int(float(raw_min))
        except (TypeError, ValueError):
            report.issues.append(ValidationIssue(
                "WARNING", excel_row, "time_min", f"Cannot parse time_min='{raw_min}'."
            ))

    if raw_max is not None and not (isinstance(raw_max, float) and math.isnan(raw_max)):
        try:
            t_max = int(float(raw_max))
        except (TypeError, ValueError):
            report.issues.append(ValidationIssue(
                "WARNING", excel_row, "time_max", f"Cannot parse time_max='{raw_max}'."
            ))

    if t_min is not None and t_max is not None and t_min > t_max:
        report.issues.append(ValidationIssue(
            "ERROR", excel_row, "time_min/time_max",
            f"time_min ({t_min}) > time_max ({t_max}) — impossible range."
        ))

    if t_max is not None and t_max > 480:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "time_max",
            f"time_max={t_max} min (>8h) — unusually long. Intentional?"
        ))

    if t_min is not None and t_min <= 0:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "time_min",
            f"time_min={t_min} — should be > 0."
        ))


def _check_tod(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    """FIX #97: Detect Polish recommended_time_of_day values."""
    val = str(row.get("recommended_time_of_day", "") or "").strip().lower()
    if not val or val in ("nan", "none", ""):
        return  # Missing is OK — engine defaults to 'any'

    if val in _TOD_POLISH:
        report.issues.append(ValidationIssue(
            "ERROR", excel_row, "recommended_time_of_day",
            f"Polish value '{val}' detected. normalizer.py will auto-translate, "
            f"but fix in Excel for clarity. Expected: morning/midday/afternoon/evening/any."
        ))
    elif val not in _KNOWN_TOD_EN:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "recommended_time_of_day",
            f"Unknown value '{val}'. Expected: morning/midday/afternoon/evening/any."
        ))


def _check_tags(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    """FIX #94/#95: Detect tags that won't match any preference in tag_preferences.py."""
    raw = row.get("Tags", "")
    if raw is None or (isinstance(raw, float) and math.isnan(raw)) or str(raw).strip() == "":
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "Tags",
            "No tags — POI will score 0 for all user preferences (preference-based scoring disabled)."
        ))
        return

    tags = _parse_tag_list(raw)
    unknown = [t for t in tags if t not in _KNOWN_TAGS]

    if unknown:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "Tags",
            f"Tag(s) not in tag_preferences.py: {unknown}. "
            f"They will be IGNORED in preference scoring. "
            f"Add them to tag_preferences.py or fix typo in Excel."
        ))

    known_count = len(tags) - len(unknown)
    if known_count == 0 and tags:
        report.issues.append(ValidationIssue(
            "ERROR", excel_row, "Tags",
            f"ALL {len(tags)} tag(s) are unknown to tag_preferences.py: {tags}. "
            f"POI will score 0 for every user preference."
        ))


def _check_opening_hours_sentinel(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    """FIX #75: Detect '{}' / '[]' sentinel values that engine misreads as 'closed'."""
    for col in ("Opening hours", "opening_hours"):
        val = str(row.get(col, "") or "").strip()
        if val in ("{}", "[]", "{ }", "[ ]"):
            report.issues.append(ValidationIssue(
                "WARNING", excel_row, col,
                f"Value '{val}' is an empty sentinel. Engine treats this as closed. "
                f"Clear the cell (leave empty) to mean 'always open'."
            ))


def _check_target_group(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    raw = row.get("Target group", row.get("target_group", ""))
    if raw is None or (isinstance(raw, float) and math.isnan(raw)) or str(raw).strip() == "":
        return  # Missing is OK — defaults to 'all'

    groups = _parse_tag_list(raw)
    unknown = [g for g in groups if g not in _KNOWN_TARGET_GROUPS]
    if unknown:
        report.issues.append(ValidationIssue(
            "WARNING", excel_row, "Target group",
            f"Unknown target group(s): {unknown}. "
            f"Expected subset of: {sorted(_KNOWN_TARGET_GROUPS)}."
        ))


def _check_must_see_score(row: pd.Series, excel_row: int, report: ValidationReport) -> None:
    """FIX #96: Warn if Must see score >= 8 but 'must_see' tag is absent from Tags."""
    raw_score = row.get("Must see score")
    if raw_score is None or (isinstance(raw_score, float) and math.isnan(raw_score)):
        return

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return

    if score >= 8:
        raw_tags = row.get("Tags", "")
        tags = _parse_tag_list(raw_tags)
        if "must_see" not in tags:
            report.issues.append(ValidationIssue(
                "INFO", excel_row, "Must see score",
                f"Score={score:.0f} (>=8) but 'must_see' tag absent. "
                f"normalizer.py will auto-inject it (FIX #96). OK — just informational."
            ))


# ──────────────────────────────────────────────────────────────────────────────
# Batch validator (for all cities at once)
# ──────────────────────────────────────────────────────────────────────────────

def validate_all_cities(city_excel_map: dict, raise_on_error: bool = False) -> List[ValidationReport]:
    """
    Validate multiple city Excel files in one call.

    Args:
        city_excel_map: dict mapping city_name → excel_path
                        e.g. {"Kraków": "data/krakow.xlsx", "Gdańsk": "data/gdansk.xlsx"}
        raise_on_error: If True, raises ValueError on first ERROR found.

    Returns:
        List of ValidationReport (one per city).

    Example:
        reports = validate_all_cities({
            "Kraków":   "data/krakow.xlsx",
            "Zakopane": "data/zakopane.xlsx",
            "Gdańsk":   "data/gdansk.xlsx",
        })
        for r in reports:
            r.print_summary()
    """
    reports = []
    for city_name, excel_path in city_excel_map.items():
        report = validate_excel(
            excel_path=excel_path,
            city_name=city_name,
            raise_on_error=raise_on_error,
        )
        reports.append(report)
    return reports


def print_all_reports(reports: List[ValidationReport], errors_only: bool = False) -> None:
    """Print all reports. If errors_only=True, skip cities with no issues."""
    for r in reports:
        if errors_only and not r.has_errors:
            continue
        r.print_summary()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.infrastructure.repositories.excel_validator <path.xlsx> [city_name]")
        sys.exit(1)

    _path = sys.argv[1]
    _city = sys.argv[2] if len(sys.argv) > 2 else ""
    _report = validate_excel(_path, city_name=_city)
    _report.print_summary()
    sys.exit(1 if _report.has_errors else 0)
