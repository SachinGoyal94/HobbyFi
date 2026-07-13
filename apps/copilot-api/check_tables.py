import asyncio
import sys
from sqlalchemy import text
from app.db.session import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = result.fetchall()
        table_names = [t[0] for t in tables]
        print('Existing tables:', table_names, file=sys.stderr)
        return table_names

tables = asyncio.run(check())
print('Result:', tables)