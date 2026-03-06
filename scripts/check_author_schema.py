#!/usr/bin/env python3
from src.database.db_manager import DBManager

db = DBManager().db

# Check author @sachonline
author = db.authors.find_one({"username": "sachonline"})
print("=== AUTHOR @sachonline ===")
if author:
    print(f"_id: {author.get('_id')}")
    print(f"username: {author.get('username')}")
    print(f"user_id: {author.get('user_id')}")
    print(f"display_name: {author.get('display_name')}")
else:
    print("NOT FOUND")

# Check 1 online_books document
print("\n=== ONLINE_BOOKS SCHEMA (sample) ===")
book = db.online_books.find_one()
if book:
    for key in sorted(book.keys()):
        val = book[key]
        if isinstance(val, dict):
            print(f"{key}: dict with keys {list(val.keys())[:5]}")
        elif isinstance(val, list):
            print(f"{key}: list (len={len(val)})")
        else:
            print(f"{key}: {type(val).__name__} = {val}")
else:
    print("No books found")
