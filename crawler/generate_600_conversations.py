"""
Generate ALL 600 Conversations (30 Topics × 20 Conversations)

Strategy:
- Parse 600 conversation titles from Topic Conversation file
- Generate in batches of 3 conversations per DeepSeek API call
- Total API calls: 600 ÷ 3 = 200 calls
- Auto-generate situations for each conversation
- Save to MongoDB: conversation_library + conversation_vocabulary

RUN IN DOCKER:
    docker exec ai-chatbot-rag python crawler/generate_600_conversations.py

RUN SPECIFIC RANGE:
    docker exec ai-chatbot-rag python crawler/generate_600_conversations.py --start 1 --end 100
    docker exec ai-chatbot-rag python crawler/generate_600_conversations.py --topic 1
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, List
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.models.conversation_models import ConversationLevel


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-d04b95eeae094da2ba4b69eb62c5e1bd")

LEVEL_CONFIG = {
    ConversationLevel.BEGINNER: {
        "turns": "6-8",
        "vocabulary_count": "8-10",
        "grammar_count": "3-4",
        "difficulty_score": 2.5,
    },
    ConversationLevel.INTERMEDIATE: {
        "turns": "8-12",
        "vocabulary_count": "10-12",
        "grammar_count": "4-5",
        "difficulty_score": 5.5,
    },
    ConversationLevel.ADVANCED: {
        "turns": "10-15",
        "vocabulary_count": "12-15",
        "grammar_count": "5-6",
        "difficulty_score": 8.5,
    },
}

# Vietnamese topic names
TOPIC_VI_MAP = {
    "Greetings & Introductions": "Chào hỏi & Giới thiệu",
    "Daily Routines": "Thói quen hàng ngày",
    "Family & Relationships": "Gia đình & Mối quan hệ",
    "Food & Drinks": "Đồ ăn & Đồ uống",
    "Shopping": "Mua sắm",
    "Weather & Seasons": "Thời tiết & Mùa",
    "Home & Accommodation": "Nhà ở & Chỗ ở",
    "Transportation": "Phương tiện giao thông",
    "Health & Body": "Sức khỏe & Cơ thể",
    "Hobbies & Interests": "Sở thích & Quan tâm",
    "Work & Office": "Công việc & Văn phòng",
    "Travel & Tourism": "Du lịch & Khách sạn",
    "Education & Learning": "Giáo dục & Học tập",
    "Technology & Internet": "Công nghệ & Internet",
    "Social Issues": "Vấn đề xã hội",
    "Entertainment & Media": "Giải trí & Truyền thông",
    "Sports & Fitness": "Thể thao & Thể dục",
    "Finance & Money": "Tài chính & Tiền bạc",
    "Events & Celebrations": "Sự kiện & Lễ kỷ niệm",
    "Emergency & Safety": "Khẩn cấp & An toàn",
    "Business & Entrepreneurship": "Kinh doanh & Khởi nghiệp",
    "Law & Justice": "Luật pháp & Công lý",
    "Science & Research": "Khoa học & Nghiên cứu",
    "Medicine & Healthcare": "Y học & Chăm sóc sức khỏe",
    "Politics & Government": "Chính trị & Chính phủ",
    "Philosophy & Ethics": "Triết học & Đạo đức",
    "Art & Creativity": "Nghệ thuật & Sáng tạo",
    "Environment & Nature": "Môi trường & Thiên nhiên",
    "History & Culture": "Lịch sử & Văn hóa",
    "Future & Innovation": "Tương lai & Đổi mới",
}


def parse_600_conversations(file_path: str) -> List[Dict]:
    """Parse all 600 conversations from file"""

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    conversations = []
    current_topic = None
    current_topic_num = None
    current_level = None

    for line in lines:
        line = line.strip()

        # Detect level sections
        if "📘 PHẦN 1: CƠ BẢN" in line:
            current_level = ConversationLevel.BEGINNER
            continue
        elif "📗 PHẦN 2: TRUNG CẤP" in line:
            current_level = ConversationLevel.INTERMEDIATE
            continue
        elif "📙 PHẦN 3: NÂNG CAO" in line:
            current_level = ConversationLevel.ADVANCED
            continue

        # Parse topic line (format: "1\tGreetings & Introductions\t1. Hello...")
        if "\t" in line and current_level:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip().isdigit():
                num = int(parts[0].strip())
                if 1 <= num <= 30:
                    current_topic_num = num
                    current_topic = parts[1].strip()

        # Parse conversation line (format: "1. Hello, How Are You?")
        if current_topic and line and line[0].isdigit() and ". " in line:
            try:
                idx = line.index(". ")
                title_en = line[idx + 2 :].strip()
                if title_en and not title_en.startswith("Conversation"):
                    conversations.append(
                        {
                            "level": current_level,
                            "topic_number": current_topic_num,
                            "topic_en": current_topic,
                            "topic_vi": TOPIC_VI_MAP.get(current_topic, current_topic),
                            "topic_slug": current_topic.lower()
                            .replace(" & ", "_")
                            .replace(" ", "_")
                            .replace("&", ""),
                            "title_en": title_en,
                        }
                    )
            except:
                pass

    return conversations


def build_batch_prompt(batch: List[Dict]) -> str:
    """Build prompt for 3 conversations at once"""

    level = batch[0]["level"]
    config = LEVEL_CONFIG[level]

    conversations_text = ""
    for i, conv in enumerate(batch, 1):
        conversations_text += f"""
