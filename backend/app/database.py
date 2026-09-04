from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from .config import settings
import logging
import os

logger = logging.getLogger("uvicorn")

_storage_backend = settings.storage_backend.lower()
_engine = None
_SessionLocal = None


def _ensure_sqlite_directory():
    url = make_url(settings.database_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return
    db_path = os.path.abspath(url.database)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)


if _storage_backend in ("sqlite", "mysql", "postgres"):
    if _storage_backend == "sqlite":
        _ensure_sqlite_directory()
    _engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if _storage_backend == "sqlite" else {})
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_db():
    if _SessionLocal is None:
        return None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if _engine is not None:
        from .models import Base
        Base.metadata.create_all(bind=_engine)
        _migrate()


def _migrate():
    """Add missing columns for schema updates."""
    if _storage_backend == "sqlite" and _engine is not None:
        migrations = [
            "ALTER TABLE bookings ADD COLUMN custom_data TEXT DEFAULT '{}'",
        ]
        with _engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"Migration applied: {sql}")
                except Exception:
                    pass  # Column already exists
