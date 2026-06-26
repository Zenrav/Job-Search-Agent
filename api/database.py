import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Base is defined here so Alembic can import it without touching the engine
Base = declarative_base()


def get_engine():
    """Lazy engine creation — only called at runtime, not at import time."""
    DATABASE_URL = os.getenv("DATABASE_URL")
    return create_async_engine(DATABASE_URL, echo=False)


def get_session_factory(engine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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
@property
def AsyncSessionLocal():
    return _get_async_session_local()


async def get_db():
    AsyncSessionLocal = _get_async_session_local()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise