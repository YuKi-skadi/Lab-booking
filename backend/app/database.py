from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .config import settings
import logging

logger = logging.getLogger("uvicorn")

_storage_backend = settings.storage_backend.lower()
_engine = None
_SessionLocal = None

if _storage_backend in ("sqlite", "mysql", "postgres"):
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
