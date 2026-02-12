"""
Test Conversation Generation + Database Storage (PRODUCTION)
Test 3 conversations (1 per level) from topic #1

Beginner: Greetings & Introductions - "Hello, How Are You?"
Intermediate: Work & Office - "Job Interview"
Advanced: Business & Entrepreneurship - "Pitching an Idea"

RUN IN DOCKER (Production):
    docker exec ai-chatbot-rag python crawler/test_conversation_db.py

Local Test (if needed):
    python crawler/test_conversation_db.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict
from openai import OpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.models.conversation_models import ConversationLevel


# ============================================================================
# CONFIGURATION
# ============================================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")

# Test conversations - Topic 1 from each level
TEST_CONVERSATIONS = [
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 1,
        "topic_slug": "greetings_introductions",
        "topic_en": "Greetings & Introductions",
        "topic_vi": "Chào hỏi & Giới thiệu",
        "title_en": "Hello, How Are You?",
        "title_vi": "Xin chào, Bạn khỏe không?",
        "situation": "Two friends meet and greet each other on the street.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 11,
        "topic_slug": "work_office",
        "topic_en": "Work & Office",
        "topic_vi": "Công việc & Văn phòng",
        "title_en": "Job Interview",
        "title_vi": "Phỏng vấn xin việc",
        "situation": "A candidate is being interviewed for a position at a company.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 21,
        "topic_slug": "business_entrepreneurship",
        "topic_en": "Business & Entrepreneurship",
        "topic_vi": "Kinh doanh & Khởi nghiệp",
        "title_en": "Pitching an Idea",
        "title_vi": "Trình bày ý tưởng",
        "situation": "An entrepreneur pitches their startup idea to potential investors.",
    },
]

# Level configurations
LEVEL_CONFIG = {
    ConversationLevel.BEGINNER: {
        "turns": "6-8",
        "turns_min": 6,
        "turns_max": 8,
        "vocabulary_count": "8-10",
        "grammar_count": "3-4",
        "difficulty_score": 2.5,
        "description": "Simple, everyday vocabulary. Short sentences. Common situations.",
    },
    ConversationLevel.INTERMEDIATE: {
        "turns": "8-12",
        "turns_min": 8,
        "turns_max": 12,
        "vocabulary_count": "10-12",
        "grammar_count": "4-5",
        "difficulty_score": 5.5,
        "description": "More complex vocabulary. Longer sentences. Various contexts.",
    },
    ConversationLevel.ADVANCED: {
        "turns": "10-15",
        "turns_min": 10,
        "turns_max": 15,
        "vocabulary_count": "12-15",
        "grammar_count": "5-6",
        "difficulty_score": 8.5,
        "description": "Advanced vocabulary. Complex sentences. Professional/academic contexts.",
    },
}


# ============================================================================
# PROMPT BUILDER
# ============================================================================


def build_prompt(conv_data: Dict) -> str:
    """Build prompt for Deepseek API"""

    level = conv_data["level"]
    config = LEVEL_CONFIG[level]

    prompt = f"""Generate 1 English conversation for learning English at {level.value.upper()} level.

TOPIC: {conv_data['topic_en']} ({conv_data['topic_vi']})
TITLE: {conv_data['title_en']} ({conv_data['title_vi']})
SITUATION: {conv_data['situation']}

LEVEL REQUIREMENTS for {level.value.upper()}:
- Dialogue turns: {config['turns']} turns (STRICTLY between {config['turns_min']}-{config['turns_max']})
- Vocabulary difficulty: {config['description']}
- Vocabulary items: {config['vocabulary_count']} words
- Grammar points: {config['grammar_count']} patterns

CONVERSATION STRUCTURE:
1. Metadata:
   - title_en: "{conv_data['title_en']}"
   - title_vi: "{conv_data['title_vi']}"
   - situation: "{conv_data['situation']}"

2. Dialogue:
   - {config['turns_min']}-{config['turns_max']} dialogue turns
   - Speakers: A (first speaker) and B (second speaker)
   - Each turn has:
     * speaker: "A" or "B"
     * gender: "male" or "female" (choose naturally)
     * text_en: English text
     * text_vi: Vietnamese translation
     * order: Turn number (1, 2, 3, ...)

