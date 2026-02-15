#!/usr/bin/env python3
"""
Parallel Test Generation: Generate Online Tests for ALL Advanced Conversations

Purpose:
- Generate IELTS tests for all advanced conversations
- Parallel processing: 5 batches, each batch waits 5s
- DeepSeek API for question generation
- NO cover image generation (skip xAI to save credits)
- Save to production database

RUN:
    python crawler/parallel_test_generation_advanced.py

PRODUCTION:
    docker exec -d ai-chatbot-rag python crawler/parallel_test_generation_advanced.py

MONITOR:
    docker logs ai-chatbot-rag --tail 100 -f | grep "🎓\|✅\|❌"
"""

import os
import sys
import json
import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from openai import OpenAI
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable required")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# Parallel processing config
BATCH_SIZE = 5  # Process 5 conversations in parallel
BATCH_DELAY = 5  # Wait 5 seconds between batches

# Level configuration
LEVEL_CONFIG = {
    "beginner": {
        "total_questions": 10,
        "time_limit": 10,
        "distribution": {
            "mcq": 4,  # Vocabulary definition
            "matching": 2,  # Words → Vietnamese
            "completion": 2,  # Grammar fill-in-blanks
            "sentence_completion": 2,  # Vocabulary in context
        },
        "description": "Simple vocabulary definitions and basic grammar patterns",
    },
    "intermediate": {
        "total_questions": 15,
        "time_limit": 15,
        "distribution": {
            "mcq": 5,  # Vocabulary nuances
            "matching": 3,  # Grammar patterns → Examples
            "completion": 3,  # Grammar structures
            "sentence_completion": 2,  # Vocabulary usage
            "short_answer": 2,  # Grammar transformation
        },
        "description": "Vocabulary nuances and complex grammar structures",
    },
    "advanced": {
        "total_questions": 20,
        "time_limit": 20,
        "distribution": {
            "mcq": 8,  # Idiomatic expressions & vocabulary nuances
            "matching": 4,  # Vocabulary register/formality
            "completion": 4,  # Advanced grammar contexts
            "sentence_completion": 4,  # Complex vocabulary in context
        },
        "description": "Advanced idiomatic expressions and sophisticated grammar",
    },
}


def format_dialogue(dialogue: List[Dict]) -> str:
    """Format dialogue for prompt"""
    lines = []
    for idx, turn in enumerate(dialogue, 1):
        speaker = turn.get("speaker", "?")
        text_en = turn.get("text_en", "")
        lines.append(f"[{speaker}] {text_en}")
    return "\n".join(lines)


def format_vocabulary(vocabulary: List[Dict]) -> str:
    """Format vocabulary for prompt"""
    lines = []
    for idx, item in enumerate(vocabulary, 1):
        word = item.get("word", "")
        pos = item.get("pos_tag", "")
        definition_en = item.get("definition_en", "")
        definition_vi = item.get("definition_vi", "")
        example = item.get("example", "")
        lines.append(
            f"{idx}. {word} ({pos}) - {definition_en}\n"
            f"   Vietnamese: {definition_vi}\n"
            f"   Example: {example}"
        )
    return "\n\n".join(lines)


def format_grammar(grammar_points: List[Dict]) -> str:
    """Format grammar for prompt"""
    lines = []
    for idx, point in enumerate(grammar_points, 1):
        pattern = point.get("pattern", "")
        explanation_en = point.get("explanation_en", "")
        explanation_vi = point.get("explanation_vi", "")
        example = point.get("example", "")
        lines.append(
            f"{idx}. {pattern}\n"
            f"   English: {explanation_en}\n"
            f"   Vietnamese: {explanation_vi}\n"
            f"   Example: {example}"
        )
    return "\n\n".join(lines)


