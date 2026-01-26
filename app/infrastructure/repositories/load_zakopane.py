# type: ignore
# Oryginalny load_zakopane.py - refaktoryzacja type hints w ETAP 3
import pandas as pd
from app.infrastructure.repositories.normalizer import normalize_pois


def load_zakopane_poi(path: str):
    df = pd.read_excel(path)

    print("KOLUMNY:", list(df.columns))

    pois = []

    for _, row in df.iterrows():
        poi = {
            "ID": str(row.get("ID", "")).strip(),
            "Name": str(row.get("Name", "")).strip(),
            "Description_short": str(row.get("Description_short", "")).strip(),
            "Description_long": str(row.get("Description_long", "")).strip(),
            "Why visit": str(row.get("Why visit", "")).strip(),
            "Opening hours": str(row.get("Opening hours", "")).strip(),
            "opening_hours_seasonal": str(
                row.get("opening_hours_seasonal", "")
            ).strip(),
            "time_min": row.get("time_min"),
            "time_max": row.get("time_max"),
            "Price": row.get("Price"),
            "ticket_normal": row.get("ticket_normal"),
            "ticket_reduced": row.get("ticket_reduced"),
            "Address": str(row.get("Address", "")).strip(),
            "Region": str(row.get("Region", "")).strip(),
            "Lat": row.get("Lat"),
            "Lng": row.get("Lng"),
            "Link do godzin": str(row.get("Link do godzin", "")).strip(),
            "Link do cennika": str(row.get("Link do cennika", "")).strip(),
            "Space": str(row.get("Space", "")).strip(),
            "Intensity": str(row.get("Intensity", "")).strip(),
            "weather_dependency": str(
                row.get("weather_dependency", "")
            ).strip(),
            "popularity_score": row.get("popularity_score"),
            "Must see score": row.get("Must see score"),
            "Peak hours": str(row.get("Peak hours", "")).strip(),
            "recommended_time_of_day": str(
                row.get("recommended_time_of_day", "")
            ).strip(),
            "City": str(row.get("City", "")).strip(),
            "Target group": str(row.get("Target group", "")).strip(),
            "Children's age": str(row.get("Children's age", "")).strip(),
            "Type of attraction": str(
                row.get("Type of attraction", "")
            ).strip(),
            "Activity_style": str(row.get("Activity_style", "")).strip(),
            "crowd_level": str(row.get("crowd_level", "")).strip(),
            "Budget type": str(row.get("Budget type", "")).strip(),
            "Seasonality of attractions": str(
                row.get("Seasonality of attractions", "")
            ).strip(),
            "Pro_tip": str(row.get("Pro_tip", "")).strip(),
            "parking_name": str(row.get("parking_name", "")).strip(),
            "parking_address": str(row.get("parking_address", "")).strip(),
            "parking_lat": row.get("parking_lat"),
            "parking_lng": row.get("parking_lng"),
            "parking_type": str(row.get("parking_type", "")).strip(),
            "parking_walk_time_min": row.get("parking_walk_time_min"),
            "priority_level": str(row.get("priority_level", "")).strip(),
            "kids_only": str(row.get("kids_only", "")).strip(),
            "Tags": str(row.get("Tags", "")).strip(),
        }

        pois.append(poi)

    print(f"ZAŁADOWANO POI: {len(pois)}")

    pois = normalize_pois(pois)

    return pois
