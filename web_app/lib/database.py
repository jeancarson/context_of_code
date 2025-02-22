import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from .models.generated_models import Base, Metrics, Visits, Devices, MetricTypes

logger = logging.getLogger(__name__)

# Get the web_app directory path
WEB_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database URL - use web_app/db.db
db_path = os.path.join(WEB_APP_DIR, 'db.db')
logger.info(f"Using database at: {db_path}")
db_url = f"sqlite:///{db_path}?timeout=30&check_same_thread=False"

# Create engine with connection pooling and timeout
engine = create_engine(
    db_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=0,
    pool_timeout=30,
    connect_args={
        'timeout': 30,
        'check_same_thread': False
    }
)

# Create scoped session factory
Session = scoped_session(sessionmaker(
    bind=engine,
    expire_on_commit=False  # Don't expire objects after commit
))

@contextmanager
def get_db():
    """Get a database session with proper resource management"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()
        Session.remove()  # Remove session from registry

def init_db():
    """Initialize database, creating tables only if they don't exist"""
    try:
        # Create tables only if they don't exist
        Base.metadata.create_all(engine)
        
        # Verify we can connect
        with get_db() as db:
            db.execute(text('SELECT 1'))
            logger.info("Database connection verified successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
