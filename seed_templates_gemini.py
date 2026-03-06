"""
Generate code templates for learning topics using Gemini Flash.

TEST MODE: Processes only 2 topics by default (3 templates each).
FULL MODE: Run with --all to process all topics missing templates.

Usage:
    ./copy-and-run.sh seed_templates_gemini.py --bg --deps
    ./copy-and-run.sh "seed_templates_gemini.py --all" --bg --deps
    ./copy-and-run.sh "seed_templates_gemini.py --category javascript --limit 5" --bg --deps

What it does:
  1. Finds topics with template_count == 0
  2. Calls Gemini Flash to generate 3 code templates per topic
  3. Also creates/finds appropriate code_template_categories entries
  4. Inserts into code_templates collection
"""

import sys
import os
import time
import json
import uuid
import argparse
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from pymongo import MongoClient
import httpx

# ── Config ─────────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin",
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash-lite"  # or gemini-1.5-flash-latest
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
REQUEST_DELAY = 1.2   # seconds between API calls
MAX_RETRIES = 3
TEMPLATES_PER_TOPIC = 3

now = datetime.now(timezone.utc)
client = MongoClient(MONGO_URI)
db = client["ai_service_db"]


# ── Get next category display_order ────────────────────────────────────────────
def get_next_category_order() -> int:
    last = db.code_template_categories.find_one(sort=[("display_order", -1)])
    return (last["display_order"] + 1) if last else 1


# ── Helpers ─────────────────────────────────────────────────────────────────────
LANG_MAP = {
    "python": "python",
    "javascript": "javascript",
    "java": "java",
    "c-cpp": "c_cpp",
    "rust": "rust",
    "go": "go",
    "html-css": "html",
    "sql": "sql",
    "software-architecture": "python",
    "ai": "python",
}

LANG_EXT = {
    "python": ".py",
    "javascript": ".js",
    "java": ".java",
    "c_cpp": ".cpp",
    "rust": ".rs",
    "go": ".go",
    "html": ".html",
    "css": ".css",
    "sql": ".sql",
}


def get_language(category_id: str) -> str:
    return LANG_MAP.get(category_id, "python")


def gemini_call(prompt: str, max_tokens: int = 4000) -> str:
    """Call Gemini Flash API. Returns text response or raises."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        },
    }

    url = f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"    [WARN] Gemini attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise


# ── Category Management ─────────────────────────────────────────────────────────
def ensure_category(topic: dict) -> str:
    """Ensure a code_template_category exists for this topic. Returns category_id."""
    # Use topic_id as category slug
    cat_id = f"tmpl-{topic['id']}"
    
    existing = db.code_template_categories.find_one({"slug": cat_id})
    if existing:
        return existing["id"] if "id" in existing else cat_id

    language = get_language(topic["category_id"])
    order = get_next_category_order()

    cat_doc = {
        "id": cat_id,
        "name": topic["name"],
        "slug": cat_id,
        "language": language,
        "description": topic.get("description", f"Templates for {topic['name']}"),
        "icon": topic.get("icon", "📝"),
        "color": "#3B82F6",
        "template_count": 0,
        "display_order": order,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.code_template_categories.insert_one(cat_doc)
    print(f"    [CAT] Created category: {cat_id}")
    return cat_id


# ── Template Generation ─────────────────────────────────────────────────────────
TEMPLATE_PROMPT = """Tạo {count} code templates thực tế cho lập trình viên học topic sau:

Topic: {topic_name}
Category: {category_id}
Level: {level}
Language: {language}
Description: {description}

Yêu cầu mỗi template:
- Code đầy đủ, chạy được, có nhiều comments tiếng Việt giải thích
- Minh họa 1 khái niệm/pattern cụ thể của topic
- Độ dài code: 15-50 dòng (vừa đủ để học, không quá phức tạp)
- Title ngắn gọn mô tả template làm gì
- Description 1-2 câu tiếng Việt
- Khó độ phù hợp level (template 1: beginner, 2: beginner/intermediate, 3: intermediate)
- Tags liên quan

Template 1: Ví dụ cơ bản nhất của topic
Template 2: Ví dụ thực tế hơn hoặc pattern phổ biến
Template 3: Ví dụ nâng cao hơn hoặc use case thực tế

