"""Zenless Zone Zero detail normalization."""

from __future__ import annotations

import html
import logging
from typing import Any

from ..detail_models import BuildSection, ContentEntry, ExtraSection, SkillDetail
from ..detail_text import (
    format_markup,
    last_numeric_key,
    number,
    percent,
    plain_text,
)

logger = logging.getLogger(__name__)

_SKILLS = [
    ("basic", "Basic Attack"),
    ("dodge", "Dodge"),
    ("special", "Special Attack"),
    ("chain", "Chain Attack / Ultimate"),
    ("assist", "Assist"),
]

# Mapping for the stat IDs that can appear in ``fairy_recommend.part_sub_list``.
# Nanoka does not expose a stat-name JSON; its own character-detail frontend
# hardcodes this same mapping (see the ``ao`` function in its ZZZ route chunk).
# Main-stat names come from the detail JSON itself (``part4/5/6`` and
# ``part_sub``); only sub-stat IDs need this map.
_STAT_NAMES = {
    11102: "HP%",
    11103: "HP",
    12102: "ATK%",
    12103: "ATK",
    13102: "DEF%",
    13103: "DEF",
    20103: "CRIT Rate",
    21103: "CRIT DMG",
    23103: "PEN Ratio",
    23203: "PEN",
    12202: "Impact",
    30502: "Energy Regen",
    31203: "Anomaly Proficiency",
    31402: "Anomaly Mastery",
}


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    base = raw.get("stats") or {}
    levels = raw.get("level") or {}
    bonus = levels.get(last_numeric_key(levels)) or {}
    growth = (60 - 1) / 10000

    extra_levels = raw.get("extra_level") or {}
    extra = (extra_levels.get(last_numeric_key(extra_levels)) or {}).get(
        "extra"
    ) or {}
    extra_atk = 0.0
    extra_impact = 0.0
    for entry in extra.values():
        name = str(entry.get("name") or "").lower()
        try:
            value = float(entry.get("value") or 0)
        except (TypeError, ValueError):
            continue
        if name == "base atk":
            extra_atk += value
        elif name == "impact":
            extra_impact += value

    hp = (
        (base.get("hp_max") or 0)
        + (bonus.get("hp_max") or 0)
        + (base.get("hp_growth") or 0) * growth
    )
    atk = (
        (base.get("attack") or 0)
        + (bonus.get("attack") or 0)
        + (base.get("attack_growth") or 0) * growth
        + extra_atk
    )
    defence = (
        (base.get("defence") or 0)
        + (bonus.get("defence") or 0)
        + (base.get("defence_growth") or 0) * growth
    )
    impact = (base.get("break_stun") or 0) + extra_impact
    return [
        ("HP", number(hp)),
        ("ATK", number(atk)),
        ("DEF", number(defence)),
        ("Impact", number(impact)),
        ("CRIT Rate", percent((base.get("crit") or 0) / 10000)),
        ("CRIT DMG", percent((base.get("crit_damage") or 0) / 10000)),
        ("Anomaly Mastery", number(base.get("element_mystery") or 0)),
        ("Anomaly Proficiency", number(base.get("element_abnormal_power") or 0)),
    ]


def skill_value(param: dict[str, Any], level: int = 12) -> str:
    value = param.get("main")
    if value is None:
        return ""
    try:
        value = float(value) + float(param.get("growth") or 0) * (level - 1)
    except (TypeError, ValueError):
        return str(value)
    fmt = str(param.get("format") or "")
    if fmt == "%" or "%" in fmt:
        shown = value / 100
        return f"{shown:.1f}".rstrip("0").rstrip(".") + "%"
    return f"{value:g}"


