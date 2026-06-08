"""
Import Planer - miasta atrakcje6.xlsx (client Zone A/B/C) into backend data files.

Usage (from travel-planner-backend):
    python _import_atrakcje6.py
    python _import_atrakcje6.py "C:/path/to/Planer - miasta atrakcje6.xlsx"
"""
from __future__ import annotations

import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "planer_update" / "Planer - miasta atrakcje6.xlsx"
MULTI_DST = Path(__file__).resolve().parent / "data" / "multi_city_attractions.xlsx"
ZAKOPANE_DST = Path(__file__).resolve().parent / "data" / "zakopane.xlsx"

CANONICAL_CITY = {
    "warsaw": "Warszawa",
    "krakow": "Kraków",
    "wroclaw": "Wrocław",
    "gdansk": "Gdańsk",
    "poznan": "Poznań",
    "lodz": "Łódź",
}

EXPLICIT_BY_NAME: dict[str, dict] = {
    "Muzeum Świat Iluzji we Wrocławiu": {
        "City": "Wrocław",
        "Lat": 51.1153758,
        "Lng": 17.0398402,
        "Address": "Staromłyńska 4, 50-266 Wrocław",
        "Zone": "A",
    },
    "Fontanna Multimedialna": {"City": "Wrocław", "Zone": "A"},
    "GoJump Wrocław": {"City": "Wrocław", "Zone": "A"},
    "Ogród Botaniczny Uniwersytetu Wrocławskiego": {
        "City": "Wrocław",
        "Lat": 51.1159,
        "Lng": 17.0478,
        "Address": "Henryka Sienkiewicza 23, 50-335 Wrocław",
        "Zone": "A",
    },
}

# Name appears in multiple hubs (e.g. Bulwary Wiślane) — scope fixes to sheet.
EXPLICIT_IN_HUB: dict[str, dict[str, dict]] = {
    "Kraków": {
        "Bulwary Wiślane": {"City": "Kraków"},
        "Kładka Ojca Bernatka": {"City": "Kraków"},
        "Muzeum Armii Krajowej w Krakowie": {"City": "Kraków"},
        "Muzeum Sztuki Współczesnej MOCAK": {"City": "Kraków"},
        "Fabryka Wódki w Krakowie": {"City": "Kraków"},
        "Muzeum Geologiczne w Krakowie": {"City": "Kraków"},
        "Ogród Botaniczny Uniwersytetu Jagiellońskiego": {"City": "Kraków"},
    },
}

EXPLICIT_BY_ID = {
    "9e98aa2a-0a35-5a94-ae5f-6b2420aeb145": {"City": "Warszawa"},
}


def norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_all_sheets(path: Path) -> pd.DataFrame:
    frames = []
    for sheet in pd.ExcelFile(path).sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = df.columns.str.strip()
        df["Hub"] = sheet
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def apply_city_fixes(df: pd.DataFrame) -> list[str]:
    changes: list[str] = []
    for i in range(len(df)):
        name = str(df.at[i, "Name"]).strip() if pd.notna(df.at[i, "Name"]) else ""
        row_id = str(df.at[i, "ID"]) if "ID" in df.columns and pd.notna(df.at[i, "ID"]) else ""

        if row_id in EXPLICIT_BY_ID:
            for col, val in EXPLICIT_BY_ID[row_id].items():
                if df.at[i, col] != val:
                    changes.append(f"{name} [{row_id[:8]}]: {col} → {val}")
                    df.at[i, col] = val

        if name in EXPLICIT_BY_NAME:
            for col, val in EXPLICIT_BY_NAME[name].items():
                if col in df.columns and df.at[i, col] != val:
                    changes.append(f"{name}: {col} → {val}")
                    df.at[i, col] = val

        hub = str(df.at[i, "Hub"])
        if hub in EXPLICIT_IN_HUB and name in EXPLICIT_IN_HUB[hub]:
            for col, val in EXPLICIT_IN_HUB[hub][name].items():
                if col in df.columns and df.at[i, col] != val:
                    changes.append(f"{name} [{hub}]: {col} → {val}")
                    df.at[i, col] = val

        city = df.at[i, "City"]
        if pd.notna(city):
            cn = norm(str(city))
            if cn in CANONICAL_CITY:
                new = CANONICAL_CITY[cn]
                if str(city) != new:
                    changes.append(f"{name}: City {city} → {new}")
                    df.at[i, "City"] = new

        if pd.isna(df.at[i, "City"]) or str(df.at[i, "City"]).strip() == "":
            hub = str(df.at[i, "Hub"])
            changes.append(f"{name}: City NaN → Hub {hub}")
            df.at[i, "City"] = hub

    return changes


def prepare_multi_city_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["Name"].notna() & (df["Name"].astype(str).str.strip() != "")].copy()
    df = df.reset_index(drop=True)

    if "id" not in df.columns:
        df["id"] = df["ID"].astype(str) if "ID" in df.columns else ""
    if "name" not in df.columns:
        df["name"] = df["Name"]

    # Align legacy column names
    if "Target group" not in df.columns and "Target group " in df.columns:
        df["Target group"] = df["Target group "]
    if "Children's age" not in df.columns and "Children's age " in df.columns:
        df["Children's age"] = df["Children's age "]
    if "Budget type" not in df.columns and "Budget type " in df.columns:
        df["Budget type"] = df["Budget type "]

    df["Zone"] = df["Zone"].fillna("").astype(str).str.strip().str.upper()
    df.loc[~df["Zone"].isin(["A", "B", "C"]), "Zone"] = ""

    return df


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        raise FileNotFoundError(src)

    print(f"Source: {src}")
    df = load_all_sheets(src)
    print(f"Loaded {len(df)} rows from {df['Hub'].nunique()} sheets")

    fixes = apply_city_fixes(df)
    df = prepare_multi_city_df(df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if MULTI_DST.exists():
        shutil.copy2(MULTI_DST, MULTI_DST.with_name(f"multi_city_attractions_backup_{ts}.xlsx"))
    if ZAKOPANE_DST.exists():
        shutil.copy2(ZAKOPANE_DST, ZAKOPANE_DST.with_name(f"zakopane_backup_{ts}.xlsx"))

    with pd.ExcelWriter(MULTI_DST, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="All Cities", index=False)

    zak = df[df["Hub"] == "Zakopane"].copy()
    zak = zak.drop(columns=["Hub"], errors="ignore")
    zak.to_excel(ZAKOPANE_DST, index=False)

    print(f"\nSaved multi_city: {MULTI_DST} ({len(df)} rows)")
    print(f"Saved zakopane:   {ZAKOPANE_DST} ({len(zak)} rows)")
    print(f"Zone totals: {df['Zone'].value_counts().to_dict()}")

    for hub in ["Warszawa", "Kraków", "Wrocław", "Gdańsk", "Zakopane"]:
        sub = df[df["Hub"] == hub]
        if len(sub):
            print(f"  {hub}: {len(sub)} POIs, zones={sub['Zone'].value_counts().to_dict()}")

    if fixes:
        print(f"\nCity fixes applied ({len(fixes)}):")
        for c in fixes[:15]:
            print(f"  - {c}")
        if len(fixes) > 15:
            print(f"  ... +{len(fixes) - 15} more")


if __name__ == "__main__":
    main()