def build_test_prompt(conversation: Dict, vocab_data: Dict, level: str) -> str:
    """Build DeepSeek prompt with IELTS question types"""

    config = LEVEL_CONFIG[level]
    dialogue_text = format_dialogue(conversation["dialogue"])
    vocabulary_text = format_vocabulary(vocab_data["vocabulary"])
    grammar_text = format_grammar(vocab_data["grammar_points"])

    title_en = conversation["title"]["en"]
    title_vi = conversation["title"]["vi"]

    # Build distribution text
    distribution_lines = []
    for q_type, count in config["distribution"].items():
        if q_type == "mcq":
            distribution_lines.append(
                f"- {count} MCQ (single answer) - Vocabulary definitions"
            )
        elif q_type == "matching":
            if level == "beginner":
                distribution_lines.append(
                    f"- {count} Matching - Words → Vietnamese translations"
                )
            else:
                distribution_lines.append(
                    f"- {count} Matching - Grammar patterns → Examples from conversation"
                )
        elif q_type == "completion":
            distribution_lines.append(
                f"- {count} Completion - Grammar fill-in-blanks (IELTS style)"
            )
        elif q_type == "sentence_completion":
            distribution_lines.append(
                f"- {count} Sentence Completion - Vocabulary in context"
            )
    distribution_text = "\n".join(distribution_lines)

    prompt = f"""Generate an English vocabulary and grammar test for {level.upper()} level based on the conversation below.

**SOURCE CONVERSATION:**
Title: "{title_en}" ({title_vi})

Dialogue:
{dialogue_text}

---

**VOCABULARY ({len(vocab_data['vocabulary'])} words):**
{vocabulary_text}

---

**GRAMMAR ({len(vocab_data['grammar_points'])} patterns):**
{grammar_text}

---

**TEST REQUIREMENTS:**

**Question Count:** EXACTLY {config['total_questions']} questions (CRITICAL - count question objects carefully!)

**Question Distribution:**
{distribution_text}

**Question Type Usage Guidelines:**
- **MCQ**: Use for vocabulary definitions, synonyms, word meanings
- **Matching**:
  * Beginner: Match vocabulary words → Vietnamese translations
  * Intermediate/Advanced: Match grammar patterns → Examples from conversation
- **Completion**: Use for GRAMMAR practice (fill blanks with correct grammar forms)
- **Sentence Completion**: Use for VOCABULARY practice (complete sentences with words from conversation)

**Question Types Explained (ONLY 4 TYPES):**

1. **MCQ (question_type: "mcq"):**
   - 4 options (A, B, C, D)
   - 1 correct answer
   - Use "correct_answers": ["A"]
   - Include explanation in BOTH English and Vietnamese (format: "English explanation. | Vietnamese explanation.")

2. **Matching (question_type: "matching"):****
   - left_items: 4-5 items to match (numbered keys: "1", "2", etc.)
   - right_options: 5-6 options (letter keys: "A", "B", etc.) - MORE options than items
   - correct_answers: [{{"left_key": "1", "right_key": "A"}}, ...]
   - instruction: "Write the correct letter A-E next to numbers 1-4"
   - ⚠️ 1 matching object = 1 question (not 4 questions!)

3. **Completion (question_type: "completion"):**
   - question_text: Context (e.g., "Complete the dialogue below")
   - instruction: "Write NO MORE THAN TWO WORDS for each answer"
   - template: String with _____(1)_____, _____(2)_____ format
   - blanks: [{{"key": "1", "position": "description", "word_limit": 2}}, ...]
   - correct_answers: [{{"blank_key": "1", "answers": ["word1", "word2", "WORD1"]}}, ...]
   - ⚠️ 1 completion object = 1 question (even with 5 blanks!)

4. **Sentence Completion (question_type: "sentence_completion"):**
   - question_text: "Complete the sentences using words from the conversation"
   - instruction: "Write NO MORE THAN ONE/TWO WORDS for each answer"
   - sentences: [{{"key": "1", "template": "The word _____ means...", "word_limit": 1, "correct_answers": ["word"]}}, ...]
   - ⚠️ 1 sentence_completion object = 1 question

**OUTPUT FORMAT (JSON only, no markdown):****
{{
  "questions": [
    {{
      "question_type": "mcq",
      "question_text": "What does the word 'greet' mean?",
      "options": [
        {{"option_key": "A", "option_text": "To say hello"}},
        {{"option_key": "B", "option_text": "To say goodbye"}},
        {{"option_key": "C", "option_text": "To ask a question"}},
        {{"option_key": "D", "option_text": "To make a request"}}
      ],
      "correct_answers": ["A"],
      "explanation": "The word 'greet' means to say hello or welcome someone. | Từ 'greet' có nghĩa là chào hỏi hoặc chào đón ai đó.",
      "max_points": 1
    }},
    {{
      "question_type": "matching",
      "question_text": "Match the vocabulary words with their Vietnamese translations",
      "instruction": "Write the correct letter A-E next to numbers 1-4",
      "left_items": [
        {{"key": "1", "text": "morning"}},
        {{"key": "2", "text": "afternoon"}},
        {{"key": "3", "text": "evening"}},
        {{"key": "4", "text": "night"}}
      ],
      "right_options": [
        {{"key": "A", "text": "buổi sáng"}},
        {{"key": "B", "text": "buổi chiều"}},
        {{"key": "C", "text": "buổi tối"}},
        {{"key": "D", "text": "ban đêm"}},
        {{"key": "E", "text": "trưa"}}
      ],
      "correct_answers": [
        {{"left_key": "1", "right_key": "A"}},
        {{"left_key": "2", "right_key": "B"}},
        {{"left_key": "3", "right_key": "C"}},
        {{"left_key": "4", "right_key": "D"}}
      ],
      "explanation": "These are time-of-day vocabulary words from the conversation. | Đây là từ vựng về các buổi trong ngày từ hội thoại.",
      "max_points": 4
    }},
    {{
      "question_type": "completion",
      "question_text": "Complete the dialogue using grammar patterns from the conversation",
      "instruction": "Write NO MORE THAN TWO WORDS for each answer",
      "template": "A: Good morning! _____(1)_____ you doing today?\\nB: I _____(2)_____ doing great, thanks!\\nA: That's wonderful. _____(3)_____ meet you!",
      "blanks": [
        {{"key": "1", "position": "greeting question", "word_limit": 2}},
        {{"key": "2", "position": "response", "word_limit": 2}},
        {{"key": "3", "position": "closing", "word_limit": 2}}
      ],
      "correct_answers": [
        {{"blank_key": "1", "answers": ["How are", "how are", "How're"]}},
        {{"blank_key": "2", "answers": ["am", "AM", "'m"]}},
        {{"blank_key": "3", "answers": ["Nice to", "nice to", "Pleased to"]}}
      ],
      "explanation": "This tests the present continuous greeting pattern 'How are you doing?' and present tense responses. | Kiểm tra mẫu câu chào hỏi thì hiện tại tiếp diễn và cách trả lời.",
      "max_points": 3
    }},
    {{
      "question_type": "sentence_completion",
      "question_text": "Complete the sentences using words from the conversation",
      "instruction": "Write NO MORE THAN ONE WORD for each answer",
      "sentences": [
        {{"key": "1", "template": "When you meet someone for the first time, you can say 'Nice to _____ you'.", "word_limit": 1, "correct_answers": ["meet", "MEET", "Meet"]}},
        {{"key": "2", "template": "In the morning, we say 'Good _____' as a greeting.", "word_limit": 1, "correct_answers": ["morning", "MORNING", "Morning"]}}
      ],
      "explanation": "Common greeting expressions from the conversation. | Các cách chào hỏi phổ biến từ hội thoại.",
      "max_points": 2
    }},
    ... (more questions following these formats to reach {config['total_questions']} total)
  ]
}}

**CRITICAL VALIDATION BEFORE RETURNING:**
✅ Total questions = {config['total_questions']} (count question objects, NOT sub-items!)
✅ Each MCQ has exactly 4 options
✅ Each matching has correct_answers with left_key/right_key pairs
✅ Each completion has template + blanks + correct_answers with blank_key
✅ Each sentence_completion has sentences array with correct_answers
✅ All explanations are in "English | Vietnamese" format
✅ All questions use vocabulary/grammar from the conversation ONLY
✅ Matching questions for beginner: Words → Vietnamese
✅ Matching questions for intermediate/advanced: Grammar patterns → Examples
✅ Completion questions: Test GRAMMAR (verb forms, prepositions, tenses)
✅ Sentence completion: Test VOCABULARY (word usage in context)

Generate the test now. Return ONLY valid JSON (no markdown, no extra text).
"""

    return prompt