def skills(raw: dict[str, Any]) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    sections = raw.get("skill") or {}
    for key, type_name in _SKILLS:
        section = sections.get(key) or {}
        descriptions: list[str] = []
        multipliers: list[tuple[str, str]] = []
        seen: set[str] = set()
        for entry in section.get("description") or []:
            name = str(entry.get("name") or "")
            desc = str(entry.get("desc") or "")
            if desc:
                cleaned = plain_text(desc).strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    descriptions.append(
                        f"<b>{html.escape(name)}</b><br>{format_markup(desc)}"
                        if name
                        else format_markup(desc)
                    )
            for param_entry in entry.get("param") or []:
                param_map = param_entry.get("param") or {}
                for value in param_map.values():
                    shown = skill_value(value)
                    if shown:
                        multipliers.append(
                            (
                                plain_text(
                                    param_entry.get("name") or "Multiplier"
                                ),
                                shown,
                            )
                        )
        if descriptions or multipliers:
            skills.append(
                SkillDetail(
                    name=type_name,
                    type_name="Combat Skill",
                    description="<br><br>".join(descriptions),
                    multipliers=multipliers,
                    level=12,
                )
            )
    return skills


def stat_name(prop: Any, recommend: dict[str, Any]) -> str:
    """Resolve a ZZZ sub-stat ID to its display name.

    The detail JSON only stores sub-stat IDs, so the base mapping is hardcoded
    from nanoka's own frontend.  Per-character main-stat names are used as a
    fallback for IDs that are not in the base map.
    """
    try:
        key = int(prop)
    except (TypeError, ValueError):
        return str(prop)

    if key in _STAT_NAMES:
        return _STAT_NAMES[key]

    for part_key in ("part_sub", "part4", "part5", "part6"):
        part = recommend.get(part_key) or {}
        try:
            if int(part.get("prop") or 0) == key and part.get("name"):
                return str(part["name"]).replace("\xa0", " ")
        except (TypeError, ValueError):
            continue

    logger.debug("Unknown ZZZ stat id %s", key)
    return f"Stat {key}"


def build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
    recommend = raw.get("fairy_recommend") or {}
    item_map = metadata.get("item") or {}

    def set_name(set_id: Any) -> str:
        if not set_id:
            return ""
        prefix = "83" + str(set_id)[1:3]
        for key, value in item_map.items():
            if str(key).startswith(prefix):
                name = value.get("name")
                if name:
                    return str(name)
        return ""

    sections: list[BuildSection] = []
    sets = []
    four = set_name(recommend.get("slot4"))
    two = set_name(recommend.get("slot2"))
    if four:
        sets.append(f"4-piece: {four}")
    if two:
        sets.append(f"2-piece: {two}")
    alternative = set_name(recommend.get("slot_sub"))
    if alternative and alternative != two:
        sets.append(f"2-piece alternative: {alternative}")
    if sets:
        sections.append(BuildSection("Drive Discs", sets))

    main_stats = []
    for slot, key in (("4", "part4"), ("5", "part5"), ("6", "part6")):
        value = recommend.get(key) or {}
        if value.get("name"):
            main_stats.append(
                f"Slot {slot}: {str(value['name']).replace(chr(160), ' ')}"
            )
    if main_stats:
        sections.append(BuildSection("Main Stats", main_stats))

    substats = [
        stat_name(prop, recommend)
        for prop in recommend.get("part_sub_list") or []
    ]
    if substats:
        sections.append(BuildSection("Substats", substats))
    return sections


def extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passive = raw.get("passive") or {}
    levels = passive.get("level") or {}
    if levels:
        last = levels[last_numeric_key(levels)] or {}
        names = last.get("name") or []
        descs = last.get("desc") or []
        entries = [
            ContentEntry(
                str(name),
                format_markup(descs[index] if index < len(descs) else ""),
            )
            for index, name in enumerate(names)
        ]
        if entries:
            extras.append(ExtraSection("Core Passive", entries))

    talents = [
        ContentEntry(
            str(item.get("name") or "Mindscape"),
            format_markup(item.get("desc") or ""),
        )
        for item in (raw.get("talent") or {}).values()
    ]
    if talents:
        extras.append(ExtraSection("Mindscapes", talents))
    return extras
