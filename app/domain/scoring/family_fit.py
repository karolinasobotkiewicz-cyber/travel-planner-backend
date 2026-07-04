# type: ignore
"""
Target Group Matching - Hard Filter + Scoring.

Feedback klientki (03.02.2026):
- Target group powinno działać jako HARD FILTER, nie tylko soft scoring
- Jeśli user.group NOT IN poi.target_group → EXCLUDE
"""


def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""


_CHILD_POI_NAME_MARKERS = (
    "mini zoo", "papugarn", "papuga", "królikarn", "krolikarn", "królikarnia",
    "akwariat", "podwodny świat", "podwodny swiat", "myszogród", "myszogrod",
    "dino park", "park rozrywki", "sala zabaw", "plac zabaw", "tatra family",
    "park harnasia", "góralski ślizg", "goral ski slizg", "woskowych", "iluzja park",
    "lego", "wielka wystawa klock", "loopy", "pixel xl",
    "guliwer", "centrum rozrywki",
)
# FIX #197: recurring client mismatches (name heuristics when Excel target_group is loose)
_GROUP_POI_NAME_DENY: dict[str, tuple[str, ...]] = {
    "friends": (
        "farma wuja toma", "wuja tom",
        "guliwer", "centrum rozrywki guliwer",
        # FIX #229: monuments/bridges/places for friends+adventure
        "pomnik ", "most ", "plac europejski", "plac wolności",
        "grób nieznanego", "pałac prezydencki", "syrenka", "syreny",
        "kościół św. wojciecha", "sw. wojciecha",
        # FIX #231
        "be happy museum", "plac bohaterów getta",
    ),
    "seniors": (
        "kopiec powstania",
        # FIX #229: don't open day with micro memorials
        "grób nieznanego", "pałac prezydencki", "pomnik syren",
    ),
    "family_kids": (
        "grób nieznanego", "grob nieznanego", "changing of the guard",
        "pałac prezydencki", "palac prezydencki",
        "kościół św. anny", "kosciol sw. anny", "sw. anny",
        "parafia rzymskokatolicka", "parafia pw.",
        "kościół św. michała", "kosciol sw. michala", "św. michała", "sw. michala",
        "nowa huta", "centrum historii zajezdnia", "zajezdnia",
        # FIX #222
        "bastion sakwowy", "neon side", "most świętokrzyski", "most swietokrzyski",
        "muzeum powstania warszawskiego", "plac europejski",
        "muzeum czartoryskich", "laser tag",
        # FIX #227 (30.06.2026): Poznań
        "bazylika archikatedralna", "archikatedr", "domy kupieckie", "escape room",
        # FIX #229: extreme / bridges / micro for families
        "bungee", "secret room", "the secret room",
        "most grunwaldzki", "most ", "kładka bernatka", "kladka bernatka",
        "muzeum pałacu jana", "muzeum ewolucji", "muzeum śląskie",
        "pałac w wilanowie", "muzeum pałacu",
        "podziemia rynku", "kopiec powstania",
        "katedra wrocławska", "katedra wroclawska",
        # FIX #231 Kraków
        "kościół św. wojciecha", "sw. wojciecha", "bazylika mariacka",
        "park decjusza", "kopiec krakusa", "aula leopoldina",
    ),
    "solo": ("pixel xl", "pixel", "centrum nauki kopernik"),
    "couples": (
        "pixel xl", "pixel", "loopy",
        # FIX #229: Stacja Grawitacja for cultural+relax couples
        "stacja grawitacja", "anomalii grawitacyjnej", "miejsce anomalii",
        "centrum nauki kopernik",
    ),
}
_CHILD_POI_TAGS = frozenset({
    "family_kids", "kids", "zoo", "aquarium", "playground", "theme_park",
    "kids_entertainment", "family_friendly",
})


def is_child_oriented_attraction(poi: dict) -> bool:
    """FIX #196: atrakcje typowo dziecięce (zoo, papugarnie, sale zabaw itd.)."""
    kids_only_val = poi.get("kids_only")
    if kids_only_val is True or (
        isinstance(kids_only_val, str) and kids_only_val.lower() in ("true", "1", "yes")
    ):
        return True

    target_groups = poi.get("target_groups") or []
    tg = {_safe_str(x) for x in target_groups}
    if tg == {"family_kids"}:
        return True

    name = _safe_str(poi.get("name") or "")
    if any(marker in name for marker in _CHILD_POI_NAME_MARKERS):
        return True

    tags = {_safe_str(t) for t in (poi.get("tags") or []) if t}
    if _CHILD_POI_TAGS & tags:
        return True

    toa = _safe_str(
        poi.get("type_of_attraction") or poi.get("Type of attraction") or ""
    )
    if any(k in toa for k in ("zoo", "aquarium", "theme", "playground", "family")):
        return True

    return False


