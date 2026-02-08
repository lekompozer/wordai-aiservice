#!/usr/bin/env python3
from src.database.db_manager import DBManager

db = DBManager().db

print("=== BOOKS BY @sachonline ===\n")

# Check tất cả books có authors = @sachonline
books = list(db.online_books.find({"authors": "@sachonline"}))
print(f"Total: {len(books)} books\n")

for book in books:
    print(f"📖 {book.get('title')}")
    print(f"   book_id: {book.get('book_id')}")
    print(f"   user_id: {book.get('user_id')}")
    print(f"   slug: {book.get('slug')}")
    print(f"   authors: {book.get('authors')}")
    print(f"   visibility: {book.get('visibility')}")
    print(f"   is_published: {book.get('is_published')}")
    print(f"   is_deleted: {book.get('is_deleted')}")

    # Check community_config
    cc = book.get("community_config", {})
    print(f"   community_config.is_public: {cc.get('is_public')}")
    print()

# Check author @sachonline stats
author = db.authors.find_one({"author_id": "@sachonline"})
if author:
    print("\n=== AUTHOR @sachonline ===")
    print(f"total_books: {author.get('total_books')}")
    print(f"books array: {author.get('books', [])}")
