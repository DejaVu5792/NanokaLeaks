"""Game-markup conversion and small numeric formatting helpers.

Every per-game normalizer feeds its raw text through the same two functions
(``format_markup`` / ``plain_text``) and formats numbers the same way, so they
live here instead of being duplicated in each game module.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator, Mapping
from typing import Any

from .constants import BASE_URL

# Every game marks cross-references in its own way.  The details pane turns
# rule-term links into anchors (``term:<id>``) so QML can jump to the matching
# entry in the Rule Terms card; non-term links keep their visible text but lose
# the wrapper.  The patterns are deliberately shared by all normalizers.
_GI_LINK_RE = re.compile(r"\{LINK#([A-Za-z]*)([^{}]*)\}(.*?)\{/LINK\}", re.S)
_GI_LINK_TAG_RE = re.compile(r"\{LINK#[^}]*\}|\{/LINK\}")

_WW_TAG_RE = re.compile(r"<(te|a)\b([^>]*)>(.*?)</\1>", re.S | re.I)
_HREF_RE = re.compile(
    r"\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.I
)

_ZZZ_TERM_PAIR_RE = re.compile(
    r"<Term:(\d+)>(.*?)(?:</Term>|<\\Term>)", re.S | re.I
)
_ZZZ_TERM_OPEN_RE = re.compile(r"<Term:(\d+)>", re.I)
_ZZZ_TERM_CLOSE_RE = re.compile(r"</Term>|<\\Term>", re.I)

_NTE_HOT_OPEN_RE = re.compile(r"<hot\b([^>]*)>", re.I)

_GI_TERM_ID_RE = re.compile(r"\{LINK#N(\d+)\}")
_WW_TERM_ID_RE = re.compile(
    r"<te\b[^>]*\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.I
)
_WW_ANCHOR_TERM_ID_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*(?:\"(\d+)\"|'(\d+)'|(\d+))", re.I
)
_ZZZ_TERM_ID_RE = re.compile(r"<Term:(\d+)>", re.I)
_NTE_TERM_ID_RE = re.compile(
    r"<hot\b[^>]*\bparam\s*=\s*(?:\"nouns&([^\"]+)\"|'nouns&([^']+)')",
    re.I,
)

_TERM_ID_PATTERNS = {
    "gi": (_GI_TERM_ID_RE,),
    "ww": (_WW_TERM_ID_RE, _WW_ANCHOR_TERM_ID_RE),
    "zzz": (_ZZZ_TERM_ID_RE,),
    "nte": (_NTE_TERM_ID_RE,),
}

_TERM_LINK_COLOR = "#7ec8ff"

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


def iter_strings(value: Any) -> Iterator[str]:
    """Yield every string inside a nested JSON-like value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_strings(item)


def _first_group(match: re.Match[str]) -> str:
    return next((group for group in match.groups() if group is not None), "")


def linked_term_ids(*values: Any, game: str) -> list[str]:
    """Return term ids referenced by *values*, in first-appearance order."""
    patterns = _TERM_ID_PATTERNS.get(game, ())
    ids: list[str] = []
    for value in values:
        for text in iter_strings(value):
            for pattern in patterns:
                for match in pattern.finditer(text):
                    term_id = _first_group(match).strip()
                    if term_id and term_id not in ids:
                        ids.append(term_id)
    return ids


def _term_anchor(
    term_id: str, body: str, term_names: Mapping[str, str] | None
) -> str:
    """Render a term link, or only its visible text when it is unknown."""
    term_id = str(term_id).strip()
    if not term_id:
        return body
    name = term_names.get(term_id) if term_names is not None else None
    if term_names is not None and name is None:
        return body
    if not body.strip():
        body = name or term_id
    if not body:
        return ""
    href = html.escape(f"term:{term_id}", quote=True)
    return f'<a href="{href}">{body}</a>'


def _replace_gi_links(source: str, term_names: Mapping[str, str] | None) -> str:
    def replace(match: re.Match[str]) -> str:
        kind, term_id, body = match.groups()
        if kind.upper() == "N":
            return _term_anchor(term_id, body, term_names)
        return body

    source = _GI_LINK_RE.sub(replace, source)
    return _GI_LINK_TAG_RE.sub("", source)


def _replace_ww_links(source: str, term_names: Mapping[str, str] | None) -> str:
    def replace(match: re.Match[str]) -> str:
        tag, attributes, body = match.groups()
        href_match = _HREF_RE.search(attributes)
        href = _first_group(href_match).strip() if href_match else ""
        if href.startswith("term:"):
            # Already converted by another game's pass; leave the anchor alone.
            return match.group(0)
        if tag.lower() == "a" and not href.isdigit():
            return body
        return _term_anchor(href, body, term_names)

    return _WW_TAG_RE.sub(replace, source)


def _replace_zzz_links(source: str, term_names: Mapping[str, str] | None) -> str:
    source = _ZZZ_TERM_PAIR_RE.sub(
        lambda match: _term_anchor(match.group(1), match.group(2), term_names),
        source,
    )
    source = _ZZZ_TERM_OPEN_RE.sub(
        lambda match: _term_anchor(match.group(1), "", term_names), source
    )
    return _ZZZ_TERM_CLOSE_RE.sub("", source)


def _replace_nte_links(source: str, term_names: Mapping[str, str] | None) -> str:
    def replace(match: re.Match[str]) -> str:
        attributes = match.group(1)
        param_match = re.search(
            r"\bparam\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", attributes, re.I
        )
        if param_match is None:
            return match.group(0)
        param = _first_group(param_match)
        if not param.startswith("nouns&"):
            return match.group(0)
        key = param.split("&", 1)[1].strip()
        if not key:
            return "<span>"
        if term_names is not None and key not in term_names:
            # The body still needs an ordinary wrapper for its closing ``</>``.
            return "<span>"
        href = html.escape(f"term:{key}", quote=True)
        return f'<a href="{href}">'

    return _NTE_HOT_OPEN_RE.sub(replace, source)


def format_markup(
    text: Any, *, term_names: Mapping[str, str] | None = None
) -> str:
    """Convert game markup into a small safe subset of Qt rich text.

    Passing *term_names* restricts anchors to the terms that actually have a
    card entry, so a link can never point at something the pane does not show.
    """
    if text is None:
        return ""
    source = str(text)
    source = source.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    source = _replace_gi_links(source, term_names)
    source = _replace_ww_links(source, term_names)
    source = _replace_zzz_links(source, term_names)
    source = _replace_nte_links(source, term_names)
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
            elif low == "a" or low.startswith("a "):
                match = _HREF_RE.search(tag)
                href = _first_group(match) if match else ""
                if href.startswith("term:"):
                    safe_href = html.escape(href, quote=True)
                    output.append(
                        f'<a href="{safe_href}" '
                        f'style="color:{_TERM_LINK_COLOR}; '
                        f'text-decoration:underline">'
                    )
                    stack.append("a")
                else:
                    stack.append(None)
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
    return _GI_LINK_TAG_RE.sub("", re.sub(r"<[^>]*>", "", str(text or "")))


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