async def generate_test_questions(
    conversation_id: str, conversation: Dict, vocab_data: Dict, level: str
) -> List[Dict]:
    """Generate test questions using DeepSeek"""

    prompt = build_test_prompt(conversation, vocab_data, level)

    print(f"\n{'='*80}")
    print(f"🤖 Generating {level.upper()} test: {conversation['title']['en']}")
    print(f"{'='*80}")

    for attempt in range(3):
        try:
            print(f"\n🔄 Attempt {attempt + 1}/3...")

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=6000,
            )

            content = response.choices[0].message.content
            content = content.strip().replace("```json", "").replace("```", "").strip()

            # Parse JSON
            data = json.loads(content)
            questions = data.get("questions", [])

            # Validate question count (allow less than expected)
            expected = LEVEL_CONFIG[level]["total_questions"]
            min_required = max(5, expected - 5)  # At least 5 or expected-5
            if len(questions) < min_required:
                print(
                    f"⚠️  Question count low: {len(questions)} < {min_required} (expected {expected}). Retrying..."
                )
                continue
            elif len(questions) < expected:
                print(
                    f"⚠️  Generated {len(questions)}/{expected} questions (acceptable)"
                )

            # Validate each question
            for idx, q in enumerate(questions, 1):
                validate_question_schema(q, idx, level)

            print(f"✅ Generated {len(questions)} questions successfully!")
            return questions

        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            if attempt == 2:
                raise
        except Exception as e:
            print(f"❌ Generation error: {e}")
            if attempt == 2:
                raise

    raise Exception(f"Failed to generate test after 3 attempts")


