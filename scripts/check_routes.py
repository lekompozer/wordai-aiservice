#!/usr/bin/env python3
filepath = "src/api/conversation_learning_routes.py"

with open(filepath, "r") as f:
    content = f.read()

# Check status
print("📊 Endpoint Status:")
print(
    f"ENDPOINT 7 (progress): {content.count('# ENDPOINT 7: Get User Progress')} occurrences"
)
print(
    f"ENDPOINT 10 (saved): {content.count('# ENDPOINT 10: Get Saved Conversations')} occurrences"
)
print(
    f"ENDPOINT 13 (analytics/topics): {content.count('# ENDPOINT 13: Get Topic Analytics')} occurrences"
)
print(
    f"ENDPOINT 14 (analytics/overview): {content.count('# ENDPOINT 14: Get Overall Analytics')} occurrences"
)
print(
    f"ENDPOINT 15 (learning-path): {content.count('# ENDPOINT 15: Get Learning Path')} occurrences"
)

print("\n✅ Already moved:")
if "(MOVED BEFORE GENERIC ROUTE)" in content:
    import re

    moved = re.findall(r"# ENDPOINT \d+:.*\(MOVED BEFORE GENERIC ROUTE\)", content)
    for m in moved:
        print(f"  - {m}")
