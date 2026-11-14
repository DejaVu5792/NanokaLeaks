"""Character model utilities and display helpers."""

from .constants import BASE_URL, GAMES
from .game_data import (
    GI_ELEMENTS,
    GI_WEAPONS,
    HSR_PATHS,
    WW_ELEMENT_ICONS,
    WW_ELEMENTS,
    WW_WEAPON_ICONS,
    WW_WEAPONS,
    ZZZ_ELEMENTS,
    ZZZ_SPECIALTIES,
)


def get_character_url(game, char_id, char_data):
    """Get the URL for a character on the nanoka website."""
    info = GAMES.get(game)
    if info is None:
        return ""
    # ZZZ's character pages use a trailing slash; the other games do not.
    suffix = "/" if game == "zzz" else ""
    return f"{info['url']}/character/{char_id}{suffix}"


def get_rarity(game, char_data):
    """Get the rarity display string for a character."""
    if game == "zzz" or game == "hsr":
        rank = char_data.get("rank", 3)
        if game == "zzz":
            return "S" if rank == 4 else "A"
        return "5" if "5" in str(rank) else "4"
    elif game == "gi":
        rank = char_data.get("rank", "QUALITY_PURPLE")
        if "ORANGE" in str(rank):
            return "5"
        return "4"
    elif game == "ww":
        rank = char_data.get("rank", 4)
        return str(rank)
    elif game == "nte":
        rarity = char_data.get("rarity", 4)
        return str(rarity)
    return "?"


def get_element(game, char_data):
    """Get the element string for a character."""
    if game == "zzz":
        return ZZZ_ELEMENTS.get(char_data.get("element", 200), "Physical")
    elif game == "hsr":
        return char_data.get("damageType", "Physical")
    elif game == "gi":
        return GI_ELEMENTS.get(char_data.get("element", "Physical"), "Physical")
    elif game == "ww":
        return WW_ELEMENTS.get(char_data.get("element", 1), "Glacio")
    elif game == "nte":
        return char_data.get("element", "Unknown")
    return "Physical"


def get_name(game, char_data, char_id=None):
    """Get the display name for a character."""
    if game == "zzz":
        name = char_data.get("en", char_data.get("code", ""))
        if name.startswith("Avatar_") or name.startswith("UI_"):
            return char_data.get("code", name).replace("_En", "")
        return name
    elif game == "hsr":
        name = char_data.get("en", "Unknown")
        
        # Check if it's the Trailblazer
        is_trailblazer = False
        if char_id:
            numeric_part = "".join(filter(str.isdigit, str(char_id)))
            id_num = int(numeric_part) if numeric_part else 0
            if id_num >= 8000:
                is_trailblazer = True
                
        icon = char_data.get("icon", "").lower()
        if icon == "playergirl" or icon == "playerboy":
            is_trailblazer = True
            
        if is_trailblazer:
            return "Trailblazer"
            
        return name
    elif game == "gi":
        return char_data.get("en", "Unknown")
    elif game == "nte":
        for field in ("en", "zh", "ja", "ko", "code", "id"):
            name = char_data.get(field)
            if name:
                return name
        return "Unknown"
    elif game == "ww":
        return char_data.get("en", "Unknown")
    return "Unknown"


def get_character_image(game, char_data, char_id=None):
    """Get the character portrait image URL."""
    icon = char_data.get("icon", "")
    if game == "zzz":
        return f"{BASE_URL}/assets/zzz/{icon}.webp"
    elif game == "hsr":
        if char_id:
            return f"{BASE_URL}/assets/hsr/avatarshopicon/{char_id}.webp"
        return f"{BASE_URL}/assets/hsr/avatarshopicon/{icon}.webp"
    elif game == "gi":
        return f"{BASE_URL}/assets/gi/{icon}.webp"
    elif game == "ww":
        if icon.startswith("http://") or icon.startswith("https://"):
            return icon
        path = icon.replace("/Game/Aki/UI/", "")
        path = path.split(".")[0]
        return f"{BASE_URL}/assets/ww/{path}.webp"
    elif game == "nte":
        if icon.startswith("http://") or icon.startswith("https://"):
            return icon
        if not icon.startswith("/"):
            icon = "/" + icon
        return f"{BASE_URL}/assets/nte{icon}.webp"
    return ""


def get_element_image(game, char_data):
    """Get the element icon image URL."""
    element = get_element(game, char_data)
    if game == "zzz":
        return f"{BASE_URL}/assets/zzz/Icon{element}.webp"
    elif game == "hsr":
        return f"{BASE_URL}/assets/hsr/element/{element.lower()}.webp"
    elif game == "gi":
        return f"{BASE_URL}/assets/gi/{element}.webp"
    elif game == "ww":
        element_id = char_data.get("element", 1)
        element_name = WW_ELEMENT_ICONS.get(element_id, "Ice")
        return f"{BASE_URL}/assets/ww/UIResources/Common/Image/IconElementAttri/T_IconElementAttri{element_name}.webp"
    elif game == "nte":
        icon_path = char_data.get("element_icon", "")
        if icon_path.startswith("http://") or icon_path.startswith("https://"):
            return icon_path
        icon_path = icon_path.replace("biandui/YH_UI_zudui_shaixuan", "Equip/UI_YH_kongmuicon4_")
        if not icon_path.startswith("/"):
            icon_path = "/" + icon_path
        return f"{BASE_URL}/assets/nte{icon_path}.webp"
    return ""


def get_specialty(game, char_data):
    """Get the specialty/path/weapon name for a character."""
    if game == "zzz":
        return ZZZ_SPECIALTIES.get(char_data.get("type", 1), "Attack")
    elif game == "hsr":
        base_type = char_data.get("baseType", "Unknown")
        return HSR_PATHS.get(base_type, base_type)
    elif game == "gi":
        weapon = str(char_data.get("weapon") or "")
        if not weapon:
            return "Unknown"
        return GI_WEAPONS.get(
            weapon,
            weapon.removeprefix("WEAPON_").replace("_", " ").title(),
        )
    elif game == "ww":
        return WW_WEAPONS.get(char_data.get("weapon", 1), "Unknown")
    elif game == "nte":
        return "None"
    return "Unknown"


def get_specialty_image(game, char_data):
    """Get the specialty/path/weapon icon image URL."""
    specialty = get_specialty(game, char_data)
    if game == "zzz":
        return f"{BASE_URL}/assets/zzz/Icon{specialty}.webp"
    elif game == "hsr":
        path = char_data.get("baseType", "")
        return f"{BASE_URL}/assets/hsr/pathicon/{path.lower()}.webp"
    elif game == "gi":
        weapon = char_data.get("weapon", "")
        return f"{BASE_URL}/assets/gi/{weapon}.webp"
    elif game == "ww":
        icon_name = WW_WEAPON_ICONS.get(char_data.get("weapon", 1), "Sword")
        return f"{BASE_URL}/assets/ww/Static/SP_IconNor{icon_name}.webp"
    return ""
