"""
Generate Conversations with Deepseek V3
Test script: Generate 9 conversations (3 levels × 3 topics)

Usage:
    python crawler/generate_conversations_test.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import List, Dict
from openai import OpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.models.conversation_models import (
    ConversationLibrary,
    ConversationVocabulary,
    DialogueTurn,
    TopicDisplay,
    TitleDisplay,
    AudioInfo,
    VocabularyItem,
    GrammarPoint,
    ConversationLevel,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")

# Test topics (3 topics)
TEST_TOPICS = [
    {"slug": "restaurant", "en": "At Restaurant", "vi": "Ở nhà hàng"},
    {"slug": "shopping", "en": "Shopping", "vi": "Mua sắm"},
    {"slug": "travel", "en": "Travel", "vi": "Du lịch"},
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
# PROMPT TEMPLATES
# ============================================================================


def build_prompt(level: ConversationLevel, topic: Dict) -> str:
    """Build prompt for Deepseek API"""

    config = LEVEL_CONFIG[level]

    prompt = f"""Generate 1 English conversation for learning English at {level.value.upper()} level on topic "{topic['en']}".

LEVEL REQUIREMENTS for {level.value.upper()}:
- Dialogue turns: {config['turns']} turns (STRICTLY between {config['turns_min']}-{config['turns_max']})
- Vocabulary difficulty: {config['description']}
- Vocabulary items: {config['vocabulary_count']} words
- Grammar points: {config['grammar_count']} patterns

CONVERSATION STRUCTURE:
1. Metadata:
   - title_en: English title (concise, 3-5 words)
   - title_vi: Vietnamese title
   - situation: Brief context (1-2 sentences)

2. Dialogue ({config['turns']} turns):
   - Speaker A: Male customer/person
   - Speaker B: Female service provider/friend
   - Alternate speakers (A → B → A → B...)
   - Each turn includes:
     * speaker: "A" or "B"
     * gender: "male" or "female"
     * text_en: English text
     * text_vi: Vietnamese translation
     * order: Turn number (1, 2, 3...)

3. Vocabulary ({config['vocabulary_count']} words):
   - Select key words from the conversation
   - Include various parts of speech (nouns, verbs, adjectives, phrases)
   - Each word includes:
     * word: The word/phrase
     * definition_en: Clear English definition
     * definition_vi: Vietnamese definition
     * example: Exact sentence from conversation containing this word
     * pos_tag: NOUN, VERB, ADJ, ADV, PHRASE, etc.

4. Grammar Points ({config['grammar_count']} patterns):
   - Identify useful grammar patterns from conversation
   - Each pattern includes:
     * pattern: The grammar pattern (e.g., "Can I + verb?", "I would like + noun")
     * explanation_en: How to use this pattern
     * explanation_vi: Vietnamese explanation
     * example: Exact sentence from conversation

TOPIC CONTEXT: {topic['en']} / {topic['vi']}
- Create natural, realistic dialogue for this topic
- Use appropriate vocabulary for {level.value} level
- Ensure situation is clear and relatable

OUTPUT FORMAT: Return ONLY valid JSON (no markdown, no code blocks):
{{
  "title_en": "...",
  "title_vi": "...",
  "situation": "...",
  "dialogue": [
    {{
      "speaker": "A",
      "gender": "male",
      "text_en": "...",
      "text_vi": "...",
      "order": 1
    }}
  ],
  "vocabulary": [
    {{
      "word": "...",
      "definition_en": "...",
      "definition_vi": "...",
      "example": "...",
      "pos_tag": "..."
    }}
  ],
  "grammar_points": [
    {{
      "pattern": "...",
      "explanation_en": "...",
      "explanation_vi": "...",
      "example": "..."
    }}
  ]
}}

