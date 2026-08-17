"""
voices.py — Language and voice configuration for the CMT SA Voice Assistant.

Maps each of the 11 official SA languages to:
    - its module key (used to dynamically import CMT_SA_Accent / CMT_SA_Assistant)
    - a display name
    - male and female Azure voice IDs
    - the STT locale used to recognise speech in that language
"""

LANGUAGES = {
    "isizulu": {
        "display": "isiZulu",
        "greeting": "Sawubona!",
        "voice_female": "zu-ZA-ThandoNeural",
        "voice_male": "zu-ZA-ThembaNeural",
        "stt_locale": "zu-ZA",
        "native": True,
    },
    "isixhosa": {
        "display": "isiXhosa",
        "greeting": "Molo!",
        "voice_female": "zu-ZA-ThandoNeural",   # closest available
        "voice_male": "zu-ZA-ThembaNeural",
        "stt_locale": "zu-ZA",
        "native": False,
    },
    "afrikaans": {
        "display": "Afrikaans",
        "greeting": "Hallo!",
        "voice_female": "af-ZA-AdriNeural",
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": True,
    },
    "sesotho": {
        "display": "Sesotho",
        "greeting": "Dumela!",
        "voice_female": "af-ZA-AdriNeural",     # closest available
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": False,
    },
    "setswana": {
        "display": "Setswana",
        "greeting": "Dumela!",
        "voice_female": "af-ZA-AdriNeural",
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": False,
    },
    "sepedi": {
        "display": "Sepedi",
        "greeting": "Thobela!",
        "voice_female": "af-ZA-AdriNeural",
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": False,
    },
    "siswati": {
        "display": "siSwati",
        "greeting": "Sawubona!",
        "voice_female": "zu-ZA-ThandoNeural",
        "voice_male": "zu-ZA-ThembaNeural",
        "stt_locale": "zu-ZA",
        "native": False,
    },
    "isindebele": {
        "display": "isiNdebele",
        "greeting": "Lotjhani!",
        "voice_female": "zu-ZA-ThandoNeural",
        "voice_male": "zu-ZA-ThembaNeural",
        "stt_locale": "zu-ZA",
        "native": False,
    },
    "tshivenda": {
        "display": "Tshivenda",
        "greeting": "Ndaa!",
        "voice_female": "af-ZA-AdriNeural",
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": False,
    },
    "xitsonga": {
        "display": "Xitsonga",
        "greeting": "Avuxeni!",
        "voice_female": "af-ZA-AdriNeural",
        "voice_male": "af-ZA-WillemNeural",
        "stt_locale": "af-ZA",
        "native": False,
    },
    "english": {
        "display": "English (SA)",
        "greeting": "Howzit!",
        "voice_female": "en-ZA-LeahNeural",
        "voice_male": "en-ZA-LukeNeural",
        "stt_locale": "en-ZA",
        "native": True,
    },
}

# For auto-detect mode: the 3 real distinct STT locales we can reliably
# tell apart, mapped back to a representative language key for replying.
AUTO_DETECT_LOCALES = ["zu-ZA", "af-ZA", "en-ZA"]
LOCALE_TO_LANGUAGE_KEY = {
    "zu-ZA": "isizulu",
    "af-ZA": "afrikaans",
    "en-ZA": "english",
}


def get_voice_id(lang_key: str, gender: str) -> str:
    lang = LANGUAGES.get(lang_key, LANGUAGES["english"])
    return lang["voice_female"] if gender == "Female" else lang["voice_male"]


def language_options():
    """Returns list of (key, display_name) for the dropdown, plus Auto-detect."""
    opts = [(k, v["display"]) for k, v in LANGUAGES.items()]
    return opts
