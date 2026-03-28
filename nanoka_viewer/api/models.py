"""Character model utilities and display helpers."""


def get_character_url(game, char_id, char_data):
    """Get the URL for a character on the nanoka website."""
    if game == "zzz":
        return f"https://zzz.nanoka.cc/character/{char_id}/"
    elif game == "hsr":
        return f"https://hsr.nanoka.cc/character/{char_id}"
    elif game == "gi":
        return f"https://gi.nanoka.cc/character/{char_id}"
    return ""


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
    return "?"


def get_element(game, char_data):
    """Get the element string for a character."""
    if game == "zzz":
        elements = {
            200: "Physical",
            201: "Fire",
            202: "Ice",
            203: "Electric",
            204: "Ether",
            205: "Physical",
        }
        return elements.get(char_data.get("element", 200), "Physical")
    elif game == "hsr":
        return char_data.get("damageType", "Physical")
    elif game == "gi":
        elements = {
            "Pyro": "Pyro",
            "Hydro": "Hydro",
            "Anemo": "Anemo",
            "Electro": "Electro",
            "Dendro": "Dendro",
            "Cryo": "Cryo",
            "Geo": "Geo",
        }
        return elements.get(char_data.get("element", "Physical"), "Physical")
    return "Physical"


def get_name(game, char_data):
    """Get the display name for a character."""
    if game == "zzz":
        name = char_data.get("en", char_data.get("code", ""))
        if name.startswith("Avatar_") or name.startswith("UI_"):
            return char_data.get("code", name).replace("_En", "")
        return name
    elif game == "hsr":
        return char_data.get("en", "Unknown")
    elif game == "gi":
        return char_data.get("en", "Unknown")
    return "Unknown"


def get_character_image(game, char_data, char_id=None):
    """Get the character portrait image URL."""
    icon = char_data.get("icon", "")
    if game == "zzz":
        return f"https://static.nanoka.cc/assets/zzz/{icon}.webp"
    elif game == "hsr":
        if char_id:
            return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{char_id}.webp"
        return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{icon}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{icon}.webp"
    return ""


def get_element_image(game, char_data):
    """Get the element icon image URL."""
    element = get_element(game, char_data)
    if game == "zzz":
        element_map = {
            "Physical": "Physical",
            "Fire": "Fire",
            "Ice": "Ice",
            "Electric": "Electric",
            "Ether": "Anomaly",
        }
        return f"https://static.nanoka.cc/assets/zzz/Icon{element_map.get(element, 'Physical')}.webp"
    elif game == "hsr":
        return f"https://static.nanoka.cc/assets/hsr/element/{element.lower()}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{element}.webp"
    return ""


def get_specialty_image(game, char_data):
    """Get the specialty/path/weapon icon image URL."""
    if game == "zzz":
        type_map = {
            1: "Attack",
            2: "Defense",
            3: "Anomaly",
            4: "Support",
            5: "Star",
        }
        specialty = type_map.get(char_data.get("type", 1), "Attack")
        return f"https://static.nanoka.cc/assets/zzz/Icon{specialty}.webp"
    elif game == "hsr":
        path = char_data.get("baseType", "")
        return f"https://static.nanoka.cc/assets/hsr/pathicon/{path.lower()}.webp"
    elif game == "gi":
        weapon = char_data.get("weapon", "")
        return f"https://static.nanoka.cc/assets/gi/{weapon}.webp"
    return ""
