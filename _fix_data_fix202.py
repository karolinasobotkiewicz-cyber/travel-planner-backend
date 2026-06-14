"""
FIX #202 — automatic Excel + tag vocabulary repairs (8.06.2026).

Run: python _fix_data_fix202.py
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

EXCEL = Path("data/multi_city_attractions.xlsx")
SHEET = "All Cities"

# ── Excel row patches by exact Name ──────────────────────────────────────────
NAME_PATCHES: dict[str, dict] = {
    "Fontanna Multimedialna": {
        "City": "Wrocław",
        "Hub": "Wrocław",
    },
    "Spodek w Katowicach": {
        "Must see score": 6,
        "priority_level": "secondary",
        # Keep landmark/architecture tags — not a museum; lower score only.
    },
    "Długi Targ": {
        "Must see score": 5,
        "priority_level": "secondary",
    },
    "Pomnik Bamberki": {
        "Must see score": 4,
        "priority_level": "optional",
    },
    "Fokarium Stacji Morskiej im. Prof. Krzysztofa Skóry": {
        "Hub": "Hel",
        "City": "Hel",
    },
    "Rewa - Cypl Rewski": {
        "Hub": "Rewa",
        "City": "Rewa",
    },
}

# City → hub when City is a distinct coastal subregion (Trójmiasto cluster)
CITY_HUB_OVERRIDES = {
    "hel": "Hel",
    "rewa": "Rewa",
    "mechelinki": "Gdynia",  # stays under Gdynia hub (no separate day)
}


def norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def fix_multiline_tags(df: pd.DataFrame, changes: list[str]) -> None:
    """FIX #202: Tags column sometimes uses newlines instead of commas."""
    if "Tags" not in df.columns:
        return
    for i in range(len(df)):
        raw = df.at[i, "Tags"]
        if pd.isna(raw):
            continue
        s = str(raw)
        if "\n" not in s and "\r" not in s:
            continue
        fixed = re.sub(r"[\r\n]+", ",", s)
        fixed = re.sub(r",\s*,", ",", fixed)
        fixed = fixed.strip(" ,")
        name = str(df.at[i, "Name"])[:40]
        changes.append(f"{name}: Tags newlines → commas")
        df.at[i, "Tags"] = fixed


def fix_tod_values(df: pd.DataFrame, changes: list[str]) -> None:
    col = "recommended_time_of_day"
    if col not in df.columns:
        return
    for i in range(len(df)):
        val = df.at[i, col]
        if pd.isna(val):
            continue
        s = str(val).strip()
        if not s or s.lower() in ("nan", "none"):
            continue
        fixed = s
        fixed = fixed.replace("midday.afternoon", "midday,afternoon")
        fixed = fixed.replace("morning.midday", "morning,midday")
        fixed = fixed.replace("afternoon.evening", "afternoon,evening")
        if fixed != s:
            name = str(df.at[i, "Name"])[:40]
            changes.append(f"{name}: tod {s!r} → {fixed!r}")
            df.at[i, col] = fixed


def apply_name_patches(df: pd.DataFrame, changes: list[str]) -> None:
    for i in range(len(df)):
        name = str(df.at[i, "Name"]).strip()
        if name not in NAME_PATCHES:
            continue
        for col, val in NAME_PATCHES[name].items():
            if col not in df.columns:
                continue
            old = df.at[i, col]
            if pd.isna(old) and val is None:
                continue
            if str(old) != str(val):
                changes.append(f"{name}: {col} {old!r} → {val!r}")
                df.at[i, col] = val


def apply_city_hub_overrides(df: pd.DataFrame, changes: list[str]) -> None:
    if "Hub" not in df.columns or "City" not in df.columns:
        return
    for i in range(len(df)):
        city = df.at[i, "City"]
        if pd.isna(city):
            continue
        cn = norm(str(city))
        new_hub = CITY_HUB_OVERRIDES.get(cn)
        if not new_hub:
            continue
        old_hub = df.at[i, "Hub"]
        if str(old_hub) != new_hub:
            name = str(df.at[i, "Name"])[:45]
            changes.append(f"{name}: Hub {old_hub!r} → {new_hub!r} (city={city})")
            df.at[i, "Hub"] = new_hub


def count_validator_unknown(excel_path: Path) -> tuple[int, int]:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from app.infrastructure.repositories.excel_validator import validate_excel

    report = validate_excel(str(excel_path), sheet_name=SHEET)
    tag_warnings = sum(
        1 for i in report.warnings if "not in tag_preferences" in i.message
    )
    tod_warnings = sum(
        1 for i in report.warnings if i.column == "recommended_time_of_day"
    )
    return tag_warnings, tod_warnings


def main() -> None:
    if not EXCEL.exists():
        raise SystemExit(f"Missing {EXCEL}")

    backup = EXCEL.with_name(
        f"multi_city_attractions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    shutil.copy2(EXCEL, backup)
    print(f"Backup: {backup}")

    before_tags, before_tod = count_validator_unknown(EXCEL)
    print(f"Before: tag warnings={before_tags}, tod warnings={before_tod}")

    df = pd.read_excel(EXCEL, sheet_name=SHEET)
    changes: list[str] = []

    apply_name_patches(df, changes)
    apply_city_hub_overrides(df, changes)
    fix_multiline_tags(df, changes)
    fix_tod_values(df, changes)

    xl = pd.ExcelFile(EXCEL)
    all_sheets = {sn: pd.read_excel(EXCEL, sheet_name=sn) for sn in xl.sheet_names}
    all_sheets[SHEET] = df
    with pd.ExcelWriter(EXCEL, engine="openpyxl") as w:
        for sn, sdf in all_sheets.items():
            sdf.to_excel(w, sheet_name=sn, index=False)

    after_tags, after_tod = count_validator_unknown(EXCEL)
    print(f"\nApplied {len(changes)} Excel changes:")
    for c in changes:
        print(f"  - {c}")
    print(f"\nAfter: tag warnings={after_tags}, tod warnings={after_tod}")
    print(f"Saved: {EXCEL} ({len(df)} rows)")


if __name__ == "__main__":
    main()
