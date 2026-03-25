import requests

BASE_URL = "https://static.nanoka.cc"

GAMES = {
    "zzz": {"name": "Zenless Zone Zero", "url": "https://zzz.nanoka.cc"},
    "hsr": {"name": "Honkai: Star Rail", "url": "https://hsr.nanoka.cc"},
    "gi": {"name": "Genshin Impact", "url": "https://gi.nanoka.cc"},
}


def fetch_manifest():
    response = requests.get(f"{BASE_URL}/manifest.json")
    response.raise_for_status()
    return response.json()


def get_latest_version(game):
    manifest = fetch_manifest()
    return manifest[game]["latest"]


def fetch_characters(game):
    version = get_latest_version(game)
    url = f"{BASE_URL}/{game}/{version}/character.json"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def parse_release(game, release_data):
    if not release_data:
        return 0

    if game == "gi":
        from datetime import datetime

        try:
            return datetime.strptime(release_data, "%Y-%m-%d %H:%M:%S").timestamp()
        except:
            return 0
    return int(release_data)


def get_newest_characters(game, count=6):
    data = fetch_characters(game)
    manifest = fetch_manifest()
    new_ids = manifest[game].get("new", {}).get("character", [])

    if new_ids:
        new_ids_str = [str(id) for id in new_ids]
        result = []
        for char_id in new_ids_str:
            if char_id in data:
                result.append((char_id, data[char_id]))
            elif char_id.lstrip("-").isdigit() and char_id in data:
                result.append((char_id, data[char_id]))

        if len(result) >= count:
            return result[:count]

        existing_new_ids = [id for id, _ in result]
        remaining = count - len(result)

        for char_id, char_data in data.items():
            if char_id not in existing_new_ids and len(result) < count:
                result.append((char_id, char_data))

        return result[:count]

    chars_with_release = [
        (id, char_data) for id, char_data in data.items() if char_data.get("release")
    ]

    if chars_with_release:
        sorted_chars = sorted(
            chars_with_release,
            key=lambda x: parse_release(game, x[1].get("release")),
            reverse=True,
        )
        return sorted_chars[:count]

    return list(data.items())[:count]


def get_character_url(game, char_id, char_data):
    if game == "zzz":
        code = char_data.get("code", "").lower().replace("_en", "")
        return f"https://zzz.nanoka.cc/character/{code}"
    elif game == "hsr":
        return f"https://hsr.nanoka.cc/character/{char_id}"
    elif game == "gi":
        name = char_data.get("en", "").lower().replace(" ", "-")
        return f"https://gi.nanoka.cc/character/{name}"
    return ""


def get_rarity(game, char_data):
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
