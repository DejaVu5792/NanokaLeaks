"""Neverness to Everness detail normalization."""

from __future__ import annotations

import html
from typing import Any

from ..detail_models import ContentEntry, ExtraSection, SkillDetail
from ..detail_text import format_markup, number, plain_text


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = []
    for item in raw.get("stats") or []:
        values = item.get("values") or []
        if not values:
            continue
        name = str(item.get("name") or "Stat")
        value = values[-1]
        if any(token in name.lower() for token in ("rate", "dmg", "bonus")):
            shown = f"{value}%"
        else:
            shown = number(value)
        stats.append((name, shown))
    return stats


def skills(raw: dict[str, Any]) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    for ability in raw.get("abilities") or []:
        if not ability.get("show_detail_info", True):
            continue
        phases = []
        for phase in ability.get("phases") or []:
            name = plain_text(phase.get("name") or "")
            desc = format_markup(phase.get("desc") or "")
            if desc:
                phases.append(
                    f"<b>{html.escape(name)}</b><br>{desc}" if name else desc
                )
        multipliers = []
        for row in ability.get("param_rows") or []:
            values = row.get("values") or []
            if not values:
                continue
            index = min(9, len(values) - 1)
            multipliers.append(
                (str(row.get("label") or "Multiplier"), str(values[index]))
            )
        if phases or multipliers:
            skills.append(
                SkillDetail(
                    name=str(ability.get("name") or "Ability"),
                    type_name=str(ability.get("type_name") or "Ability"),
                    description="<br><br>".join(phases),
                    multipliers=multipliers,
                    level=10,
                )
            )
    return skills


def extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passives: list[ContentEntry] = []
    for ability in raw.get("abilities") or []:
        if ability.get("show_detail_info", True):
            continue
        parts = []
        for phase in ability.get("phases") or []:
            name = plain_text(phase.get("name") or "")
            desc = format_markup(phase.get("desc") or "")
            if desc:
                parts.append(
                    f"<b>{html.escape(name)}</b><br>{desc}" if name else desc
                )
        if parts:
            passives.append(
                ContentEntry(
                    str(ability.get("name") or "Passive"),
                    "<br><br>".join(parts),
                )
            )
    if passives:
        extras.append(ExtraSection("Passives", passives))

    awaken = [
        ContentEntry(
            str(item.get("name") or "Awakening"),
            format_markup(item.get("desc") or ""),
        )
        for item in raw.get("awaken") or []
    ]
    if awaken:
        extras.append(ExtraSection("Awakenings", awaken))
    resonance = [
        ContentEntry(
            str(item.get("name") or "Resonance"),
            format_markup(item.get("desc") or ""),
        )
        for item in raw.get("resonance") or []
    ]
    if resonance:
        extras.append(ExtraSection("Resonance", resonance))
    return extras
