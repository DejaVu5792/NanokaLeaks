"""Honkai: Star Rail detail normalization."""

from __future__ import annotations

import re
from typing import Any

from ..detail_models import BuildSection, ContentEntry, ExtraSection, SkillDetail
from ..detail_text import (
    choose_level,
    format_markup,
    last_numeric_key,
    number,
    percent,
    plain_text,
)

_SKILL_CAPS = {
    "Basic ATK": 6,
    "Skill": 10,
    "Ultimate": 10,
    "Talent": 10,
    "Technique": 1,
}

_PROPERTY_NAMES = {
    "AttackAddedRatio": "ATK%",
    "AttackDelta": "ATK",
    "HPAddedRatio": "HP%",
    "HPDelta": "HP",
    "DefenceAddedRatio": "DEF%",
    "DefenceDelta": "DEF",
    "SpeedDelta": "SPD",
    "CriticalChanceBase": "CRIT Rate",
    "CriticalDamageBase": "CRIT DMG",
    "StatusProbabilityBase": "Effect Hit Rate",
    "StatusResistanceBase": "Effect RES",
    "BreakDamageAddedRatioBase": "Break Effect",
    "HealRatioBase": "Outgoing Healing",
    "SPRatioBase": "Energy Regen Rate",
    "PhysicalAddedRatio": "Physical DMG",
    "FireAddedRatio": "Fire DMG",
    "IceAddedRatio": "Ice DMG",
    "ThunderAddedRatio": "Lightning DMG",
    "WindAddedRatio": "Wind DMG",
    "QuantumAddedRatio": "Quantum DMG",
    "ImaginaryAddedRatio": "Imaginary DMG",
}

_RELIC_SLOTS = {
    "BODY": "Body",
    "FOOT": "Feet",
    "NECK": "Planar Sphere",
    "OBJECT": "Link Rope",
}


def fill(text: str, params: list[Any]) -> str:
    percent_flags: dict[int, bool] = {}

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            return match.group(0)
        fmt = match.group(2)
        value = params[index]
        if not isinstance(value, (int, float)):
            return str(value)
        is_percent = fmt.startswith("i") and match.string[
            match.end() : match.end() + 1
        ] == "%"
        percent_flags[index] = is_percent
        if is_percent:
            return f"{value * 100:.1f}".rstrip("0").rstrip(".")
        if fmt.startswith("f"):
            digits = int(fmt[1] or 0)
            return f"{value:.{digits}f}"
        return f"{value:g}"

    return format_markup(re.sub(r"#(\d+)\[([^\]]*)\]", replace, text or ""))


def multipliers(text: str, params: list[Any]) -> list[tuple[str, str]]:
    if not params:
        return []
    percent_flags: dict[int, bool] = {}
    for match in re.finditer(r"#(\d+)\[([^\]]*)\]", text or ""):
        index = int(match.group(1)) - 1
        if 0 <= index < len(params):
            percent_flags[index] = match.group(2).startswith("i") and text[
                match.end() : match.end() + 1
            ] == "%"
    rows = []
    for index, value in enumerate(params):
        label = f"Multiplier {index + 1}"
        if isinstance(value, (int, float)):
            if percent_flags.get(index):
                shown = f"{value * 100:.1f}".rstrip("0").rstrip(".") + "%"
            else:
                shown = f"{value:g}"
        else:
            shown = str(value)
        rows.append((label, shown))
    return rows


