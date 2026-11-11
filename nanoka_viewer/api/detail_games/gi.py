"""Genshin Impact detail normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..detail_models import ContentEntry, ExtraSection, SkillDetail
from ..detail_text import format_markup, number, percent, plain_text
from ..detail_text import linked_term_ids as _linked_term_ids

_TERM_SOURCES = ("name", "desc", "skills", "passives", "constellations")


def linked_term_ids(raw: dict[str, Any]) -> list[str]:
    """Return rule-term ids referenced by the text the pane displays."""
    return _linked_term_ids(
        *(raw.get(key) for key in _TERM_SOURCES), game="gi"
    )


def linked_terms(
    raw: dict[str, Any], hyperlinks: dict[str, Any]
) -> list[ContentEntry]:
    """Build the Rule Terms card from the shared ``hyperlink.json`` table."""
    if not isinstance(hyperlinks, dict):
        return []
    pending = linked_term_ids(raw)
    seen: set[str] = set()
    resolved: list[tuple[str, str, str]] = []
    while pending:
        term_id = pending.pop(0)
        if term_id in seen:
            continue
        seen.add(term_id)
        entry = hyperlinks.get(term_id) or hyperlinks.get(f"N{term_id}")
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        description = str(entry.get("desc") or "")
        for index, value in enumerate(entry.get("param") or []):
            description = description.replace(f"{{{index}}}", str(value))
        if name or description:
            resolved.append((term_id, name, description))
        for linked_id in _linked_term_ids(description, game="gi"):
            if linked_id not in seen:
                pending.append(linked_id)
    names = {term_id: name for term_id, name, _ in resolved}
    return [
        ContentEntry(
            name,
            format_markup(description, term_names=names),
            term_id=term_id,
        )
        for term_id, name, description in resolved
    ]


def fill(text: str, params: list[Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            return match.group(0)
        value = params[index]
        fmt = match.group(2)
        if not isinstance(value, (int, float)):
            return str(value)
        if fmt.endswith("P"):
            digits = 1
            if fmt.startswith("F") and len(fmt) > 1 and fmt[1].isdigit():
                digits = int(fmt[1])
            return f"{value * 100:.{digits}f}%"
        if fmt.startswith("F"):
            digits = int(fmt[1] or 0) if len(fmt) > 1 else 0
            return f"{value:.{digits}f}"
        return f"{value:g}"

    return re.sub(r"\{param(\d+):([^}]+)\}", replace, text or "")


def skill_parts(entry: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    rows: list[tuple[str, str]] = []
    for line in entry.get("desc") or []:
        if not line:
            continue
        if "|" in line:
            label, template = line.split("|", 1)
        else:
            label, template = "Effect", line
        rows.append((plain_text(label), fill(template, entry.get("param") or [])))
    return "\n".join(f"{label}: {value}" for label, value in rows), rows


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    modifier = raw.get("stats_modifier") or {}
    ascension = (modifier.get("ascension") or [{}])[-1]
    hp_mult = (modifier.get("hp") or {}).get("90", 0)
    atk_mult = (modifier.get("atk") or {}).get("90", 0)
    def_mult = (modifier.get("def") or {}).get("90", 0)
    return [
        (
            "HP",
            number(
                (raw.get("base_hp") or 0) * hp_mult
                + (ascension.get("fight_prop_base_hp") or 0)
            ),
        ),
        (
            "ATK",
            number(
                (raw.get("base_atk") or 0) * atk_mult
                + (ascension.get("fight_prop_base_attack") or 0)
            ),
        ),
        (
            "DEF",
            number(
                (raw.get("base_def") or 0) * def_mult
                + (ascension.get("fight_prop_base_defense") or 0)
            ),
        ),
        ("CRIT Rate", percent(raw.get("crit_rate") or 0)),
        (
            "CRIT DMG",
            percent(
                (raw.get("crit_dmg") or 0)
                + (ascension.get("fight_prop_critical_hurt") or 0)
            ),
        ),
        ("Elemental Mastery", number(raw.get("elemental_mastery") or 0)),
    ]


def skills(
    raw: dict[str, Any], term_names: Mapping[str, str] | None = None
) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    skill_icons_seen = 0
    for skill in raw.get("skills") or []:
        promotes = skill.get("promote") or {}
        # Genshin's promote keys are zero-based while their level field starts
        # at one.  Pick the highest entry that is still F2P talent level 10.
        entries = sorted(
            (entry for entry in promotes.values() if isinstance(entry, dict)),
            key=lambda entry: int(entry.get("level") or 0),
        )
        entry = {}
        for candidate in entries:
            if int(candidate.get("level") or 0) <= 10:
                entry = candidate
        description, rows = skill_parts(entry)
        icon = str(entry.get("icon") or skill.get("icon") or "")
        if "_A_" in icon:
            type_name = "Normal Attack"
        elif "_E_" in icon:
            type_name = "Elemental Burst"
        elif "_S_" in icon:
            skill_icons_seen += 1
            type_name = (
                "Elemental Skill" if skill_icons_seen == 1 else "Alternate Sprint"
            )
        else:
            type_name = "Talent"
        skills.append(
            SkillDetail(
                name=str(skill.get("name") or "Talent"),
                type_name=type_name,
                description=format_markup(
                    skill.get("desc") or description, term_names=term_names
                ),
                multipliers=rows,
                level=10,
            )
        )
    return skills


def extras(
    raw: dict[str, Any], term_names: Mapping[str, str] | None = None
) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passives = [
        ContentEntry(
            str(item.get("name") or "Passive"),
            format_markup(item.get("desc") or "", term_names=term_names),
        )
        for item in raw.get("passives") or []
    ]
    if passives:
        extras.append(ExtraSection("Passives", passives))
    constellations = [
        ContentEntry(
            str(item.get("name") or "Constellation"),
            format_markup(item.get("desc") or "", term_names=term_names),
        )
        for item in raw.get("constellations") or []
    ]
    if constellations:
        extras.append(ExtraSection("Constellations", constellations))
    return extras
