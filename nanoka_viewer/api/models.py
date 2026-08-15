"""Character model utilities and display helpers."""


def get_character_url(game, char_id, char_data):
    """Get the URL for a character on the nanoka website."""
    if game == "zzz":
        return f"https://zzz.nanoka.cc/character/{char_id}/"
    elif game == "hsr":
        return f"https://hsr.nanoka.cc/character/{char_id}"
    elif game == "gi":
        return f"https://gi.nanoka.cc/character/{char_id}"
    elif game == "ww":
        return f"https://ww.nanoka.cc/character/{char_id}"
    elif game == "nte":
        return f"https://nte.nanoka.cc/character/{char_id}"
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
        elements = {
            200: "Physical",
            201: "Fire",
            202: "Ice",
            203: "Electric",
            204: "Wind",
            205: "Ether",
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
    elif game == "ww":
        elements = {
            1: "Glacio",
            2: "Fusion",
            3: "Electro",
            4: "Aero",
            5: "Spectro",
            6: "Havoc",
        }
        return elements.get(char_data.get("element", 1), "Glacio")
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
        return f"https://static.nanoka.cc/assets/zzz/{icon}.webp"
    elif game == "hsr":
        if char_id:
            return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{char_id}.webp"
        return f"https://static.nanoka.cc/assets/hsr/avatarshopicon/{icon}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{icon}.webp"
    elif game == "ww":
        if icon.startswith("http://") or icon.startswith("https://"):
            return icon
        path = icon.replace("/Game/Aki/UI/", "")
        path = path.split(".")[0]
        return f"https://static.nanoka.cc/assets/ww/{path}.webp"
    elif game == "nte":
        if icon.startswith("http://") or icon.startswith("https://"):
            return icon
        if not icon.startswith("/"):
            icon = "/" + icon
        return f"https://static.nanoka.cc/assets/nte{icon}.webp"
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
            "Wind": "Wind",
            "Ether": "Ether",
        }
        return f"https://static.nanoka.cc/assets/zzz/Icon{element_map.get(element, 'Physical')}.webp"
    elif game == "hsr":
        return f"https://static.nanoka.cc/assets/hsr/element/{element.lower()}.webp"
    elif game == "gi":
        return f"https://static.nanoka.cc/assets/gi/{element}.webp"
    elif game == "ww":
        element_id = char_data.get("element", 1)
        element_map = {
            1: "Ice",
            2: "Fire",
            3: "Thunder",
            4: "Wind",
            5: "Light",
            6: "Dark",
        }
        element_name = element_map.get(element_id, "Ice")
        return f"https://static.nanoka.cc/assets/ww/UIResources/Common/Image/IconElementAttri/T_IconElementAttri{element_name}.webp"
    elif game == "nte":
        icon_path = char_data.get("element_icon", "")
        if icon_path.startswith("http://") or icon_path.startswith("https://"):
            return icon_path
        icon_path = icon_path.replace("biandui/YH_UI_zudui_shaixuan", "Equip/UI_YH_kongmuicon4_")
        if not icon_path.startswith("/"):
            icon_path = "/" + icon_path
        return f"https://static.nanoka.cc/assets/nte{icon_path}.webp"
    return ""


def get_specialty_image(game, char_data):
    """Get the specialty/path/weapon icon image URL."""
    if game == "zzz":
        type_map = {
            1: "Attack",
            2: "Stun",
            3: "Anomaly",
            4: "Support",
            5: "Defense",
            6: "Rupture",
        }
        specialty = type_map.get(char_data.get("type", 1), "Attack")
        return f"https://static.nanoka.cc/assets/zzz/Icon{specialty}.webp"
    elif game == "hsr":
        path = char_data.get("baseType", "")
        return f"https://static.nanoka.cc/assets/hsr/pathicon/{path.lower()}.webp"
    elif game == "gi":
        weapon = char_data.get("weapon", "")
        return f"https://static.nanoka.cc/assets/gi/{weapon}.webp"
    elif game == "ww":
        weapon_map = {
            1: "Sword",
            2: "Knife",
            3: "Gun",
            4: "Fist",
            5: "Magic",
        }
        weapon_id = char_data.get("weapon", 1)
        weapon_name = weapon_map.get(weapon_id, "Sword")
        return f"https://static.nanoka.cc/assets/ww/Static/SP_IconNor{weapon_name}.webp"
    return ""
