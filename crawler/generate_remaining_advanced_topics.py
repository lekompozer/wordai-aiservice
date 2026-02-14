#!/usr/bin/env python3
"""
Generate Remaining 6 Advanced Topics (25 conversations each)

Topics to generate:
- Politics & Government (25 convs)
- Philosophy & Ethics (25 convs)
- Art & Creativity (25 convs)
- Environment & Nature (25 convs)
- History & Culture (25 convs)
- Future & Innovation (25 convs)

Total: 150 conversations

RUN IN BACKGROUND:
    nohup docker exec ai-chatbot-rag python crawler/generate_remaining_advanced_topics.py > /tmp/gen_advanced.log 2>&1 &
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, List
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")

# 6 remaining Advanced topics
ADVANCED_TOPICS = [
    {
        "topic_en": "Politics & Government",
        "topic_vi": "Chính trị & Chính phủ",
        "topic_slug": "politics_government",
        "topic_number": 25,
    },
    {
        "topic_en": "Philosophy & Ethics",
        "topic_vi": "Triết học & Đạo đức",
        "topic_slug": "philosophy_ethics",
        "topic_number": 26,
    },
    {
        "topic_en": "Art & Creativity",
        "topic_vi": "Nghệ thuật & Sáng tạo",
        "topic_slug": "art_creativity",
        "topic_number": 27,
    },
    {
        "topic_en": "Environment & Nature",
        "topic_vi": "Môi trường & Thiên nhiên",
        "topic_slug": "environment_nature",
        "topic_number": 28,
    },
    {
        "topic_en": "History & Culture",
        "topic_vi": "Lịch sử & Văn hóa",
        "topic_slug": "history_culture",
        "topic_number": 29,
    },
    {
        "topic_en": "Future & Innovation",
        "topic_vi": "Tương lai & Đổi mới",
        "topic_slug": "future_innovation",
        "topic_number": 30,
    },
]

# 25 conversation titles per topic
CONVERSATION_TITLES = {
    "Politics & Government": [
        "Democratic Systems and Elections",
        "Political Parties and Ideologies",
        "Government Structures and Functions",
        "Constitutional Rights and Amendments",
        "Foreign Policy and Diplomacy",
        "Political Campaigns and Voting",
        "Legislative Processes and Bills",
        "Executive Branch Powers",
        "Judicial System and Courts",
        "Federalism and State Rights",
        "Political Accountability and Transparency",
        "Lobbying and Interest Groups",
        "Political Scandals and Reforms",
        "Public Policy Development",
        "International Relations",
        "Political Communication and Media",
        "Civic Engagement and Activism",
        "Electoral Reform Debates",
        "Bureaucracy and Public Administration",
        "Political Philosophy and Theory",
        "Separation of Powers",
        "Political Ethics and Corruption",
        "Geopolitics and Power Dynamics",
        "Democracy vs Authoritarianism",
        "Global Governance and UN",
    ],
    "Philosophy & Ethics": [
        "Introduction to Western Philosophy",
        "Eastern Philosophy Traditions",
        "Ethics and Moral Philosophy",
        "Logic and Critical Thinking",
        "Epistemology: Theory of Knowledge",
        "Metaphysics and Reality",
        "Political Philosophy",
        "Existentialism and Meaning",
        "Utilitarianism and Consequentialism",
        "Deontological Ethics",
        "Virtue Ethics",
        "Applied Ethics in Medicine",
        "Business Ethics",
        "Environmental Ethics",
        "Philosophy of Mind",
        "Free Will vs Determinism",
        "The Problem of Evil",
        "Philosophy of Science",
        "Aesthetics and Beauty",
        "Social Contract Theory",
        "Moral Relativism vs Absolutism",
        "Animal Rights and Ethics",
        "Technology and Ethics",
        "Philosophy of Language",
        "Meaning of Life",
    ],
    "Art & Creativity": [
        "History of Western Art",
        "Renaissance Art and Artists",
        "Modern Art Movements",
        "Contemporary Art Trends",
        "Painting Techniques and Styles",
        "Sculpture and 3D Art",
        "Photography as Art",
        "Digital Art and Design",
        "Street Art and Graffiti",
        "Performance Art",
        "Installation Art",
        "Art Criticism and Theory",
        "Creative Writing Process",
        "Poetry and Verse",
        "Filmmaking and Cinematography",
        "Music Composition",
        "Theater and Drama",
        "Dance and Choreography",
        "Fashion Design",
        "Graphic Design Principles",
        "Architecture and Space",
        "Art Marketing and Galleries",
        "Creative Thinking Skills",
        "Inspiration and Artist's Block",
        "Art and Social Change",
    ],
    "Environment & Nature": [
        "Climate Change Science",
        "Renewable Energy Solutions",
        "Conservation and Biodiversity",
        "Pollution and Air Quality",
        "Ocean Ecosystems",
        "Forest Management",
        "Wildlife Protection",
        "Sustainable Agriculture",
        "Water Resources Management",
        "Carbon Footprint Reduction",
        "Green Technology Innovation",
        "Environmental Policies",
        "Ecosystem Services",
        "Endangered Species",
        "Plastic Pollution Crisis",
        "Deforestation Issues",
        "Urban Sustainability",
        "Renewable vs Fossil Fuels",
        "Environmental Justice",
        "Nature Photography",
        "Ecological Restoration",
        "Green Building Design",
        "Circular Economy",
        "Ecotourism",
        "Climate Adaptation Strategies",
    ],
    "History & Culture": [
        "Ancient Civilizations",
        "Medieval Europe",
        "Renaissance Period",
        "Age of Exploration",
        "Industrial Revolution",
        "World War I",
        "World War II",
        "Cold War Era",
        "Decolonization Movements",
        "Civil Rights Movement",
        "Cultural Anthropology",
        "Archaeological Methods",
        "Historical Research",
        "Primary vs Secondary Sources",
        "Oral History Traditions",
        "Museum Studies",
        "Cultural Heritage Preservation",
        "Language Evolution",
        "Religious History",
        "Economic History",
        "Social History",
        "Women in History",
        "Historiography",
        "Cultural Exchange and Trade",
        "Historical Revisionism",
    ],
    "Future & Innovation": [
        "Artificial Intelligence Future",
        "Space Colonization",
        "Quantum Computing",
        "Gene Editing and CRISPR",
        "Brain-Computer Interfaces",
        "Virtual Reality Worlds",
        "Autonomous Vehicles",
        "Smart Cities",
        "Internet of Things",
        "5G and Beyond",
        "Blockchain Technology",
        "Biotechnology Advances",
        "Nanotechnology Applications",
        "Renewable Energy Future",
        "Food Technology Innovation",
        "Medical Breakthroughs",
        "Transhumanism",
        "Artificial General Intelligence",
        "Robotics and Automation",
        "3D Printing Revolution",
        "Future of Work",
        "Education Technology",
        "Sustainable Future",
        "Ethical AI Development",
        "Innovation Ecosystems",
    ],
}


def build_conversation_prompt(topic_info: Dict, title_en: str, index: int) -> str:
    """Build prompt for generating one conversation"""

    prompt = f"""Generate an ADVANCED level English conversation about: {title_en}

