#!/usr/bin/env python3
"""
Create unique index for test_ratings collection
Ensures one user can only have one rating per test
"""

import os
from pymongo import MongoClient, ASCENDING

# MongoDB connection
MONGO_URI = os.getenv(
    "MONGO_URI", "mongodb://admin:wordai@localhost:27017/wordai?authSource=admin"
)

client = MongoClient(MONGO_URI)
db = client["wordai"]

# Create unique compound index on test_ratings collection
# This ensures one user can only have ONE rating per test
print("Creating unique index on test_ratings collection...")

result = db.test_ratings.create_index(
    [("test_id", ASCENDING), ("user_id", ASCENDING)],
    unique=True,
    name="unique_test_user_rating",
)

print(f"✅ Index created: {result}")
print("   This ensures one user can only rate each test once")

# List all indexes to verify
print("\nAll indexes on test_ratings:")
for index in db.test_ratings.list_indexes():
    print(f"   - {index['name']}: {index.get('key', {})}")

print("\n✅ Setup complete!")
print("Now even if application logic fails, MongoDB will prevent duplicate ratings")
