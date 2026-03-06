"""
Generate knowledge articles AND code exercises for learning topics using DeepSeek.

TEST MODE: Processes only 2 topics by default.
FULL MODE: Run with --all to process all topics missing knowledge.

Usage:
    ./copy-and-run.sh seed_knowledge_deepseek.py --bg --deps
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all" --bg --deps
    ./copy-and-run.sh "seed_knowledge_deepseek.py --category javascript --limit 5" --bg --deps

What it does:
  1. Finds topics with 0 knowledge_articles
  2. Calls DeepSeek to generate 1 markdown knowledge article per topic (Vietnamese)
  3. Calls DeepSeek to generate 2 code exercises per topic
  4. Inserts into knowledge_articles + code_exercises collections
"""

import sys
import os
import time
import json
import random
import string
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
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
REQUEST_DELAY = 1.5  # seconds between API calls
MAX_RETRIES = 3

now = datetime.now(timezone.utc)
client = MongoClient(MONGO_URI)
db = client["ai_service_db"]


# ── Helpers ─────────────────────────────────────────────────────────────────────
def rand_id(prefix: str = "", length: int = 8) -> str:
    chars = string.ascii_lowercase + string.digits
    suffix = "".join(random.choices(chars, k=length))
    return f"{prefix}{suffix}" if prefix else suffix


def deepseek_call(prompt: str, system: str = "", max_tokens: int = 3000) -> str:
    """Call DeepSeek chat API. Returns text response or raises."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set in environment")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                DEEPSEEK_ENDPOINT, json=payload, headers=headers, timeout=120
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    [WARN] DeepSeek attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise


# ── Knowledge Article Generation ────────────────────────────────────────────────
KNOWLEDGE_SYSTEM = """Bạn là technical writer chuyên viết tài liệu lập trình bằng tiếng Việt.
Viết bài giảng học lập trình chất lượng cao, rõ ràng, có ví dụ code cụ thể.
Output PHẢI là JSON hợp lệ theo schema được yêu cầu. Không thêm text ngoài JSON."""

KNOWLEDGE_PROMPT = """Tạo 1 bài học cho topic lập trình sau:

Topic ID: {topic_id}
Topic Name: {topic_name}
Category: {category_id}
Level: {level}
Description: {description}

Yêu cầu bài học:
- Ngôn ngữ: Tiếng Việt
- Độ dài content: 600-1000 từ
- Format: Markdown với headers, code blocks, bullet points
- Có ít nhất 2 ví dụ code thực tế (code block với syntax highlighting)
- Giải thích rõ ràng, dễ hiểu cho level {level}
- Tags liên quan

Trả về JSON theo schema sau CHÍNH XÁC:
{{
  "title": "Tiêu đề bài học tiếng Việt (ngắn gọn, rõ ràng)",
  "excerpt": "Tóm tắt 1-2 câu về nội dung bài học",
  "content": "Nội dung markdown đầy đủ",
  "tags": ["tag1", "tag2", "tag3"],
  "difficulty": "{difficulty}"
}}"""


def generate_knowledge(topic: dict) -> dict | None:
    """Generate 1 knowledge article for a topic using DeepSeek."""
    level = topic.get("level", "beginner")
    difficulty = (
        "beginner"
        if level in ("beginner",)
        else ("intermediate" if level in ("intermediate", "practical") else "advanced")
    )

    prompt = KNOWLEDGE_PROMPT.format(
        topic_id=topic["id"],
        topic_name=topic["name"],
        category_id=topic["category_id"],
        level=level,
        description=topic.get("description", ""),
        difficulty=difficulty,
    )

    try:
        raw = deepseek_call(prompt, system=KNOWLEDGE_SYSTEM, max_tokens=3000)
        # Extract JSON from possible markdown code fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return data
    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON parse failed for {topic['id']}: {e}")
        return None
    except Exception as e:
        print(f"    [ERROR] Knowledge generation failed for {topic['id']}: {e}")
        return None


def insert_knowledge(topic: dict, article_data: dict) -> str | None:
    """Insert a knowledge article into MongoDB."""
    article_id = f"ka-{topic['id']}-01"

    # Check for duplicate
    if db.knowledge_articles.find_one({"id": article_id}):
        print(f"    [SKIP] Knowledge article {article_id} already exists")
        return None

    doc = {
        "id": article_id,
        "topic_id": topic["id"],
        "category_id": topic["category_id"],
        "title": article_data["title"],
        "title_multilang": {"vi": article_data["title"]},
        "content": article_data["content"],
        "content_multilang": {"vi": article_data["content"]},
        "excerpt": article_data.get("excerpt", ""),
        "excerpt_multilang": {"vi": article_data.get("excerpt", "")},
        "available_languages": ["vi"],
        "difficulty": article_data.get("difficulty", "beginner"),
        "tags": article_data.get("tags", []),
        "source_type": "wordai_team",
        "created_by": "system",
        "author_name": "WordAI Team",
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "is_published": True,
        "is_featured": False,
        "created_at": now,
        "updated_at": now,
        "published_at": now,
    }
    db.knowledge_articles.insert_one(doc)
    # Update topic knowledge_count
    db.learning_topics.update_one({"id": topic["id"]}, {"$inc": {"knowledge_count": 1}})
    print(f"    [OK] Inserted knowledge article: {article_id}")
    return article_id


# ── Exercise Generation ──────────────────────────────────────────────────────────
EXERCISE_SYSTEM = """Bạn là giáo viên lập trình chuyên tạo bài tập thực hành.
Tạo bài tập coding chất lượng, rõ ràng với yêu cầu cụ thể.
Output PHẢI là JSON hợp lệ theo schema được yêu cầu. Không thêm text ngoài JSON."""

EXERCISE_PROMPT = """Tạo 2 bài tập coding cho topic:

