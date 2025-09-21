#!/usr/bin/env python3
import re

# New nginx pattern - more explicit matching
new_pattern = r"^/api/(auth|quote|chat/(?!stream)|admin|health|docs|redoc)"

test_paths = [
    "/api/quote-settings/",  # Should MATCH
    "/api/quotes/history",   # Should MATCH
    "/api/auth/profile",     # Should MATCH
    "/api/chat/providers",   # Should MATCH
    "/api/chat/stream",      # Should NOT MATCH
    "/api/unified/chat-stream", # Should NOT MATCH
    "/api/admin/companies",  # Should MATCH
]

print("Testing NEW nginx regex pattern:", new_pattern)
print("=" * 60)
for path in test_paths:
    match = re.match(new_pattern, path)
    status = "✅ MATCHES" if match else "❌ NO MATCH"
    print(f"{path:<25} -> {status}")
    if match:
        print(f"  Matched: '{match.group()}'")
