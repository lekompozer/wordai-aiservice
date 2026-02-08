#!/usr/bin/env python3
from src.database.db_manager import DBManager

db = DBManager().db

# Check author @sachonline
print("=== AUTHOR @sachonline ===")
author = db.authors.find_one({"author_id": "@sachonline"})
if author:
    print(f"✅ FOUND!")
    print(f"  _id: {author.get('_id')}")
    print(f"  author_id: {author.get('author_id')}")
    print(f"  name: {author.get('name')}")
    print(f"  user_id: {author.get('user_id')}")
    print(f"  total_books: {author.get('total_books')}")
else:
    print("❌ NOT FOUND")

# Check books của @sachonline
print("\n=== BOOKS BY @sachonline ===")
books = list(db.online_books.find({"authors": "@sachonline"}).limit(3))
print(f"Found {len(books)} books")
for book in books:
    print(f"  - {book.get('title')}")
    print(f"    book_id: {book.get('book_id')}")
    print(f"    user_id: {book.get('user_id')}")
    print(f"    slug: {book.get('slug')}")
    print(f"    authors: {book.get('authors')}")
    print()
