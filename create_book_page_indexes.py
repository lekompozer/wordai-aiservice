"""
Create indexes for book_page_texts and book_page_audio collections.

book_page_texts  — per-page text + image data crawled from LetsRead
book_page_audio  — generated TTS audio per book × voice

Run once on a new server:
    python create_book_page_indexes.py

Production (via Docker exec):
    docker cp create_book_page_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_book_page_indexes.py
"""

from src.database.db_manager import DBManager


def create_book_page_indexes():
    db_manager = DBManager()
    db = db_manager.db

    # ------------------------------------------------------------------ #
    # book_page_texts
    # ------------------------------------------------------------------ #
    col_texts = db["book_page_texts"]
    print("Creating indexes for book_page_texts collection...")

    # Unique per book + page_number (primary lookup key)
    print("1. Unique compound index (book_id, page_number)...")
    col_texts.create_index(
        [("book_id", 1), ("page_number", 1)],
        unique=True,
        name="book_id_page_number_unique",
    )

    # Lookup by letsread native UUID (for crawler re-runs)
    print("2. Index on letsread_book_id...")
    col_texts.create_index("letsread_book_id", name="letsread_book_id_idx")

    # Lookup by language (for multi-language support later)
    print("3. Index on language...")
    col_texts.create_index("language", name="language_idx")

    # Sort pages within a book by page_number
    print("4. Compound index (book_id, page_number ASC) for ordered reads...")
    col_texts.create_index(
        [("book_id", 1), ("page_number", 1)],
        name="book_id_page_ordered",
    )  # duplicates the unique index — MongoDB will reuse it

    print("✅ book_page_texts indexes created")

    # ------------------------------------------------------------------ #
    # book_page_audio
    # ------------------------------------------------------------------ #
    col_audio = db["book_page_audio"]
    print("\nCreating indexes for book_page_audio collection...")

    # Unique per book × voice × version
    print("1. Unique compound index (book_id, voice_name, version)...")
    col_audio.create_index(
        [("book_id", 1), ("voice_name", 1), ("version", 1)],
        unique=True,
        name="book_id_voice_version_unique",
    )

    # Latest version per book × voice
    print("2. Compound index (book_id, voice_name, version DESC)...")
    col_audio.create_index(
        [("book_id", 1), ("voice_name", 1), ("version", -1)],
        name="book_id_voice_version_desc",
    )

    # Status filtering (for queuing / validation)
    print("3. Index on status...")
    col_audio.create_index("status", name="status_idx")

    # Sort by creation time (for admin listing)
    print("4. Index on created_at DESC...")
    col_audio.create_index([("created_at", -1)], name="created_at_desc")

    print("✅ book_page_audio indexes created")

    # ------------------------------------------------------------------ #
    # Print summary
    # ------------------------------------------------------------------ #
    print("\n--- book_page_texts indexes ---")
    for idx in col_texts.list_indexes():
        print(f"  {idx['name']}: {idx['key']}")

    print("\n--- book_page_audio indexes ---")
    for idx in col_audio.list_indexes():
        print(f"  {idx['name']}: {idx['key']}")

    print("\n✅ All indexes created successfully!")


if __name__ == "__main__":
    create_book_page_indexes()