3. Vocabulary:
   - {config['vocabulary_count']} key vocabulary items from the dialogue
   - Each item has:
     * word: The word/phrase
     * definition_en: English definition
     * definition_vi: Vietnamese definition
     * example: Sentence from dialogue where it appears
     * pos_tag: Part of speech (NOUN, VERB, ADJ, ADV, PHRASE, etc.)

4. Grammar Points:
   - {config['grammar_count']} grammar patterns from the dialogue
   - Each has:
     * pattern: Grammar structure (e.g., "Can I + verb?")
     * explanation_en: English explanation
     * explanation_vi: Vietnamese explanation
     * example: Sentence from dialogue demonstrating it

CRITICAL RULES:
1. Dialogue turns MUST be STRICTLY between {config['turns_min']}-{config['turns_max']}
2. Use ONLY the exact title and situation provided above
3. Make dialogue natural and realistic
4. Vietnamese translations must be accurate and natural
5. All vocabulary and grammar must come from the actual dialogue
6. Output MUST be valid JSON (no markdown, no extra text)

OUTPUT FORMAT (pure JSON):
{{
  "title_en": "{conv_data['title_en']}",
  "title_vi": "{conv_data['title_vi']}",
  "situation": "{conv_data['situation']}",
  "dialogue": [
    {{
      "speaker": "A",
      "gender": "male",
      "text_en": "...",
      "text_vi": "...",
      "order": 1
    }},
    ...
  ],
  "vocabulary": [
    {{
      "word": "...",
      "definition_en": "...",
      "definition_vi": "...",
      "example": "...",
      "pos_tag": "NOUN"
    }},
    ...
  ],
  "grammar_points": [
    {{
      "pattern": "...",
      "explanation_en": "...",
      "explanation_vi": "...",
      "example": "..."
    }},
    ...
  ]
}}

