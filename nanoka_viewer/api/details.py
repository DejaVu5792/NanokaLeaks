"""Character detail loading and normalization with in-memory caching.

The main character list is cached by :mod:`nanoka_viewer.api.characters`.
Character details and build metadata are cached in memory by (game, version, char_id)
so subsequent opens of viewed characters are near-instant and do not hit the network.
Shift+Reload clears all caches including this in-memory detail cache.
This module also normalizes the five game-specific detail formats into one model
consumed by the native detail popup.
"""

from __future__ import annotations

import copy
import hashlib
import pickle
import html
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from requests.adapters import HTTPAdapter

from .constants import BASE_URL, CACHE_DIR
from .manifest import get_latest_version
from .models import get_character_url, get_name
from ..settings import get_setting

DETAIL_CACHE_DIR = CACHE_DIR / "details"
DETAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

METADATA_CACHE_DIR = CACHE_DIR / "details_metadata"
METADATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DETAIL_ART_CACHE_DIR = CACHE_DIR / "details_art"
DETAIL_ART_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory caches.  These are always used for the current session; the settings
# below decide whether the same data is also persisted to disk.
_detail_cache: dict[tuple[str, str, str], CharacterDetail] = {}
_metadata_cache: dict[tuple[str, str, str], Any] = {}
_art_cache: dict[str, bytes] = {}

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "NanokaLeaks/4.1",
}

_DETAIL_TIMEOUT = 25

# Shared persistent session for warm HTTP/2 & keep-alive connection reuse
_session = requests.Session()
_session.headers.update(_DEFAULT_HEADERS)
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

