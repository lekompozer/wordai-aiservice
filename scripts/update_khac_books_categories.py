"""
Update categories for books classified from "Khác" category
"""

import json
from src.database.db_manager import DBManager
from bson import ObjectId


def main():
    # Load classified books
    with open("khac_books_classified.json", "r", encoding="utf-8") as f:
        books = json.load(f)

    print(f"Total books to update: {len(books)}")

    # Connect to database
    db_manager = DBManager()
    db = db_manager.db

    # Count by category
    category_counts = {}
    updated_count = 0
    error_count = 0

    for book in books:
        # Handle both ObjectId formats
        if isinstance(book["_id"], dict):
            book_id = ObjectId(book["_id"]["$oid"])
        else:
            book_id = ObjectId(book["_id"])

        new_category = book["new_category"]
        new_parent = book["new_parent"]

        # Count
        key = f"{new_parent} > {new_category}"
        category_counts[key] = category_counts.get(key, 0) + 1

        # Update
        try:
            result = db.online_books.update_one(
                {"_id": book_id},
                {
                    "$set": {
                        "community_config.category": new_category,
                        "community_config.parent_category": new_parent,
                    }
                },
            )
            if result.modified_count > 0:
                updated_count += 1
        except Exception as e:
            print(f"Error updating {book['title']}: {e}")
            error_count += 1

    # Print summary
    print(f"\n=== UPDATE SUMMARY ===")
    print(f"Successfully updated: {updated_count} books")
    print(f"Errors: {error_count}")

    print(f"\n=== CATEGORY DISTRIBUTION ===")
    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {category:50} : {count:4} books")


if __name__ == "__main__":
    main()
