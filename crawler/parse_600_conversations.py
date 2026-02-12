"""
Parse 600 Conversations from Topic Conversation File

Reads the structured file and extracts all 30 topics × 20 conversations = 600 items
Maps each conversation to correct level (beginner/intermediate/advanced)
"""

import re
from typing import List, Dict
from src.models.conversation_models import ConversationLevel


def parse_topic_conversation_file(file_path: str) -> List[Dict]:
    """
    Parse the Topic Conversation file
    Returns list of 600 conversation definitions
    """

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    conversations = []

    # Split by sections
    sections = [
        {
            "header": "📘 PHẦN 1: CƠ BẢN",
            "level": ConversationLevel.BEGINNER,
            "topic_range": (1, 10),
        },
        {
            "header": "📗 PHẦN 2: TRUNG CẤP",
            "level": ConversationLevel.INTERMEDIATE,
            "topic_range": (11, 20),
        },
        {
            "header": "📙 PHẦN 3: NÂNG CAO",
            "level": ConversationLevel.ADVANCED,
            "topic_range": (21, 30),
        },
    ]

    for section in sections:
        # Find section content
        start_idx = content.find(section["header"])
        if start_idx == -1:
            continue

        # Find end of section (next section header or end of file)
        next_section_idx = len(content)
        for other_section in sections:
            if other_section == section:
                continue
            other_idx = content.find(other_section["header"], start_idx + 1)
            if other_idx != -1 and other_idx < next_section_idx:
                next_section_idx = other_idx

        section_content = content[start_idx:next_section_idx]

        # Parse topics in this section
        parse_section_topics(
            section_content, section["level"], section["topic_range"], conversations
        )

    return conversations


def parse_section_topics(
    section_content: str,
    level: ConversationLevel,
    topic_range: tuple,
    conversations: List[Dict],
):
    """Parse all topics in a section"""

    lines = section_content.split("\n")

    current_topic = None
    current_topic_number = None
    current_topic_slug = None
    current_topic_en = None
    current_topic_vi = None
    conversation_index = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Check if this is a topic header line (format: "1\tGreetings & Introductions\t1. Hello, How Are You?")
        # OR (format: "#\tTopic Name\t20 Conversations Name")
        if "\t" in line:
            parts = line.split("\t")

            # Check if first part is a number (topic number)
            if len(parts) >= 2 and parts[0].strip().isdigit():
                topic_num = int(parts[0].strip())

                # Verify it's in the expected range
                if topic_range[0] <= topic_num <= topic_range[1]:
                    current_topic_number = topic_num
                    current_topic_en = parts[1].strip()
                    current_topic_slug = create_slug(current_topic_en)
                    current_topic_vi = get_vietnamese_topic_name(current_topic_en)
                    conversation_index = 0

                    # Check if there's a first conversation in this line
                    if len(parts) >= 3:
                        conv_text = parts[2].strip()
                        if conv_text and not conv_text.startswith("20 Conversations"):
                            # Parse this conversation
                            conv_en, conv_vi = parse_conversation_line(conv_text)
                            if conv_en:
                                conversation_index += 1
                                conversations.append(
                                    {
                                        "level": level,
                                        "topic_number": current_topic_number,
                                        "topic_slug": current_topic_slug,
                                        "topic_en": current_topic_en,
                                        "topic_vi": current_topic_vi,
                                        "conversation_index": conversation_index,
                                        "title_en": conv_en,
                                        "title_vi": conv_vi,
                                    }
                                )

        # Check if line is a numbered conversation (format: "1. Hello, How Are You?")
        elif current_topic_number is not None:
            conv_en, conv_vi = parse_conversation_line(line)
            if conv_en:
                conversation_index += 1
                conversations.append(
                    {
                        "level": level,
                        "topic_number": current_topic_number,
                        "topic_slug": current_topic_slug,
                        "topic_en": current_topic_en,
                        "topic_vi": current_topic_vi,
                        "conversation_index": conversation_index,
                        "title_en": conv_en,
                        "title_vi": conv_vi,
                    }
                )

        i += 1


def parse_conversation_line(line: str) -> tuple:
    """
    Parse a conversation line
    Returns (english_title, vietnamese_title) or (None, None)
    """

    # Remove numbering (e.g., "1. ", "20. ")
    match = re.match(r"^\d+\.\s+(.+)$", line)
    if not match:
        return None, None

    title_en = match.group(1).strip()

    # Generate Vietnamese title (simplified - you can enhance this)
    title_vi = translate_to_vietnamese(title_en)

    return title_en, title_vi


def create_slug(topic_name: str) -> str:
    """Create URL-friendly slug from topic name"""
    slug = topic_name.lower()
    slug = re.sub(r"[&\s]+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug


def get_vietnamese_topic_name(topic_en: str) -> str:
    """Map English topic names to Vietnamese"""

    mapping = {
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

    return mapping.get(topic_en, topic_en)


def translate_to_vietnamese(title_en: str) -> str:
    """
    Simple translation mapping for common conversation titles
    This is a basic version - you can enhance with more mappings
    """

    # Common translations
    translations = {
        "Hello, How Are You?": "Xin chào, Bạn khỏe không?",
        "Nice to Meet You": "Rất vui được gặp bạn",
        "Job Interview": "Phỏng vấn xin việc",
        "Pitching an Idea": "Trình bày ý tưởng",
        # Add more as needed...
    }

    # Return translation if exists, otherwise return English title
    # (The AI will translate when generating)
    return translations.get(title_en, title_en)


if __name__ == "__main__":
    # Test parser
    import os
    import sys

    file_path = "docs/wordai/Learn English With Songs/Topic Conversation"

    if os.path.exists(file_path):
        conversations = parse_topic_conversation_file(file_path)

        print(f"Total conversations parsed: {len(conversations)}")
        print()

        # Show sample
        print("Sample conversations:")
        for i, conv in enumerate(conversations[:5], 1):
            print(f"{i}. Topic #{conv['topic_number']}: {conv['topic_en']}")
            print(f"   Conversation #{conv['conversation_index']}: {conv['title_en']}")
            print(f"   Level: {conv['level'].value}")
            print()

        # Count by level
        beginner = sum(
            1 for c in conversations if c["level"] == ConversationLevel.BEGINNER
        )
        intermediate = sum(
            1 for c in conversations if c["level"] == ConversationLevel.INTERMEDIATE
        )
        advanced = sum(
            1 for c in conversations if c["level"] == ConversationLevel.ADVANCED
        )

        print(f"By level:")
        print(f"  Beginner: {beginner}")
        print(f"  Intermediate: {intermediate}")
        print(f"  Advanced: {advanced}")
        print(f"  Total: {beginner + intermediate + advanced}")
    else:
        print(f"File not found: {file_path}")