def validate_question_schema(question: Dict, index: int, level: str):
    """Validate question follows IELTS schema"""

    q_type = question.get("question_type")

    if not q_type:
        raise ValueError(f"Question {index}: Missing question_type")

    # Common validations
    if "question_text" not in question:
        raise ValueError(f"Question {index}: Missing question_text")

    if "explanation" not in question:
        raise ValueError(f"Question {index}: Missing explanation")

    # Check bilingual format
    explanation = question.get("explanation", "")
    if "|" not in explanation:
        raise ValueError(
            f"Question {index}: Explanation must be bilingual (English | Vietnamese)"
        )

    # Type-specific validations
    if q_type == "mcq":
        assert "options" in question, f"Q{index}: Missing options"
        assert len(question["options"]) == 4, f"Q{index}: Must have 4 options"
        assert "correct_answers" in question, f"Q{index}: Missing correct_answers"
        assert (
            len(question["correct_answers"]) == 1
        ), f"Q{index}: MCQ must have 1 answer"

    elif q_type == "mcq_multiple":
        assert "options" in question, f"Q{index}: Missing options"
        assert len(question["options"]) >= 4, f"Q{index}: Must have 4+ options"
        assert "correct_answers" in question, f"Q{index}: Missing correct_answers"
        assert (
            len(question["correct_answers"]) >= 2
        ), f"Q{index}: Multiple MCQ must have 2+ answers"

    elif q_type == "matching":
        assert "left_items" in question, f"Q{index}: Missing left_items"
        assert "right_options" in question, f"Q{index}: Missing right_options"
        assert "correct_answers" in question, f"Q{index}: Missing correct_answers"
        assert len(question["right_options"]) > len(
            question["left_items"]
        ), f"Q{index}: Must have more options than items"
        for match in question["correct_answers"]:
            assert (
                "left_key" in match and "right_key" in match
            ), f"Q{index}: Invalid match structure"

    elif q_type == "completion":
        assert "template" in question, f"Q{index}: Missing template"
        assert "blanks" in question, f"Q{index}: Missing blanks"
        assert "correct_answers" in question, f"Q{index}: Missing correct_answers"
        for answer in question["correct_answers"]:
            assert (
                "blank_key" in answer and "answers" in answer
            ), f"Q{index}: Invalid completion structure"

    elif q_type == "sentence_completion":
        assert "sentences" in question, f"Q{index}: Missing sentences"
        for sent in question["sentences"]:
            assert "key" in sent, f"Q{index}: Sentence missing key"
            assert "template" in sent, f"Q{index}: Sentence missing template"
            assert (
                "correct_answers" in sent
            ), f"Q{index}: Sentence missing correct_answers"

    elif q_type == "short_answer":
        assert "correct_answers" in question, f"Q{index}: Missing correct_answers"
        assert isinstance(
            question["correct_answers"], list
        ), f"Q{index}: correct_answers must be array"

    print(f"  ✅ Q{index} ({q_type}) validated")


