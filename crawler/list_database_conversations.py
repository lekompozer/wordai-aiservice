"""
Liệt kê TẤT CẢ conversations trong database - không so sánh
Chỉ show những gì đang có thật trong DB
"""

import sys

sys.path.append("/app")

from src.database.db_manager import DBManager


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("DATABASE CONVERSATION LIBRARY - CURRENT STATE")
    print("=" * 80)

    report = []
    report.append("=" * 80)
    report.append("DATABASE CONVERSATION LIBRARY - CURRENT STATE")
    report.append("=" * 80)
    report.append("")

    # Get total stats
    total = db.conversation_library.count_documents({})
    with_audio = db.conversation_library.count_documents(
        {"audio_url": {"$exists": True, "$ne": None}}
    )
    without_audio = total - with_audio

    stats = f"📊 TOTAL: {total} conversations | 🎵 With audio: {with_audio} | 🔇 Without audio: {without_audio}"
    print(stats)
    report.append(stats)
    report.append("")

    # List all topics that exist in database
    topics_in_db = db.conversation_library.distinct("topic_number")
    topics_in_db.sort()

    print(f"📁 Topics found in database: {len(topics_in_db)}")
    print(f"   Topic numbers: {topics_in_db}")
    print("")

    report.append(f"📁 Topics found in database: {len(topics_in_db)}")
    report.append(f"   Topic numbers: {topics_in_db}")
    report.append("")

    # Process each topic
    for topic_num in range(1, 31):
        # Get all conversations for this topic
        convs = list(
            db.conversation_library.find({"topic_number": topic_num}).sort(
                "conversation_id", 1
            )
        )

        if not convs:
            # Skip empty topics
            continue

        # Get topic info from first conversation
        first_conv = convs[0]
        topic_slug = first_conv.get("topic_slug", "N/A")

        print(f"\n{'='*80}")
        print(f"TOPIC {topic_num}: {topic_slug.upper()}")
        print(f"{'='*80}")
        print(f"Total: {len(convs)} conversations")

        report.append(f"\n{'='*80}")
        report.append(f"TOPIC {topic_num}: {topic_slug.upper()}")
        report.append(f"{'='*80}")
        report.append(f"Total: {len(convs)} conversations")

        # Count audio
        topic_with_audio = sum(1 for c in convs if c.get("audio_url"))
        topic_without_audio = len(convs) - topic_with_audio

        audio_stats = f"🎵 With audio: {topic_with_audio} | 🔇 Without audio: {topic_without_audio}"
        print(audio_stats)
        report.append(audio_stats)
        report.append("")

        # List each conversation
        for i, conv in enumerate(convs, 1):
            # Extract index from ID
            parts = conv["conversation_id"].split("_")
            conv_index = parts[-1]  # Last part is index

            title_en = conv["title"]["en"]
            title_vi = conv["title"]["vi"]
            has_audio = "🎵" if conv.get("audio_url") else "🔇"

            line = f"  [{i:2d}] {conv_index} | {has_audio} | {title_en}"
            print(line)
            report.append(line)

            # Vietnamese title on next line
            vi_line = f"       └─ {title_vi}"
            print(vi_line)
            report.append(vi_line)

        report.append("")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY BY TOPIC")
    print("=" * 80)

    report.append("\n" + "=" * 80)
    report.append("SUMMARY BY TOPIC")
    report.append("=" * 80)

    for topic_num in range(1, 31):
        count = db.conversation_library.count_documents({"topic_number": topic_num})
        if count > 0:
            convs = list(db.conversation_library.find({"topic_number": topic_num}))
            with_audio = sum(1 for c in convs if c.get("audio_url"))
            slug = convs[0].get("topic_slug", "N/A") if convs else "N/A"

            summary_line = f"  Topic {topic_num:2d} ({slug:30s}): {count:3d} convs | 🎵 {with_audio:3d} | 🔇 {count-with_audio:3d}"
            print(summary_line)
            report.append(summary_line)

    # Write report
    report_path = "/tmp/database_conversations_list.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n✅ Report saved to: {report_path}")


if __name__ == "__main__":
    main()
