"""Game-markup conversion and small numeric formatting helpers.

Every per-game normalizer feeds its raw text through the same two functions
(``format_markup`` / ``plain_text``) and formats numbers the same way, so they
live here instead of being duplicated in each game module.
"""

from __future__ import annotations

import html
import re
from typing import Any

from .constants import BASE_URL

_COLOR_NAMES = {
    "title": "#e0c068",
    "highlight": "#ffd166",
    "ice": "#7ec8ff",
    "fire": "#ff8066",
    "thunder": "#c792ea",
    "wind": "#7bd88f",
    "light": "#ffe082",
    "dark": "#b388ff",
}


def format_markup(text: Any) -> str:
    """Convert game markup into a small safe subset of Qt rich text."""
    if text is None:
        return ""
    source = str(text)
    source = source.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []
    stack: list[str | None] = []

    for token in re.split(r"(<[^>]*>)", source):
        if not token:
            continue
        if token.startswith("<") and token.endswith(">"):
            tag = token[1:-1].strip()
            if tag.startswith("/"):
                if stack:
                    closing = stack.pop()
                    if closing:
                        output.append(f"</{closing}>")
                continue

            low = tag.lower()
            if low.startswith("color="):
                colour = tag.split("=", 1)[1].strip().strip("\"'")
                if colour.startswith("#"):
                    colour = "#" + colour[1:7]
                else:
                    colour = _COLOR_NAMES.get(colour.lower(), "#c8c8c8")
                output.append(f'<span style="color:{colour}">')
                stack.append("span")
            elif low in {"title", "b", "bold"}:
                output.append("<b>")
                stack.append("b")
            elif low in {"italic", "i"}:
                output.append("<i>")
                stack.append("i")
            elif low in {"u", "underline"}:
                output.append("<u>")
                stack.append("u")
            elif low.startswith(("numgreen", "zhou", "hot")):
                colour = "#7bd88f" if low.startswith("numgreen") else "#c792ea"
                output.append(f'<span style="color:{colour}">')
                stack.append("span")
            else:
                stack.append(None)
            continue

        escaped = html.escape(token).replace("\n", "<br>")
        output.append(escaped)

    while stack:
        closing = stack.pop()
        if closing:
            output.append(f"</{closing}>")
    return "".join(output)


def plain_text(text: Any) -> str:
    """Remove game markup for compact labels."""
    return re.sub(r"<[^>]*>", "", str(text or ""))


def number(value: Any, decimals: int = 0) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{numeric:,.0f}"
    return f"{numeric:,.{decimals}f}"


def percent(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return str(value)


def last_numeric_key(mapping: dict[str, Any]) -> str:
    keys = [key for key in mapping if str(key).lstrip("-").isdigit()]
    return max(keys, key=lambda key: int(key)) if keys else ""


def choose_level(mapping: dict[str, Any], cap: int) -> dict[str, Any]:
    keys = sorted(int(key) for key in mapping if str(key).isdigit())
    if not keys:
        return {}
    selected = cap if cap in keys else max(
        (key for key in keys if key <= cap), default=keys[0]
    )
    return mapping.get(str(selected), {})


def art_url(game: str, char_id: str, raw: dict[str, Any]) -> str:
    if game == "hsr":
        return f"{BASE_URL}/assets/hsr/avatardrawcard/{char_id}.webp"
    if game == "gi":
        icon = str(raw.get("icon", ""))
        if icon.startswith("UI_AvatarIcon_"):
            suffix = icon.removeprefix("UI_AvatarIcon_")
            return f"{BASE_URL}/assets/gi/UI_Gacha_AvatarImg_{suffix}.webp"
        return f"{BASE_URL}/assets/gi/{icon}.webp"
    if game == "ww":
        background = str(
            raw.get("background")
            or raw.get("background_stand")
            or raw.get("icon")
            or ""
        )
        path = background.replace("/Game/Aki/UI/", "").split(".")[0]
        path = path.removeprefix("/")
        return f"{BASE_URL}/assets/ww/{path}.webp"
    if game == "zzz":
        return f"{BASE_URL}/assets/zzz/{raw.get('icon', '')}.webp"
    if game == "nte":
        icon = str(raw.get("icon_gacha") or raw.get("icon") or "")
        if not icon.startswith("/"):
            icon = "/" + icon
        return f"{BASE_URL}/assets/nte{icon}.webp"
    return ""