Topic ID: {topic_id}
Topic Name: {topic_name}
Category: {category_id}
Level: {level}
Language: {language}

Yêu cầu mỗi bài tập:
- Tiêu đề rõ ràng bằng tiếng Việt
- Mô tả bài toán chi tiết (tiếng Việt)
- Starter code (có comments hướng dẫn)
- 2-3 test cases với input/expected_output
- Hints để gợi ý (không spoil đáp án)
- Bài 1: difficulty = beginner
- Bài 2: difficulty = intermediate

Trả về JSON array CHÍNH XÁC:
[
  {{
    "title": "Tiêu đề bài tập 1",
    "description": "Mô tả yêu cầu chi tiết bằng tiếng Việt",
    "difficulty": "beginner",
    "starter_code": "# Code khởi đầu với comments\\n# TODO: implement...",
    "test_cases": [
      {{"input": "input1", "expected_output": "output1", "description": "Test case 1"}},
      {{"input": "input2", "expected_output": "output2", "description": "Test case 2"}}
    ],
    "hints": ["Gợi ý 1", "Gợi ý 2"],
    "tags": ["tag1", "tag2"],
    "estimated_minutes": 20
  }},
  {{
    "title": "Tiêu đề bài tập 2",
    "description": "...",
    "difficulty": "intermediate",
    "starter_code": "...",
    "test_cases": [...],
    "hints": [...],
    "tags": [...],
    "estimated_minutes": 35
  }}
]"""

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


def generate_exercises(topic: dict) -> list | None:
    """Generate 2 exercises for a topic using DeepSeek."""
    language = get_language(topic["category_id"])
    prompt = EXERCISE_PROMPT.format(
        topic_id=topic["id"],
        topic_name=topic["name"],
        category_id=topic["category_id"],
        level=topic.get("level", "beginner"),
        language=language,
    )

    try:
        raw = deepseek_call(prompt, system=EXERCISE_SYSTEM, max_tokens=3000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON parse failed for exercises {topic['id']}: {e}")
        return None
    except Exception as e:
        print(f"    [ERROR] Exercise generation failed for {topic['id']}: {e}")
        return None


def insert_exercises(topic: dict, exercises: list):
    """Insert exercises into MongoDB."""
    language = get_language(topic["category_id"])
    inserted = 0

    for i, ex in enumerate(exercises, start=1):
        ex_id = f"ex-{topic['id']}-{i:02d}"
        if db.code_exercises.find_one({"id": ex_id}):
            print(f"    [SKIP] Exercise {ex_id} already exists")
            continue

        doc = {
            "id": ex_id,
            "topic_id": topic["id"],
            "category_id": topic["category_id"],
            "title": ex.get("title", f"Bài tập {i}"),
            "description": ex.get("description", ""),
            "difficulty": ex.get("difficulty", "beginner"),
            "programming_language": language,
            "starter_code": ex.get("starter_code", ""),
            "solution_code": "",  # Will be added manually later
            "test_cases": ex.get("test_cases", []),
            "hints": ex.get("hints", []),
            "tags": ex.get("tags", []),
            "estimated_minutes": ex.get("estimated_minutes", 30),
            "grading_type": "test_cases",
            "source_type": "wordai_team",
            "created_by": "system",
            "author_name": "WordAI Team",
            "submission_count": 0,
            "pass_rate": 0.0,
            "is_published": True,
            "is_featured": False,
            "created_at": now,
            "updated_at": now,
        }
        db.code_exercises.insert_one(doc)
        inserted += 1

    # Update topic exercise_count
    if inserted > 0:
        db.learning_topics.update_one(
            {"id": topic["id"]}, {"$inc": {"exercise_count": inserted}}
        )
    print(f"    [OK] Inserted {inserted} exercises for {topic['id']}")


# ── Main ─────────────────────────────────────────────────────────────────────────
def get_topics_missing_knowledge(category_id: str = None, limit: int = None) -> list:
    """Find topics with 0 knowledge articles."""
    query = {"knowledge_count": {"$lte": 0}, "is_active": True}
    if category_id:
        query["category_id"] = category_id

    cursor = db.learning_topics.find(query).sort("order", 1)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def main():
    parser = argparse.ArgumentParser(
        description="Seed knowledge articles + exercises via DeepSeek"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process ALL topics missing knowledge (not just 2)",
    )
    parser.add_argument("--category", type=str, help="Filter by category_id")
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Max topics to process (default: 2 for test)",
    )
    parser.add_argument(
        "--skip-exercises", action="store_true", help="Skip exercise generation"
    )
    args = parser.parse_args()

    limit = None if args.all else args.limit

    print("=" * 70)
    print(f"Seed Knowledge + Exercises via DeepSeek")
    print(f"  Mode: {'ALL (full run)' if args.all else f'TEST ({limit} topics)'}")
    if args.category:
        print(f"  Category filter: {args.category}")
    print("=" * 70)

    if not DEEPSEEK_API_KEY:
        print("[ERROR] DEEPSEEK_API_KEY not set. Exiting.")
        sys.exit(1)

    topics = get_topics_missing_knowledge(category_id=args.category, limit=limit)
    print(f"\nFound {len(topics)} topics missing knowledge articles")

    stats = {"topics": 0, "knowledge": 0, "exercises": 0, "errors": 0}

    for idx, topic in enumerate(topics, start=1):
        print(
            f"\n[{idx}/{len(topics)}] {topic['id']} — {topic['name']} ({topic.get('level', '?')})"
        )

        # === Knowledge Article ===
        print(f"  → Generating knowledge article...")
        article_data = generate_knowledge(topic)
        if article_data:
            result = insert_knowledge(topic, article_data)
            if result:
                stats["knowledge"] += 1
        else:
            print(f"  [SKIP] No article generated for {topic['id']}")
            stats["errors"] += 1

        time.sleep(REQUEST_DELAY)

        # === Exercises ===
        if not args.skip_exercises:
            print(f"  → Generating exercises...")
            exercises = generate_exercises(topic)
            if exercises:
                insert_exercises(topic, exercises)
                stats["exercises"] += len(exercises)
            else:
                print(f"  [SKIP] No exercises generated for {topic['id']}")
                stats["errors"] += 1

            time.sleep(REQUEST_DELAY)

        stats["topics"] += 1

    # Final summary
    print("\n" + "=" * 70)
    print("DONE — Summary:")
    print(f"  Topics processed : {stats['topics']}")
    print(f"  Knowledge created: {stats['knowledge']}")
    print(f"  Exercises created: {stats['exercises']}")
    print(f"  Errors           : {stats['errors']}")

    total_ka = db.knowledge_articles.count_documents({})
    total_ex = db.code_exercises.count_documents({})
    print(f"\nDB totals — knowledge_articles: {total_ka}, code_exercises: {total_ex}")
    print("=" * 70)


if __name__ == "__main__":
    main()
