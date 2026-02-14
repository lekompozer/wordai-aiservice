#!/usr/bin/env python3
"""
Test Script: Generate Online Tests from 3 Conversations (Beginner, Intermediate, Advanced)

Purpose:
- Validate IELTS question type prompts
- Test DeepSeek API generation
- Save to production database for manual verification
- Generate cover image prompts

RUN:
    python crawler/test_conversation_online_test_generation.py

PRODUCTION:
    ssh root@104.248.147.155 "docker cp /home/hoile/wordai/crawler/test_conversation_online_test_generation.py ai-chatbot-rag:/app/crawler/ && docker exec ai-chatbot-rag python crawler/test_conversation_online_test_generation.py"
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple
from openai import OpenAI
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable required")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# Test conversations (specific IDs to test)
TEST_CONVERSATIONS = {
    "beginner": "conv_beginner_greetings_introductions_01_001",  # "Hello, How Are You?"
    "intermediate": "conv_intermediate_work_office_11_001",  # "Job Interview"
    "advanced": "conv_advanced_business_entrepreneurship_21_001",  # "Pitching an Idea"
}

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
            "mcq": 6,  # Idiomatic expressions
            "mcq_multiple": 2,  # Multiple correct grammar patterns
            "matching": 4,  # Vocabulary register/formality
            "completion": 4,  # Advanced grammar contexts
            "sentence_completion": 2,  # Complex vocabulary
            "short_answer": 2,  # Discourse analysis
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
        elif q_type == "mcq_multiple":
            distribution_lines.append(
                f"- {count} MCQ (multiple answers) - Grammar patterns (select all that apply)"
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
        elif q_type == "short_answer":
            distribution_lines.append(
                f"- {count} Short Answer - Grammar transformation (1-3 words)"
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
- **Short Answer**: Use for GRAMMAR transformation (tense changes, prepositions, etc.)

**Question Types Explained:**

1. **MCQ (question_type: "mcq"):**
   - 4 options (A, B, C, D)
   - 1 correct answer
   - Use "correct_answers": ["A"]
   - Include explanation in BOTH English and Vietnamese (format: "English explanation. | Vietnamese explanation.")

2. **MCQ Multiple (question_type: "mcq_multiple"):**
   - 4-6 options (A, B, C, D, E, F)
   - 2+ correct answers
   - Use "correct_answers": ["A", "C", "D"]
   - Include explanation in BOTH English and Vietnamese

3. **Matching (question_type: "matching"):**
   - left_items: 4-5 items to match (numbered keys: "1", "2", etc.)
   - right_options: 5-6 options (letter keys: "A", "B", etc.) - MORE options than items
   - correct_answers: [{{"left_key": "1", "right_key": "A"}}, ...]
   - instruction: "Write the correct letter A-E next to numbers 1-4"
   - ⚠️ 1 matching object = 1 question (not 4 questions!)

4. **Completion (question_type: "completion"):**
   - question_text: Context (e.g., "Complete the dialogue below")
   - instruction: "Write NO MORE THAN TWO WORDS for each answer"
   - template: String with _____(1)_____, _____(2)_____ format
   - blanks: [{{"key": "1", "position": "description", "word_limit": 2}}, ...]
   - correct_answers: [{{"blank_key": "1", "answers": ["word1", "word2", "WORD1"]}}, ...]
   - ⚠️ 1 completion object = 1 question (even with 5 blanks!)

5. **Sentence Completion (question_type: "sentence_completion"):**
   - question_text: "Complete the sentences using words from the conversation"
   - instruction: "Write NO MORE THAN ONE/TWO WORDS for each answer"
   - sentences: [{{"key": "1", "template": "The word _____ means...", "word_limit": 1, "correct_answers": ["word"]}}, ...]
   - ⚠️ 1 sentence_completion object = 1 question

6. **Short Answer (question_type: "short_answer"):**
   - question_text: "What is the past tense of 'go'?"
   - instruction: "Write NO MORE THAN ONE/TWO WORDS"
   - word_limit: 2
   - correct_answers: ["went", "WENT"]
   - Include multiple acceptable variations

**OUTPUT FORMAT (JSON only, no markdown):**
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
    ... ({config['total_questions'] - 1} more questions with various types)
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

            # Validate question count
            expected = LEVEL_CONFIG[level]["total_questions"]
            if len(questions) != expected:
                print(
                    f"❌ Question count mismatch: {len(questions)} != {expected}. Retrying..."
                )
                continue

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


async def generate_cover_image_prompt(title: str, level: str) -> str:
    """Generate cover image prompt using DeepSeek (minimal style, <200 chars)"""

    # Level-specific color schemes
    color_schemes = {
        "beginner": "Soft blues and greens (calming)",
        "intermediate": "Warm oranges and yellows (energetic)",
        "advanced": "Deep purples and teals (sophisticated)",
    }
    colors = color_schemes[level]

    prompt = f"""Generate a SHORT image generation prompt (MAX 200 characters) for a test cover image.

Test Title: "{title}"
Level: {level}
Author: WordAI Team

