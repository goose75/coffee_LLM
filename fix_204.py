#!/usr/bin/env python3
"""
Run from the coffee_LLM root folder:
  python3 fix_204.py
"""

path = "services/api/app/api/v1/admin.py"

with open(path) as f:
    content = f.read()

# Change all 204 delete decorators to use 200 instead
# This is the simplest reliable fix across all FastAPI versions
content = content.replace(
    ', status_code=204, response_class=Response)',
    ', status_code=200)',
)
content = content.replace(
    ', status_code=204)',
    ', status_code=200)',
)

# Also fix any delete functions that return None to return a dict instead
# Find the delete_mapping function and fix its return
old = '''async def delete_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a mapping entry."""
    try:
        mid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    row = (await db.execute(
        select(NormalisationMapping).where(NormalisationMapping.id == mid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.delete(row)
    await db.commit()'''

new = '''async def delete_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a mapping entry."""
    try:
        mid = uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")
    row = (await db.execute(
        select(NormalisationMapping).where(NormalisationMapping.id == mid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": True}'''

if old in content:
    content = content.replace(old, new)
    print("✓ Fixed delete_mapping function")
else:
    # Fallback: just remove -> None return annotations from delete functions
    import re
    content = re.sub(
        r'(async def delete_\w+[^)]*\)) -> None:',
        r'\1:',
        content
    )
    print("✓ Fixed delete function return annotations")

# Remove the Response import we added since we no longer need it
content = content.replace("from fastapi.responses import Response\n", "")

with open(path, "w") as f:
    f.write(content)

print("✓ Done — run: docker compose restart api")