IMPORTANT RULES:
1. MUST have exactly {config['turns_min']}-{config['turns_max']} dialogue turns
2. Dialogue must be natural and realistic
3. Vietnamese translations must be accurate
4. Grammar patterns must actually appear in the dialogue
5. Vocabulary examples must be exact quotes from dialogue
6. Return ONLY valid JSON"""

    return prompt


# ============================================================================
# DEEPSEEK API
# ============================================================================

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


async def generate_conversation(level: ConversationLevel, topic: Dict) -> Dict:
    """Generate single conversation"""

    print(f"\n🔄 Generating: {level.value.upper()} - {topic['en']}")

    prompt = build_prompt(level, topic)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert English teacher creating natural conversations for language learners. Always respond in valid JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
            stream=False,
        )

        raw_response = response.choices[0].message.content

        # Clean response
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Parse JSON
        data = json.loads(cleaned)

        # Validate structure
        required_keys = [
            "title_en",
            "title_vi",
            "situation",
            "dialogue",
            "vocabulary",
            "grammar_points",
        ]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key: {key}")

        # Validate turn count
        turn_count = len(data["dialogue"])
        config = LEVEL_CONFIG[level]
        if turn_count < config["turns_min"] or turn_count > config["turns_max"]:
            print(
                f"  ⚠️ Warning: {turn_count} turns (expected {config['turns_min']}-{config['turns_max']})"
            )

        print(
            f"  ✅ Generated: {turn_count} turns, {len(data['vocabulary'])} words, {len(data['grammar_points'])} grammar"
        )

        return data

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON Error: {e}")
        print(f"  Raw response: {raw_response[:200]}...")
        raise
    except Exception as e:
        print(f"  ❌ Error: {e}")
        raise


def save_conversation_to_db(
    level: ConversationLevel, topic: Dict, data: Dict, index: int
):
    """Save conversation to MongoDB"""

    db_manager = DBManager()
    db = db_manager.db

    # Generate conversation ID
    conversation_id = f"conv_{level.value}_{topic['slug']}_{index:03d}"

    # Build dialogue turns
    dialogue_turns = []
    for turn in data["dialogue"]:
        dialogue_turns.append(
            DialogueTurn(
                speaker=turn["speaker"],
                gender=turn["gender"],
                text_en=turn["text_en"],
                text_vi=turn["text_vi"],
                order=turn["order"],
            )
        )

    # Build full text
    full_text_en = "\n".join(
        [f"{turn['speaker']}: {turn['text_en']}" for turn in data["dialogue"]]
    )
    full_text_vi = "\n".join(
        [f"{turn['speaker']}: {turn['text_vi']}" for turn in data["dialogue"]]
    )

    # Count words
    word_count = sum(len(turn["text_en"].split()) for turn in data["dialogue"])

    # Create conversation record
    conversation = ConversationLibrary(
        conversation_id=conversation_id,
        level=level,
        topic=topic["slug"],
        topic_display=TopicDisplay(en=topic["en"], vi=topic["vi"]),
        title=TitleDisplay(en=data["title_en"], vi=data["title_vi"]),
        situation=data["situation"],
        dialogue=dialogue_turns,
        full_text_en=full_text_en,
        full_text_vi=full_text_vi,
        audio=AudioInfo(),
        word_count=word_count,
        turn_count=len(dialogue_turns),
        difficulty_score=LEVEL_CONFIG[level]["difficulty_score"],
        generated_by="deepseek-v3",
        generated_at=datetime.utcnow(),
    )

    # Save to database
    db["conversation_library"].insert_one(conversation.model_dump())

    # Create vocabulary record
    vocabulary_items = []
    for item in data["vocabulary"]:
        vocabulary_items.append(
            VocabularyItem(
                word=item["word"],
                definition_en=item["definition_en"],
                definition_vi=item["definition_vi"],
                example=item["example"],
                pos_tag=item["pos_tag"],
            )
        )

    grammar_points = []
    for point in data["grammar_points"]:
        grammar_points.append(
            GrammarPoint(
                pattern=point["pattern"],
                explanation_en=point["explanation_en"],
                explanation_vi=point["explanation_vi"],
                example=point["example"],
            )
        )

    vocabulary = ConversationVocabulary(
        vocab_id=f"vocab_{conversation_id}",
        conversation_id=conversation_id,
        vocabulary=vocabulary_items,
        grammar_points=grammar_points,
        generated_by="deepseek-v3",
        generated_at=datetime.utcnow(),
    )

    db["conversation_vocabulary"].insert_one(vocabulary.model_dump())

    print(f"  💾 Saved to database: {conversation_id}")

    return conversation_id


def save_conversation_to_file(
    level: ConversationLevel, topic: Dict, data: Dict, index: int
):
    """Save conversation to local JSON file"""

    conversation_id = f"conv_{level.value}_{topic['slug']}_{index:03d}"

    # Create output directory
    output_dir = "test_conversations_output"
    os.makedirs(output_dir, exist_ok=True)

    # Save to file
    filename = f"{output_dir}/{conversation_id}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  💾 Saved to file: {filename}")

    return filename


# ============================================================================
# MAIN TEST
# ============================================================================


async def main():
    """Generate 9 test conversations (3 levels × 3 topics)"""

    print("=" * 80)
    print("CONVERSATION GENERATION TEST")
    print("=" * 80)
    print(f"\nGenerating 9 conversations:")
    print(f"  • 3 Levels: Beginner, Intermediate, Advanced")
    print(f"  • 3 Topics: {', '.join([t['en'] for t in TEST_TOPICS])}")
    print(f"  • Total: 9 conversations")
    print()

    results = []

    for level in [
        ConversationLevel.BEGINNER,
        ConversationLevel.INTERMEDIATE,
        ConversationLevel.ADVANCED,
    ]:
        print(f"\n{'=' * 80}")
        print(f"LEVEL: {level.value.upper()}")
        print(f"{'=' * 80}")

        for idx, topic in enumerate(TEST_TOPICS, 1):
            try:
                # Generate conversation
                data = await generate_conversation(level, topic)

                # Save to local file
                filename = save_conversation_to_file(level, topic, data, idx)

                # Save to database (optional - comment out if you don't want DB saves yet)
                # conversation_id = save_conversation_to_db(level, topic, data, idx)

                results.append(
                    {
                        "level": level.value,
                        "topic": topic["slug"],
                        "title_en": data["title_en"],
                        "turns": len(data["dialogue"]),
                        "vocabulary": len(data["vocabulary"]),
                        "grammar": len(data["grammar_points"]),
                        "filename": filename,
                        "status": "✅ Success",
                    }
                )

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                print(f"  ❌ Failed: {e}")
                results.append(
                    {
                        "level": level.value,
                        "topic": topic["slug"],
                        "status": f"❌ Failed: {e}",
                    }
                )

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")

    print(
        f"{'Level':<15} {'Topic':<15} {'Title':<30} {'Turns':<8} {'Vocab':<8} {'Grammar':<8} {'Status'}"
    )
    print("-" * 80)

    for result in results:
        if "turns" in result:
            print(
                f"{result['level']:<15} {result['topic']:<15} {result['title_en']:<30} {result['turns']:<8} {result['vocabulary']:<8} {result['grammar']:<8} {result['status']}"
            )
        else:
            print(
                f"{result['level']:<15} {result['topic']:<15} {'N/A':<30} {'N/A':<8} {'N/A':<8} {'N/A':<8} {result['status']}"
            )

    print(f"\n{'=' * 80}")
    success_count = sum(1 for r in results if "✅" in r["status"])
    print(f"✅ Successful: {success_count}/9")
    print(f"❌ Failed: {9 - success_count}/9")
    print(f"\n📁 Output directory: test_conversations_output/")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(main())
