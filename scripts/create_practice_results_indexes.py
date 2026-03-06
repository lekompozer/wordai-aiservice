"""
Create MongoDB indexes for user_practice_results collection.

Run once in production:
    docker cp create_practice_results_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_practice_results_indexes.py
"""

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

print("Creating indexes for user_practice_results...")

db["user_practice_results"].create_index(
    [("user_id", 1), ("completed_at", -1)],
    name="user_completed_at",
)
db["user_practice_results"].create_index(
    [("user_id", 1), ("practice_type", 1)],
    name="user_practice_type",
)
db["user_practice_results"].create_index(
    [("user_id", 1), ("conversation_id", 1)],
    name="user_conversation",
)

print("  ✓ user_practice_results indexes created")

# Also ensure ai_checks fields are indexed on user_learning_xp
print("Ensuring user_learning_xp ai_checks index...")
db["user_learning_xp"].create_index(
    [("user_id", 1)],
    unique=True,
    name="user_id_unique",
)
print("  ✓ user_learning_xp index ensured")

print("\nDone! All indexes created successfully.")
