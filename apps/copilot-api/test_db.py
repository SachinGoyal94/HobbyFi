import asyncio
from app.db.session import engine
from app.domain.models import Base

async def test():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Tables created successfully")
        await engine.dispose()
        print("Connection test passed")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test())