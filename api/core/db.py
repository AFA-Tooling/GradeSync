import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# DATABASE_URL must be set in the environment for Postgres, e.g.:
# postgresql://user:password@host:port/dbname
# Default matches docker-compose.yml database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://gradesync:changeme@localhost:5432/gradesync")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Create tables if they don't exist. Models import happens here to avoid circular imports.
    try:
        from . import models
        models.Base.metadata.create_all(bind=engine)
    except Exception:
        # Defer failures to caller; keep lightweight
        raise
