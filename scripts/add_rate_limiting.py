"""
Script to add rate limiting to expensive AI endpoints
Run this to update all endpoints that need rate limiting
"""

# List of endpoints that need rate limiting
ENDPOINTS_TO_UPDATE = {
    "src/api/translation_job_routes.py": {
        "endpoint": "start_translation_job",
        "action": "chapter_translation",
        "line_after": 'user_id = user["uid"]',
    },
    "src/api/ai_editor_routes.py": {
        "endpoints": [
            {"name": "edit_by_ai", "action": "ai_edit"},
            {"name": "translate_document", "action": "ai_translate"},
            {"name": "format_document", "action": "ai_format"},
        ]
    },
    "src/api/test_creation_routes.py": {
        "endpoints": [
            {"name": "generate_test", "action": "test_generation"},
            {"name": "generate_general_test", "action": "test_generation"},
            {"name": "generate_listening_test", "action": "test_generation"},
        ]
    },
    "src/api/slide_ai_routes.py": {
        "endpoints": [
            {"name": "generate_slides_batch", "action": "slide_ai_batch"},
            {"name": "generate_single_slide", "action": "slide_ai_single"},
        ]
    },
    "src/api/slide_narration_routes.py": {
        "endpoints": [
            {"name": "generate_subtitles", "action": "subtitle_generation"},
            {"name": "generate_audio", "action": "audio_generation"},
        ]
    },
}

# Code to insert after getting user_id
RATE_LIMIT_CODE = """
    # ✅ SECURITY: Rate limiting for expensive AI operation
    from src.middleware.rate_limiter import check_ai_rate_limit
    from src.queue.queue_manager import get_redis_client

    redis_client = get_redis_client()
    await check_ai_rate_limit(
        user_id=user_id,
        action="{action}",
        redis_client=redis_client,
    )
"""

print("=" * 80)
print("RATE LIMITING UPDATE SCRIPT")
print("=" * 80)
print("\nEndpoints that need manual rate limiting:\n")

for file_path, config in ENDPOINTS_TO_UPDATE.items():
    print(f"\n📁 {file_path}")

    if "endpoints" in config:
        for endpoint_config in config["endpoints"]:
            endpoint_name = endpoint_config["name"]
            action = endpoint_config["action"]

            print(f"\n  🔧 Function: {endpoint_name}()")
            print(f"     Action: {action}")
            print(f"     Add after: user_id = user['uid']")
            print("\n     Code to insert:")
            print(RATE_LIMIT_CODE.format(action=action).replace("\n    ", "\n        "))
    else:
        endpoint_name = config["endpoint"]
        action = config["action"]
        print(f"\n  🔧 Function: {endpoint_name}()")
        print(f"     Action: {action}")
        print(f"     Add after: {config['line_after']}")
        print("\n     Code to insert:")
        print(RATE_LIMIT_CODE.format(action=action).replace("\n    ", "\n        "))

print("\n" + "=" * 80)
print("INSTRUCTIONS:")
print("=" * 80)
print(
    """
1. Open each file listed above
2. Find the function mentioned
3. Locate the line: user_id = user["uid"]
4. Add the rate limiting code right after
5. Update the 'action' parameter to match the endpoint type
6. Test the endpoint to verify rate limiting works

Example:

  async def start_translation_job(...):
      user_id = user["uid"]

      # ✅ Add this code block here:
      from src.middleware.rate_limiter import check_ai_rate_limit
      from src.queue.queue_manager import get_redis_client

      redis_client = get_redis_client()
      await check_ai_rate_limit(
          user_id=user_id,
          action="chapter_translation",
          redis_client=redis_client,
      )

      # ... rest of function

RATE LIMITS CONFIGURED:
- subtitle_generation: 20 requests/hour
- audio_generation: 15 requests/hour
- test_generation: 10 requests/hour
- ai_image_generation: 30 requests/hour
- ai_edit: 30 requests/hour
- ai_format: 30 requests/hour
- chapter_translation: 20 requests/hour
- slide_ai_batch: 10 requests/hour
- slide_ai_single: 50 requests/hour

See src/middleware/rate_limiter.py for full configuration.
"""
)

print("\n✅ Rate limiter middleware created at: src/middleware/rate_limiter.py")
print("⚠️  Now manually update each endpoint file as shown above")
