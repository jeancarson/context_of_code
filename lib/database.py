from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from contextlib import contextmanager
from .models.generated_models import Base, Person, Metrics
from .models.visit_model import Visit
from .models.temperature_model import CapitalTemperature
from .config import database
import logging

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
engine = create_engine(database.database_url)

# Create a scoped session factory
Session = scoped_session(sessionmaker(bind=engine))

@contextmanager
def get_db():
    """Get a database session using a context manager.
    
    Usage:
        with get_db() as db:
            result = db.query(Person).all()
            # session is automatically closed after the with block
    """
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
        Session.remove()

def init_db():
    """Initialize the database, creating only missing tables"""
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logging.info("Database tables verified/created successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

# Alias get_db as get_session for compatibility
get_session = get_db