def generate_cover_image_prompt(title: str, level: str) -> str:
    """
    Generate simple cover image prompt for xAI Grok Imagine

    Format:
    - Top: "Vocabulary & Grammar Test" (smaller text)
    - Center: Title (large, bold)
    - Bottom right: "WordAI Team"
    """

    # Level-specific color schemes
    color_schemes = {
        "beginner": "soft blue and green gradients",
        "intermediate": "warm orange and yellow tones",
        "advanced": "deep purple and teal accents",
    }
    colors = color_schemes.get(level, "soft pastel colors")

    # Simple, direct prompt for xAI
    prompt = (
        f"Modern educational test cover. "
        f"{colors}, minimal geometric shapes, clean layout. "
        f"16:9 landscape orientation."
    )

    return prompt


async def save_test_to_database(
    conversation_id: str,
    questions: List[Dict],
    level: str,
    conversation: Dict,
    cover_prompt: str,
) -> Tuple[str, str]:
    """Save test to online_tests collection"""

    db_manager = DBManager()
    db = db_manager.db

    title_en = conversation["title"]["en"]
    topic_dict = conversation.get("topic", {})
    topic_slug = (
        topic_dict.get("en", "unknown")
        if isinstance(topic_dict, dict)
        else str(topic_dict)
    )

    # Generate slug
    slug = f"test-{level}-{topic_slug.lower().replace(' ', '-').replace('&', 'and')}-{conversation_id.split('_')[-1]}"

    # Short description (160 chars max)
    short_desc = (
        f"Test your {level} English with {len(questions)} questions on {title_en}"
    )
    if len(short_desc) > 160:
        short_desc = short_desc[:157] + "..."

    # Full description
    full_desc = f"Test your understanding of vocabulary and grammar from the conversation '{title_en}'. {LEVEL_CONFIG[level]['description']}"

    # Meta description for SEO (160 chars max)
    meta_desc = f"{level.capitalize()} English test: {title_en}. {len(questions)} IELTS-style questions. Free practice test."
    if len(meta_desc) > 160:
        meta_desc = meta_desc[:157] + "..."

    # Difficulty mapping (matches production values)
    difficulty_map = {
        "beginner": "beginner",
        "intermediate": "intermediate",
        "advanced": "advanced",
    }

    # Add question_id and question_number to each question (for compatibility)
    for idx, q in enumerate(questions, 1):
        q["question_id"] = f"q{idx}"
        q["question_number"] = idx
        # Add empty questions array if not exists (old schema compatibility)
        if "questions" not in q:
            q["questions"] = []

    # Prepare test document
    now = datetime.utcnow()
    test_doc = {
        "title": f"Vocabulary & Grammar Test: {title_en}",
        "description": full_desc,
        "slug": slug,  # ✅ Root level (for by-slug endpoint compatibility)
        "meta_description": meta_desc,  # ✅ Root level SEO
        # Creator info (admin user tienhoi.lh@gmail.com)
        "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",  # ✅ Firebase UID for /me/tests endpoint
        "creator_name": "WordAI Team",
        # Test configuration
        "test_type": "mcq",
        "test_category": "academic",
        "status": "ready",
        "is_active": True,
        # Conversation linkage
        "source_type": "conversation",
        "conversation_id": conversation_id,
        "conversation_level": level,
        "conversation_topic": topic_dict,
        # Test settings
        "time_limit_minutes": LEVEL_CONFIG[level]["time_limit"],
        "max_retries": 3,
        "passing_score": 50,
        "show_answers_timing": "immediate",
        # Questions
        "questions": questions,
        # Marketplace (COMPLETE config matching production tests)
        "marketplace_config": {
            "is_public": True,  # ⭐ Visible in community marketplace
            "version": "v1",  # Version number
            "title": f"Vocabulary & Grammar Test: {title_en}",
            "description": full_desc,
            "short_description": short_desc,
            "cover_image_url": None,  # Will be generated later (use cover_image_prompt)
            "price_points": 1,  # 1 point per test
            "category": "English Learning - Conversations",
            "tags": [
                f"{level}",
                "vocabulary",
                "grammar",
                "conversation",
                "IELTS",
                "test",
            ],  # Array, not string
            "difficulty_level": difficulty_map[level],
            "published_at": now,  # Publication timestamp
            "total_participants": 0,  # Stats (updated by system)
            "total_earnings": 0,
            "average_rating": 0,
            "rating_count": 0,
            "average_participant_score": 0,
            "avg_rating": 0,  # Duplicate field (legacy compatibility)
            "slug": slug,  # SEO-friendly URL
            "meta_description": meta_desc,  # SEO meta tag
            "updated_at": now,
        },
        # Cover image
        "cover_image_prompt": cover_prompt,
        "cover_image_url": None,  # Will be generated later
        # Timestamps
        "created_at": now,
        "updated_at": now,
        "generated_at": now,
    }

    # Insert to database
    result = db.online_tests.insert_one(test_doc)
    test_id = str(result.inserted_id)

    # Update conversation document
    db.conversation_library.update_one(
        {"conversation_id": conversation_id},
        {
            "$set": {
                "online_test_id": ObjectId(test_id),
                "online_test_slug": slug,
                "has_online_test": True,
            }
        },
    )

    return test_id, slug


