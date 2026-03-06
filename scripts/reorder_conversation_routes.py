#!/usr/bin/env python3
"""
Reorder routes in conversation_learning_routes.py to fix 404 errors.
Move static routes BEFORE generic /{conversation_id} route.
"""

import re

filepath = "src/api/conversation_learning_routes.py"

# Read file
with open(filepath, "r") as f:
    content = f.read()

# Find the position of the generic route
generic_route_pattern = r'(# ={70,}\n# ENDPOINT 4: Get Conversation Detail\n# ={70,}\n\n\n@router\.get\("/{conversation_id}"\))'
match = re.search(generic_route_pattern, content)

if not match:
    print("❌ Could not find generic route /{conversation_id}")
    exit(1)

generic_start = match.start()
print(f"✅ Found generic route at position {generic_start}")

# Extract static routes that need to be moved BEFORE generic route
routes_to_move = []

# ENDPOINT 7: /progress (line ~767)
progress_pattern = r'(# ={70,}\n# ENDPOINT 7: Get User Progress\n# ={70,}\n\n\n@router\.get\("/progress"\).*?(?=\n\n# ={70,}\n# ENDPOINT))'
progress_match = re.search(progress_pattern, content, re.DOTALL)
if progress_match:
    routes_to_move.append(
        (
            "progress",
            progress_match.group(0),
            progress_match.start(),
            progress_match.end(),
        )
    )
    print(f"✅ Found /progress endpoint")

# ENDPOINT 10: /saved (line ~1005)
saved_pattern = r'(# ={70,}\n# ENDPOINT 10: Get Saved Conversations\n# ={70,}\n\n\n@router\.get\("/saved"\).*?(?=\n\n# ={70,}\n# ENDPOINT))'
saved_match = re.search(saved_pattern, content, re.DOTALL)
if saved_match:
    routes_to_move.append(
        ("saved", saved_match.group(0), saved_match.start(), saved_match.end())
    )
    print(f"✅ Found /saved endpoint")

# ENDPOINT 13: /analytics/topics (line ~1197)
topics_pattern = r'(# ={70,}\n# ENDPOINT 13: Get Topic Analytics\n# ={70,}\n\n\n@router\.get\("/analytics/topics"\).*?(?=\n\n# ={70,}\n# ENDPOINT))'
topics_match = re.search(topics_pattern, content, re.DOTALL)
if topics_match:
    routes_to_move.append(
        (
            "analytics/topics",
            topics_match.group(0),
            topics_match.start(),
            topics_match.end(),
        )
    )
    print(f"✅ Found /analytics/topics endpoint")

# ENDPOINT 14: /analytics/overview (line ~1330)
overview_pattern = r'(# ={70,}\n# ENDPOINT 14: Get Overall Analytics\n# ={70,}\n\n\n@router\.get\("/analytics/overview"\).*?(?=\n\n# ={70,}\n# ENDPOINT))'
overview_match = re.search(overview_pattern, content, re.DOTALL)
if overview_match:
    routes_to_move.append(
        (
            "analytics/overview",
            overview_match.group(0),
            overview_match.start(),
            overview_match.end(),
        )
    )
    print(f"✅ Found /analytics/overview endpoint")

# ENDPOINT 15: /learning-path (line ~1523)
learning_pattern = r'(# ={70,}\n# ENDPOINT 15: Get Learning Path Recommendation\n# ={70,}\n\n\n@router\.get\("/learning-path"\).*?$)'
learning_match = re.search(learning_pattern, content, re.DOTALL)
if learning_match:
    routes_to_move.append(
        (
            "learning-path",
            learning_match.group(0),
            learning_match.start(),
            learning_match.end(),
        )
    )
    print(f"✅ Found /learning-path endpoint")

# Sort by position (reverse order for removal)
routes_to_move.sort(key=lambda x: x[2], reverse=True)

# Remove routes from their original positions
new_content = content
for name, text, start, end in routes_to_move:
    # Remove from original position
    new_content = new_content[:start] + new_content[end:]
    print(f"📝 Removed /{name} from original position")

# Now insert all routes BEFORE the generic route
# Find generic route position again in new content
generic_match = re.search(generic_route_pattern, new_content)
if not generic_match:
    print("❌ Could not find generic route after removals")
    exit(1)

insert_pos = generic_match.start()

# Build the routes to insert (in correct order)
routes_text = (
    "\n\n".join([text for name, text, start, end in reversed(routes_to_move)]) + "\n\n"
)

# Insert before generic route
new_content = new_content[:insert_pos] + routes_text + new_content[insert_pos:]

# Write back
with open(filepath, "w") as f:
    f.write(new_content)

print(f"\n✅ Successfully reordered routes!")
print(f"   Moved {len(routes_to_move)} static routes BEFORE /{'{'}conversation_id{'}'}")
print(f"   File size: {len(content)} → {len(new_content)} chars")
print("\n📋 Route order is now:")
print("   1. /browse")
print("   2. /topics")
print("   3. /history")
print("   4. /progress ⬅️ moved")
print("   5. /saved ⬅️ moved")
print("   6. /analytics/topics ⬅️ moved")
print("   7. /analytics/overview ⬅️ moved")
print("   8. /learning-path ⬅️ moved")
print("   9. /{conversation_id} ⬅️ generic route (now AFTER static routes)")
