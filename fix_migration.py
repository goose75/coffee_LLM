#!/usr/bin/env python3
"""
Run from the coffee_LLM root folder:
  python3 fix_migration.py
"""

import glob

# Find the migration file
files = glob.glob("services/api/alembic/versions/*.py")
print(f"Found migration files: {files}")

for path in files:
    with open(path) as f:
        content = f.read()

    changed = False

    # Fix bad JSON defaults — triple-quoted strings are invalid SQL
    # '''[]''' -> '[]'
    # '''{}''' -> '{}'
    if "'''[]'''" in content:
        content = content.replace("'''[]'''", "'[]'")
        changed = True
        print(f"✓ Fixed '''[]''' in {path}")

    if "'''{}'''" in content:
        content = content.replace("'''{}'''", "'{}'")
        changed = True
        print(f"✓ Fixed '''{{}}''' in {path}")

    # Also fix any other triple-quoted SQL defaults
    import re
    triple_quoted = re.findall(r"'''[^']*'''", content)
    for match in triple_quoted:
        fixed = match[1:-1]  # strip one layer of quotes each side
        content = content.replace(match, fixed)
        changed = True
        print(f"✓ Fixed {match} -> {fixed} in {path}")

    if changed:
        with open(path, "w") as f:
            f.write(content)
    else:
        print(f"  No changes needed in {path}")

print("\nDone. Now run:")
print("  docker exec coffee_api alembic downgrade base")
print("  docker exec coffee_api alembic upgrade head")
