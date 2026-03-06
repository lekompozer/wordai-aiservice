"""
Create MongoDB indexes for user_saved_vocabulary and user_saved_grammar collections.

Run once in production:
    docker cp create_saved_vocab_grammar_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_saved_vocab_grammar_indexes.py
"""

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

# ── user_saved_vocabulary ────────────────────────────────────────────────────
print("Creating indexes for user_saved_vocabulary...")

db["user_saved_vocabulary"].create_index(
    [("user_id", 1), ("saved_at", -1)],
    name="user_saved_at",
)
db["user_saved_vocabulary"].create_index(
    [("user_id", 1), ("word", 1)],
    unique=True,
    name="user_word_unique",
)
db["user_saved_vocabulary"].create_index(
    [("user_id", 1), ("topic_slug", 1)],
    name="user_topic_slug",
)
db["user_saved_vocabulary"].create_index(
    [("user_id", 1), ("next_review_date", 1)],
    name="user_next_review_date",
)
db["user_saved_vocabulary"].create_index(
    [("user_id", 1), ("level", 1)],
    name="user_level",
)

print("  ✓ user_saved_vocabulary indexes created")

# ── user_saved_grammar ───────────────────────────────────────────────────────
print("Creating indexes for user_saved_grammar...")

db["user_saved_grammar"].create_index(
    [("user_id", 1), ("saved_at", -1)],
    name="user_saved_at",
)
db["user_saved_grammar"].create_index(
    [("user_id", 1), ("pattern", 1)],
    unique=True,
    name="user_pattern_unique",
)
db["user_saved_grammar"].create_index(
    [("user_id", 1), ("topic_slug", 1)],
    name="user_topic_slug",
)
db["user_saved_grammar"].create_index(
    [("user_id", 1), ("next_review_date", 1)],
    name="user_next_review_date",
)
db["user_saved_grammar"].create_index(
    [("user_id", 1), ("level", 1)],
    name="user_level",
)

print("  ✓ user_saved_grammar indexes created")
print("\nDone! All indexes created successfully.")
