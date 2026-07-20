import asyncio

from .db import SessionLocal
from .services import purge_expired_metadata


async def run() -> None:
    async with SessionLocal() as session:
        result = await purge_expired_metadata(session)
        await session.commit()
        print(result)  # noqa: T201 - intended scheduler output is non-sensitive counts


if __name__ == "__main__":
    asyncio.run(run())