def points(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one representative record for each HSR skill-tree node."""
    points: list[dict[str, Any]] = []
    for node in (raw.get("skill_trees") or {}).values():
        if not isinstance(node, dict):
            continue
        if "point_name" in node:
            points.append(node)
            continue
        for entry in node.values():
            if isinstance(entry, dict) and "point_name" in entry:
                points.append(entry)
                break
    return points


def skill_caps(raw: dict[str, Any]) -> dict[str, int]:
    caps: dict[str, int] = {}
    for point in points(raw):
        level = int(point.get("max_level") or 1)
        for skill_id in point.get("level_up_skill_id") or []:
            caps[str(skill_id)] = level
    return caps


def skills(raw: dict[str, Any]) -> list[SkillDetail]:
    caps = skill_caps(raw)
    order = {"Basic ATK": 0, "Skill": 1, "Ultimate": 2, "Talent": 3, "Technique": 4}
    skills: list[SkillDetail] = []
    for skill_id, skill in (raw.get("skills") or {}).items():
        type_name = str(skill.get("type_name") or "")
        if not type_name or type_name == "None":
            continue
        cap = caps.get(str(skill_id), _SKILL_CAPS.get(type_name, 1))
        level_data = choose_level(skill.get("level") or {}, cap)
        level = int(level_data.get("level") or cap)
        params = level_data.get("param_list") or []
        skills.append(
            SkillDetail(
                name=str(skill.get("name") or "Skill"),
                type_name=type_name,
                description=fill(str(skill.get("desc") or ""), params),
                multipliers=multipliers(str(skill.get("desc") or ""), params),
                level=level,
            )
        )
    skills.sort(key=lambda item: (order.get(item.type_name, 99), item.name))
    return skills


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = raw.get("stats") or {}
    phase = stats.get(last_numeric_key(stats)) or {}
    return [
        ("HP", number((phase.get("hp_base") or 0) + (phase.get("hp_add") or 0) * 79)),
        (
            "ATK",
            number(
                (phase.get("attack_base") or 0)
                + (phase.get("attack_add") or 0) * 79
            ),
        ),
        (
            "DEF",
            number(
                (phase.get("defence_base") or 0)
                + (phase.get("defence_add") or 0) * 79
            ),
        ),
        ("SPD", number(phase.get("speed_base") or 0)),
        ("CRIT Rate", percent(phase.get("critical_chance") or 0)),
        ("CRIT DMG", percent(phase.get("critical_damage") or 0)),
    ]


def build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
    relics = raw.get("relics") or {}
    relic_sets = metadata.get("relicset") or {}
    lightcones = metadata.get("lightcone") or {}
    characters = metadata.get("characters") or {}
    sections: list[BuildSection] = []

    set_items: list[str] = []
    for set_id in relics.get("set4_id_list") or []:
        name = (relic_sets.get(str(set_id)) or {}).get("en")
        if name:
            set_items.append(f"4-piece: {name}")
    for set_id in relics.get("set2_id_list") or []:
        name = (relic_sets.get(str(set_id)) or {}).get("en")
        if name:
            set_items.append(f"2-piece: {name}")
    if set_items:
        sections.append(BuildSection("Relic Sets", set_items))

    main_stats = []
    for item in relics.get("property_list") or []:
        slot = _RELIC_SLOTS.get(
            str(item.get("relic_type")), str(item.get("relic_type"))
        )
        prop = _PROPERTY_NAMES.get(
            str(item.get("property_type")), plain_text(item.get("property_type"))
        )
        main_stats.append(f"{slot}: {prop}")
    if main_stats:
        sections.append(BuildSection("Main Stats", main_stats))

    substats = [
        _PROPERTY_NAMES.get(str(prop), plain_text(prop))
        for prop in relics.get("sub_affix_property_list") or []
    ]
    if substats:
        sections.append(BuildSection("Substats", substats))

    cone_items = []
    for cone_id in raw.get("lightcones") or []:
        name = (lightcones.get(str(cone_id)) or {}).get("en")
        if name:
            cone_items.append(name)
    if cone_items:
        sections.append(BuildSection("Light Cones", cone_items))

    team_items = []
    for index, team in enumerate((raw.get("teams") or [])[:3], start=1):
        members = []
        for member_id in team.get("member_list") or []:
            name = (characters.get(str(member_id)) or {}).get("en")
            members.append(name or str(member_id))
        if members:
            team_items.append(f"Team {index}: {' / '.join(members)}")
    if team_items:
        sections.append(BuildSection("Teams", team_items))
    return sections


def extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    traces: list[ContentEntry] = []
    stat_totals: dict[str, float] = {}
    for point in points(raw):
        name = point.get("point_name")
        desc = point.get("point_desc")
        if name and desc:
            traces.append(
                ContentEntry(
                    str(name),
                    fill(str(desc), point.get("param_list") or []),
                )
            )
            continue
        for status in point.get("status_add_list") or []:
            prop = _PROPERTY_NAMES.get(
                str(status.get("property_type")), plain_text(status.get("name"))
            )
            try:
                value = float(status.get("value") or 0)
            except (TypeError, ValueError):
                continue
            if not prop or not value:
                continue
            stat_totals[prop] = stat_totals.get(prop, 0.0) + value
    for prop, total in stat_totals.items():
        is_percent = prop.endswith("%") or any(
            token in prop for token in ("Rate", "DMG", "Effect", "Healing")
        )
        shown = f"{total * 100:.1f}%" if is_percent else number(total, 1)
        traces.append(ContentEntry(prop, f"+{shown}"))
    if traces:
        extras.append(ExtraSection("Traces", traces))

    eidolons = []
    for rank in (raw.get("ranks") or {}).values():
        if rank.get("name") and rank.get("desc"):
            params = rank.get("param_list") or []
            eidolons.append(
                ContentEntry(
                    str(rank["name"]),
                    fill(str(rank["desc"]), params),
                )
            )
    if eidolons:
        extras.append(ExtraSection("Eidolons", eidolons))
    return extras
