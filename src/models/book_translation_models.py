"""
Book Translation Models
Pydantic models for multi-language support in books and chapters
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# 17 Supported Languages
SUPPORTED_LANGUAGES = [
    "en",  # English
    "vi",  # Tiếng Việt
    "zh-CN",  # Chinese (Simplified)
    "zh-TW",  # Chinese (Traditional)
    "ja",  # Japanese
    "ko",  # Korean
    "th",  # Thai
    "id",  # Indonesian
    "km",  # Khmer
    "lo",  # Lao
    "hi",  # Hindi
    "ms",  # Malay
    "pt",  # Portuguese
    "ru",  # Russian
    "fr",  # French
    "de",  # German
    "es",  # Spanish
]

LANGUAGE_NAMES = {
    "en": {"name": "English", "flag": "🇬🇧"},
    "vi": {"name": "Tiếng Việt", "flag": "🇻🇳"},
    "zh-CN": {"name": "Chinese (Simplified)", "flag": "🇨🇳"},
    "zh-TW": {"name": "Chinese (Traditional)", "flag": "🇹🇼"},
    "ja": {"name": "Japanese", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "flag": "🇰🇷"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "id": {"name": "Indonesian", "flag": "🇮🇩"},
    "km": {"name": "Khmer", "flag": "🇰🇭"},
    "lo": {"name": "Lao", "flag": "🇱🇦"},
    "hi": {"name": "Hindi", "flag": "🇮🇳"},
    "ms": {"name": "Malay", "flag": "🇲🇾"},
    "pt": {"name": "Portuguese", "flag": "🇵🇹"},
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "fr": {"name": "French", "flag": "🇫🇷"},
    "de": {"name": "German", "flag": "🇩🇪"},
    "es": {"name": "Spanish", "flag": "🇪🇸"},
}


# ==================== TRANSLATION REQUESTS ====================


class TranslateBookRequest(BaseModel):
    """Request to translate entire book"""

    target_language: str = Field(
        ..., description="Target language code (e.g., 'en', 'zh-CN')"
    )
    source_language: Optional[str] = Field(
        None,
        description="Source language code (if None, use book's default_language)",
    )
    translate_chapters: bool = Field(
        True, description="Translate all chapters (default: true)"
    )
    preserve_background: bool = Field(
        True, description="Keep same background for all languages (default: true)"
    )
    custom_background: Optional[Dict[str, Any]] = Field(
        None, description="Custom background config for this language"
    )

    @validator("target_language")
    def validate_target_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return v

    @validator("source_language")
    def validate_source_language(cls, v):
        if v is not None and v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return v


class TranslateChapterRequest(BaseModel):
    """Request to translate single chapter"""

    target_language: str = Field(
        ..., description="Target language code (e.g., 'en', 'zh-CN')"
    )
    source_language: Optional[str] = Field(
        None,
        description="Source language code (if None, use chapter's default_language)",
    )
    preserve_background: bool = Field(
        True, description="Keep same background (default: true)"
    )
    custom_background: Optional[Dict[str, Any]] = Field(
        None, description="Custom background config for this language"
    )

    @validator("target_language")
    def validate_target_language(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return v

    @validator("source_language")
    def validate_source_language(cls, v):
        if v is not None and v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {v}. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return v


# ==================== TRANSLATION RESPONSES ====================


class TranslatedFields(BaseModel):
    """Fields that were translated"""

    title: Optional[str] = None
    description: Optional[str] = None
    content_html: Optional[str] = None


class TranslateBookResponse(BaseModel):
    """Response after translating book"""

    success: bool
    book_id: str
    target_language: str
    source_language: str
    translated_fields: TranslatedFields
    chapters_translated: int = Field(0, description="Number of chapters translated")
    total_cost_points: int = Field(
        ..., description="Total points deducted for translation"
    )
    message: str


class TranslateChapterResponse(BaseModel):
    """Response after translating chapter"""

    success: bool
    chapter_id: str
    book_id: str
    target_language: str
    source_language: str
    translated_fields: TranslatedFields
    translation_cost_points: int = Field(
        2, description="Points deducted (2 per chapter)"
    )
    message: str


# ==================== LANGUAGE MANAGEMENT ====================


class LanguageInfo(BaseModel):
    """Information about a language"""

    code: str = Field(..., description="Language code (e.g., 'en', 'vi')")
    name: str = Field(..., description="Language name (e.g., 'English')")
    flag: str = Field(..., description="Flag emoji (e.g., '🇬🇧')")
    is_default: bool = Field(False, description="Whether this is the default language")
    translated_at: Optional[datetime] = Field(
        None, description="When translation was created"
    )


class LanguageListResponse(BaseModel):
    """Response for listing available languages"""

    book_id: str
    default_language: str
    available_languages: List[LanguageInfo] = Field(
        ..., description="List of available language versions"
    )


# ==================== BACKGROUND MANAGEMENT ====================


class UpdateBackgroundForLanguageRequest(BaseModel):
    """Update background for specific language"""

    background_config: Dict[str, Any] = Field(
        ..., description="Background configuration for this language"
    )


class UpdateBackgroundForLanguageResponse(BaseModel):
    """Response after updating background for language"""

    success: bool
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    language: str
    background_config: Dict[str, Any]
    message: str


# ==================== DELETE TRANSLATION ====================


class DeleteTranslationResponse(BaseModel):
    """Response after deleting translation"""

    success: bool
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    language_deleted: str
    remaining_languages: List[str]
    message: str


# ==================== EXTENDED MODELS (for responses) ====================


class BookTranslationData(BaseModel):
    """Translation data for a book"""

    title: str
    description: Optional[str] = None
    translated_at: datetime
    translated_by: str = "gemini-2.5-pro"
    translation_cost_points: int = 2


class ChapterTranslationData(BaseModel):
    """Translation data for a chapter"""

    title: str
    description: Optional[str] = None
    content_html: str
    translated_at: datetime
    translated_by: str = "gemini-2.5-pro"
    translation_cost_points: int = 2


# ==================== HELPER FUNCTIONS ====================


def get_language_name(code: str) -> str:
    """Get language name from code"""
    return LANGUAGE_NAMES.get(code, {}).get("name", code)


def get_language_flag(code: str) -> str:
    """Get language flag from code"""
    return LANGUAGE_NAMES.get(code, {}).get("flag", "🏳️")


def validate_language_code(code: str) -> bool:
    """Check if language code is supported"""
    return code in SUPPORTED_LANGUAGES
