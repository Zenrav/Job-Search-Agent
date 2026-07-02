import os
# 🚀 1. Added async_sessionmaker to the imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_engine():
    """Lazy engine creation — only called at runtime, not at import time."""
    DATABASE_URL = os.getenv("DATABASE_URL")
    print("Db reading alchemy engine")
    return create_async_engine(DATABASE_URL, echo=False)


def get_session_factory(engine):
    # 🚀 2. Swapped standard sessionmaker for async_sessionmaker
    # We can drop class_=AsyncSession because async_sessionmaker defaults to it
    return async_sessionmaker(engine, expire_on_commit=False)


# Runtime singletons — created when first accessed
_engine = None
_AsyncSessionLocal = None


def _get_async_session_local():
    global _engine, _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _engine = get_engine()
        _AsyncSessionLocal = get_session_factory(_engine)
    return _AsyncSessionLocal


# Convenience alias used by agent files
def AsyncSessionLocal():
    return _get_async_session_local()()


async def get_db():
    AsyncSessionLocal_factory = _get_async_session_local()
    # 🚀 This will now work cleanly because the factory supports async context execution
    async with AsyncSessionLocal_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise