"""
Generate All 30 Topics × 3 Levels = 90 Conversations

Total: 30 topics × 3 levels (Beginner, Intermediate, Advanced) = 90 conversations
Each topic gets 1 conversation per level (first conversation from each topic's 20 options)

Beginner (10 topics):   Topics 1-10
Intermediate (10):      Topics 11-20
Advanced (10):          Topics 21-30

RUN IN DOCKER (Production):
    docker exec ai-chatbot-rag python crawler/generate_all_30_topics.py

RUN SPECIFIC SECTION:
    docker exec ai-chatbot-rag python crawler/generate_all_30_topics.py --section beginner
    docker exec ai-chatbot-rag python crawler/generate_all_30_topics.py --section intermediate
    docker exec ai-chatbot-rag python crawler/generate_all_30_topics.py --section advanced

RUN SPECIFIC TOPIC:
    docker exec ai-chatbot-rag python crawler/generate_all_30_topics.py --topic 1
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, List
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
# ALL 30 TOPICS × 3 LEVELS = 90 CONVERSATIONS
# ============================================================================

ALL_TOPICS = [
    # ========================================================================
    # PHẦN 1: CƠ BẢN (10 Topics) - BEGINNER LEVEL
    # ========================================================================
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
        "level": ConversationLevel.BEGINNER,
        "topic_number": 2,
        "topic_slug": "daily_routines",
        "topic_en": "Daily Routines",
        "topic_vi": "Thói quen hàng ngày",
        "title_en": "Waking Up Early",
        "title_vi": "Thức dậy sớm",
        "situation": "A person talks about their morning routine and waking up early.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 3,
        "topic_slug": "family_relationships",
        "topic_en": "Family & Relationships",
        "topic_vi": "Gia đình & Mối quan hệ",
        "title_en": "Talking About Parents",
        "title_vi": "Nói về cha mẹ",
        "situation": "Two people talk about their parents and family life.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 4,
        "topic_slug": "food_drinks",
        "topic_en": "Food & Drinks",
        "topic_vi": "Đồ ăn & Đồ uống",
        "title_en": "Ordering Coffee",
        "title_vi": "Gọi cà phê",
        "situation": "A customer orders coffee at a café.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 5,
        "topic_slug": "shopping",
        "topic_en": "Shopping",
        "topic_vi": "Mua sắm",
        "title_en": "At the Supermarket",
        "title_vi": "Ở siêu thị",
        "situation": "A person shops for groceries at the supermarket.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 6,
        "topic_slug": "weather_seasons",
        "topic_en": "Weather & Seasons",
        "topic_vi": "Thời tiết & Mùa",
        "title_en": "A Sunny Day",
        "title_vi": "Một ngày nắng đẹp",
        "situation": "Two people talk about the beautiful sunny weather.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 7,
        "topic_slug": "home_accommodation",
        "topic_en": "Home & Accommodation",
        "topic_vi": "Nhà ở & Chỗ ở",
        "title_en": "Renting an Apartment",
        "title_vi": "Thuê căn hộ",
        "situation": "A person talks to a landlord about renting an apartment.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 8,
        "topic_slug": "transportation",
        "topic_en": "Transportation",
        "topic_vi": "Phương tiện giao thông",
        "title_en": "Taking a Bus",
        "title_vi": "Đi xe buýt",
        "situation": "A person asks about taking a bus to get somewhere.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 9,
        "topic_slug": "health_body",
        "topic_en": "Health & Body",
        "topic_vi": "Sức khỏe & Cơ thể",
        "title_en": "Making a Doctor's Appointment",
        "title_vi": "Đặt lịch khám bác sĩ",
        "situation": "A patient calls to make an appointment with a doctor.",
    },
    {
        "level": ConversationLevel.BEGINNER,
        "topic_number": 10,
        "topic_slug": "hobbies_interests",
        "topic_en": "Hobbies & Interests",
        "topic_vi": "Sở thích & Quan tâm",
        "title_en": "Talking About Music",
        "title_vi": "Nói về âm nhạc",
        "situation": "Two friends discuss their favorite music and artists.",
    },
    # ========================================================================
    # PHẦN 2: TRUNG CẤP (10 Topics) - INTERMEDIATE LEVEL
    # ========================================================================
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
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 12,
        "topic_slug": "travel_tourism",
        "topic_en": "Travel & Tourism",
        "topic_vi": "Du lịch & Khách sạn",
        "title_en": "Planning a Vacation",
        "title_vi": "Lên kế hoạch kỳ nghỉ",
        "situation": "Two people plan their upcoming vacation together.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 13,
        "topic_slug": "education_learning",
        "topic_en": "Education & Learning",
        "topic_vi": "Giáo dục & Học tập",
        "title_en": "Choosing a University",
        "title_vi": "Chọn trường đại học",
        "situation": "A student discusses university choices with an advisor.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 14,
        "topic_slug": "technology_internet",
        "topic_en": "Technology & Internet",
        "topic_vi": "Công nghệ & Internet",
        "title_en": "Buying a New Laptop",
        "title_vi": "Mua laptop mới",
        "situation": "A customer asks for advice when buying a new laptop.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 15,
        "topic_slug": "social_issues",
        "topic_en": "Social Issues",
        "topic_vi": "Vấn đề xã hội",
        "title_en": "Gender Equality",
        "title_vi": "Bình đẳng giới",
        "situation": "Two people discuss gender equality in the workplace.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 16,
        "topic_slug": "entertainment_media",
        "topic_en": "Entertainment & Media",
        "topic_vi": "Giải trí & Truyền thông",
        "title_en": "Movie Night",
        "title_vi": "Đêm xem phim",
        "situation": "Friends decide what movie to watch together.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 17,
        "topic_slug": "sports_fitness",
        "topic_en": "Sports & Fitness",
        "topic_vi": "Thể thao & Thể dục",
        "title_en": "Joining a Gym",
        "title_vi": "Đăng ký phòng tập",
        "situation": "A person inquires about joining a gym and membership options.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 18,
        "topic_slug": "finance_money",
        "topic_en": "Finance & Money",
        "topic_vi": "Tài chính & Tiền bạc",
        "title_en": "Opening a Bank Account",
        "title_vi": "Mở tài khoản ngân hàng",
        "situation": "A customer opens a new bank account at a branch.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 19,
        "topic_slug": "events_celebrations",
        "topic_en": "Events & Celebrations",
        "topic_vi": "Sự kiện & Lễ kỷ niệm",
        "title_en": "Birthday Party",
        "title_vi": "Tiệc sinh nhật",
        "situation": "Friends plan a birthday party for their friend.",
    },
    {
        "level": ConversationLevel.INTERMEDIATE,
        "topic_number": 20,
        "topic_slug": "emergency_safety",
        "topic_en": "Emergency & Safety",
        "topic_vi": "Khẩn cấp & An toàn",
        "title_en": "Calling 911",
        "title_vi": "Gọi 911",
        "situation": "A person calls emergency services to report an accident.",
    },
    # ========================================================================
    # PHẦN 3: NÂNG CAO (10 Topics) - ADVANCED LEVEL
    # ========================================================================
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
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 22,
        "topic_slug": "law_justice",
        "topic_en": "Law & Justice",
        "topic_vi": "Luật pháp & Công lý",
        "title_en": "Reporting a Crime",
        "title_vi": "Báo cáo tội phạm",
        "situation": "A person reports a crime to the police at a station.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 23,
        "topic_slug": "science_research",
        "topic_en": "Science & Research",
        "topic_vi": "Khoa học & Nghiên cứu",
        "title_en": "Lab Experiment",
        "title_vi": "Thí nghiệm trong phòng thí nghiệm",
        "situation": "Scientists discuss their lab experiment and findings.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 24,
        "topic_slug": "medicine_healthcare",
        "topic_en": "Medicine & Healthcare",
        "topic_vi": "Y học & Chăm sóc sức khỏe",
        "title_en": "Diagnosis Discussion",
        "title_vi": "Thảo luận chẩn đoán",
        "situation": "A doctor discusses a diagnosis with a patient.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 25,
        "topic_slug": "politics_government",
        "topic_en": "Politics & Government",
        "topic_vi": "Chính trị & Chính phủ",
        "title_en": "Voting Day",
        "title_vi": "Ngày bầu cử",
        "situation": "Citizens discuss the importance of voting on election day.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 26,
        "topic_slug": "philosophy_ethics",
        "topic_en": "Philosophy & Ethics",
        "topic_vi": "Triết học & Đạo đức",
        "title_en": "Meaning of Life",
        "title_vi": "Ý nghĩa cuộc sống",
        "situation": "Two philosophers debate the meaning and purpose of life.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 27,
        "topic_slug": "art_creativity",
        "topic_en": "Art & Creativity",
        "topic_vi": "Nghệ thuật & Sáng tạo",
        "title_en": "Artist Statement",
        "title_vi": "Tuyên bố nghệ thuật",
        "situation": "An artist explains their artistic vision and creative process.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 28,
        "topic_slug": "environment_nature",
        "topic_en": "Environment & Nature",
        "topic_vi": "Môi trường & Thiên nhiên",
        "title_en": "Wildlife Conservation",
        "title_vi": "Bảo tồn động vật hoang dã",
        "situation": "Conservationists discuss protecting endangered wildlife species.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 29,
        "topic_slug": "history_culture",
        "topic_en": "History & Culture",
        "topic_vi": "Lịch sử & Văn hóa",
        "title_en": "Museum Tour",
        "title_vi": "Tham quan bảo tàng",
        "situation": "A guide leads a museum tour explaining historical artifacts.",
    },
    {
        "level": ConversationLevel.ADVANCED,
        "topic_number": 30,
        "topic_slug": "future_innovation",
        "topic_en": "Future & Innovation",
        "topic_vi": "Tương lai & Đổi mới",
        "title_en": "Life in 2050",
        "title_vi": "Cuộc sống năm 2050",
        "situation": "Futurists discuss predictions about life and technology in 2050.",
    },
]


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

    # Generate conversation_id: conv_{level}_{topic_slug}_{level_initial}
    # Example: conv_beginner_greetings_introductions_b (b for beginner)
    # Example: conv_intermediate_work_office_i (i for intermediate)
    # Example: conv_advanced_business_entrepreneurship_a (a for advanced)
    level_initial = level.value[0]  # b, i, or a
    conversation_id = f"conv_{level.value}_{conv_data['topic_slug']}_{level_initial}"

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

    print(f"✅ Saved: {conversation_id}")
    print(f"   {conv['level'].title()}: {conv['topic']['en']} - {conv['title']['en']}")
    print(f"   Turns: {conv['turn_count']}, Words: {conv['word_count']}")

    # Check vocabulary
    vocab = db_manager.db.conversation_vocabulary.find_one(
        {"conversation_id": conversation_id}
    )

    if vocab:
        print(
            f"   Vocab: {len(vocab['vocabulary'])}, Grammar: {len(vocab['grammar_points'])}"
        )


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Generate all 30 topics × 3 levels = 90 conversations"""

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Generate all 30 topics × 3 levels conversations"
    )
    parser.add_argument(
        "--section",
        choices=["beginner", "intermediate", "advanced"],
        help="Generate only specific section (beginner: topics 1-10, intermediate: 11-20, advanced: 21-30)",
    )
    parser.add_argument(
        "--topic", type=int, help="Generate only specific topic number (1-30)"
    )
    args = parser.parse_args()

    # Filter topics based on arguments
    topics_to_generate = ALL_TOPICS

    if args.section:
        section_map = {
            "beginner": ConversationLevel.BEGINNER,
            "intermediate": ConversationLevel.INTERMEDIATE,
            "advanced": ConversationLevel.ADVANCED,
        }
        topics_to_generate = [
            t for t in ALL_TOPICS if t["level"] == section_map[args.section]
        ]

    if args.topic:
        topics_to_generate = [
            t for t in topics_to_generate if t["topic_number"] == args.topic
        ]

    print("=" * 80)
    print("GENERATE ALL 30 TOPICS × 3 LEVELS = 90 CONVERSATIONS")
    print("=" * 80)
    print()
    print(f"Total conversations to generate: {len(topics_to_generate)}")
    if args.section:
        print(f"Section: {args.section.upper()}")
    if args.topic:
        print(f"Topic: #{args.topic}")
    print()

    # Initialize database
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    print(f"✅ Connected to database: {db_manager.db.name}")
    print()

    # Track progress
    success_count = 0
    fail_count = 0
    failed_topics = []

    # Generate conversations
    for i, conv_data in enumerate(topics_to_generate, 1):
        level = conv_data["level"]
        topic_num = conv_data["topic_number"]

        print("=" * 80)
        print(
            f"[{i}/{len(topics_to_generate)}] TOPIC #{topic_num}: {conv_data['topic_en']} ({level.value.upper()})"
        )
        print("=" * 80)
        print(f"Title: {conv_data['title_en']}")

        try:
            # Generate conversation
            generated_data = await generate_conversation(conv_data)

            # Validate
            turn_count = len(generated_data["dialogue"])
            vocab_count = len(generated_data["vocabulary"])
            grammar_count = len(generated_data["grammar_points"])

            print(
                f"✅ Generated: {turn_count} turns, {vocab_count} vocab, {grammar_count} grammar"
            )

            # Save to database
            conversation_id = save_to_database(conv_data, generated_data, db_manager)

            # Verify
            verify_database(conversation_id, db_manager)

            success_count += 1
            print()

            # Rate limiting (2 seconds between requests)
            if i < len(topics_to_generate):
                print("⏳ Waiting 2 seconds...")
                await asyncio.sleep(2)
                print()

        except Exception as e:
            print(f"❌ Failed: {e}")
            fail_count += 1
            failed_topics.append(
                {
                    "topic_number": topic_num,
                    "topic_en": conv_data["topic_en"],
                    "level": level.value,
                    "error": str(e),
                }
            )
            print()
            continue

    # Summary
    print("=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print()
    print(f"✅ Success: {success_count}/{len(topics_to_generate)}")
    print(f"❌ Failed: {fail_count}/{len(topics_to_generate)}")
    print()

    if failed_topics:
        print("Failed topics:")
        for topic in failed_topics:
            print(
                f"  - Topic #{topic['topic_number']}: {topic['topic_en']} ({topic['level']})"
            )
            print(f"    Error: {topic['error']}")
        print()

    # Database summary
    print("📊 Database Summary:")
    for level in [
        ConversationLevel.BEGINNER,
        ConversationLevel.INTERMEDIATE,
        ConversationLevel.ADVANCED,
    ]:
        count = db_manager.db.conversation_library.count_documents(
            {"level": level.value}
        )
        print(f"   {level.value.title()}: {count} conversations")

    total = db_manager.db.conversation_library.count_documents({})
    print(f"   Total: {total} conversations")
    print()


if __name__ == "__main__":
    asyncio.run(main())
