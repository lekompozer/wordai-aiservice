"""
Generate code templates for learning topics using Claude via Vertex AI.

TEST MODE: Processes only 2 topics by default (3 templates each).
FULL MODE: Run with --all to process all topics missing templates.

Usage:
    ./copy-and-run.sh seed_templates_gemini.py --bg --deps
    ./copy-and-run.sh "seed_templates_gemini.py --all" --bg --deps
    ./copy-and-run.sh "seed_templates_gemini.py --category javascript --limit 5" --bg --deps

What it does:
  1. Finds topics with template_count == 0
  2. Calls Claude via Vertex AI to generate 3 code templates per topic
  3. Also creates/finds appropriate code_template_categories entries
  4. Inserts into code_templates collection
"""

import sys
import os
import re
import time
import json
import uuid
import argparse
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from pymongo import MongoClient
from anthropic import AnthropicVertex

# ── Config ────────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv(
    "MONGODB_URI_AUTH",
    "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin",
)
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "wordai-6779e")
GCP_REGION = os.getenv("GCP_REGION", "asia-southeast1")
CLAUDE_MODEL = "claude-sonnet-4-6"
REQUEST_DELAY = 1.5  # seconds between API calls
MAX_RETRIES = 3
TEMPLATES_PER_TOPIC = 3

now = datetime.now(timezone.utc)
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ai_service_db"]

# Initialize Vertex AI Claude client
vertex_client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT_ID)


# ── Get next category display_order ──────────────────────────────────────────
def get_next_category_order() -> int:
    last = db.code_template_categories.find_one(sort=[("display_order", -1)])
    if not last:
        last = db.code_template_categories.find_one(sort=[("order", -1)])
    if not last:
        return 1
    return (last.get("display_order") or last.get("order") or 0) + 1


# ── Helpers ───────────────────────────────────────────────────────────────────
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


def get_language(category_id: str) -> str:
    return LANG_MAP.get(category_id, "python")


def claude_call(prompt: str, max_tokens: int = 4000) -> str:
    """Call Claude via Vertex AI. Returns text response or raises."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            message = vertex_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            print(
                f"    [WARN] Claude Vertex attempt {attempt}/{MAX_RETRIES} failed: {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise


# ── Category Management ───────────────────────────────────────────────────────
def ensure_category(topic: dict) -> str:
    """Ensure a code_template_category exists for this topic. Returns category_id."""
    cat_id = f"tmpl-{topic['id']}"

    existing = db.code_template_categories.find_one({"slug": cat_id})
    if existing:
        return existing.get("id", cat_id)

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


# ── Template Generation ───────────────────────────────────────────────────────
TEMPLATE_PROMPT = """Generate exactly {count} code templates for developers learning this topic:

Topic: {topic_name}
Category: {category_id}
Level: {level}
Language: {language}
Description: {description}

Requirements for each template:
- Complete, runnable code with Vietnamese comments explaining key concepts
- Demonstrates one specific concept/pattern of the topic
- Code length: 15-50 lines (enough to learn, not too complex)
- Short title describing what the template does
- 1-2 sentence Vietnamese description
- Appropriate difficulty level (template 1: beginner, 2: beginner/intermediate, 3: intermediate)
- Relevant tags

Template 1: Most basic example of the topic
Template 2: More practical example or common pattern
Template 3: More advanced example or real-world use case

