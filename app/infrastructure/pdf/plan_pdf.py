"""
Plan PDF generator (01.07.2026 - front feedback: pobieranie PDF nie działało,
bo backend nie miał endpointu ani generatora).

Używa ReportLab (czysty Python, działa na Render bez zależności systemowych).
Obsługa polskich znaków:
- Jeśli w systemie jest font Unicode (DejaVuSans / Arial), rejestrujemy go.
- Jeśli nie — używamy Helvetica i transliterujemy polskie znaki do ASCII,
  aby PDF zawsze się wygenerował poprawnie (bez "krzaczków").
"""
import io
import os
from typing import Any, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_UNICODE_FONT = False

_FONT_CANDIDATES = [
    # (regular_path, bold_path)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
]

_PL_TRANSLIT = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o",
    "ś": "s", "ż": "z", "ź": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O",
    "Ś": "S", "Ż": "Z", "Ź": "Z",
    "–": "-", "—": "-", "„": '"', "”": '"', "’": "'",
})


def _register_fonts() -> None:
    """Rejestruje font Unicode jeśli dostępny (raz na proces)."""
    global _FONT_REGULAR, _FONT_BOLD, _UNICODE_FONT
    if _UNICODE_FONT:
        return
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont("PlanFont", regular))
                bold_name = "PlanFont-Bold"
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont(bold_name, bold))
                else:
                    bold_name = "PlanFont"
                _FONT_REGULAR = "PlanFont"
                _FONT_BOLD = bold_name
                _UNICODE_FONT = True
                return
            except Exception:
                continue


def _t(text: Any) -> str:
    """Przygotowuje tekst: str + transliteracja gdy brak fontu Unicode."""
    if text is None:
        return ""
    s = str(text)
    if not _UNICODE_FONT:
        s = s.translate(_PL_TRANSLIT)
    # Escape XML dla Paragraph (reportlab traktuje &<> jako markup)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _item_attr(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _item_type(item: Any) -> str:
    t = _item_attr(item, "type")
    return getattr(t, "value", t) or ""


def _first_suggestion_name(item: Any) -> Optional[str]:
    suggestions = _item_attr(item, "suggestions") or []
    if not suggestions:
        return None
    first = suggestions[0]
    if isinstance(first, dict):
        return first.get("name")
    return getattr(first, "name", None)


def _format_line(item: Any) -> Optional[str]:
    """Zamienia pojedynczy element planu na czytelną linię tekstu."""
    itype = _item_type(item)
    start = _item_attr(item, "start_time")
    end = _item_attr(item, "end_time")
    time_range = f"{start}–{end}" if start and end else ""

    if itype == "attraction":
        name = _item_attr(item, "name", "Atrakcja")
        cost = _item_attr(item, "cost_estimate")
        cost_str = f" · {int(cost)} zł" if cost else ""
        return f"{time_range}  {name}{cost_str}"
    if itype == "lunch_break":
        rest = _first_suggestion_name(item)
        label = _item_attr(item, "label", "Lunch")
        extra = f" — {rest}" if rest else ""
        return f"{time_range}  {label}{extra}"
    if itype == "dinner_break":
        rest = _first_suggestion_name(item)
        label = _item_attr(item, "label", "Kolacja")
        extra = f" — {rest}" if rest else ""
        return f"{time_range}  {label}{extra}"
    if itype == "free_time":
        # Pomijamy krótkie bufory techniczne
        if _item_attr(item, "is_technical_buffer"):
            return None
        label = _item_attr(item, "label", "Czas wolny")
        return f"{time_range}  {label}"
    if itype == "day_start":
        return None
    if itype == "day_end":
        return None
    # transit / parking pomijamy dla czytelności
    return None


def build_plan_pdf(plan: Any) -> bytes:
    """
    Buduje PDF z planu (PlanResponse) i zwraca bajty.

    Args:
        plan: PlanResponse (lub obiekt z .days / .city / .start_date / .title)

    Returns:
        bytes zawartości PDF
    """
    _register_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Plan podróży",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PlanTitle", parent=styles["Title"],
        fontName=_FONT_BOLD, fontSize=20, spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "PlanSub", parent=styles["Normal"],
        fontName=_FONT_REGULAR, fontSize=11, textColor=colors.HexColor("#555555"),
        spaceAfter=12,
    )
    day_header_style = ParagraphStyle(
        "DayHeader", parent=styles["Heading2"],
        fontName=_FONT_BOLD, fontSize=13, spaceBefore=10, spaceAfter=4,
        textColor=colors.HexColor("#1a3d5c"),
    )
    line_style = ParagraphStyle(
        "Line", parent=styles["Normal"],
        fontName=_FONT_REGULAR, fontSize=10.5, leading=15,
    )

    story: List[Any] = []

    city = _item_attr(plan, "city") or _item_attr(plan, "location") or "Plan podróży"
    title = _item_attr(plan, "title") or city
    story.append(Paragraph(_t(title), title_style))

    # Subtitle line: daty + grupa + liczba dni
    sub_parts = []
    start_date = _item_attr(plan, "start_date")
    days_count = _item_attr(plan, "days_count")
    group_type = _item_attr(plan, "group_type")
    if start_date:
        sub_parts.append(f"Start: {start_date}")
    if days_count:
        sub_parts.append(f"{days_count} " + ("dzień" if days_count == 1 else "dni"))
    if group_type:
        sub_parts.append(f"Grupa: {group_type}")
    if sub_parts:
        story.append(Paragraph(_t("  ·  ".join(sub_parts)), sub_style))

    days = _item_attr(plan, "days") or []
    for day in days:
        day_num = _item_attr(day, "day")
        day_date = _item_attr(day, "date")
        weekday = _item_attr(day, "weekday")
        day_title = _item_attr(day, "title")

        header_bits = [f"Dzień {day_num}"]
        date_bits = []
        if weekday:
            date_bits.append(weekday)
        if day_date:
            date_bits.append(day_date)
        if date_bits:
            header_bits.append("(" + ", ".join(date_bits) + ")")
        if day_title:
            header_bits.append("— " + str(day_title))
        story.append(Paragraph(_t(" ".join(header_bits)), day_header_style))

        items = _item_attr(day, "items") or []
        lines = []
        for it in items:
            line = _format_line(it)
            if line:
                lines.append(_t(line))
        if not lines:
            lines.append(_t("Dzień do zaplanowania."))
        for ln in lines:
            story.append(Paragraph("• " + ln, line_style))

    if not days:
        story.append(Paragraph(_t("Ten plan nie zawiera jeszcze żadnych dni."), line_style))

    story.append(Spacer(1, 10 * mm))
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName=_FONT_REGULAR, fontSize=8, textColor=colors.HexColor("#999999"),
    )
    story.append(Paragraph(_t("Wygenerowano przez Travel Planner"), footer_style))

    doc.build(story)
    return buf.getvalue()
