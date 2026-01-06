"""
Language Code Normalization Utilities
Ensures all language codes are stored in ISO 639-1 (2-letter) format
"""

# ISO 639-1 to BCP 47 mapping for TTS providers
LANGUAGE_LOCALE_MAP = {
    "vi": "vi-VN",
    "en": "en-US",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "th": "th-TH",
    "ru": "ru-RU",
    "pt": "pt-BR",
    "it": "it-IT",
    "ar": "ar-SA",
    "hi": "hi-IN",
    "id": "id-ID",
}

# Reverse mapping: BCP 47 → ISO 639-1
LOCALE_TO_LANGUAGE = {v: k for k, v in LANGUAGE_LOCALE_MAP.items()}

# Additional common variations
LOCALE_TO_LANGUAGE.update(
    {
        "en-GB": "en",
        "en-AU": "en",
        "en-CA": "en",
        "zh-TW": "zh",
        "zh-HK": "zh",
        "pt-PT": "pt",
        "es-MX": "es",
        "es-AR": "es",
        "fr-CA": "fr",
    }
)


def normalize_language_code(language: str | None) -> str:
    """
    Normalize language code to ISO 639-1 (2-letter) format

    Examples:
        "ja-JP" → "ja"
        "en-US" → "en"
        "vi-VN" → "vi"
        "ja" → "ja" (already normalized)
        "JA-JP" → "ja" (case insensitive)

    Args:
        language: Language code in any format

    Returns:
        ISO 639-1 (2-letter) language code in lowercase
    """
    if not language:
        return "vi"  # Default fallback

    # Convert to lowercase for case-insensitive matching
    lang = str(language).lower().strip()

    # If it's already 2 letters, return as-is
    if len(lang) == 2 and lang.isalpha():
        return lang

    # If it's BCP 47 format (e.g., "ja-JP"), extract base language
    if "-" in lang:
        base_lang = lang.split("-")[0]
        # Validate it's actually in our reverse map
        if lang in LOCALE_TO_LANGUAGE:
            return LOCALE_TO_LANGUAGE[lang]
        # Otherwise just use the base part
        if len(base_lang) == 2 and base_lang.isalpha():
            return base_lang

    # If we have an exact reverse mapping
    if lang in LOCALE_TO_LANGUAGE:
        return LOCALE_TO_LANGUAGE[lang]

    # Last resort: return as-is (should be rare)
    return lang[:2] if len(lang) >= 2 else "vi"


def get_tts_locale(language: str) -> str:
    """
    Convert ISO 639-1 language code to BCP 47 locale for TTS providers

    Examples:
        "ja" → "ja-JP"
        "en" → "en-US"
        "vi" → "vi-VN"

    Args:
        language: ISO 639-1 language code

    Returns:
        BCP 47 locale string for TTS API
    """
    # First normalize to ensure we have clean input
    normalized = normalize_language_code(language)

    # Return the full locale
    return LANGUAGE_LOCALE_MAP.get(normalized, f"{normalized}-{normalized.upper()}")


def validate_language_code(language: str) -> bool:
    """
    Check if a language code is valid ISO 639-1 format

    Args:
        language: Language code to validate

    Returns:
        True if valid 2-letter code, False otherwise
    """
    if not language:
        return False

    normalized = normalize_language_code(language)
    return len(normalized) == 2 and normalized.isalpha()
