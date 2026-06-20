#!/usr/bin/env python
"""
Add new roaster stores to the database.
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.store import Store
from app.models.enums import SourceType, ParserStrategy


async def add_roasters():
    """Add three new Shopify roaster stores."""

    # Database connection
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    roasters = [
        {
            "name": "House Coffee of Doncaster",
            "domain": "housecoffeeofdoncaster.com",
            "homepage_url": "https://www.housecoffeeofdoncaster.com/shop",
            "source_type": SourceType.shopify,
            "parser_strategy": ParserStrategy.shopify,
            "roaster_flag": True,
        },
        {
            "name": "Hoxton Coffee",
            "domain": "hoxtoncoffee.com",
            "homepage_url": "https://hoxtoncoffee.com/collections/coffee",
            "source_type": SourceType.shopify,
            "parser_strategy": ParserStrategy.shopify,
            "roaster_flag": True,
        },
        {
            "name": "HR Higgins Ltd",
            "domain": "hrhiggins.co.uk",
            "homepage_url": "https://www.hrhiggins.co.uk/collections/coffee",
            "source_type": SourceType.shopify,
            "parser_strategy": ParserStrategy.shopify,
            "roaster_flag": True,
        },
    ]

    async with async_session() as session:
        for roaster_data in roasters:
            # Check if already exists
            from sqlalchemy import select
            stmt = select(Store).where(Store.domain == roaster_data["domain"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                print(f"✓ {roaster_data['name']} already exists (ID: {existing.id})")
            else:
                # Create new store
                store = Store(
                    id=uuid.uuid4(),
                    name=roaster_data["name"],
                    domain=roaster_data["domain"],
                    homepage_url=roaster_data["homepage_url"],
                    source_type=roaster_data["source_type"],
                    parser_strategy=roaster_data["parser_strategy"],
                    roaster_flag=roaster_data["roaster_flag"],
                    active_flag=True,
                    country_code="GB",
                )
                session.add(store)
                await session.flush()
                print(f"✓ Added {roaster_data['name']} (ID: {store.id})")

        await session.commit()
        print("\n✓ All roasters added successfully!")


if __name__ == "__main__":
    asyncio.run(add_roasters())