Trả về JSON array CHÍNH XÁC (không thêm text ngoài JSON):
[
  {{
    "title": "Tiêu đề template 1",
    "description": "Mô tả ngắn",
    "difficulty": "beginner",
    "code": "// Code với comments\\n// giải thích...",
    "tags": ["tag1", "tag2"]
  }},
  {{
    "title": "Tiêu đề template 2",
    "description": "Mô tả ngắn",
    "difficulty": "beginner",
    "code": "...",
    "tags": [...]
  }},
  {{
    "title": "Tiêu đề template 3",
    "description": "Mô tả ngắn",
    "difficulty": "intermediate",
    "code": "...",
    "tags": [...]
  }}
]"""


def generate_templates(topic: dict, count: int = TEMPLATES_PER_TOPIC) -> list | None:
    """Generate code templates using Gemini Flash."""
    language = get_language(topic["category_id"])
    prompt = TEMPLATE_PROMPT.format(
        count=count,
        topic_name=topic["name"],
        category_id=topic["category_id"],
        level=topic.get("level", "beginner"),
        language=language,
        description=topic.get("description", ""),
    )

    try:
        raw = gemini_call(prompt, max_tokens=4000)
        raw = raw.strip()

        # Strip markdown code fence if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            raw = "\n".join(lines[start:end])

        data = json.loads(raw.strip())
        if isinstance(data, list):
            return data[:count]
        return None

    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON parse failed for {topic['id']}: {e}")
        print(f"    Raw (first 300 chars): {raw[:300]}")
        return None
    except Exception as e:
        print(f"    [ERROR] Template generation failed for {topic['id']}: {e}")
        return None


def insert_templates(topic: dict, templates: list, category_id: str) -> int:
    """Insert templates into code_templates collection."""
    language = get_language(topic["category_id"])
    inserted = 0

    for i, tmpl in enumerate(templates, start=1):
        template_id = str(uuid.uuid4())

        doc = {
            "id": template_id,
            "title": tmpl.get("title", f"Template {i} — {topic['name']}"),
            "name": tmpl.get("title", f"Template {i}"),  # legacy field
            "category": category_id,
            "category_id": topic["category_id"],
            "topic_id": topic["id"],
            "programming_language": language,
            "difficulty": tmpl.get("difficulty", "beginner"),
            "description": tmpl.get("description", ""),
            "code": tmpl.get("code", ""),
            "tags": tmpl.get("tags", []),
            "is_featured": False,
            "is_active": True,
            "is_published": True,
            "source_type": "wordai_team",
            "metadata": {
                "author": "WordAI Team",
                "version": "1.0",
                "usage_count": 0,
                "dependencies": [],
            },
            "display_order": inserted + 1,
            "created_at": now,
            "updated_at": now,
        }

        db.code_templates.insert_one(doc)
        inserted += 1

    if inserted > 0:
        # Update template_count on topic
        db.learning_topics.update_one(
            {"id": topic["id"]},
            {"$inc": {"template_count": inserted}}
        )
        # Update template_count on category
        db.code_template_categories.update_one(
            {"id": category_id},
            {"$inc": {"template_count": inserted}}
        )
    print(f"    [OK] Inserted {inserted} templates for {topic['id']}")
    return inserted


# ── Main ─────────────────────────────────────────────────────────────────────────
def get_topics_missing_templates(category_id: str = None, limit: int = None) -> list:
    """Find topics with 0 code templates."""
    query = {"template_count": {"$lte": 0}, "is_active": True}
    if category_id:
        query["category_id"] = category_id

    cursor = db.learning_topics.find(query).sort("order", 1)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def main():
    parser = argparse.ArgumentParser(description="Seed code templates via Gemini Flash")
    parser.add_argument("--all", action="store_true", help="Process ALL topics missing templates")
    parser.add_argument("--category", type=str, help="Filter by category_id")
    parser.add_argument("--limit", type=int, default=2, help="Max topics (default: 2 for test)")
    parser.add_argument("--count", type=int, default=TEMPLATES_PER_TOPIC,
                        help=f"Templates per topic (default: {TEMPLATES_PER_TOPIC})")
    args = parser.parse_args()

    limit = None if args.all else args.limit

    print("=" * 70)
    print(f"Seed Code Templates via Gemini Flash")
    print(f"  Mode    : {'ALL (full run)' if args.all else f'TEST ({limit} topics)'}")
    print(f"  Per topic: {args.count} templates")
    if args.category:
        print(f"  Category: {args.category}")
    print("=" * 70)

    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set. Exiting.")
        sys.exit(1)

    topics = get_topics_missing_templates(category_id=args.category, limit=limit)
    print(f"\nFound {len(topics)} topics missing templates")

    stats = {"topics": 0, "templates": 0, "errors": 0}

    for idx, topic in enumerate(topics, start=1):
        print(f"\n[{idx}/{len(topics)}] {topic['id']} — {topic['name']} ({topic.get('level', '?')})")

        # Ensure category entry exists
        cat_id = ensure_category(topic)

        # Generate templates
        print(f"  → Calling Gemini Flash ({args.count} templates)...")
        templates = generate_templates(topic, count=args.count)

        if templates:
            n = insert_templates(topic, templates, cat_id)
            stats["templates"] += n
            stats["topics"] += 1
        else:
            print(f"  [SKIP] No templates generated for {topic['id']}")
            stats["errors"] += 1

        time.sleep(REQUEST_DELAY)

    # Summary
    print("\n" + "=" * 70)
    print("DONE — Summary:")
    print(f"  Topics processed  : {stats['topics']}")
    print(f"  Templates created : {stats['templates']}")
    print(f"  Errors            : {stats['errors']}")

    total_tmpl = db.code_templates.count_documents({})
    print(f"\nDB total code_templates: {total_tmpl}")
    print("=" * 70)


if __name__ == "__main__":
    main()