Return EXACTLY this JSON array (no text outside JSON):
[
  {{
    "title": "Template title 1",
    "description": "Short description in Vietnamese",
    "difficulty": "beginner",
    "code": "// Code with Vietnamese comments\\n// explaining concepts...",
    "tags": ["tag1", "tag2"]
  }},
  {{
    "title": "Template title 2",
    "description": "Short description",
    "difficulty": "beginner",
    "code": "...",
    "tags": []
  }},
  {{
    "title": "Template title 3",
    "description": "Short description",
    "difficulty": "intermediate",
    "code": "...",
    "tags": []
  }}
]"""


def generate_templates(topic: dict, count: int = TEMPLATES_PER_TOPIC):
    """Generate code templates using Claude via Vertex AI. Returns list or None."""
    language = get_language(topic["category_id"])
    prompt = TEMPLATE_PROMPT.format(
        count=count,
        topic_name=topic["name"],
        category_id=topic["category_id"],
        level=topic.get("level", "beginner"),
        language=language,
        description=topic.get("description", ""),
    )

    raw = ""
    try:
        raw = claude_call(prompt, max_tokens=4000)
        raw = raw.strip()

        # Strip markdown code fence if present
        if "```" in raw:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
            if m:
                raw = m.group(1).strip()

        data = json.loads(raw)
        if isinstance(data, list):
            return data[:count]
        return None

    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON parse failed for {topic['id']}: {e}")
        print(f"    Raw (first 300): {raw[:300]}")
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
            "title": tmpl.get("title", f"Template {i} - {topic['name']}"),
            "name": tmpl.get("title", f"Template {i}"),
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
            "display_order": i,
            "created_at": now,
            "updated_at": now,
        }
        db.code_templates.insert_one(doc)
        inserted += 1

    if inserted > 0:
        db.learning_topics.update_one(
            {"id": topic["id"]}, {"$inc": {"template_count": inserted}}
        )
        db.code_template_categories.update_one(
            {"id": category_id}, {"$inc": {"template_count": inserted}}
        )
    print(f"    [OK] Inserted {inserted} templates for {topic['id']}")
    return inserted


# ── Main ──────────────────────────────────────────────────────────────────────
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
    parser = argparse.ArgumentParser(
        description="Seed code templates via Claude Vertex AI"
    )
    parser.add_argument(
        "--all", action="store_true", help="Process ALL topics missing templates"
    )
    parser.add_argument("--category", type=str, help="Filter by category_id")
    parser.add_argument(
        "--limit", type=int, default=2, help="Max topics (default: 2 for test)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=TEMPLATES_PER_TOPIC,
        help=f"Templates per topic (default: {TEMPLATES_PER_TOPIC})",
    )
    args = parser.parse_args()

    limit = None if args.all else args.limit

    print("=" * 70)
    print("Seed Code Templates via Claude Vertex AI")
    print(f"  Model    : {CLAUDE_MODEL}")
    print(f"  Mode     : {'ALL (full run)' if args.all else f'TEST ({limit} topics)'}")
    print(f"  Per topic: {args.count} templates")
    if args.category:
        print(f"  Category : {args.category}")
    print("=" * 70)

    topics = get_topics_missing_templates(category_id=args.category, limit=limit)
    print(f"\nFound {len(topics)} topics missing templates")

    stats = {"topics": 0, "templates": 0, "errors": 0}

    for idx, topic in enumerate(topics, start=1):
        print(
            f"\n[{idx}/{len(topics)}] {topic['id']} - {topic['name']} ({topic.get('level', '?')})"
        )

        cat_id = ensure_category(topic)

        print(f"  -> Calling Claude Vertex AI ({args.count} templates)...")
        templates = generate_templates(topic, count=args.count)

        if templates:
            n = insert_templates(topic, templates, cat_id)
            stats["templates"] += n
            stats["topics"] += 1
        else:
            print(f"  [SKIP] No templates generated for {topic['id']}")
            stats["errors"] += 1

        time.sleep(REQUEST_DELAY)

    print("\n" + "=" * 70)
    print("DONE - Summary:")
    print(f"  Topics processed  : {stats['topics']}")
    print(f"  Templates created : {stats['templates']}")
    print(f"  Errors            : {stats['errors']}")

    total_tmpl = db.code_templates.count_documents({})
    print(f"\nDB total code_templates: {total_tmpl}")
    print("=" * 70)


if __name__ == "__main__":
    main()
