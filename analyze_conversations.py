"""
Analyze conversation distribution by level and topic
"""

from src.database.db_manager import DBManager
from collections import defaultdict

db_manager = DBManager()
db = db_manager.db

# Get all conversations
conversations = list(
    db.conversation_library.find(
        {}, {"level": 1, "topic_number": 1, "topic": 1, "_id": 0}
    )
)

# Count by level and topic
by_level = defaultdict(int)
by_topic = defaultdict(lambda: {"count": 0, "name": "", "by_level": defaultdict(int)})

for conv in conversations:
    level = conv["level"]
    topic_num = conv["topic_number"]
    topic_name = conv["topic"]["en"]

    by_level[level] += 1
    by_topic[topic_num]["count"] += 1
    by_topic[topic_num]["name"] = topic_name
    by_topic[topic_num]["by_level"][level] += 1

# Print summary
print("=" * 80)
print("CONVERSATION DISTRIBUTION ANALYSIS")
print("=" * 80)
print()

print("BY LEVEL:")
print("-" * 80)
for level in ["beginner", "intermediate", "advanced"]:
    count = by_level[level]
    print(f"{level.capitalize():15} {count:4} conversations")
print(f"{'TOTAL':15} {sum(by_level.values()):4} conversations")
print()

print("BY TOPIC:")
print("-" * 80)
print(f"{'#':<4} {'Topic Name':<40} {'Total':<8} {'B':<6} {'I':<6} {'A':<6}")
print("-" * 80)

for topic_num in sorted(by_topic.keys()):
    info = by_topic[topic_num]
    print(
        f"{topic_num:<4} {info['name']:<40} {info['count']:<8} "
        f"{info['by_level']['beginner']:<6} "
        f"{info['by_level']['intermediate']:<6} "
        f"{info['by_level']['advanced']:<6}"
    )

print()
print("Legend: B=Beginner, I=Intermediate, A=Advanced")
print("=" * 80)
