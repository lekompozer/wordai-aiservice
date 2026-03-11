"""
Generate knowledge articles, code templates, and exercises for learning topics.

Knowledge  → Gemini (gemini-3.1-flash-lite-preview) — better structured articles
Templates  → DeepSeek  — 5 runnable code snippets per topic demonstrating concepts
Exercises  → Gemini    — disabled by default, enable with --with-exercises

Usage:
    # Full run — all categories, knowledge + templates:
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all" --bg --deps

    # Python only, knowledge + templates:
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all --category python" --bg --deps

    # Templates only (skip knowledge for already-done topics):
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all --category python --templates-only" --bg --deps

    # Include exercises too:
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all --category python --with-exercises" --bg --deps

    # Control template count per topic (default 5):
    ./copy-and-run.sh "seed_knowledge_deepseek.py --all --category python --templates-count 5" --bg --deps
"""

import sys
import os
import re
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
    "MONGODB_URI_AUTH",
    "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin",
)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
# Gemini direct API for exercises
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "wordai-6779e")
GCP_REGION = os.getenv("GCP_REGION", "asia-southeast1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
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


def gemini_call(prompt: str, max_tokens: int = 3000) -> str:
    """Call gemini-3.1-flash-lite-preview via Gemini direct API."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"    [WARN] Gemini attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise


# ── JSON Repair ───────────────────────────────────────────────────────────────
def _fix_json_strings(raw: str) -> str:
    """Escape literal newlines/tabs inside JSON string values (LLM often forgets)."""
    result = []
    in_string = False
    escape_next = False
    for ch in raw:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == "\\":
            result.append(ch)
            escape_next = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        elif in_string and ch == "\t":
            result.append("\\t")
        else:
            result.append(ch)
    return "".join(result)


def robust_json_parse(raw: str) -> any:
    """Parse JSON iteratively, fixing unescaped double-quotes at error positions.

    LLMs often forget to escape quotes inside code strings, e.g.:
      "code": "console.log("hello")"
    We detect the error position and escape the offending quote, then retry.
    """
    for _ in range(200):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            pos = e.pos
            if pos is None or pos >= len(raw):
                raise
            # The error is usually AT or just before a stray quote
            if raw[pos] == '"':
                raw = raw[:pos] + '\\"' + raw[pos + 1 :]
            elif pos > 0 and raw[pos - 1] == '"':
                raw = raw[: pos - 1] + '\\"' + raw[pos:]
            else:
                raise
    return json.loads(raw)


# ── Knowledge Article Generation ────────────────────────────────────────────────
KNOWLEDGE_SYSTEM = """You are a bilingual technical writer specializing in programming education.
Create high-quality programming lessons with practical code examples.
Output MUST be valid JSON only — no text outside the JSON object."""

KNOWLEDGE_PROMPT = """Create a complete programming lesson for the topic below in BOTH Vietnamese and English (single API call).

Topic: {topic_name}
Category: {category_id}
Level: {level}
Description: {description}

Return a JSON object with this EXACT structure (no text outside JSON):
{{
  "title_vi": "Tiêu đề ngắn gọn bằng tiếng Việt",
  "title_en": "Short title in English",
  "excerpt_vi": "Tóm tắt 1-2 câu bằng tiếng Việt",
  "excerpt_en": "1-2 sentence summary in English",
  "content_vi": "# Tiêu đề\\n\\n## Giới thiệu\\nNội dung markdown đầy đủ tiếng Việt (600-900 từ, ít nhất 3-4 ```python``` blocks với comment VI)",
  "content_en": "# Title\\n\\n## Introduction\\nFull English markdown content (600-900 words, same code examples but English comments)",
  "tags": ["tag1", "tag2", "tag3"],
  "difficulty": "{difficulty}"
}}

Requirements for content_vi: markdown with ##/### headings, Vietnamese throughout, 3-4 ```python``` code blocks with Vietnamese comments, Tóm tắt bullet section at end.
Requirements for content_en: same structure, English throughout, identical code examples with English comments, Summary bullet section at end.
"""


def generate_knowledge(topic: dict) -> dict | None:
    """Generate 1 bilingual knowledge article (VI+EN) for a topic using a single Gemini call."""
    level = topic.get("level", "beginner")
    difficulty = (
        "beginner"
        if level in ("beginner",)
        else ("intermediate" if level in ("intermediate", "practical") else "advanced")
    )

    # Single call: Gemini returns JSON with both VI and EN content
    prompt = (
        KNOWLEDGE_SYSTEM
        + "\n\n"
        + KNOWLEDGE_PROMPT.format(
            topic_name=topic["name"],
            category_id=topic["category_id"],
            level=level,
            description=topic.get("description", ""),
            difficulty=difficulty,
        )
    )
    raw = ""
    try:
        raw = gemini_call(prompt, max_tokens=8000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[^\n]*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw).strip()
        raw = _fix_json_strings(raw)
        data = robust_json_parse(raw)
        return data
    except json.JSONDecodeError as e:
        print(f"    [ERROR] Knowledge JSON parse failed for {topic['id']}: {e}")
        print(f"    Raw (first 400): {raw[:400]}")
        return None
    except Exception as e:
        print(f"    [ERROR] Knowledge generation failed for {topic['id']}: {e}")
        return None


def insert_knowledge(topic: dict, article_data: dict) -> str | None:
    """Insert a bilingual knowledge article into MongoDB."""
    article_id = f"ka-{topic['id']}-01"

    # Check for duplicate
    if db.knowledge_articles.find_one({"id": article_id}):
        print(f"    [SKIP] Knowledge article {article_id} already exists")
        return None

    title_vi = article_data.get("title_vi", topic["name"])
    title_en = article_data.get("title_en", topic["name"])
    excerpt_vi = article_data.get("excerpt_vi", "")
    excerpt_en = article_data.get("excerpt_en", "")
    content_vi = article_data.get("content_vi", "")
    content_en = article_data.get("content_en", "")

    doc = {
        "id": article_id,
        "topic_id": topic["id"],
        "category_id": topic["category_id"],
        "title": title_vi,
        "title_multilang": {"vi": title_vi, "en": title_en},
        "content": content_vi,
        "content_multilang": {"vi": content_vi, "en": content_en},
        "excerpt": excerpt_vi,
        "excerpt_multilang": {"vi": excerpt_vi, "en": excerpt_en},
        "available_languages": ["vi", "en"],
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


# ── Template Generation (DeepSeek) ─────────────────────────────────────────────
TEMPLATE_PROMPT = """Tạo {count} code template Python cho topic lập trình sau.
Mỗi template là một đoạn code MẪU, HOÀN CHỈNH, chạy được ngay — KHÔNG phải bài tập.

Topic ID: {topic_id}
Topic Name: {topic_name}
Level: {level}
Category: {category_id}

Yêu cầu từng template:
- title: Tiêu đề ngắn mô tả chính xác ví dụ (tiếng Việt)
- title_en: Same title in English
- description: 1 dòng mô tả template làm gì (tiếng Việt)
- description_en: Same description in English
- difficulty: "beginner" / "intermediate" / "advanced"
- code_vi: Code Python hoàn chỉnh, 20-80 dòng, comment TIẾNG VIỆT giải thích từng bước
- code_en: Code Python giống hệt code_vi nhưng tất cả comment đổi sang TIẾNG ANH
- tags: 2-4 tags liên quan (lowercase, dùng dấu gạch ngang)

Phân phối độ khó ({count} templates):
- 2 beginner: ví dụ đơn giản nhất của topic, dễ hiểu ngay
- 2 intermediate: kết hợp nhiều khái niệm, thực tế hơn
- 1 advanced: ứng dụng nâng cao hoặc bài toán thực tế

Mỗi template minh họa một KHÍA CẠNH KHÁC NHAU của topic — không lặp lại.
Code phải có print() để thấy kết quả khi chạy.
code_vi và code_en phải có cùng logic, chỉ khác phần comments.
TRONG CODE Python: dùng DẤU NHÁY ĐƠN (') cho strings, KHÔNG dùng dấu nháy kép (") để tránh lỗi JSON.

Ví dụ format (template cho vòng lặp for):
{{
  "title": "Vòng lặp for với range()",
  "title_en": "For loop with range()",
  "description": "Sử dụng range() để tạo vòng lặp với các bước khác nhau",
  "description_en": "Using range() to create loops with different step sizes",
  "difficulty": "beginner",
  "code_vi": "# range(start, stop, step)\nfor i in range(5):\n    # In số từ 0 đến 4\n    print(i)\n\n# Đếm ngược\nfor i in range(10, 0, -1):\n    print(i)",
  "code_en": "# range(start, stop, step)\nfor i in range(5):\n    # Print numbers from 0 to 4\n    print(i)\n\n# Count down\nfor i in range(10, 0, -1):\n    print(i)",
  "tags": ["for", "range", "vong-lap"]
}}

Trả về JSON ARRAY gồm đúng {count} objects. Không text ngoài JSON.
"""

TEMPLATE_PROMPT_EN = """Create {count} code templates for the following programming topic.
Each template is a COMPLETE, RUNNABLE code example — NOT an exercise.

Topic ID: {topic_id}
Topic Name: {topic_name}
Level: {level}
Category: {category_id}
Language: {lang}

Requirements per template:
- title: Short descriptive title in English
- description: 1-line description of what the template does (English)
- difficulty: "beginner" / "intermediate" / "advanced"
- code: Complete {lang} code, 20-80 lines, English comments explaining each step
- tags: 2-4 relevant tags (lowercase, hyphenated)

Difficulty distribution ({count} templates):
- 2 beginner: simplest examples, easy to understand immediately
- 2 intermediate: combining concepts, more practical
- 1 advanced: advanced usage or real-world problem

Each template demonstrates a DIFFERENT ASPECT of the topic — no repetition.
Code must produce visible output when run.
IMPORTANT: Use SINGLE QUOTES for string literals in code to avoid JSON parse errors.

Example format:
{{
  "title": "Basic array iteration",
  "description": "Iterate over an array using a for loop and print each element",
  "difficulty": "beginner",
  "code": "// Iterate over an array\nconst fruits = ['apple', 'banana', 'cherry'];\nfor (let i = 0; i < fruits.length; i++) {{\n    // Print each item\n    console.log(fruits[i]);\n}}",
  "tags": ["for-loop", "array", "iteration"]
}}

Return a JSON ARRAY of exactly {count} objects. No text outside JSON.
"""


def generate_templates(
    topic: dict, count: int = 5, exclude_titles: list = None, en_only: bool = False
) -> list | None:
    """Generate `count` code templates for a topic using DeepSeek."""
    level = topic.get("level", "beginner")
    lang = get_language(topic["category_id"])
    exclude_note = ""
    if exclude_titles:
        titles_str = "\n".join(f"- {t}" for t in exclude_titles)
        if en_only:
            exclude_note = f"\n\nEXISTING TITLES (do not repeat):\n{titles_str}\n"
        else:
            exclude_note = (
                f"\n\nCÁC TITLE ĐÃ TỒN TẠI (không được lặp lại):\n{titles_str}\n"
            )
    if en_only:
        prompt = (
            TEMPLATE_PROMPT_EN.format(
                count=count,
                topic_id=topic["id"],
                topic_name=topic["name"],
                level=level,
                category_id=topic["category_id"],
                lang=lang,
            )
            + exclude_note
        )
    else:
        prompt = (
            TEMPLATE_PROMPT.format(
                count=count,
                topic_id=topic["id"],
                topic_name=topic["name"],
                level=level,
                category_id=topic["category_id"],
            )
            + exclude_note
        )
    raw = ""
    try:
        raw = deepseek_call(prompt, system="", max_tokens=5000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[^\n]*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw).strip()
        raw = _fix_json_strings(raw)
        data = robust_json_parse(raw)
        if isinstance(data, list):
            return data
        print(f"    [WARN] Templates response is not a list for {topic['id']}")
        return None
    except json.JSONDecodeError as e:
        print(f"    [ERROR] Template JSON parse failed for {topic['id']}: {e}")
        print(f"    Raw (first 300): {raw[:300]}")
        return None
    except Exception as e:
        print(f"    [ERROR] Template generation failed for {topic['id']}: {e}")
        return None


def get_existing_template_titles(topic_id: str) -> set:
    """Return set of existing template titles for a topic."""
    return {
        doc["title"]
        for doc in db.code_templates.find(
            {"topic_id": topic_id}, {"title": 1, "_id": 0}
        )
    }


def insert_templates(topic: dict, templates: list, en_only: bool = False) -> int:
    """Insert new templates into code_templates, skip duplicates by title."""
    import uuid as _uuid

    existing_titles = get_existing_template_titles(topic["id"])
    inserted = 0
    language = get_language(topic["category_id"])

    for tmpl in templates:
        title = tmpl.get("title", "").strip()
        primary_code = (
            tmpl.get("code", "")
            if en_only
            else (tmpl.get("code_vi") or tmpl.get("code", ""))
        ).strip()
        if not title or not primary_code:
            continue
        if title in existing_titles:
            print(f"    [SKIP] Template already exists: {title}")
            continue

        if en_only:
            code = primary_code
            desc = tmpl.get("description", "")
            title_multilang = {"en": title}
            code_multilang = {"en": code}
            desc_multilang = {"en": desc}
            available_langs = ["en"]
        else:
            title_en = tmpl.get("title_en", title)
            code = primary_code  # code_vi
            code_en = tmpl.get("code_en", code)
            desc = tmpl.get("description", "")
            desc_en = tmpl.get("description_en", desc)
            title_multilang = {"vi": title, "en": title_en}
            code_multilang = {"vi": code, "en": code_en}
            desc_multilang = {"vi": desc, "en": desc_en}
            available_langs = ["vi", "en"]

        doc = {
            "id": str(_uuid.uuid4()),
            "topic_id": topic["id"],
            "category": topic["id"],  # legacy field
            "category_id": topic["category_id"],
            "title": title,
            "title_multilang": title_multilang,
            "programming_language": language,
            "code": code,
            "code_multilang": code_multilang,
            "description": desc,
            "description_multilang": desc_multilang,
            "available_languages": available_langs,
            "difficulty": tmpl.get("difficulty", "beginner"),
            "tags": tmpl.get("tags", []),
            "is_featured": False,
            "is_active": True,
            "is_published": True,
            "source_type": "wordai_team",
            "created_by": "system",
            "author_name": "WordAI Team",
            "metadata": {
                "author": "WordAI",
                "version": "1.0",
                "usage_count": 0,
                "dependencies": [],
            },
            "created_at": now,
            "updated_at": now,
        }
        db.code_templates.insert_one(doc)
        existing_titles.add(title)
        inserted += 1

    print(f"    [OK] Inserted {inserted} templates for {topic['id']}")
    return inserted


def get_topics_missing_templates(
    category_id: str = None, min_templates: int = 5, limit: int = None
) -> list:
    """Find topics that have fewer than min_templates code templates."""
    query = {"is_active": True}
    if category_id:
        query["category_id"] = category_id

    topics = list(db.learning_topics.find(query).sort("order", 1))
    result = []
    for t in topics:
        count = db.code_templates.count_documents({"topic_id": t["id"]})
        if count < min_templates:
            t["_current_templates"] = count
            result.append(t)
    if limit:
        result = result[:limit]
    return result


# ── Exercise Generation ──────────────────────────────────────────────────────────
EXERCISE_SYSTEM = """Bạn là giáo viên lập trình chuyên tạo bài tập thực hành.
Tạo bài tập coding chất lượng, rõ ràng với yêu cầu cụ thể.
Output PHẢI là JSON hợp lệ theo schema được yêu cầu. Không thêm text ngoài JSON."""

EXERCISE_SYSTEM_EN = """You are a programming instructor creating practical coding exercises.
Create clear, high-quality coding exercises with specific requirements.
Output MUST be valid JSON only — no text outside the JSON array."""

EXERCISE_PROMPT_EN = """Create 2 coding exercises for the following topic in English.

Topic ID: {topic_id}
Topic Name: {topic_name}
Category: {category_id}
Level: {level}
Language: {language}

Requirements per exercise:
- title: Clear descriptive title in English
- description: Detailed problem description in English
- starter_code: {language} code with English comments and TODO markers. Use SINGLE QUOTES for strings.
- 2-3 test cases with input/expected_output
- hints: 1-2 hints array in English (no spoilers)
- Exercise 1: difficulty = beginner
- Exercise 2: difficulty = intermediate

Return JSON array EXACTLY:
[
  {{
    "title": "Exercise title",
    "description": "Detailed requirements in English",
    "difficulty": "beginner",
    "starter_code": "// English comments\\n// TODO: implement...",
    "test_cases": [
      {{"input": "input1", "expected_output": "output1", "description": "Test 1"}},
      {{"input": "input2", "expected_output": "output2", "description": "Test 2"}}
    ],
    "hints": ["Hint 1", "Hint 2"],
    "tags": ["tag1", "tag2"],
    "estimated_minutes": 20
  }},
  {{
    "title": "Exercise title 2",
    "description": "...",
    "difficulty": "intermediate",
    "starter_code": "...",
    "test_cases": [...],
    "hints": [...],
    "tags": [...],
    "estimated_minutes": 35
  }}
]"""

EXERCISE_PROMPT = """Tạo 2 bài tập coding cho topic:

Topic ID: {topic_id}
Topic Name: {topic_name}
Category: {category_id}
Level: {level}
Language: {language}

Yêu cầu mỗi bài tập (trả về SONG NGỮ VI + EN trong cùng 1 JSON object):
- title: Tiêu đề rõ ràng bằng tiếng Việt | title_en: Same in English
- description: Mô tả chi tiết tiếng Việt | description_en: Same in English
- starter_code: Có comments TIẾNG VIỆT | starter_code_en: Có comments TIẾNG ANH (cùng logic)
- hints: Gợi ý tiếng Việt (array) | hints_en: Same hints in English (array)
- 2-3 test cases với input/expected_output
- Bài 1: difficulty = beginner
- Bài 2: difficulty = intermediate

Trả về JSON array CHÍNH XÁC:
[
  {{
    "title": "Tiêu đề bài tập 1 (VI)",
    "title_en": "Exercise title 1 (EN)",
    "description": "Mô tả yêu cầu chi tiết bằng tiếng Việt",
    "description_en": "Detailed requirement description in English",
    "difficulty": "beginner",
    "starter_code": "# Code khởi đầu với comments VI\\n# TODO: implement...",
    "starter_code_en": "# Starter code with EN comments\\n# TODO: implement...",
    "test_cases": [
      {{"input": "input1", "expected_output": "output1", "description": "Test case 1"}},
      {{"input": "input2", "expected_output": "output2", "description": "Test case 2"}}
    ],
    "hints": ["Gợi ý 1 (VI)", "Gợi ý 2 (VI)"],
    "hints_en": ["Hint 1 (EN)", "Hint 2 (EN)"],
    "tags": ["tag1", "tag2"],
    "estimated_minutes": 20
  }},
  {{
    "title": "Tiêu đề bài tập 2 (VI)",
    "title_en": "Exercise title 2 (EN)",
    "description": "...",
    "description_en": "...",
    "difficulty": "intermediate",
    "starter_code": "...",
    "starter_code_en": "...",
    "test_cases": [...],
    "hints": [...],
    "hints_en": [...],
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


def generate_exercises(topic: dict, en_only: bool = False) -> list | None:
    """Generate 2 exercises for a topic using Gemini."""
    language = get_language(topic["category_id"])
    if en_only:
        full_prompt = (
            EXERCISE_SYSTEM_EN
            + "\n\n"
            + EXERCISE_PROMPT_EN.format(
                topic_id=topic["id"],
                topic_name=topic["name"],
                category_id=topic["category_id"],
                level=topic.get("level", "beginner"),
                language=language,
            )
        )
    else:
        full_prompt = (
            EXERCISE_SYSTEM
            + "\n\n"
            + EXERCISE_PROMPT.format(
                topic_id=topic["id"],
                topic_name=topic["name"],
                category_id=topic["category_id"],
                level=topic.get("level", "beginner"),
                language=language,
            )
        )

    raw = ""
    try:
        raw = gemini_call(full_prompt, max_tokens=3000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[^\n]*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw).strip()
        raw = _fix_json_strings(raw)
        data = robust_json_parse(raw)
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError as e:
        print(f"    [ERROR] JSON parse failed for exercises {topic['id']}: {e}")
        print(f"    Raw (first 300): {raw[:300]}")
        return None
    except Exception as e:
        print(f"    [ERROR] Exercise generation failed for {topic['id']}: {e}")
        return None


def insert_exercises(topic: dict, exercises: list, en_only: bool = False):
    """Insert exercises into MongoDB."""
    language = get_language(topic["category_id"])
    inserted = 0

    for i, ex in enumerate(exercises, start=1):
        ex_id = f"ex-{topic['id']}-{i:02d}"
        if db.code_exercises.find_one({"id": ex_id}):
            print(f"    [SKIP] Exercise {ex_id} already exists")
            continue

        if en_only:
            title_vi = ex.get("title", f"Exercise {i}")
            title_en = title_vi
            desc_vi = ex.get("description", "")
            desc_en = desc_vi
            starter_vi = ex.get("starter_code", "")
            starter_en = starter_vi
            hints_vi = ex.get("hints", [])
            hints_en = hints_vi
            available_langs = ["en"]
        else:
            title_vi = ex.get("title", f"Bài tập {i}")
            title_en = ex.get("title_en", title_vi)
            desc_vi = ex.get("description", "")
            desc_en = ex.get("description_en", desc_vi)
            starter_vi = ex.get("starter_code", "")
            starter_en = ex.get("starter_code_en", starter_vi)
            hints_vi = ex.get("hints", [])
            hints_en = ex.get("hints_en", hints_vi)
            available_langs = ["vi", "en"]

        doc = {
            "id": ex_id,
            "topic_id": topic["id"],
            "category_id": topic["category_id"],
            "title": title_vi,
            "title_multilang": {"vi": title_vi, "en": title_en},
            "description": desc_vi,
            "description_multilang": {"vi": desc_vi, "en": desc_en},
            "difficulty": ex.get("difficulty", "beginner"),
            "programming_language": language,
            "starter_code": starter_vi,
            "starter_code_multilang": {"vi": starter_vi, "en": starter_en},
            "solution_code": "",  # Will be added manually later
            "test_cases": ex.get("test_cases", []),
            "hints": hints_vi,
            "hints_multilang": {"vi": hints_vi, "en": hints_en},
            "available_languages": available_langs,
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
    """Find topics with 0 knowledge articles (including topics where field is missing)."""
    query = {
        "$or": [
            {"knowledge_count": {"$exists": False}},
            {"knowledge_count": {"$lte": 0}},
        ],
        "is_active": True,
    }
    if category_id:
        query["category_id"] = category_id

    cursor = db.learning_topics.find(query).sort("order", 1)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def main():
    parser = argparse.ArgumentParser(
        description="Seed knowledge (Gemini) + templates (DeepSeek) + exercises (Gemini, optional)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Process ALL topics (not just 2)"
    )
    parser.add_argument("--category", type=str, help="Filter by category_id")
    parser.add_argument(
        "--limit", type=int, default=2, help="Max topics (default: 2 for test mode)"
    )
    parser.add_argument(
        "--templates-only",
        action="store_true",
        help="Skip knowledge, only generate templates",
    )
    parser.add_argument(
        "--knowledge-only", action="store_true", help="Skip templates and exercises"
    )
    parser.add_argument(
        "--with-exercises",
        action="store_true",
        help="Also generate exercises (disabled by default)",
    )
    parser.add_argument(
        "--templates-count",
        type=int,
        default=5,
        help="Templates to generate per topic (default: 5)",
    )
    parser.add_argument(
        "--templates-min",
        type=int,
        default=5,
        help="Re-generate if topic has fewer than N templates (default: 5)",
    )
    parser.add_argument(
        "--en-only",
        action="store_true",
        help="Generate EN-only content (simpler JSON, fewer parse errors — use for JS/SQL/etc.)",
    )
    args = parser.parse_args()

    limit = None if args.all else args.limit
    do_knowledge = not args.templates_only
    do_templates = not args.knowledge_only
    do_exercises = args.with_exercises
    en_only = args.en_only

    print("=" * 70)
    print("Seed: Knowledge [Gemini] + Templates [DeepSeek] + Exercises [Gemini]")
    print(f"  Mode         : {'ALL' if args.all else f'TEST ({limit} topics)'}")
    print(f"  Category     : {args.category or 'all'}")
    print(f"  Language     : {'EN only' if en_only else 'VI+EN bilingual'}")
    print(f"  Knowledge    : {'YES (Gemini)' if do_knowledge else 'SKIP'}")
    print(
        f"  Templates    : {'YES x' + str(args.templates_count) + ' (DeepSeek, min=' + str(args.templates_min) + ')' if do_templates else 'SKIP'}"
    )
    print(
        f"  Exercises    : {'YES (Gemini)' if do_exercises else 'SKIP (use --with-exercises to enable)'}"
    )
    print("=" * 70)

    if not DEEPSEEK_API_KEY:
        print("[ERROR] DEEPSEEK_API_KEY not set. Exiting.")
        sys.exit(1)
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set. Exiting.")
        sys.exit(1)

    # === Determine topics to process ===
    # Union of: topics missing knowledge + topics missing templates
    knowledge_topics = set()
    template_topics = set()
    all_topics_map = {}

    if do_knowledge:
        for t in get_topics_missing_knowledge(category_id=args.category, limit=limit):
            knowledge_topics.add(t["id"])
            all_topics_map[t["id"]] = t

    if do_templates:
        for t in get_topics_missing_templates(
            category_id=args.category,
            min_templates=args.templates_min,
            limit=limit,
        ):
            template_topics.add(t["id"])
            all_topics_map[t["id"]] = t

    all_topic_ids = sorted(knowledge_topics | template_topics)
    if limit and not args.all:
        all_topic_ids = all_topic_ids[:limit]

    print(f"\nTopics to process: {len(all_topic_ids)}")
    print(f"  Need knowledge : {len(knowledge_topics)}")
    if do_templates:
        print(
            f"  Need templates : {len(template_topics)} (< {args.templates_min} templates)"
        )

    stats = {"topics": 0, "knowledge": 0, "templates": 0, "exercises": 0, "errors": 0}

    for idx, tid in enumerate(all_topic_ids, start=1):
        topic = all_topics_map[tid]
        current_tmpl = topic.get(
            "_current_templates", db.code_templates.count_documents({"topic_id": tid})
        )
        print(
            f"\n[{idx}/{len(all_topic_ids)}] {tid} — {topic['name']} "
            f"(level={topic.get('level','?')}, templates={current_tmpl})"
        )

        # === Knowledge Article ===
        if do_knowledge and tid in knowledge_topics:
            article_id = f"ka-{tid}-01"
            if db.knowledge_articles.find_one({"id": article_id}):
                print(f"  [SKIP] Knowledge already exists: {article_id}")
            else:
                print(f"  → [Gemini] Generating knowledge article...")
                article_data = generate_knowledge(topic)
                if article_data:
                    result = insert_knowledge(topic, article_data)
                    if result:
                        stats["knowledge"] += 1
                else:
                    print(f"  [FAIL] No article generated for {tid}")
                    stats["errors"] += 1
                time.sleep(REQUEST_DELAY)

        # === Templates ===
        if do_templates and tid in template_topics:
            needed = args.templates_count - current_tmpl
            if needed <= 0:
                print(f"  [SKIP] Already has {current_tmpl} templates")
            else:
                print(
                    f"  → [DeepSeek] Generating {args.templates_count} templates ({current_tmpl} existing)..."
                )
                templates = generate_templates(
                    topic,
                    count=args.templates_count,
                    exclude_titles=list(get_existing_template_titles(tid)),
                    en_only=en_only,
                )
                if templates:
                    n = insert_templates(topic, templates, en_only=en_only)
                    stats["templates"] += n
                else:
                    print(f"  [FAIL] No templates generated for {tid}")
                    stats["errors"] += 1
                time.sleep(REQUEST_DELAY)

        # === Exercises ===
        if do_exercises:
            ex_id_1 = f"ex-{tid}-01"
            if db.code_exercises.find_one({"id": ex_id_1}):
                print(f"  [SKIP] Exercises already exist for {tid}")
            else:
                print(f"  → [Gemini] Generating exercises...")
                exercises = generate_exercises(topic, en_only=en_only)
                if exercises:
                    insert_exercises(topic, exercises, en_only=en_only)
                    stats["exercises"] += len(exercises)
                else:
                    print(f"  [FAIL] No exercises generated for {tid}")
                    stats["errors"] += 1
                time.sleep(REQUEST_DELAY)

        stats["topics"] += 1

    # Final summary
    print("\n" + "=" * 70)
    print("DONE — Summary:")
    print(f"  Topics processed : {stats['topics']}")
    print(f"  Knowledge created: {stats['knowledge']}")
    print(f"  Templates created: {stats['templates']}")
    print(f"  Exercises created: {stats['exercises']}")
    print(f"  Errors           : {stats['errors']}")
    total_ka = db.knowledge_articles.count_documents({})
    total_ex = db.code_exercises.count_documents({})
    total_tmpl = db.code_templates.count_documents({})
    print(
        f"\nDB totals — knowledge: {total_ka} | templates: {total_tmpl} | exercises: {total_ex}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