Generate now:"""

    return prompt


# ============================================================================
# DEEPSEEK API
# ============================================================================


async def generate_conversation(conv_data: Dict) -> Dict:
    """Generate conversation using Deepseek V3"""

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    prompt = build_prompt(conv_data)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000,
        )

        content = response.choices[0].message.content

        # Clean markdown formatting if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line (```)
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        # Parse JSON
        data = json.loads(content)
        return data

    except Exception as e:
        print(f"❌ Error generating conversation: {e}")
        raise


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================


def save_to_database(
    conv_data: Dict, generated_data: Dict, db_manager: DBManager
) -> str:
    """Save conversation to MongoDB"""

    level = conv_data["level"]
    topic_number = conv_data["topic_number"]
    config = LEVEL_CONFIG[level]

    # Generate conversation_id: conv_{level}_{topic_slug}_{index}
    conversation_id = f"conv_{level.value}_{conv_data['topic_slug']}_001"

    # Count words
    full_text_en = " ".join([turn["text_en"] for turn in generated_data["dialogue"]])
    word_count = len(full_text_en.split())

    # Full Vietnamese text
    full_text_vi = " ".join([turn["text_vi"] for turn in generated_data["dialogue"]])

    # Turn count
    turn_count = len(generated_data["dialogue"])

    # Prepare conversation_library document
    conversation_doc = {
        "conversation_id": conversation_id,
        "level": level.value,
        "topic_number": topic_number,
        "topic_slug": conv_data["topic_slug"],
        "topic": {"en": conv_data["topic_en"], "vi": conv_data["topic_vi"]},
        "title": {"en": generated_data["title_en"], "vi": generated_data["title_vi"]},
        "situation": generated_data["situation"],
        "dialogue": generated_data["dialogue"],
        "full_text_en": full_text_en,
        "full_text_vi": full_text_vi,
        "word_count": word_count,
        "turn_count": turn_count,
        "difficulty_score": config["difficulty_score"],
        "generated_by": "deepseek-v3",
        "has_audio": False,
        "audio_info": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # Save to conversation_library
    db_manager.db.conversation_library.update_one(
        {"conversation_id": conversation_id}, {"$set": conversation_doc}, upsert=True
    )

    # Prepare conversation_vocabulary document
    vocab_doc = {
        "vocab_id": f"vocab_{conversation_id}",
        "conversation_id": conversation_id,
        "vocabulary": generated_data["vocabulary"],
        "grammar_points": generated_data["grammar_points"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # Save to conversation_vocabulary
    db_manager.db.conversation_vocabulary.update_one(
        {"conversation_id": conversation_id}, {"$set": vocab_doc}, upsert=True
    )

    return conversation_id


def verify_database(conversation_id: str, db_manager: DBManager):
    """Verify conversation was saved correctly"""

    # Check conversation_library
    conv = db_manager.db.conversation_library.find_one(
        {"conversation_id": conversation_id}
    )

    if not conv:
        print(f"❌ Conversation not found: {conversation_id}")
        return

    print(f"\n✅ Conversation saved: {conversation_id}")
    print(f"   Level: {conv['level']}")
    print(f"   Topic: {conv['topic']['en']} ({conv['topic']['vi']})")
    print(f"   Title: {conv['title']['en']}")
    print(f"   Turns: {conv['turn_count']}")
    print(f"   Words: {conv['word_count']}")
    print(f"   Difficulty: {conv['difficulty_score']}")

    # Check vocabulary
    vocab = db_manager.db.conversation_vocabulary.find_one(
        {"conversation_id": conversation_id}
    )

    if vocab:
        print(f"   Vocabulary: {len(vocab['vocabulary'])} items")
        print(f"   Grammar: {len(vocab['grammar_points'])} points")
    else:
        print(f"   ❌ Vocabulary not found")

    # Show sample dialogue
    print(f"\n   📝 Sample dialogue:")
    for i, turn in enumerate(conv["dialogue"][:3]):
        print(f"      {turn['speaker']}: {turn['text_en']}")
        print(f"         ({turn['text_vi']})")


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Test conversation generation and database storage"""

    print("=" * 80)
    print("TEST CONVERSATION GENERATION + DATABASE")
    print("=" * 80)
    print()
    print("Testing 3 conversations (1 per level, topic #1):")
    print("  • Beginner: Greetings & Introductions - Hello, How Are You?")
    print("  • Intermediate: Work & Office - Job Interview")
    print("  • Advanced: Business & Entrepreneurship - Pitching an Idea")
    print()

    # Initialize database
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    print(f"✅ Connected to database: {db_manager.db.name}")
    print()

    # Generate and save conversations
    for conv_data in TEST_CONVERSATIONS:
        level = conv_data["level"]
        print("=" * 80)
        print(f"LEVEL: {level.value.upper()}")
        print("=" * 80)
        print()
        print(f"🔄 Generating: {conv_data['title_en']}")
        print(f"   Topic: {conv_data['topic_en']}")

        try:
            # Generate conversation
            generated_data = await generate_conversation(conv_data)

            # Validate
            turn_count = len(generated_data["dialogue"])
            vocab_count = len(generated_data["vocabulary"])
            grammar_count = len(generated_data["grammar_points"])

            print(
                f"  ✅ Generated: {turn_count} turns, {vocab_count} vocab, {grammar_count} grammar"
            )

            # Save to database
            conversation_id = save_to_database(conv_data, generated_data, db_manager)

            # Verify
            verify_database(conversation_id, db_manager)

            print()

            # Rate limiting
            if conv_data != TEST_CONVERSATIONS[-1]:
                print("⏳ Waiting 2 seconds...")
                await asyncio.sleep(2)
                print()

        except Exception as e:
            print(f"❌ Failed: {e}")
            continue

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("📊 Database Summary:")

    # Count conversations by level
    for level in [
        ConversationLevel.BEGINNER,
        ConversationLevel.INTERMEDIATE,
        ConversationLevel.ADVANCED,
    ]:
        count = db_manager.db.conversation_library.count_documents(
            {"level": level.value}
        )
        print(f"   {level.value.title()}: {count} conversations")

    print()


if __name__ == "__main__":
    asyncio.run(main())