async def generate_and_upload_cover(
    test_id: str, title: str, cover_prompt: str, xai_service
) -> Optional[str]:
    """Generate cover image and upload to R2 using xAI Grok Imagine"""
    try:
        print(f"\n🎨 Generating cover image with xAI Grok Imagine...")
        print(f"   Prompt: {cover_prompt[:80]}...")

        # Generate cover with xAI Grok Imagine (1K resolution, 16:9)
        result = await xai_service.generate_test_cover(
            title=title, description=cover_prompt, style="minimal, modern, educational"
        )

        # Decode base64
        image_bytes = base64.b64decode(result["image_base64"])
        print(f"✅ Image generated ({len(image_bytes)} bytes)")

        # Upload to R2
        filename = f"test_{test_id}_cover.jpg"
        upload_result = await xai_service.upload_to_r2(
            image_bytes=image_bytes, user_id="wordai_team", filename=filename
        )

        cover_url = upload_result["file_url"]
        print(f"☁️  Uploaded to R2: {cover_url}")

        return cover_url

    except Exception as e:
        print(f"❌ Cover generation failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def process_conversation(
    conversation: Dict,
    level: str,
    db_manager: DBManager,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """Process one conversation (with rate limiting)"""
    async with semaphore:
        conversation_id = conversation["conversation_id"]
        title_en = conversation.get("title", {}).get("en", "Unknown")

        try:
            # Get vocabulary data from conversation_vocabulary collection
            vocab_data = db_manager.db.conversation_vocabulary.find_one(
                {"conversation_id": conversation_id}
            ) or {"vocabulary": [], "grammar_patterns": []}

            # Generate test questions
            questions = await generate_test_questions(
                conversation_id=conversation_id,
                conversation=conversation,
                vocab_data=vocab_data,
                level=level,
            )

            if not questions:
                return {
                    "conversation_id": conversation_id,
                    "title": title_en,
                    "success": False,
                    "error": "No questions generated",
                }

            # Generate cover prompt
            cover_prompt = generate_cover_image_prompt(title_en, level)

            # Save to database
            test_id, slug = await save_test_to_database(
                conversation_id=conversation_id,
                questions=questions,
                level=level,
                conversation=conversation,
                cover_prompt=cover_prompt,
            )

            # Skip cover generation to save xAI credits
            # Cover will be added manually later

            # Update conversation
            db_manager.db.conversation_library.update_one(
                {"conversation_id": conversation_id},
                {
                    "$set": {
                        "online_test_id": ObjectId(test_id),
                        "online_test_slug": slug,
                        "has_online_test": True,
                    }
                },
            )

            return {
                "conversation_id": conversation_id,
                "title": title_en,
                "test_id": test_id,
                "slug": slug,
                "num_questions": len(questions),
                "success": True,
            }

        except Exception as e:
            return {
                "conversation_id": conversation_id,
                "title": title_en,
                "success": False,
                "error": str(e),
            }


async def main():
    """Generate tests for ALL advanced conversations in parallel batches"""
    print("=" * 80)
    print("🎓 PARALLEL TEST GENERATION - ADVANCED CONVERSATIONS")
    print("=" * 80)
    print(f"Batch Size: {BATCH_SIZE} conversations")
    print(f"Batch Delay: {BATCH_DELAY} seconds")
    print("Database: Production (ai_service_db)")
    print("Cover Generation: DISABLED (save xAI credits)")
    print("=" * 80)

    # Connect to database
    db_manager = DBManager()
    print(f"✅ MongoDB: {db_manager.db.name}")

    # Get advanced conversations WITHOUT tests
    conversations = list(
        db_manager.db.conversation_library.find(
            {
                "level": "advanced",
                "has_online_test": {"$ne": True},
            }
        ).sort("conversation_id", 1)
    )

    total = len(conversations)
    print(f"📚 Found {total} advanced conversations without tests")
    print()

    if total == 0:
        print("✅ All intermediate conversations already have tests!")
        return

    # Process in batches
    results = []
    semaphore = asyncio.Semaphore(BATCH_SIZE)

    for i in range(0, total, BATCH_SIZE):
        batch = conversations[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n{'='*80}")
        print(f"📦 BATCH {batch_num}/{total_batches} ({len(batch)} conversations)")
        print(f"{'='*80}")

        # Process batch in parallel
        tasks = [
            process_conversation(
                    conv, "advanced", db_manager, semaphore
        ]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print batch results
        for result in batch_results:
            if isinstance(result, Exception):
                print(f"❌ Exception: {result}")
                continue

            if result.get("success"):
                print(
                    f"✅ {result['conversation_id'][:50]:50} | {result['num_questions']:2}Q | {result['slug']}"
                )
            else:
                print(
                    f"❌ {result['conversation_id'][:50]:50} | {result.get('error', 'Unknown')}"
                )

            results.append(result)

        # Wait before next batch (except last batch)
        if i + BATCH_SIZE < total:
            print(f"\n⏳ Waiting {BATCH_DELAY}s before next batch...")
            await asyncio.sleep(BATCH_DELAY)

    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count

    print("\n" + "=" * 80)
    print("📊 GENERATION SUMMARY")
    print("=" * 80)
    print(f"Total: {len(results)}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print()

    if failed_count > 0:
        print("❌ FAILED CONVERSATIONS:")
        for r in results:
            if not r.get("success"):
                print(f"   - {r['conversation_id']}: {r.get('error', 'Unknown')}")
        print()

    print("✅ Parallel test generation complete!")


if __name__ == "__main__":
    asyncio.run(main())
