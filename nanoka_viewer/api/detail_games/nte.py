"""Neverness to Everness detail normalization."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any

from ..detail_models import ContentEntry, ExtraSection, SkillDetail
from ..detail_text import format_markup, number, plain_text
from ..detail_text import linked_term_ids as _linked_term_ids

_TERM_SOURCES = ("desc", "abilities", "awaken", "resonance")


def _normalize_key(value: Any) -> str:
    return re.sub(r"[_\s-]", "", str(value or "")).lower()


def _lookup_noun(nouns: dict[str, Any], key: str) -> dict[str, Any] | None:
    entry = nouns.get(key)
    if isinstance(entry, dict):
        return entry
    wanted = _normalize_key(key)
    for table_key, value in nouns.items():
        if not isinstance(value, dict):
            continue
        if _normalize_key(table_key) == wanted or _normalize_key(
            value.get("id")
        ) == wanted:
            return value
    return None


def linked_term_ids(raw: dict[str, Any]) -> list[str]:
    """Return noun keys referenced by the text the pane displays."""
    return _linked_term_ids(
        *(raw.get(key) for key in _TERM_SOURCES), game="nte"
    )


def linked_terms(raw: dict[str, Any]) -> list[ContentEntry]:
    """Build the Rule Terms card from NTE's embedded ``nouns`` table."""
    nouns = raw.get("nouns") or {}
    if not isinstance(nouns, dict):
        return []
    pending = linked_term_ids(raw)
    seen: set[str] = set()
    resolved: list[tuple[str, str, str]] = []
    while pending:
        term_id = pending.pop(0)
        if term_id in seen:
            continue
        seen.add(term_id)
        entry = _lookup_noun(nouns, term_id)
        if entry is None:
            continue
        name = str(entry.get("title") or entry.get("name") or term_id)
        description = str(
            entry.get("desc")
            or entry.get("description")
            or entry.get("explanation")
            or ""
        )
        if name or description:
            resolved.append((term_id, name, description))
        for linked_id in _linked_term_ids(description, game="nte"):
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


def skills(
    raw: dict[str, Any], term_names: Mapping[str, str] | None = None
) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    for ability in raw.get("abilities") or []:
        if not ability.get("show_detail_info", True):
            continue
        phases = []
        for phase in ability.get("phases") or []:
            name = plain_text(phase.get("name") or "")
            desc = format_markup(
                phase.get("desc") or "", term_names=term_names
            )
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


def extras(
    raw: dict[str, Any], term_names: Mapping[str, str] | None = None
) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passives: list[ContentEntry] = []
    for ability in raw.get("abilities") or []:
        if ability.get("show_detail_info", True):
            continue
        parts = []
        for phase in ability.get("phases") or []:
            name = plain_text(phase.get("name") or "")
            desc = format_markup(
                phase.get("desc") or "", term_names=term_names
            )
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
            format_markup(item.get("desc") or "", term_names=term_names),
        )
        for item in raw.get("awaken") or []
    ]
    if awaken:
        extras.append(ExtraSection("Awakenings", awaken))
    resonance = [
        ContentEntry(
            str(item.get("name") or "Resonance"),
            format_markup(item.get("desc") or "", term_names=term_names),
        )
        for item in raw.get("resonance") or []
    ]
    if resonance:
        extras.append(ExtraSection("Resonance", resonance))
    return extras
