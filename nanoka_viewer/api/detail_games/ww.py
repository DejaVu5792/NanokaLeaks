"""Wuthering Waves detail normalization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..detail_models import BuildSection, ContentEntry, ExtraSection, SkillDetail
from ..detail_text import format_markup, last_numeric_key, number, plain_text
from ..detail_text import linked_term_ids as _linked_term_ids

_TERM_SOURCES = ("desc", "skill_trees", "chains")


def linked_term_ids(raw: dict[str, Any]) -> list[str]:
    """Return term ids referenced by the text the pane displays."""
    return _linked_term_ids(
        *(raw.get(key) for key in _TERM_SOURCES), game="ww"
    )


def linked_terms(
    raw: dict[str, Any], hyperlinks: dict[str, Any]
) -> list[ContentEntry]:
    """Build the Rule Terms card from WW's shared ``hyperlink.json`` table."""
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
        entry = hyperlinks.get(term_id)
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("title") or "")
        description = str(entry.get("desc") or "")
        for index, value in enumerate(entry.get("param") or []):
            description = description.replace(f"{{{index}}}", str(value))
        if name or description:
            resolved.append((term_id, name, description))
        for linked_id in _linked_term_ids(description, game="ww"):
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


def fill(
    text: str,
    params: list[Any],
    term_names: Mapping[str, str] | None = None,
) -> str:
    for index, value in enumerate(params or []):
        text = text.replace(f"{{{index}}}", str(value))
    return format_markup(text, term_names=term_names)


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = raw.get("stats") or {}
    phase = stats.get(last_numeric_key(stats)) or {}
    level = phase.get(last_numeric_key(phase)) or {}
    return [
        ("HP", number(level.get("life") or 0)),
        ("ATK", number(level.get("atk") or 0)),
        ("DEF", number(level.get("def") or 0)),
    ]


def skills(
    raw: dict[str, Any], term_names: Mapping[str, str] | None = None
) -> tuple[list[SkillDetail], list[ExtraSection]]:
    skills: list[SkillDetail] = []
    inherent: list[ContentEntry] = []
    trees = raw.get("skill_trees") or {}
    for node_key in sorted(
        trees, key=lambda key: int(key) if str(key).isdigit() else 999
    ):
        node = trees[node_key] or {}
        skill = node.get("skill") or {}
        name = str(skill.get("name") or "Skill")
        type_name = str(skill.get("type") or "Skill")
        levels = skill.get("level") or {}
        if levels:
            rows: list[tuple[str, str]] = []
            for row in levels.values():
                params = row.get("param") or []
                values = []
                for value_list in params:
                    if not value_list:
                        continue
                    index = min(9, len(value_list) - 1)
                    values.append(str(value_list[index]))
                value = " / ".join(values)
                fmt = row.get("format")
                if fmt and value:
                    try:
                        value = fmt.format(value)
                    except (IndexError, KeyError, ValueError):
                        pass
                if value:
                    rows.append(
                        (plain_text(row.get("name") or "Multiplier"), value)
                    )
            skills.append(
                SkillDetail(
                    name=name,
                    type_name=type_name,
                    description=fill(
                        str(skill.get("desc") or ""),
                        skill.get("param") or [],
                        term_names,
                    ),
                    multipliers=rows,
                    level=10,
                )
            )
        elif skill.get("desc"):
            inherent.append(
                ContentEntry(
                    name,
                    fill(str(skill["desc"]), [], term_names),
                )
            )
    extras = []
    if inherent:
        extras.append(ExtraSection("Inherent Skills", inherent))
    chains = [
        ContentEntry(
            str(chain.get("name") or "Sequence"),
            fill(
                str(chain.get("desc") or ""),
                chain.get("param") or [],
                term_names,
            ),
        )
        for chain in (raw.get("chains") or {}).values()
    ]
    if chains:
        extras.append(ExtraSection("Sequences", chains))
    return skills, extras


def build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
    recommend = raw.get("recommend") or {}
    weapons = metadata.get("weapon") or {}
    items = []
    for weapon_id in recommend.get("weapon") or []:
        name = (weapons.get(str(weapon_id)) or {}).get("en")
        if name:
            items.append(name)
    return [BuildSection("Recommended Weapons", items)] if items else []
