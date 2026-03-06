#!/usr/bin/env python3
from src.database.db_manager import DBManager

db = DBManager().db

# Check author @sachonline với author_id
print("=== SEARCH BY author_id ===")
author = db.authors.find_one({"author_id": "@sachonline"})
if author:
    print(f"✅ FOUND!")
    for key in sorted(author.keys()):
        print(f"  {key}: {author[key]}")
else:
    print("❌ NOT FOUND by author_id")

# Check tất cả authors
print("\n=== ALL AUTHORS ===")
authors = list(
    db.authors.find({}, {"author_id": 1, "name": 1, "user_id": 1, "_id": 1}).limit(10)
)
for a in authors:
    print(
        f"  {a.get('author_id')} | {a.get('name')} | user_id={a.get('user_id')} | _id={a.get('_id')}"
    )

# Check schema của 1 book thành công (book đầu tiên crawl được)
print("\n=== BOOK CREATED BY CRAWLER ===")
book = db.online_books.find_one({"source": "nhasachmienphi.com"})
if book:
    print("✅ Found crawled book:")
    print(f"  _id: {book.get('_id')}")
    print(f"  title: {book.get('title')}")
    print(f"  slug: {book.get('slug')}")
    print(f"  user_id: {book.get('user_id')}")
    print(f"  author_id: {book.get('author_id')}")
    print(f"  authors: {book.get('authors')}")
else:
    print("❌ No crawled books found")
