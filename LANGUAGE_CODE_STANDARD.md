# Language Code Standard - WordAI System

**Last Updated:** January 6, 2026

## 🎯 Core Principle

**ALWAYS use ISO 639-1 (2-letter) language codes in database and API.**

## 📋 Standard Language Codes

| Language | ✅ CORRECT (Use This) | ❌ WRONG (Don't Use) |
|----------|----------------------|---------------------|
| Vietnamese | `vi` | ~~vi-VN~~ |
| English | `en` | ~~en-US~~, ~~en-GB~~ |
| Japanese | `ja` | ~~ja-JP~~ |
| Chinese | `zh` | ~~zh-CN~~, ~~zh-TW~~ |
| Korean | `ko` | ~~ko-KR~~ |
| French | `fr` | ~~fr-FR~~ |
| German | `de` | ~~de-DE~~ |
| Spanish | `es` | ~~es-ES~~ |
| Thai | `th` | ~~th-TH~~ |

## 🗂️ Where to Use

### ✅ Database Collections
- `presentation_subtitles.language` → Use `"ja"` (not `"ja-JP"`)
- `presentation_audio.language` → Use `"ja"` (not `"ja-JP"`)
- `presentation_sharing_config.allowed_languages` → Use `["vi", "en", "ja"]`

### ✅ API Requests/Responses
```json
{
  "language": "ja",
  "subtitle_id": "...",
  "audio_url": "..."
}
```

### ✅ Frontend State
```javascript
const selectedLanguage = "ja"; // ✅
const selectedLanguage = "ja-JP"; // ❌
```

## 🔄 TTS/STT Provider Mapping

**ONLY convert to BCP 47 format when calling external APIs:**

### Google TTS (Gemini)
```python
# In google_tts_service.py
LANGUAGE_TO_VOICE_MAP = {
    "vi": "vi-VN",  # Convert for Google API
    "en": "en-US",
    "ja": "ja-JP",
}

# Usage:
db_language = subtitle.language  # "ja" from DB
tts_language = LANGUAGE_TO_VOICE_MAP.get(db_language, db_language)
# Use tts_language for API call
```

### Azure/Other Providers
```python
# Convert only at API boundary
azure_locale = f"{db_language}-{region.upper()}"
```

## 🚫 Common Mistakes to Avoid

### ❌ Mixing formats in DB
```python
# WRONG: Storing different formats
db.subtitles.insert_one({"language": "ja-JP"})  # ❌
db.subtitles.insert_one({"language": "ja"})     # ❌
# Now you have 2 different language entries!
```

### ❌ Using full locale in queries
```python
# WRONG
subtitles = db.presentation_subtitles.find({"language": "ja-JP"})  # ❌ Won't find "ja"

# CORRECT
subtitles = db.presentation_subtitles.find({"language": "ja"})  # ✅
```

### ❌ Hardcoding allowed_languages
```python
# WRONG
allowed = ["vi", "en"]  # ❌ Hardcoded, blocks new languages

# CORRECT
allowed = db.presentation_subtitles.distinct("language", {...})  # ✅ Auto-detect
```

## 📝 Implementation Checklist

When adding a new language:

- [ ] Use ISO 639-1 code (2 letters) in DB: `"ja"`
- [ ] Add mapping to TTS service if needed: `"ja": "ja-JP"`
- [ ] Test subtitle generation with new language
- [ ] Test audio generation with new language
- [ ] Verify public presentation shows new language automatically
- [ ] Update this document with new language

## 🔍 How to Check Compliance

### Check DB for inconsistent codes
```bash
# Find all unique language codes
docker exec mongodb mongosh ai_service_db \
  -u ai_service_user -p PASSWORD --authenticationDatabase admin \
  --eval "db.presentation_subtitles.distinct('language')"

# Expected: ["vi", "en", "ja"]
# Bad: ["vi", "en-US", "ja-JP"] ← Mixed formats!
```

### Check code for hardcoded locales
```bash
# Search for hardcoded BCP 47 codes
grep -r "ja-JP\|en-US\|vi-VN" src/ --exclude-dir=google_tts_service.py
# Should only appear in TTS mapping files
```

## 🛠️ Migration Guide

If you have existing data with mixed formats:

```javascript
// MongoDB migration script
db.presentation_subtitles.find().forEach(function(doc) {
  var newLang = doc.language;

  // Normalize to ISO 639-1
  if (newLang === "ja-JP") newLang = "ja";
  if (newLang === "en-US" || newLang === "en-GB") newLang = "en";
  if (newLang === "vi-VN") newLang = "vi";

  if (newLang !== doc.language) {
    db.presentation_subtitles.updateOne(
      {_id: doc._id},
      {$set: {language: newLang}}
    );
    print("Updated:", doc._id, doc.language, "→", newLang);
  }
});
```

## ✅ Auto-Load All Languages (Default)

**All endpoints MUST auto-detect and load ALL available languages:**

```python
# ✅ CORRECT Pattern
available_languages = db.presentation_subtitles.distinct(
    "language",
    {"presentation_id": presentation_id}
)
# Use all available, don't filter

# ❌ WRONG Pattern
allowed_languages = config.get("allowed_languages", ["vi", "en"])
# Hardcoded fallback blocks new languages!
```

## 📚 References

- ISO 639-1: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
- BCP 47: https://tools.ietf.org/html/bcp47
- Google TTS Voices: https://cloud.google.com/text-to-speech/docs/voices

---

**Rule of Thumb:** If you see a hyphen in a language code in the database, it's wrong! Fix it.
