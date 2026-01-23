import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build DATABASE_URL from individual components or use direct URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Build from individual components
    POSTGRES_USER = os.getenv("POSTGRES_USER", "gradesync")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "gradesync")
    # URL encode password to handle special characters
    POSTGRES_PASSWORD_ENCODED = quote_plus(POSTGRES_PASSWORD)
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD_ENCODED}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# 数据库连接配置 - 添加超时和连接池设置
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 检查连接是否有效
    pool_size=5,         # 连接池大小
    max_overflow=10,     # 超出pool_size后最多可创建的连接数
    pool_timeout=30,     # 获取连接的超时时间（秒）
    pool_recycle=1800,   # 连接回收时间（秒），避免连接过期
    connect_args={
        "connect_timeout": 10,  # 连接超时10秒
        "options": "-c statement_timeout=60000"  # SQL语句超时60秒
    }
)
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