def restaurant_matches_target_group(restaurant: dict, user: dict) -> bool:
    """FIX #229: filter lunch/dinner suggestions by restaurant target_group."""
    user_group = _safe_str(user.get("target_group", ""))
    if not user_group:
        return True
    target_groups = restaurant.get("target_groups") or []
    if not target_groups:
        return True
    if isinstance(target_groups, str):
        target_groups = [x.strip() for x in target_groups.split(",")]
    tg = {_safe_str(x) for x in target_groups if x}
    if not tg:
        return True
    return user_group in tg


def should_exclude_by_target_group(poi: dict, user: dict) -> bool:
    """
    Hard filter: Czy POI powinno być wykluczone z powodu target_group mismatch?
    
    Logic (Feedback klientki - 03.02.2026):
    - Jeśli POI ma target_groups określone, a user.group NIE jest w liście → EXCLUDE
    - Jeśli POI nie ma target_groups → ALLOW (neutralne dla wszystkich)
    
    Przykłady wykluczeń:
    - seniors → brak kids_only attractions
    - friends → brak kids_only attractions
    - couple → brak atrakcji stricte dziecięcych
    - solo → brak kids_only attractions
    
    Args:
        poi: POI dict z "target_groups" (list) i "kids_only" (bool)
        user: User dict z "target_group" (string)
    
    Returns:
        True jeśli POI powinno być wykluczone, False w przeciwnym razie
    
    Examples:
        >>> poi = {"kids_only": True, "target_groups": ["family_kids"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        True
        
        >>> poi = {"target_groups": ["solo", "couples"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        True
        
        >>> poi = {"target_groups": ["seniors", "solo", "couples"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        False
    """
    import random
    check_id = random.randint(1000, 9999)  # Unique ID for this check
    
    user_group = _safe_str(user.get("target_group", ""))
    poi_id_val = poi.get("id", "unknown")  # Use ID instead of name to avoid Unicode errors
    
    print(f"[DEBUG TARGET #{check_id}] Checking POI ID: {poi_id_val} | user_group={user_group} | poi.target_groups={poi.get('target_groups')} | kids_only={poi.get('kids_only')}")
    
    # Brak grupy użytkownika -> neutralne
    if not user_group:
        print(f"[DEBUG TARGET #{check_id}] -> ALLOW (no user_group)")
        return False

    # FIX #197: name-based denylist (Farma Wuja Toma/friends, Kopiec/seniors, …)
    poi_name = _safe_str(poi.get("name") or "")
    for marker in _GROUP_POI_NAME_DENY.get(user_group, ()):
        if marker in poi_name:
            print(f"[DEBUG TARGET #{check_id}] -> EXCLUDE (FIX#197 name deny '{marker}')")
            return True
    
    # Kids_only = hard exclude dla grup nie-family
    # HOTFIX #7: bool("false") = True w Pythonie! Sprawdzamy wartość prawdziwie boolean
    kids_only_val = poi.get("kids_only")
    is_kids_only = kids_only_val is True or (isinstance(kids_only_val, str) and kids_only_val.lower() in ["true", "1", "yes"])
    
    if is_kids_only and user_group not in ["family_kids", "family"]:
        print(f"[DEBUG TARGET #{check_id}] -> EXCLUDE (kids_only={kids_only_val} parsed as {is_kids_only} and user_group={user_group})")
        return True
    
    # Sprawdź target_groups POI
    target_groups = poi.get("target_groups")
    
    # POI bez target_groups -> neutralne, dostępne dla wszystkich
    if not target_groups:
        print(f"[DEBUG TARGET #{check_id}] -> ALLOW (no target_groups)")
        return False
    
    # Normalizacja do set
    try:
        tg = set([_safe_str(x) for x in target_groups])
    except Exception as e:
        print(f"[DEBUG TARGET #{check_id}] WARNING: ERROR normalizing target_groups={target_groups}: {e}")
        # Jeśli błąd w target_groups -> exclude (safer default)
        print(f"[DEBUG TARGET #{check_id}] -> EXCLUDE (error in target_groups)")
        return True
    
    # "all" in target_groups → neutral (open to every profile)
    if "all" in tg:
        print(f"[DEBUG TARGET #{check_id}] -> ALLOW (target_groups contains 'all')")
        return False

    # FIX #209 (20.06.2026): family_kids — spa/small towns tag POI as
    # couples/friends/seniors; families should still visit parks, museums, nature.
    if user_group == "family_kids":
        _fk_open = {"family_kids", "family", "families", "friends", "groups", "all"}
        if tg & _fk_open:
            print(f"[DEBUG TARGET #{check_id}] -> ALLOW (family_kids + open group {tg & _fk_open})")
            return False
        if tg == {"seniors"} or tg <= {"seniors", "solo"}:
            print(f"[DEBUG TARGET #{check_id}] -> EXCLUDE (seniors-only POI for family_kids)")
            return True
        if "couples" in tg or "friends" in tg:
            print(f"[DEBUG TARGET #{check_id}] -> ALLOW (family_kids + general POI {tg})")
            return False

    # Jeśli user_group NIE jest w target_groups POI -> EXCLUDE
    if user_group not in tg:
        print(f"[DEBUG TARGET #{check_id}] -> EXCLUDE (user_group={user_group} NOT IN target_groups={tg})")
        return True
    
    print(f"[DEBUG TARGET #{check_id}] -> ALLOW (user_group={user_group} IN target_groups={tg})")
    return False


