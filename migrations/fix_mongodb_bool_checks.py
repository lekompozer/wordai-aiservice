#!/usr/bin/env python3
"""
Fix MongoDB Database bool() checks in user_manager.py

Error: Database objects do not implement truth value testing
Fix: Replace 'if self.db and self.db.client:' with 'if self.db is not None and self.db.client is not None:'
"""

file_path = "src/services/user_manager.py"

# Read file
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Count occurrences
old_pattern = "if self.db and self.db.client:"
new_pattern = "if self.db is not None and self.db.client is not None:"

count = content.count(old_pattern)
print(f"Found {count} occurrences of '{old_pattern}'")

# Replace all
new_content = content.replace(old_pattern, new_pattern)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"✅ Fixed {count} occurrences in {file_path}")
print(f"Changed: {old_pattern}")
print(f"To:      {new_pattern}")
