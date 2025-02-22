import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from .models.generated_models import Base, Metrics, Visits, Devices, MetricTypes

logger = logging.getLogger(__name__)

# Get the web_app directory path
WEB_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database URL - use web_app/db.db
db_path = os.path.join(WEB_APP_DIR, 'db.db')
logger.info(f"Using database at: {db_path}")
DATABASE_URL = f"sqlite:///{db_path}"

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database, creating tables only if they don't exist"""
    try:
        # Create tables only if they don't exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Get list of tables we need
        needed_tables = {table.__tablename__ for table in Base.__subclasses__()}
        
        # Create only missing tables
        missing_tables = needed_tables - set(existing_tables)
        if missing_tables:
            logger.info(f"Creating missing tables: {missing_tables}")
            Base.metadata.create_all(bind=engine)
        else:
            logger.info("All required tables already exist")
        
        # Verify we can connect
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

@contextmanager
def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
