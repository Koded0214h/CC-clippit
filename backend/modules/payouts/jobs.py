from core.database import AsyncSessionLocal

from . import service


async def reconcile_tick() -> int:
    async with AsyncSessionLocal() as db:
        return await service.reconcile(db)
