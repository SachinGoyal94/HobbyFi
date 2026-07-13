import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.domain.models import Vendor, VendorUser, Game, AppUser, Membership, RevenueDaily

async def check():
    async with AsyncSessionLocal() as db:
        try:
            vendors = (await db.execute(select(Vendor))).scalars().all()
            print(f'Vendors: {len(vendors)}')
            for v in vendors:
                print(f'  {v.id} - {v.name} ({v.timezone})')

            users = (await db.execute(select(VendorUser))).scalars().all()
            print(f'VendorUsers: {len(users)}')
            for u in users:
                print(f'  {u.id} - {u.email} ({u.role})')

            games = (await db.execute(select(Game))).scalars().all()
            print(f'Games: {len(games)}')
            for g in games:
                print(f'  {g.id} - {g.slug} ({g.name})')

            app_users = (await db.execute(select(AppUser))).scalars().all()
            print(f'AppUsers: {len(app_users)}')

            memberships = (await db.execute(select(Membership))).scalars().all()
            print(f'Memberships: {len(memberships)}')

            revenue = (await db.execute(select(RevenueDaily))).scalars().all()
            print(f'RevenueDaily: {len(revenue)}')
        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()

asyncio.run(check())