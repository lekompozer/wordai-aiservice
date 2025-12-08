# Listening Test Audio Management Endpoints

Cần thêm 2 endpoints vào `test_creation_routes.py`:

## 1. Delete Audio from Listening Test Section
```python
@router.delete("/{test_id}/audio-sections/{section_number}")
async def delete_listening_test_audio(
    test_id: str,
    section_number: int,
    user_info: dict = Depends(require_auth),
):
    """
    Delete audio file from a specific section of listening test (Owner only)

    - Removes audio_url and audio_file_id from audio_section
    - Keeps transcript and script intact
    - Audio file remains in library as archived
    """
```

## 2. Replace Audio for Listening Test Section
```python
@router.put("/{test_id}/audio-sections/{section_number}/audio")
async def replace_listening_test_audio(
    test_id: str,
    section_number: int,
    audio_file: UploadFile = File(...),
    user_info: dict = Depends(require_auth),
):
    """
    Replace audio file for a specific section (Owner only)

    - Uploads new audio to R2
    - Updates audio_url and audio_file_id
    - Saves to library
    - Archives old audio file
    """
```

## Owner View Response Structure

GET /api/v1/tests/{test_id} cho listening test owner sẽ trả về:

```json
{
  "test_type": "listening",
  "audio_sections": [
    {
      "section_number": 1,
      "section_title": "Hotel Booking Conversation",
      "audio_url": "https://static.wordai.pro/listening-tests/user123/test456/section_1.wav",
      "audio_file_id": "lib_abc123",
      "duration_seconds": 125,
      "transcript": "Customer: Good morning...\nAgent: Hello...",
      "script": {
        "speaker_roles": ["Customer", "Agent"],
        "lines": [
          {"speaker": 0, "text": "Good morning, I'd like to book a room"},
          {"speaker": 1, "text": "Of course! When would you like to check in?"}
        ]
      },
      "voice_config": {
        "voice_names": ["Aoede", "Charon"],
        "num_speakers": 2
      },
      "questions": [...]
    }
  ],
  "questions": [...],
  "num_audio_sections": 1
}
```
