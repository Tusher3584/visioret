"""Database engine/session setup. Reads DATABASE_URL from the environment
(via a .env file in local dev), falling back to a sensible local default.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://visioret:visioret@localhost:5433/visioret"
)

# pool_pre_ping: check a pooled connection is still alive before handing it
# out. Without it, every connection in the pool is dead after the database
# restarts, and requests fail with "server closed the connection unexpectedly"
# until the pool happens to turn over. That is not hypothetical here -- the
# db container has been restarted mid-session more than once.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency: yields a session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
