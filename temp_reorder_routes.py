#!/usr/bin/env python3
"""
Script to reorder routes in conversation_learning_routes.py
Move static routes BEFORE generic /{conversation_id} route
"""

filepath = "src/api/conversation_learning_routes.py"

with open(filepath, "r") as f:
    lines = f.readlines()

# Find line numbers
endpoints_to_move_after_generic = []
generic_route_line = None
endpoints_already_moved = []

for i, line in enumerate(lines):
    # Find generic route
    if '@router.get("/{conversation_id}")' in line:
        if generic_route_line is None:
            generic_route_line = i

    # Find endpoints already moved (with "MOVED BEFORE GENERIC ROUTE" comment)
    if "MOVED BEFORE GENERIC ROUTE" in line:
        endpoints_already_moved.append(i)

    # Find original endpoints that need to be removed
    if (
        line.strip().startswith("# ENDPOINT 7: Get User Progress")
        and "(MOVED" not in line
    ):
        endpoints_to_move_after_generic.append(("ENDPOINT 7", i))

    if (
        line.strip().startswith("# ENDPOINT 10: Get Saved Conversations")
        and "(MOVED" not in line
    ):
        endpoints_to_move_after_generic.append(("ENDPOINT 10", i))

    if (
        line.strip().startswith("# ENDPOINT 13: Get Topic Analytics")
        and "(MOVED" not in line
    ):
        endpoints_to_move_after_generic.append(("ENDPOINT 13", i))

    if (
        line.strip().startswith("# ENDPOINT 14: Get Overall Analytics")
        and "(MOVED" not in line
    ):
        endpoints_to_move_after_generic.append(("ENDPOINT 14", i))

    if (
        line.strip().startswith("# ENDPOINT 15: Get Learning Path")
        and "(MOVED" not in line
    ):
        endpoints_to_move_after_generic.append(("ENDPOINT 15", i))

print(f"Generic route /{conversation_id} encontered at line {generic_route_line}")
print(f"Already moved endpoints: {len(endpoints_already_moved)}")
print(f"Endpoints still after generic route: {endpoints_to_move_after_generic}")

if endpoints_to_move_after_generic:
    print("\nNeed to remove duplicate endpoints from original locations")
    print("Running cleanup...")

    # Remove duplicates by finding and deleting old endpoint sections
    # We'll identify each endpoint block and remove it

    new_lines = []
    skip_until_line = None

    for i, line in enumerate(lines):
        # Check if we should start skipping
        for name, start_line in endpoints_to_move_after_generic:
            if i == start_line:
                # Find where this endpoint ends (next # ENDPOINT or end of file)
                end_line = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("# ===========") and lines[
                        j + 1
                    ].strip().startswith("# ENDPOINT"):
                        end_line = j
                        break

                print(f"Removing {name} (lines {i}-{end_line})")
                skip_until_line = end_line
                break

        # Skip if we're in a section to remove
        if skip_until_line is not None and i < skip_until_line:
            continue

        # Reset skip flag when we pass the end
        if skip_until_line is not None and i >= skip_until_line:
            skip_until_line = None

        new_lines.append(line)

    # Write back
    with open(filepath, "w") as f:
        f.writelines(new_lines)

    print(f"\n✅ Removed {len(endpoints_to_move_after_generic)} duplicate endpoints")
    print(f"File reduced from {len(lines)} to {len(new_lines)} lines")
else:
    print("\n✅ All endpoints already in correct order!")
