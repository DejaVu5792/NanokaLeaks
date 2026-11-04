"""Shared per-game lookup tables.

The card list (:mod:`nanoka_viewer.api.models`) and the detail/build
normalizers (:mod:`nanoka_viewer.api.details`) need the same numeric-code to
display-name maps.  They live here so the two paths cannot drift; the WW
pistol name and the ZZZ Lumiflux element had already diverged when they were
copied.
"""

ZZZ_ELEMENTS = {
    200: "Physical",
    201: "Fire",
    202: "Ice",
    203: "Electric",
    204: "Wind",
    205: "Ether",
    300: "Lumiflux",
}

ZZZ_SPECIALTIES = {
    1: "Attack",
    2: "Stun",
    3: "Anomaly",
    4: "Support",
    5: "Defense",
    6: "Rupture",
    7: "Armorer",
}

HSR_PATHS = {
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

GI_ELEMENTS = {
    "Pyro": "Pyro",
    "Hydro": "Hydro",
    "Anemo": "Anemo",
    "Electro": "Electro",
    "Dendro": "Dendro",
    "Cryo": "Cryo",
    "Geo": "Geo",
}

GI_WEAPONS = {
    "WEAPON_SWORD_ONE_HAND": "Sword",
    "WEAPON_CLAYMORE": "Claymore",
    "WEAPON_POLE": "Polearm",
    "WEAPON_BOW": "Bow",
    "WEAPON_CATALYST": "Catalyst",
}

WW_ELEMENTS = {
    1: "Glacio",
    2: "Fusion",
    3: "Electro",
    4: "Aero",
    5: "Spectro",
    6: "Havoc",
}

# Element ids map to different names in the icon filenames.
WW_ELEMENT_ICONS = {
    1: "Ice",
    2: "Fire",
    3: "Thunder",
    4: "Wind",
    5: "Light",
    6: "Dark",
}

WW_WEAPONS = {
    1: "Broadblade",
    2: "Sword",
    3: "Pistol",
    4: "Gauntlets",
    5: "Rectifier",
}

WW_WEAPON_ICONS = {
    1: "Sword",
    2: "Knife",
    3: "Gun",
    4: "Fist",
    5: "Magic",
}