CONVERSATION {i}:
- Topic: {conv['topic_en']} ({conv['topic_vi']})
- Title (EN): {conv['title_en']}
- Title (VI): [Translate to Vietnamese naturally]
- Situation: [Create a realistic 1-sentence situation for this conversation]
"""

    prompt = f"""Generate 3 English conversations at {level.value.upper()} level.

{conversations_text}

REQUIREMENTS for {level.value.upper()}:
- Dialogue turns: {config['turns']}
- Vocabulary: {config['vocabulary_count']} words
- Grammar: {config['grammar_count']} patterns

OUTPUT FORMAT (JSON array of 3 conversations):
[
  {{
    "title_en": "...",
    "title_vi": "...",
    "situation": "...",
    "dialogue": [
      {{"speaker": "A", "gender": "male/female", "text_en": "...", "text_vi": "...", "order": 1}},
      ...
    ],
    "vocabulary": [
      {{"word": "...", "definition_en": "...", "definition_vi": "...", "example": "...", "pos_tag": "NOUN"}},
      ...
    ],
    "grammar_points": [
      {{"pattern": "...", "explanation_en": "...", "explanation_vi": "...", "example": "..."}},
      ...
    ]
  }},
  ... (2 more conversations)
]

Generate now (output pure JSON array only):"""

    return prompt


async def generate_batch(batch: List[Dict]) -> List[Dict]:
    """Generate 3 conversations in one API call"""

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    prompt = build_batch_prompt(batch)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=8000,
    )

    content = response.choices[0].message.content

    # Clean markdown
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        content = "\n".join(lines)

    data = json.loads(content)
    return data


def save_conversation(
    conv_def: Dict, generated: Dict, db_manager: DBManager, conv_index: int
) -> str:
    """Save one conversation to MongoDB"""

    level = conv_def["level"]
    config = LEVEL_CONFIG[level]

    # Use conversation index to ensure unique IDs (001-020 for each topic)
    conversation_id = f"conv_{level.value}_{conv_def['topic_slug']}_{conv_def['topic_number']:02d}_{conv_index:03d}"

    full_text_en = " ".join([t["text_en"] for t in generated["dialogue"]])
    full_text_vi = " ".join([t["text_vi"] for t in generated["dialogue"]])

    doc = {
        "conversation_id": conversation_id,
        "level": level.value,
        "topic_number": conv_def["topic_number"],
        "topic_slug": conv_def["topic_slug"],
        "topic": {"en": conv_def["topic_en"], "vi": conv_def["topic_vi"]},
        "title": {"en": generated["title_en"], "vi": generated["title_vi"]},
        "situation": generated["situation"],
        "dialogue": generated["dialogue"],
        "full_text_en": full_text_en,
        "full_text_vi": full_text_vi,
        "word_count": len(full_text_en.split()),
        "turn_count": len(generated["dialogue"]),
        "difficulty_score": config["difficulty_score"],
        "generated_by": "deepseek-v3",
        "has_audio": False,
        "audio_info": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    db_manager.db.conversation_library.update_one(
        {"conversation_id": conversation_id}, {"$set": doc}, upsert=True
    )

    vocab_doc = {
        "vocab_id": f"vocab_{conversation_id}",
        "conversation_id": conversation_id,
        "vocabulary": generated["vocabulary"],
        "grammar_points": generated["grammar_points"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    db_manager.db.conversation_vocabulary.update_one(
        {"conversation_id": conversation_id}, {"$set": vocab_doc}, upsert=True
    )

    return conversation_id


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start index (1-600)")
    parser.add_argument("--end", type=int, default=600, help="End index (1-600)")
    parser.add_argument("--topic", type=int, help="Generate only specific topic (1-30)")
    args = parser.parse_args()

    print("=" * 80)
    print("GENERATE 600 CONVERSATIONS (30 Topics × 20 Conversations)")
    print("=" * 80)
    print()

    # Parse file
    file_path = "docs/wordai/Learn English With Songs/Topic Conversation.md"
    print(f"📖 Parsing: {file_path}")
    conversations = parse_600_conversations(file_path)
    print(f"✅ Parsed {len(conversations)} conversations")
    print()

    # Filter by arguments
    if args.topic:
        conversations = [c for c in conversations if c["topic_number"] == args.topic]
        print(f"🎯 Filtered to topic #{args.topic}: {len(conversations)} conversations")
    else:
        conversations = conversations[args.start - 1 : args.end]
        print(f"🎯 Range: {args.start}-{args.end} ({len(conversations)} conversations)")
    print()

    # Database
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    print(f"✅ Connected: {db_manager.db.name}")
    print()

    # Generate in batches of 3
    batches = [conversations[i : i + 3] for i in range(0, len(conversations), 3)]
    total_batches = len(batches)

    print(f"📦 Processing {total_batches} batches (3 conversations each)")
    print()

    success = 0
    failed = 0
    conv_index = 1  # Track global conversation index

    for i, batch in enumerate(batches, 1):
        print(f"[{i}/{total_batches}] Batch {i}: {len(batch)} conversations")

        try:
            # Generate
            generated_list = await generate_batch(batch)

            # Save each
            for conv_def, generated in zip(batch, generated_list):
                conv_id = save_conversation(conv_def, generated, db_manager, conv_index)
                print(f"  ✅ {conv_id}")
                success += 1
                conv_index += 1  # Increment for next conversation

            print()

            # Rate limit
            if i < total_batches:
                await asyncio.sleep(2)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += len(batch)
            print()

    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total in DB: {db_manager.db.conversation_library.count_documents({})}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