def clear_detail_cache():
    """Clear in-memory and disk cached character details, metadata, and artwork."""
    global _detail_cache, _metadata_cache, _art_cache
    _detail_cache.clear()
    _metadata_cache.clear()
    _art_cache.clear()

    for directory in (DETAIL_CACHE_DIR, METADATA_CACHE_DIR, DETAIL_ART_CACHE_DIR):
        try:
            if directory.exists():
                for item in directory.iterdir():
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        import shutil

                        shutil.rmtree(item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not clear cache directory %s: %s", directory, exc)

    logger.info("Character detail, metadata, and artwork cache cleared")


class DetailUnavailable(Exception):
    """Raised when nanoka has no detail page for a character yet."""


@dataclass
class BuildSection:
    """A group of compact recommended-build lines."""

    title: str
    items: list[str] = field(default_factory=list)


@dataclass
class SkillDetail:
    """A single skill with its max-level description and multipliers."""

    name: str
    type_name: str
    description: str
    multipliers: list[tuple[str, str]] = field(default_factory=list)
    level: int = 1


@dataclass
class ContentEntry:
    """A named passive, trace, constellation, or similar overview entry."""

    name: str
    text: str


@dataclass
class ExtraSection:
    """A collapsed overview section such as passives or mindscapes."""

    title: str
    entries: list[ContentEntry] = field(default_factory=list)


@dataclass
class BuildContext:
    """Transient data needed to load a recommended build later."""

    game: str
    version: str
    raw: dict[str, Any] = field(repr=False, compare=False)


@dataclass
class CharacterDetail:
    """Normalized character detail data for the native popup."""

    game: str
    char_id: str
    name: str
    subtitle: str
    overview: str
    level_label: str
    badges: list[str] = field(default_factory=list)
    stats: list[tuple[str, str]] = field(default_factory=list)
    build: list[BuildSection] = field(default_factory=list)
    skills: list[SkillDetail] = field(default_factory=list)
    extras: list[ExtraSection] = field(default_factory=list)
    art_url: str = ""
    source_url: str = ""
    build_context: BuildContext | None = field(
        default=None, repr=False, compare=False
    )


# ---------------------------------------------------------------------------
# Network helpers


def _get_json(url: str) -> Any:
    response = _session.get(url, timeout=_DETAIL_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _safe_json(url: str) -> Any:
    try:
        return _get_json(url)
    except Exception as exc:  # noqa: BLE001 - supporting data is optional
        logger.warning("Could not fetch detail metadata %s: %s", url, exc)
        return None


def _get_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        response = _session.get(url, timeout=_DETAIL_TIMEOUT)
        response.raise_for_status()
        return response.content
    except Exception as exc:  # noqa: BLE001 - art is optional
        logger.warning("Could not fetch character art %s: %s", url, exc)
        return None


def load_character_art(url: str) -> bytes | None:
    """Fetch character art separately so text never waits for the image.

    Artwork is always cached in memory for the current session.  Disk caching
    is controlled by the ``cache_character_artwork`` setting.
    """
    if not url:
        return None

    caching = get_setting("cache_character_artwork")

    if url in _art_cache:
        return _art_cache[url]

    if caching:
        cache_file = DETAIL_ART_CACHE_DIR / f"{hashlib.md5(url.encode()).hexdigest()}.bin"
        if cache_file.exists():
            try:
                data = cache_file.read_bytes()
                _art_cache[url] = data
                return data
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read cached artwork %s: %s", cache_file, exc)

    data = _get_bytes(url)
    if data is not None:
        _art_cache[url] = data
        if caching:
            cache_file = DETAIL_ART_CACHE_DIR / f"{hashlib.md5(url.encode()).hexdigest()}.bin"
            try:
                cache_file.write_bytes(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not write cached artwork %s: %s", cache_file, exc)
    return data


def _latest_version(game: str) -> str:
    """Resolve the current latest version without using a detail cache."""
    try:
        manifest = _get_json(f"{BASE_URL}/manifest.json")
        return str(manifest[game]["latest"])
    except Exception as exc:  # noqa: BLE001 - fall back to the app's manifest
        logger.warning("Could not fetch a fresh manifest: %s", exc)
        return str(get_latest_version(game))


def _metadata_disk_path(cache_key: tuple[str, str, str]) -> Path:
    game, version, resource_name = cache_key
    digest = hashlib.sha256(f"{game}:{version}:{resource_name}".encode()).hexdigest()
    return METADATA_CACHE_DIR / f"{digest}.pkl"


def _fetch_metadata_file(game: str, version: str, resource_name: str, url: str) -> Any:
    cache_key = (game, version, resource_name)
    caching = get_setting("cache_character_builds")

    if cache_key in _metadata_cache:
        return _metadata_cache[cache_key]

    if caching:
        disk_path = _metadata_disk_path(cache_key)
        if disk_path.exists():
            try:
                with disk_path.open("rb") as handle:
                    data = pickle.load(handle)
                _metadata_cache[cache_key] = data
                return data
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read cached metadata %s: %s", disk_path, exc)
                try:
                    disk_path.unlink()
                except OSError:
                    pass

    data = _safe_json(url)
    if data is not None:
        _metadata_cache[cache_key] = data
        if caching:
            disk_path = _metadata_disk_path(cache_key)
            try:
                with disk_path.open("wb") as handle:
                    pickle.dump(data, handle)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not write cached metadata %s: %s", disk_path, exc)
    return data


def _fetch_metadata(game: str, version: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Fetch only the small metadata files needed for a recommended build."""
    if game == "hsr" and any(
        raw.get(key) for key in ("relics", "lightcones", "teams")
    ):
        return {
            "relicset": _fetch_metadata_file(game, version, "relicset", f"{BASE_URL}/hsr/{version}/relicset.json"),
            "lightcone": _fetch_metadata_file(game, version, "lightcone", f"{BASE_URL}/hsr/{version}/lightcone.json"),
            "characters": _fetch_metadata_file(game, version, "character", f"{BASE_URL}/hsr/{version}/character.json"),
        }
    if game == "ww" and (raw.get("recommend") or {}).get("weapon"):
        return {"weapon": _fetch_metadata_file(game, version, "weapon", f"{BASE_URL}/ww/{version}/weapon.json")}
    if game == "zzz" and raw.get("fairy_recommend"):
        return {"item": _fetch_metadata_file(game, version, "item", f"{BASE_URL}/zzz/{version}/en/item.json")}
    return {}


def _detail_disk_path(cache_key: tuple[str, str, str]) -> Path:
    game, version, char_id = cache_key
    digest = hashlib.sha256(f"{game}:{version}:{char_id}".encode()).hexdigest()
    return DETAIL_CACHE_DIR / f"{digest}.pkl"


def _detail_url(game: str, version: str, char_id: str) -> str:
    return f"{BASE_URL}/{game}/{version}/en/character/{char_id}.json"


def load_character_detail(game: str, char_id: str) -> CharacterDetail:
    """Fetch and normalize a character's detail page without build data.

    The cached manifest version is used first, so text appears immediately.
    If that version has gone stale, the fresh manifest is fetched once and the
    detail request is retried.  Results are cached in memory by (game, version, char_id).
    """
    try:
        version = str(get_latest_version(game))
    except Exception as exc:  # noqa: BLE001 - a fresh manifest may still work
        logger.warning("Could not read the cached manifest: %s", exc)
        version = _latest_version(game)

    cache_key = (game, version, str(char_id))
    caching = get_setting("cache_character_details")

    if cache_key in _detail_cache:
        logger.debug("Using cached character detail for %s %s (version %s)", game, char_id, version)
        return copy.deepcopy(_detail_cache[cache_key])

    if caching:
        disk_path = _detail_disk_path(cache_key)
        if disk_path.exists():
            try:
                with disk_path.open("rb") as handle:
                    detail = pickle.load(handle)
                _detail_cache[cache_key] = detail
                return copy.deepcopy(detail)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read cached detail %s: %s", disk_path, exc)
                try:
                    disk_path.unlink()
                except OSError:
                    pass

    try:
        raw = _get_json(_detail_url(game, version, char_id))
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        fresh_version = _latest_version(game)
        if fresh_version == version:
            raise DetailUnavailable(
                "Details are not available for this character yet."
            ) from exc
        version = fresh_version
        cache_key = (game, version, str(char_id))
        caching = get_setting("cache_character_details")

        if cache_key in _detail_cache:
            return copy.deepcopy(_detail_cache[cache_key])

        if caching:
            disk_path = _detail_disk_path(cache_key)
            if disk_path.exists():
                try:
                    with disk_path.open("rb") as handle:
                        detail = pickle.load(handle)
                    _detail_cache[cache_key] = detail
                    return copy.deepcopy(detail)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not read cached detail %s: %s", disk_path, exc)
                    try:
                        disk_path.unlink()
                    except OSError:
                        pass
        try:
            raw = _get_json(_detail_url(game, version, char_id))
        except requests.HTTPError as retry_exc:
            if retry_exc.response is not None and retry_exc.response.status_code == 404:
                raise DetailUnavailable(
                    "Details are not available for this character yet."
                ) from retry_exc
            raise
        except requests.RequestException as retry_exc:
            raise DetailUnavailable(
                "Could not reach nanoka.cc. Check your connection."
            ) from retry_exc
    except requests.RequestException as exc:
        raise DetailUnavailable(
            "Could not reach nanoka.cc. Check your connection."
        ) from exc

    detail = _normalize(game, char_id, raw, {}, with_build=False)
    detail.art_url = _art_url(game, char_id, raw)
    detail.source_url = get_character_url(game, char_id, raw)

    has_build = (
        (
            game == "hsr"
            and any(raw.get(key) for key in ("relics", "lightcones", "teams"))
        )
        or (game == "ww" and bool((raw.get("recommend") or {}).get("weapon")))
        or (game == "zzz" and bool(raw.get("fairy_recommend")))
    )
    if has_build:
        detail.build_context = BuildContext(game, version, raw)

    _detail_cache[cache_key] = detail
    if get_setting("cache_character_details"):
        disk_path = _detail_disk_path(cache_key)
        try:
            with disk_path.open("wb") as handle:
                pickle.dump(detail, handle)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write cached detail %s: %s", disk_path, exc)
    return copy.deepcopy(detail)


def load_character_build(detail: CharacterDetail) -> list[BuildSection]:
    """Fetch only the metadata needed for a character's recommended build.

    This is intentionally separate from :func:`load_character_detail` so the
    core text and art can render while build metadata is still downloading.
    """
    context = detail.build_context
    if context is None:
        return []

    metadata = _fetch_metadata(context.game, context.version, context.raw)
    if context.game == "hsr":
        return _hsr_build(context.raw, metadata)
    if context.game == "ww":
        return _ww_build(context.raw, metadata)
    if context.game == "zzz":
        return _zzz_build(context.raw, metadata)
    return []


# ---------------------------------------------------------------------------
# Text formatting


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


# ---------------------------------------------------------------------------
# Small formatting helpers


def _number(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{number:,.0f}"
    return f"{number:,.{decimals}f}"


def _percent(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return str(value)


def _last_numeric_key(mapping: dict[str, Any]) -> str:
    keys = [key for key in mapping if str(key).lstrip("-").isdigit()]
    return max(keys, key=lambda key: int(key)) if keys else ""


def _choose_level(mapping: dict[str, Any], cap: int) -> dict[str, Any]:
    keys = sorted(int(key) for key in mapping if str(key).isdigit())
    if not keys:
        return {}
    selected = cap if cap in keys else max((key for key in keys if key <= cap), default=keys[0])
    return mapping.get(str(selected), {})


def _art_url(game: str, char_id: str, raw: dict[str, Any]) -> str:
    if game == "hsr":
        return f"{BASE_URL}/assets/hsr/avatardrawcard/{char_id}.webp"
    if game == "gi":
        icon = str(raw.get("icon", ""))
        if icon.startswith("UI_AvatarIcon_"):
            suffix = icon.removeprefix("UI_AvatarIcon_")
            return f"{BASE_URL}/assets/gi/UI_Gacha_AvatarImg_{suffix}.webp"
        return f"{BASE_URL}/assets/gi/{icon}.webp"
    if game == "ww":
        background = str(raw.get("background") or raw.get("background_stand") or raw.get("icon") or "")
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


# ---------------------------------------------------------------------------
# HSR


_HSR_SKILL_CAPS = {
    "Basic ATK": 6,
    "Skill": 10,
    "Ultimate": 10,
    "Talent": 10,
    "Technique": 1,
}

_HSR_PROPERTY_NAMES = {
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

_HSR_RELIC_SLOTS = {
    "BODY": "Body",
    "FOOT": "Feet",
    "NECK": "Planar Sphere",
    "OBJECT": "Link Rope",
}

_HSR_PATH_NAMES = {
    "Warrior": "Destruction",
    "Rogue": "The Hunt",
    "Mage": "Erudition",
    "Knight": "Preservation",
    "Warlock": "Nihility",
    "Priest": "Abundance",
    "Shaman": "Harmony",
    "Memory": "Remembrance",
    "Elation": "Elation",
}


def _hsr_fill(text: str, params: list[Any]) -> str:
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


def _hsr_multipliers(text: str, params: list[Any]) -> list[tuple[str, str]]:
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


def _hsr_points(raw: dict[str, Any]) -> list[dict[str, Any]]:
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


def _hsr_skill_caps(raw: dict[str, Any]) -> dict[str, int]:
    caps: dict[str, int] = {}
    for point in _hsr_points(raw):
        level = int(point.get("max_level") or 1)
        for skill_id in point.get("level_up_skill_id") or []:
            caps[str(skill_id)] = level
    return caps


def _hsr_skills(raw: dict[str, Any]) -> list[SkillDetail]:
    caps = _hsr_skill_caps(raw)
    order = {"Basic ATK": 0, "Skill": 1, "Ultimate": 2, "Talent": 3, "Technique": 4}
    skills: list[SkillDetail] = []
    for skill_id, skill in (raw.get("skills") or {}).items():
        type_name = str(skill.get("type_name") or "")
        if not type_name or type_name == "None":
            continue
        cap = caps.get(str(skill_id), _HSR_SKILL_CAPS.get(type_name, 1))
        level_data = _choose_level(skill.get("level") or {}, cap)
        level = int(level_data.get("level") or cap)
        params = level_data.get("param_list") or []
        skills.append(
            SkillDetail(
                name=str(skill.get("name") or "Skill"),
                type_name=type_name,
                description=_hsr_fill(str(skill.get("desc") or ""), params),
                multipliers=_hsr_multipliers(str(skill.get("desc") or ""), params),
                level=level,
            )
        )
    skills.sort(key=lambda item: (order.get(item.type_name, 99), item.name))
    return skills


def _hsr_stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = raw.get("stats") or {}
    phase = stats.get(_last_numeric_key(stats)) or {}
    return [
        ("HP", _number((phase.get("hp_base") or 0) + (phase.get("hp_add") or 0) * 79)),
        (
            "ATK",
            _number(
                (phase.get("attack_base") or 0)
                + (phase.get("attack_add") or 0) * 79
            ),
        ),
        (
            "DEF",
            _number(
                (phase.get("defence_base") or 0)
                + (phase.get("defence_add") or 0) * 79
            ),
        ),
        ("SPD", _number(phase.get("speed_base") or 0)),
        ("CRIT Rate", _percent(phase.get("critical_chance") or 0)),
        ("CRIT DMG", _percent(phase.get("critical_damage") or 0)),
    ]


def _hsr_build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
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
        slot = _HSR_RELIC_SLOTS.get(str(item.get("relic_type")), str(item.get("relic_type")))
        prop = _HSR_PROPERTY_NAMES.get(
            str(item.get("property_type")), plain_text(item.get("property_type"))
        )
        main_stats.append(f"{slot}: {prop}")
    if main_stats:
        sections.append(BuildSection("Main Stats", main_stats))

    substats = [
        _HSR_PROPERTY_NAMES.get(str(prop), plain_text(prop))
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


def _hsr_extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    traces: list[ContentEntry] = []
    stat_names: dict[str, str] = {}
    stat_totals: dict[str, float] = {}
    for point in _hsr_points(raw):
        name = point.get("point_name")
        desc = point.get("point_desc")
        if name and desc:
            traces.append(
                ContentEntry(
                    str(name),
                    _hsr_fill(str(desc), point.get("param_list") or []),
                )
            )
            continue
        for status in point.get("status_add_list") or []:
            prop = _HSR_PROPERTY_NAMES.get(
                str(status.get("property_type")), plain_text(status.get("name"))
            )
            try:
                value = float(status.get("value") or 0)
            except (TypeError, ValueError):
                continue
            if not prop or not value:
                continue
            stat_names[prop] = prop
            stat_totals[prop] = stat_totals.get(prop, 0.0) + value
    for prop, total in stat_totals.items():
        is_percent = prop.endswith("%") or any(
            token in prop for token in ("Rate", "DMG", "Effect", "Healing")
        )
        shown = f"{total * 100:.1f}%" if is_percent else _number(total, 1)
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
                    _hsr_fill(str(rank["desc"]), params),
                )
            )
    if eidolons:
        extras.append(ExtraSection("Eidolons", eidolons))
    return extras


# ---------------------------------------------------------------------------
# Genshin Impact


def _gi_fill(text: str, params: list[Any]) -> str:
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


def _gi_skill_parts(entry: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    rows: list[tuple[str, str]] = []
    for line in entry.get("desc") or []:
        if not line:
            continue
        if "|" in line:
            label, template = line.split("|", 1)
        else:
            label, template = "Effect", line
        rows.append((plain_text(label), _gi_fill(template, entry.get("param") or [])))
    return "\n".join(f"{label}: {value}" for label, value in rows), rows


def _gi_stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    modifier = raw.get("stats_modifier") or {}
    ascension = (modifier.get("ascension") or [{}])[-1]
    hp_mult = (modifier.get("hp") or {}).get("90", 0)
    atk_mult = (modifier.get("atk") or {}).get("90", 0)
    def_mult = (modifier.get("def") or {}).get("90", 0)
    return [
        ("HP", _number((raw.get("base_hp") or 0) * hp_mult + (ascension.get("fight_prop_base_hp") or 0))),
        ("ATK", _number((raw.get("base_atk") or 0) * atk_mult + (ascension.get("fight_prop_base_attack") or 0))),
        ("DEF", _number((raw.get("base_def") or 0) * def_mult + (ascension.get("fight_prop_base_defense") or 0))),
        ("CRIT Rate", _percent(raw.get("crit_rate") or 0)),
        ("CRIT DMG", _percent((raw.get("crit_dmg") or 0) + (ascension.get("fight_prop_critical_hurt") or 0))),
        ("Elemental Mastery", _number(raw.get("elemental_mastery") or 0)),
    ]


def _gi_skills(raw: dict[str, Any]) -> list[SkillDetail]:
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
        description, rows = _gi_skill_parts(entry)
        icon = str(entry.get("icon") or skill.get("icon") or "")
        if "_A_" in icon:
            type_name = "Normal Attack"
        elif "_E_" in icon:
            type_name = "Elemental Burst"
        elif "_S_" in icon:
            skill_icons_seen += 1
            type_name = "Elemental Skill" if skill_icons_seen == 1 else "Alternate Sprint"
        else:
            type_name = "Talent"
        skills.append(
            SkillDetail(
                name=str(skill.get("name") or "Talent"),
                type_name=type_name,
                description=format_markup(skill.get("desc") or description),
                multipliers=rows,
                level=10,
            )
        )
    return skills


def _gi_extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passives = [
        ContentEntry(str(item.get("name") or "Passive"), format_markup(item.get("desc") or ""))
        for item in raw.get("passives") or []
    ]
    if passives:
        extras.append(ExtraSection("Passives", passives))
    constellations = [
        ContentEntry(
            str(item.get("name") or "Constellation"),
            format_markup(item.get("desc") or ""),
        )
        for item in raw.get("constellations") or []
    ]
    if constellations:
        extras.append(ExtraSection("Constellations", constellations))
    return extras


# ---------------------------------------------------------------------------
# Wuthering Waves


_GI_WEAPONS = {
    "WEAPON_SWORD_ONE_HAND": "Sword",
    "WEAPON_CLAYMORE": "Claymore",
    "WEAPON_POLE": "Polearm",
    "WEAPON_BOW": "Bow",
    "WEAPON_CATALYST": "Catalyst",
}

_WW_ELEMENTS = {
    1: "Glacio",
    2: "Fusion",
    3: "Electro",
    4: "Aero",
    5: "Spectro",
    6: "Havoc",
}
_WW_WEAPONS = {
    1: "Broadblade",
    2: "Sword",
    3: "Pistols",
    4: "Gauntlets",
    5: "Rectifier",
}


def _ww_fill(text: str, params: list[Any]) -> str:
    for index, value in enumerate(params or []):
        text = text.replace(f"{{{index}}}", str(value))
    return format_markup(text)


def _ww_stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    stats = raw.get("stats") or {}
    phase = stats.get(_last_numeric_key(stats)) or {}
    level = phase.get(_last_numeric_key(phase)) or {}
    return [
        ("HP", _number(level.get("life") or 0)),
        ("ATK", _number(level.get("atk") or 0)),
        ("DEF", _number(level.get("def") or 0)),
    ]


def _ww_skills(raw: dict[str, Any]) -> tuple[list[SkillDetail], list[ExtraSection]]:
    skills: list[SkillDetail] = []
    inherent: list[ContentEntry] = []
    trees = raw.get("skill_trees") or {}
    for node_key in sorted(trees, key=lambda key: int(key) if str(key).isdigit() else 999):
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
                    rows.append((plain_text(row.get("name") or "Multiplier"), value))
            skills.append(
                SkillDetail(
                    name=name,
                    type_name=type_name,
                    description=_ww_fill(str(skill.get("desc") or ""), skill.get("param") or []),
                    multipliers=rows,
                    level=10,
                )
            )
        elif skill.get("desc"):
            inherent.append(ContentEntry(name, _ww_fill(str(skill["desc"]), [])))
    extras = []
    if inherent:
        extras.append(ExtraSection("Inherent Skills", inherent))
    chains = [
        ContentEntry(
            str(chain.get("name") or "Sequence"),
            _ww_fill(str(chain.get("desc") or ""), chain.get("param") or []),
        )
        for chain in (raw.get("chains") or {}).values()
    ]
    if chains:
        extras.append(ExtraSection("Sequences", chains))
    return skills, extras


def _ww_build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
    recommend = raw.get("recommend") or {}
    weapons = metadata.get("weapon") or {}
    items = []
    for weapon_id in recommend.get("weapon") or []:
        name = (weapons.get(str(weapon_id)) or {}).get("en")
        if name:
            items.append(name)
    return [BuildSection("Recommended Weapons", items)] if items else []


# ---------------------------------------------------------------------------
# Zenless Zone Zero


_ZZZ_ELEMENTS = {
    200: "Physical",
    201: "Fire",
    202: "Ice",
    203: "Electric",
    204: "Wind",
    205: "Ether",
}
_ZZZ_SKILLS = [
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
_ZZZ_STAT_NAMES = {
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


def _zzz_stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
    base = raw.get("stats") or {}
    levels = raw.get("level") or {}
    bonus = levels.get(_last_numeric_key(levels)) or {}
    growth = (60 - 1) / 10000

    extra_levels = raw.get("extra_level") or {}
    extra = (extra_levels.get(_last_numeric_key(extra_levels)) or {}).get("extra") or {}
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

    hp = (base.get("hp_max") or 0) + (bonus.get("hp_max") or 0) + (base.get("hp_growth") or 0) * growth
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
        ("HP", _number(hp)),
        ("ATK", _number(atk)),
        ("DEF", _number(defence)),
        ("Impact", _number(impact)),
        ("CRIT Rate", _percent((base.get("crit") or 0) / 10000)),
        ("CRIT DMG", _percent((base.get("crit_damage") or 0) / 10000)),
        ("Anomaly Mastery", _number(base.get("element_mystery") or 0)),
        ("Anomaly Proficiency", _number(base.get("element_abnormal_power") or 0)),
    ]


def _zzz_skill_value(param: dict[str, Any], level: int = 12) -> str:
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


def _zzz_skills(raw: dict[str, Any]) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    sections = raw.get("skill") or {}
    for key, type_name in _ZZZ_SKILLS:
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
                    descriptions.append(f"<b>{html.escape(name)}</b><br>{format_markup(desc)}" if name else format_markup(desc))
            for param_entry in entry.get("param") or []:
                param_map = param_entry.get("param") or {}
                for value in param_map.values():
                    shown = _zzz_skill_value(value)
                    if shown:
                        multipliers.append(
                            (plain_text(param_entry.get("name") or "Multiplier"), shown)
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


def _zzz_stat_name(prop: Any, recommend: dict[str, Any]) -> str:
    """Resolve a ZZZ sub-stat ID to its display name.

    The detail JSON only stores sub-stat IDs, so the base mapping is hardcoded
    from nanoka's own frontend.  Per-character main-stat names are used as a
    fallback for IDs that are not in the base map.
    """
    try:
        key = int(prop)
    except (TypeError, ValueError):
        return str(prop)

    if key in _ZZZ_STAT_NAMES:
        return _ZZZ_STAT_NAMES[key]

    for part_key in ("part_sub", "part4", "part5", "part6"):
        part = recommend.get(part_key) or {}
        try:
            if int(part.get("prop") or 0) == key and part.get("name"):
                return str(part["name"]).replace("\xa0", " ")
        except (TypeError, ValueError):
            continue

    logger.debug("Unknown ZZZ stat id %s", key)
    return f"Stat {key}"


def _zzz_build(raw: dict[str, Any], metadata: dict[str, Any]) -> list[BuildSection]:
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
        _zzz_stat_name(prop, recommend)
        for prop in recommend.get("part_sub_list") or []
    ]
    if substats:
        sections.append(BuildSection("Substats", substats))
    return sections


def _zzz_extras(raw: dict[str, Any]) -> list[ExtraSection]:
    extras: list[ExtraSection] = []
    passive = raw.get("passive") or {}
    levels = passive.get("level") or {}
    if levels:
        last = levels[_last_numeric_key(levels)] or {}
        names = last.get("name") or []
        descs = last.get("desc") or []
        entries = [
            ContentEntry(str(name), format_markup(descs[index] if index < len(descs) else ""))
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


# ---------------------------------------------------------------------------
# Neverness to Everness


def _nte_stats(raw: dict[str, Any]) -> list[tuple[str, str]]:
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
            shown = _number(value)
        stats.append((name, shown))
    return stats


def _nte_skills(raw: dict[str, Any]) -> list[SkillDetail]:
    skills: list[SkillDetail] = []
    for ability in raw.get("abilities") or []:
        if not ability.get("show_detail_info", True):
            continue
        phases = []
        for phase in ability.get("phases") or []:
            name = plain_text(phase.get("name") or "")
            desc = format_markup(phase.get("desc") or "")
            if desc:
                phases.append(f"<b>{html.escape(name)}</b><br>{desc}" if name else desc)
        multipliers = []
        for row in ability.get("param_rows") or []:
            values = row.get("values") or []
            if not values:
                continue
            index = min(9, len(values) - 1)
            multipliers.append((str(row.get("label") or "Multiplier"), str(values[index])))
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


def _nte_extras(raw: dict[str, Any]) -> list[ExtraSection]:
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
                parts.append(f"<b>{html.escape(name)}</b><br>{desc}" if name else desc)
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
        ContentEntry(str(item.get("name") or "Awakening"), format_markup(item.get("desc") or ""))
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


# ---------------------------------------------------------------------------
# Normalization


def _badges_for(game: str, raw: dict[str, Any]) -> list[str]:
    badges: list[str] = []
    if game == "hsr":
        rarity = str(raw.get("rarity") or "")
        if "5" in rarity:
            badges.append("5★")
        elif "4" in rarity:
            badges.append("4★")
        element = str(raw.get("damage_type") or "")
        path = _HSR_PATH_NAMES.get(str(raw.get("base_type") or ""), str(raw.get("base_type") or ""))
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
                _GI_WEAPONS.get(weapon, weapon.removeprefix("WEAPON_").replace("_", " ").title()),
                faction,
            )
            if value
        )
    elif game == "ww":
        badges.append(f"{raw.get('rarity', '?')}★")
        badges.extend(
            value
            for value in (
                _WW_ELEMENTS.get(raw.get("element")),
                _WW_WEAPONS.get(raw.get("weapon")),
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


def _subtitle_for(game: str, raw: dict[str, Any]) -> str:
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
            value for value in (raw.get("ability_name"), raw.get("faction")) if value
        )
    return ""


def _overview_for(game: str, raw: dict[str, Any]) -> str:
    if game == "zzz":
        info = raw.get("partner_info") or {}
        return format_markup(info.get("profile_desc") or "")
    return format_markup(raw.get("desc") or "")


def _level_label_for(game: str) -> str:
    return {"hsr": "Lv. 80", "gi": "Lv. 90", "ww": "Lv. 90", "zzz": "Lv. 60", "nte": "Lv. 80"}.get(
        game, "Max level"
    )


def _normalize(
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
        subtitle=_subtitle_for(game, raw),
        overview=_overview_for(game, raw),
        level_label=_level_label_for(game),
        badges=_badges_for(game, raw),
    )

    if game == "hsr":
        detail.stats = _hsr_stats(raw)
        if with_build:
            detail.build = _hsr_build(raw, metadata)
        detail.skills = _hsr_skills(raw)
        detail.extras = _hsr_extras(raw)
    elif game == "gi":
        detail.stats = _gi_stats(raw)
        detail.skills = _gi_skills(raw)
        detail.extras = _gi_extras(raw)
    elif game == "ww":
        detail.stats = _ww_stats(raw)
        if with_build:
            detail.build = _ww_build(raw, metadata)
        detail.skills, extras = _ww_skills(raw)
        detail.extras = extras
    elif game == "zzz":
        detail.stats = _zzz_stats(raw)
        if with_build:
            detail.build = _zzz_build(raw, metadata)
        detail.skills = _zzz_skills(raw)
        detail.extras = _zzz_extras(raw)
    elif game == "nte":
        detail.stats = _nte_stats(raw)
        detail.skills = _nte_skills(raw)
        detail.extras = _nte_extras(raw)
    return detail
