from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.base import Base
import logging
from sqlalchemy import text

# Configure SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)  # Only show WARNING and above
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)  # Only show WARNING and above

DATABASE_URL = "sqlite+aiosqlite:///./aibangumi.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Disable echo to prevent info logs
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_schema(conn)


async def _migrate_schema(conn) -> None:
    await _ensure_column(conn, "source", "multi_season", "BOOLEAN", default="0")
    await _ensure_column(conn, "file", "extracted_season", "INTEGER")
    await _ensure_column(conn, "file", "final_season", "INTEGER")


async def _ensure_column(conn, table: str, column: str, col_type: str, default: str | None = None) -> None:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    existing = {row[1] for row in result.fetchall()}
    if column in existing:
        return
    default_clause = f" DEFAULT {default}" if default is not None else ""
    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"))

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