TOPIC: {topic_info['topic_en']} ({topic_info['topic_vi']})
TITLE: {title_en}

REQUIREMENTS:
- Dialogue turns: 12-16 turns (advanced complexity)
- Vocabulary: 12-15 advanced words (with definitions and examples)
- Grammar: 5-6 advanced grammar patterns (with explanations)
- Include: Title in Vietnamese, realistic situation, natural dialogue

OUTPUT FORMAT (JSON):
{{
  "title_en": "{title_en}",
  "title_vi": "[Translate to Vietnamese naturally]",
  "situation": "[Create a realistic 1-2 sentence situation]",
  "dialogue": [
    {{"speaker": "A", "gender": "male/female", "text_en": "...", "text_vi": "...", "order": 1}},
    ... (12-16 turns)
  ],
  "vocabulary": [
    {{
      "word": "...",
      "definition_en": "...",
      "definition_vi": "...",
      "example": "...",
      "pos_tag": "NOUN/VERB/ADJ/ADV"
    }},
    ... (12-15 words)
  ],
  "grammar_points": [
    {{
      "pattern": "...",
      "explanation_en": "...",
      "explanation_vi": "...",
      "example": "..."
    }},
    ... (5-6 patterns)
  ]
}}

Generate now (output pure JSON only):"""

    return prompt


async def generate_conversation(
    client: AsyncOpenAI,
    topic_info: Dict,
    title_en: str,
    index: int,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """Generate one conversation with retry logic"""

    async with semaphore:
        prompt = build_conversation_prompt(topic_info, title_en, index)

        for network_attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=6000,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                # Extract JSON from markdown
                json_content = content.strip()
                if "```" in json_content:
                    parts = json_content.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("json"):
                            part = part[4:].strip()
                        if part.startswith("{") and part.endswith("}"):
                            json_content = part
                            break

                # Parse JSON with retry
                for parse_attempt in range(2):
                    try:
                        data = json.loads(json_content)

                        # Validate required fields
                        required = ["dialogue", "vocabulary", "grammar_points"]
                        if not all(k in data for k in required):
                            raise ValueError(f"Missing fields")

                        # Just check dialogue is not empty
                        if not data.get("dialogue"):
                            raise ValueError("Empty dialogue")

                        return {
                            "topic_info": topic_info,
                            "title_en": title_en,
                            "index": index,
                            "data": data,
                        }

                    except json.JSONDecodeError as e:
                        if parse_attempt < 1:
                            json_content = json_content.replace("\n", " ")
                            await asyncio.sleep(0.5)
                            continue
                        else:
                            raise ValueError(f"JSON parse error: {e}")

            except Exception as e:
                if network_attempt < 2:
                    backoff = 2**network_attempt
                    await asyncio.sleep(backoff)
                    continue
                else:
                    raise Exception(f"Failed after 3 attempts: {e}")


def save_conversation(result: Dict, db_manager: DBManager) -> str:
    """Save conversation to MongoDB"""

    topic_info = result["topic_info"]
    data = result["data"]
    index = result["index"]

    conversation_id = f"conv_advanced_{topic_info['topic_slug']}_{topic_info['topic_number']:02d}_{index:03d}"

    full_text_en = " ".join([t["text_en"] for t in data["dialogue"]])
    full_text_vi = " ".join([t["text_vi"] for t in data["dialogue"]])

    doc = {
        "conversation_id": conversation_id,
        "level": "advanced",
        "topic_number": topic_info["topic_number"],
        "topic_slug": topic_info["topic_slug"],
        "topic": {"en": topic_info["topic_en"], "vi": topic_info["topic_vi"]},
        "title": {"en": data["title_en"], "vi": data["title_vi"]},
        "situation": data["situation"],
        "dialogue": data["dialogue"],
        "full_text_en": full_text_en,
        "full_text_vi": full_text_vi,
        "word_count": len(full_text_en.split()),
        "turn_count": len(data["dialogue"]),
        "difficulty_score": 8.5,
        "generated_by": "deepseek-chat",
        "has_audio": False,
        "audio_info": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    db_manager.db.conversation_library.update_one(
        {"conversation_id": conversation_id}, {"$set": doc}, upsert=True
    )

    # Save vocabulary
    vocab_doc = {
        "vocab_id": f"vocab_{conversation_id}",
        "conversation_id": conversation_id,
        "vocabulary": data["vocabulary"],
        "grammar_points": data["grammar_points"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    db_manager.db.conversation_vocabulary.update_one(
        {"conversation_id": conversation_id}, {"$set": vocab_doc}, upsert=True
    )

    return conversation_id


async def main():
    print("=" * 80)
    print("🎓 GENERATE 6 REMAINING ADVANCED TOPICS (150 conversations)")
    print("=" * 80)
    print()

    # Database
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    print(f"✅ Connected: {db_manager.db.name}")
    print()

    # Build tasks (6 topics × 25 conversations = 150)
    tasks = []
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    semaphore = asyncio.Semaphore(5)  # 5 parallel

    for topic in ADVANCED_TOPICS:
        titles = CONVERSATION_TITLES[topic["topic_en"]]
        for i in range(25):
            index = i + 1
            title = titles[i]
            tasks.append(generate_conversation(client, topic, title, index, semaphore))

    print(f"🚀 Generating {len(tasks)} conversations (5 parallel)...")
    print()

    # Execute
    success_count = 0
    failed_count = 0
    results = []

    for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Progress"):
        try:
            result = await coro
            results.append(result)
            success_count += 1
        except Exception as e:
            failed_count += 1

    print()
    print(f"✅ Generated: {success_count}/{len(tasks)}")
    print()

    # Save
    print("💾 Saving to MongoDB...")
    for result in tqdm(results, desc="Saving"):
        try:
            save_conversation(result, db_manager)
        except Exception as e:
            print(f"  ❌ Save failed: {e}")

    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print()

    for topic in ADVANCED_TOPICS:
        count = db_manager.db.conversation_library.count_documents(
            {"level": "advanced", "topic_slug": topic["topic_slug"]}
        )
        vocab_count = db_manager.db.conversation_vocabulary.count_documents(
            {"conversation_id": {"$regex": f"^conv_advanced_{topic['topic_slug']}"}}
        )
        status = "✅" if count >= 25 else "⚠️"
        print(f"{status} {topic['topic_en']}: {count}/25 (vocab: {vocab_count})")

    print()
    total = db_manager.db.conversation_library.count_documents({"level": "advanced"})
    print(f"✅ Total Advanced conversations: {total}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
