"""Turn a raw character payload into a :class:`CharacterDetail`.

The per-game modules in :mod:`nanoka_viewer.api.detail_games` supply stats,
skills, extras and builds; this module supplies the fields every game shares
(name, subtitle, overview, badges, level label).
"""

from __future__ import annotations

from typing import Any

from .detail_games import gi, hsr, nte, ww, zzz
from .detail_models import CharacterDetail
from .detail_text import format_markup
from .game_data import GI_WEAPONS, HSR_PATHS, WW_ELEMENTS, WW_WEAPONS
from .models import get_name


def badges_for(game: str, raw: dict[str, Any]) -> list[str]:
    badges: list[str] = []
    if game == "hsr":
        rarity = str(raw.get("rarity") or "")
        if "5" in rarity:
            badges.append("5★")
        elif "4" in rarity:
            badges.append("4★")
        element = str(raw.get("damage_type") or "")
        path = HSR_PATHS.get(
            str(raw.get("base_type") or ""), str(raw.get("base_type") or "")
        )
        badges.extend([value for value in (element, path) if value])
        camp = (raw.get("chara_info") or {}).get("camp")
        if camp:
            badges.append(str(camp))
    elif game == "gi":
        badges.append("5★" if "ORANGE" in str(raw.get("rarity") or "") else "4★")
        weapon = str(raw.get("weapon") or "")
        faction = (raw.get("chara_info") or {}).get("native")
        badges.extend(
            value
            for value in (
                raw.get("element"),
                GI_WEAPONS.get(
                    weapon,
                    weapon.removeprefix("WEAPON_").replace("_", " ").title(),
                ),
                faction,
            )
            if value
        )
    elif game == "ww":
        badges.append(f"{raw.get('rarity', '?')}★")
        badges.extend(
            value
            for value in (
                WW_ELEMENTS.get(raw.get("element")),
                WW_WEAPONS.get(raw.get("weapon")),
            )
            if value
        )
    elif game == "zzz":
        badges.append("S" if raw.get("rarity") == 4 else "A")
        badges.extend(str(name) for name in (raw.get("element_type") or {}).values())
        badges.extend(str(name) for name in (raw.get("weapon_type") or {}).values())
        badges.extend(str(name) for name in (raw.get("camp") or {}).values())
    elif game == "nte":
        badges.append(f"{raw.get('rarity', '?')}★")
        if raw.get("element_name"):
            badges.append(str(raw["element_name"]))
        if raw.get("faction"):
            badges.append(str(raw["faction"]))
    return [badge for badge in badges if badge]


def subtitle_for(game: str, raw: dict[str, Any]) -> str:
    if game == "hsr":
        return str((raw.get("chara_info") or {}).get("camp") or "")
    if game == "gi":
        info = raw.get("chara_info") or {}
        return " · ".join(
            value for value in (info.get("title"), info.get("native")) if value
        )
    if game == "ww":
        return str(raw.get("nick_name") or "")
    if game == "zzz":
        info = raw.get("partner_info") or {}
        return str(info.get("full_name") or info.get("birthday") or "")
    if game == "nte":
        return " · ".join(
            value
            for value in (raw.get("ability_name"), raw.get("faction"))
            if value
        )
    return ""


def overview_for(game: str, raw: dict[str, Any]) -> str:
    if game == "zzz":
        info = raw.get("partner_info") or {}
        return format_markup(info.get("profile_desc") or "")
    return format_markup(raw.get("desc") or "")


def level_label_for(game: str) -> str:
    return {
        "hsr": "Lv. 80",
        "gi": "Lv. 90",
        "ww": "Lv. 90",
        "zzz": "Lv. 60",
        "nte": "Lv. 80",
    }.get(game, "Max level")


def normalize(
    game: str,
    char_id: str,
    raw: dict[str, Any],
    metadata: dict[str, Any],
    *,
    with_build: bool = True,
) -> CharacterDetail:
    name = str(raw.get("name") or get_name(game, raw, char_id) or "Unknown")
    detail = CharacterDetail(
        game=game,
        char_id=str(char_id),
        name=name,
        subtitle=subtitle_for(game, raw),
        overview=overview_for(game, raw),
        level_label=level_label_for(game),
        badges=badges_for(game, raw),
    )

    if game == "hsr":
        detail.stats = hsr.stats(raw)
        if with_build:
            detail.build = hsr.build(raw, metadata)
        detail.skills = hsr.skills(raw)
        detail.extras = hsr.extras(raw)
    elif game == "gi":
        detail.stats = gi.stats(raw)
        detail.skills = gi.skills(raw)
        detail.extras = gi.extras(raw)
        detail.terms = gi.linked_terms(
            raw, metadata.get("hyperlinks") or {}
        )
    elif game == "ww":
        detail.stats = ww.stats(raw)
        if with_build:
            detail.build = ww.build(raw, metadata)
        detail.skills, extras = ww.skills(raw)
        detail.extras = extras
    elif game == "zzz":
        detail.stats = zzz.stats(raw)
        if with_build:
            detail.build = zzz.build(raw, metadata)
        detail.skills = zzz.skills(raw)
        detail.extras = zzz.extras(raw)
    elif game == "nte":
        detail.stats = nte.stats(raw)
        detail.skills = nte.skills(raw)
        detail.extras = nte.extras(raw)
    return detail