Requirements:
- Style: Minimal, clean, modern
- Aspect ratio: 16:9 (landscape)
- Theme: English learning, vocabulary, grammar
- Colors: {colors}
- NO text in image (will be overlaid)
- NO people (avoid copyright)
- Abstract/geometric preferred

Return ONLY the image prompt (max 200 chars), no explanation."""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=100,
    )

    image_prompt = response.choices[0].message.content.strip()

    # Truncate if too long
    if len(image_prompt) > 200:
        image_prompt = image_prompt[:197] + "..."

    return image_prompt


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
    topic_slug = conversation.get("topic", "unknown")

    # Generate slug
    slug = f"test-{level}-{topic_slug}-{conversation_id.split('_')[-1]}"

    # Prepare test document
    test_doc = {
        "title": f"Vocabulary & Grammar Test: {title_en}",
        "description": f"Test your understanding of vocabulary and grammar from the conversation '{title_en}'. {LEVEL_CONFIG[level]['description']}",
        # Creator info
        "creator_id": "wordai_team",
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
        "conversation_topic": topic_slug,
        # Test settings
        "time_limit_minutes": LEVEL_CONFIG[level]["time_limit"],
        "max_retries": 3,
        "passing_score": 70,
        "show_answers_timing": "immediate",
        # Questions
        "questions": questions,
        # Marketplace
        "marketplace_config": {
            "is_published": False,
            "price_points": 0,
            "category": "English Learning - Conversations",
            "tags": f"{level},vocabulary,grammar,conversation,IELTS,test",
        },
        # Cover image
        "cover_image_prompt": cover_prompt,
        "cover_image_url": None,  # Will be generated later
        # Timestamps
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "generated_at": datetime.utcnow(),
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


async def main():
    """Main test function"""

    print("\n" + "=" * 80)
    print("🎓 CONVERSATION ONLINE TEST GENERATION - TEST RUN")
    print("=" * 80)
    print(f"Testing 3 conversations (Beginner, Intermediate, Advanced)")
    print(f"Database: Production (ai_service_db)")
    print("=" * 80)

    db_manager = DBManager()
    db = db_manager.db

    results = []

    for level, conversation_id in TEST_CONVERSATIONS.items():
        try:
            # Get conversation
            conv = db.conversation_library.find_one(
                {"conversation_id": conversation_id}
            )
            if not conv:
                print(f"\n❌ Conversation not found: {conversation_id}")
                continue

            # Get vocabulary
            vocab = db.conversation_vocabulary.find_one(
                {"conversation_id": conversation_id}
            )
            if not vocab:
                print(f"\n❌ Vocabulary not found for: {conversation_id}")
                continue

            print(f"\n📚 Found conversation: {conv['title']['en']}")
            print(f"   Vocabulary: {len(vocab['vocabulary'])} words")
            print(f"   Grammar: {len(vocab['grammar_points'])} patterns")

            # Generate test questions
            questions = await generate_test_questions(
                conversation_id, conv, vocab, level
            )

            # Generate cover image prompt
            print(f"\n🎨 Generating cover image prompt...")
            cover_prompt = await generate_cover_image_prompt(conv["title"]["en"], level)
            print(f"   Prompt: {cover_prompt}")

            # Save to database
            print(f"\n💾 Saving test to database...")
            test_id, slug = await save_test_to_database(
                conversation_id, questions, level, conv, cover_prompt
            )

            print(f"\n✅ SUCCESS!")
            print(f"   Test ID: {test_id}")
            print(f"   Slug: {slug}")

            results.append(
                {
                    "level": level,
                    "conversation_id": conversation_id,
                    "title": conv["title"]["en"],
                    "test_id": test_id,
                    "slug": slug,
                    "questions_count": len(questions),
                    "cover_prompt": cover_prompt,
                }
            )

        except Exception as e:
            print(f"\n❌ FAILED for {level}: {e}")
            import traceback

            traceback.print_exc()

    # Print summary
    print("\n\n" + "=" * 80)
    print("📊 GENERATION SUMMARY")
    print("=" * 80)

    for result in results:
        print(f"\n{result['level'].upper()}: {result['title']}")
        print(f"   Test ID: {result['test_id']}")
        print(f"   Slug: {result['slug']}")
        print(f"   Questions: {result['questions_count']}")
        print(f"   Cover: {result['cover_prompt'][:60]}...")

    # Verification queries
    print("\n\n" + "=" * 80)
    print("🔍 VERIFICATION QUERIES (Run on production)")
    print("=" * 80)

    for result in results:
        print(f"\n# Check {result['level']} test:")
        print(
            f"db.online_tests.findOne({{_id: ObjectId('{result['test_id']}')}}, {{title: 1, questions: 1, conversation_id: 1}})"
        )

    print(f"\n# Check conversation links:")
    print(
        f"db.conversation_library.find({{has_online_test: true}}, {{conversation_id: 1, online_test_slug: 1}})"
    )

    print("\n\n✅ Test generation complete!")


if __name__ == "__main__":
    asyncio.run(main())