def calculate_family_score(poi, user):
    """
    Scoring dla target_group matching - wszystkie grupy (FIX #8).
    
    Logic:
    - family_kids: Poprzednia logika (kids_only +8, matching +6, -4 za brak)
    - Inne grupy (seniors, solo, couples, friends):
        * Perfect match: +20
        * Kids-focused POI (only family_kids): -50 (CLIENT REQUIREMENT 04.02.2026)
        * Mismatch/brak: -10
        * Neutral (brak target_groups): 0
    
    Returns:
        Score bonus/penalty za dopasowanie target_group
    """
    user_group = str(user.get("target_group", "")).strip().lower()
    
    # FAMILY_KIDS - LEGACY LOGIC (from old code)
    if user_group == "family_kids":
        # kids only -> duzy bonus
        if bool(poi.get("kids_only")):
            return 8.0

        target_groups = poi.get("target_groups") or []
        tg = set([_safe_str(x) for x in target_groups])

        # TODO: sprawdzic czy nie za duzy bonus dla family
        base = 6.0 if ("family_kids" in tg or "family" in tg) else -4.0

        # wiek dziecka vs. limity POI
        age = user.get("children_age", None)
        if isinstance(age, (int, float)):
            cmin = poi.get("children_min", None)
            cmax = poi.get("children_max", None)
            if isinstance(cmin, int) and isinstance(cmax, int):
                if int(age) < cmin:
                    # FIX #126 (30.05.2026): Hard penalty — child too young for this POI
                    # Not a hard exclude to prevent empty days, but -50 effectively removes it
                    base -= 50.0
                elif cmin <= int(age) <= cmax:
                    base += 2.0  # In-range bonus

        return base
    
    # FIX #8: Scoring dla innych grup (seniors, solo, couples, friends)
    if not user_group:
        return 0.0  # Brak grupy = neutralne
    
    target_groups = poi.get("target_groups") or []
    if not target_groups:
        return 0.0  # POI bez target_groups = neutralne dla wszystkich
    
    # Normalizacja POI target_groups do set
    tg = set([_safe_str(x) for x in target_groups])

    # FIX #196 (06.2026): couples — obniż scoring typowo dziecięcych atrakcji
    # (mini zoo, papugarnie, królikarnie, akwaria — nawet gdy couples ∈ target_groups).
    if user_group == "couples" and is_child_oriented_attraction(poi):
        return -40.0
    
    # CLIENT REQUIREMENT (04.02.2026): Kids-focused POI penalty for non-family groups
    # Kids-focused = POI with ONLY family_kids in target_groups (not multi-group POI)
    is_kids_focused = (len(tg) == 1 and "family_kids" in tg)
    if is_kids_focused and user_group in ['solo', 'couples', 'friends', 'seniors']:
        # Strong penalty for kids-focused attractions
        return -50.0
    
    # Perfect match: +20
    if user_group in tg:
        return 20.0
    
    # Mismatch: -10 (POI ma inne grupy, nie pasuje)
    return -10.0

