"""Wuthering Waves detail normalization."""

from __future__ import annotations

from typing import Any

from ..detail_models import BuildSection, ContentEntry, ExtraSection, SkillDetail
from ..detail_text import format_markup, last_numeric_key, number, plain_text


def fill(text: str, params: list[Any]) -> str:
    for index, value in enumerate(params or []):
        text = text.replace(f"{{{index}}}", str(value))
    return format_markup(text)


def stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = raw.get("stats") or {}
    phase = stats.get(last_numeric_key(stats)) or {}
    level = phase.get(last_numeric_key(phase)) or {}
    return [
        ("HP", number(level.get("life") or 0)),
        ("ATK", number(level.get("atk") or 0)),
        ("DEF", number(level.get("def") or 0)),
    ]


def skills(raw: dict[str, Any]) -> tuple[list[SkillDetail], list[ExtraSection]]:
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
                        str(skill.get("desc") or ""), skill.get("param") or []
                    ),
                    multipliers=rows,
                    level=10,
                )
            )
        elif skill.get("desc"):
            inherent.append(ContentEntry(name, fill(str(skill["desc"]), [])))
    extras = []
    if inherent:
        extras.append(ExtraSection("Inherent Skills", inherent))
    chains = [
        ContentEntry(
            str(chain.get("name") or "Sequence"),
            fill(str(chain.get("desc") or ""), chain.get("param") or []),
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
