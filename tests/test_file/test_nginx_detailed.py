#!/usr/bin/env python3
import re

# Current nginx pattern with case-sensitive match
nginx_pattern = r"^/api/(?!unified/|chat/stream)"

# Test what nginx actually uses (case insensitive with ~* modifier)
test_paths = [
    "/api/quote-settings/",
    "/api/chat/stream",
    "/api/unified/chat-stream"
]

print("=== NGINX REGEX ANALYSIS ===")
print(f"Pattern: {nginx_pattern}")
print("Note: nginx uses ~* (case insensitive) but Python re.match is case sensitive")
print()

for path in test_paths:
    match = re.match(nginx_pattern, path)
    print(f"Path: {path}")
    print(f"  Matches: {bool(match)}")
    if match:
        print(f"  Matched part: '{match.group()}'")
        print(f"  Full match groups: {match.groups()}")
    print()

# Test negative lookahead specifically
print("=== NEGATIVE LOOKAHEAD TEST ===")
test_pattern = r"(?!unified/|chat/stream)"
test_strings = ["quote-settings/", "unified/", "chat/stream", "auth/profile"]

for s in test_strings:
    match = re.match(test_pattern, s)
    print(f"'{s}' -> {'PASSES' if match else 'BLOCKED'} negative lookahead")
