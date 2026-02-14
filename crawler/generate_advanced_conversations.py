#!/usr/bin/env python3
"""
Generate Additional Advanced Conversations to reach 25 per topic

Current Status:
- Business & Entrepreneurship: 3/25 → need 22 more
- Law & Justice: 12/25 → need 13 more
- Science & Research: 6/25 → need 19 more
- Medicine & Healthcare: 9/25 → need 16 more

Total: 70 conversations to generate

Features:
- Parallel API calls to DeepSeek for speed
- Generate vocabulary + grammar in single call
- 12-16 dialogue turns for advanced level
- Auto-save to MongoDB

RUN:
    docker exec ai-chatbot-rag python crawler/generate_advanced_conversations.py
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, List
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")

# Advanced topics that need more conversations
ADVANCED_TOPICS = [
    {
        "topic_en": "Business & Entrepreneurship",
        "topic_vi": "Kinh doanh & Khởi nghiệp",
        "topic_slug": "business_entrepreneurship",
        "topic_number": 21,
        "current_count": 3,
        "target_count": 25,
    },
    {
        "topic_en": "Law & Justice",
        "topic_vi": "Luật pháp & Công lý",
        "topic_slug": "law_justice",
        "topic_number": 22,
        "current_count": 12,
        "target_count": 25,
    },
    {
        "topic_en": "Science & Research",
        "topic_vi": "Khoa học & Nghiên cứu",
        "topic_slug": "science_research",
        "topic_number": 23,
        "current_count": 6,
        "target_count": 25,
    },
    {
        "topic_en": "Medicine & Healthcare",
        "topic_vi": "Y học & Chăm sóc sức khỏe",
        "topic_slug": "medicine_healthcare",
        "topic_number": 24,
        "current_count": 9,
        "target_count": 25,
    },
]

# Conversation titles for each topic (25 titles per topic)
CONVERSATION_TITLES = {
    "Business & Entrepreneurship": [
        "Starting Your Own Business",
        "Writing a Business Plan",
        "Finding Investors and Funding",
        "Marketing Strategies for Startups",
        "Managing Business Finances",
        "Hiring Your First Employees",
        "Scaling Your Business",
        "Dealing with Competition",
        "Business Partnerships and Contracts",
        "Corporate Social Responsibility",
        "Franchising Your Business",
        "International Business Expansion",
        "Mergers and Acquisitions",
        "Business Ethics and Compliance",
        "Crisis Management in Business",
        "Innovation and Product Development",
        "E-commerce and Online Business",
        "Supply Chain Management",
        "Business Networking Strategies",
        "Exit Strategies for Entrepreneurs",
        "Venture Capital and Private Equity",
        "Building a Strong Brand Identity",
        "Customer Retention Strategies",
        "Business Analytics and Data-Driven Decisions",
        "Sustainable Business Practices",
    ],
    "Law & Justice": [
        "Understanding Constitutional Law",
        "Criminal Law Fundamentals",
        "Civil Rights and Liberties",
        "Contract Law Basics",
        "Intellectual Property Rights",
        "Family Law and Divorce Proceedings",
        "Employment Law and Workers' Rights",
        "Environmental Law and Regulations",
        "International Law and Treaties",
        "Cyber Law and Digital Privacy",
        "Corporate Law and Governance",
        "Tax Law and Compliance",
        "Immigration Law and Policies",
        "Human Rights Law",
        "Legal Ethics and Professional Responsibility",
        "Alternative Dispute Resolution",
        "Tort Law and Personal Injury",
        "Property Law and Real Estate",
        "Criminal Justice System Reform",
        "Legal Research and Writing",
        "Courtroom Procedures and Litigation",
        "Juvenile Justice System",
        "Antitrust and Competition Law",
        "Securities and Financial Regulation",
        "Legal Technology and Innovation",
    ],
    "Science & Research": [
        "The Scientific Method",
        "Conducting Literature Reviews",
        "Designing Research Experiments",
        "Data Collection and Analysis",
        "Peer Review and Publication",
        "Research Ethics and Integrity",
        "Quantum Physics Fundamentals",
        "Climate Change Research",
        "Biotechnology and Genetic Engineering",
        "Artificial Intelligence Research",
        "Space Exploration and Astronomy",
        "Neuroscience and Brain Research",
        "Renewable Energy Technologies",
        "Nanotechnology Applications",
        "Vaccine Development and Immunology",
        "Marine Biology and Ocean Research",
        "Particle Physics and CERN",
        "Cancer Research and Treatments",
        "Archaeological Discoveries",
        "Materials Science Innovations",
        "Robotics and Automation",
        "Stem Cell Research",
        "Epidemiology and Disease Prevention",
        "Nuclear Energy and Safety",
        "Research Funding and Grants",
    ],
    "Medicine & Healthcare": [
        "Medical School and Training",
        "Diagnosis and Treatment Planning",
        "Patient Care and Communication",
        "Medical Ethics and Decision Making",
        "Emergency Medicine Procedures",
        "Surgical Techniques and Innovations",
        "Pharmacology and Drug Development",
        "Mental Health and Psychiatry",
        "Pediatric Medicine",
        "Geriatric Care and Aging",
        "Infectious Disease Management",
        "Chronic Disease Treatment",
        "Preventive Medicine and Wellness",
        "Medical Imaging and Diagnostics",
        "Telemedicine and Digital Health",
        "Hospital Administration",
        "Medical Research and Clinical Trials",
        "Organ Transplantation",
        "Palliative Care and End-of-Life",
        "Public Health Policy",
        "Global Health Challenges",
        "Medical Malpractice and Liability",
        "Healthcare Quality and Safety",
        "Precision Medicine and Genomics",
        "Healthcare Economics and Insurance",
    ],
}


def build_conversation_prompt(topic_info: Dict, title_en: str, index: int) -> str:
    """Build prompt for generating one conversation with vocab + grammar"""

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

        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=6000,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response")

                # Clean markdown
                if content.startswith("```"):
                    lines = content.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines)

                data = json.loads(content)

                # Validate structure
                if not all(
                    k in data for k in ["dialogue", "vocabulary", "grammar_points"]
                ):
                    raise ValueError("Missing required fields")

                return {
                    "topic_info": topic_info,
                    "title_en": title_en,
                    "index": index,
                    "data": data,
                }

            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2)
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
    print("🎓 GENERATE ADVANCED CONVERSATIONS (Fill to 25 per topic)")
    print("=" * 80)
    print()

    # Database
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    print(f"✅ Connected: {db_manager.db.name}")
    print()

    # Check current counts
    print("📊 Current status:")
    for topic in ADVANCED_TOPICS:
        current = db_manager.db.conversation_library.count_documents(
            {"level": "advanced", "topic_slug": topic["topic_slug"]}
        )
        needed = topic["target_count"] - current
        print(
            f"  • {topic['topic_en']}: {current}/{topic['target_count']} (need {needed} more)"
        )
    print()

    # Build task list
    tasks = []
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    semaphore = asyncio.Semaphore(10)  # Max 10 parallel requests

    for topic in ADVANCED_TOPICS:
        current_count = db_manager.db.conversation_library.count_documents(
            {"level": "advanced", "topic_slug": topic["topic_slug"]}
        )

        titles = CONVERSATION_TITLES[topic["topic_en"]]
        needed = topic["target_count"] - current_count

        for i in range(needed):
            index = current_count + i + 1
            title = (
                titles[index - 1]
                if index - 1 < len(titles)
                else f"Conversation {index}"
            )

            tasks.append(generate_conversation(client, topic, title, index, semaphore))

    print(f"🚀 Generating {len(tasks)} conversations in parallel...")
    print()

    # Execute with progress bar
    success_count = 0
    failed_count = 0
    failed_tasks = []

    results = []
    for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Progress"):
        try:
            result = await coro
            results.append(result)
            success_count += 1
        except Exception as e:
            failed_count += 1
            failed_tasks.append(str(e))

    print()
    print(f"✅ Generated: {success_count}/{len(tasks)}")
    print()

    # Save to database
    print("💾 Saving to MongoDB...")
    saved_count = 0
    for result in tqdm(results, desc="Saving"):
        try:
            conv_id = save_conversation(result, db_manager)
            saved_count += 1
        except Exception as e:
            print(f"  ❌ Save failed: {e}")

    print()

    # Final summary
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print()

    for topic in ADVANCED_TOPICS:
        final_count = db_manager.db.conversation_library.count_documents(
            {"level": "advanced", "topic_slug": topic["topic_slug"]}
        )
        vocab_count = db_manager.db.conversation_vocabulary.count_documents(
            {"conversation_id": {"$regex": f"^conv_advanced_{topic['topic_slug']}"}}
        )
        status = "✅" if final_count >= topic["target_count"] else "⚠️"
        print(f"{status} {topic['topic_en']}:")
        print(f"   Conversations: {final_count}/{topic['target_count']}")
        print(f"   Vocabulary docs: {vocab_count}")
        print()

    print(
        f"✅ Total conversations in DB: {db_manager.db.conversation_library.count_documents({'level': 'advanced'})}"
    )
    print(
        f"✅ Total vocabulary docs: {db_manager.db.conversation_vocabulary.count_documents({})}"
    )
    print()

    if failed_count > 0:
        print(f"⚠️  Failed: {failed_count} conversations")
        print("Failed tasks:")
        for i, err in enumerate(failed_tasks[:5], 1):
            print(f"  {i}. {err}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
