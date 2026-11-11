"""Explicit one-time normalization formerly performed on every startup.

Run with: python -m migrations.normalize_executive_departments
"""

import asyncio
from core.database import col, close_db


async def main():
    try:
        for role, department in [("ceo", "Executive"), ("hr", "People & Culture")]:
            result = await col("users").update_many(
                {"role": {"$regex": f"^{role}$", "$options": "i"}},
                {"$set": {"dept": department}})
            print(f"{role}: {result.modified_count} departments updated")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
