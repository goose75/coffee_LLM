#!/usr/bin/env python3
"""
Run this script from the coffee_LLM root folder:
  python fix_admin.py

It fixes the FastAPI 204 assertion error in services/api/app/api/v1/admin.py
by adding response_class=Response to the delete endpoint decorator.
"""

import re

path = "services/api/app/api/v1/admin.py"

with open(path) as f:
    content = f.read()

# Fix 1: Add Response to imports if not already there
if "from fastapi.responses import Response" not in content:
    content = content.replace(
        "from fastapi import",
        "from fastapi.responses import Response\nfrom fastapi import",
    )

# Fix 2: Add response_class=Response to the delete mappings decorator
old = '@router.delete("/mappings/{mapping_id}", status_code=204)'
new = '@router.delete("/mappings/{mapping_id}", status_code=204, response_class=Response)'
content = content.replace(old, new)

# Fix 3: Same for any other 204 delete endpoints
content = re.sub(
    r'@router\.delete\(([^)]+),\s*status_code=204\)',
    lambda m: m.group(0).replace('status_code=204)', 'status_code=204, response_class=Response)')
    if 'response_class' not in m.group(0) else m.group(0),
    content,
)

with open(path, "w") as f:
    f.write(content)

print("✓ Fixed admin.py — now run: docker compose restart api")
