from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from contextlib import contextmanager
from .models.generated_models import Base, Person, Metrics
from .models.visit_model import Visit
from .models.country_commits_model import CountryCommits
from .models.country_model import Country
from .models.temperature_model import CapitalTemperature
from .config import database
import logging

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
engine = create_engine(database.database_url)

# Create all tables in the correct order
Base.metadata.create_all(engine)

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
    """Initialize the database, creating all tables and dropping old ones"""
    # Use the configured database URL
    engine = create_engine(database.database_url)
    
    # Get metadata of existing tables
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # Drop all existing tables
    metadata.drop_all(bind=engine)
    
    # Create all tables in the correct order
    Base.metadata.create_all(bind=engine)
    
    # Create a session to initialize any required data
    with get_db() as db:
        try:
            # Initialize any required data here
            countries = [
                {'code': 'IE', 'name': 'Ireland', 'capital': 'Dublin'},
                {'code': 'GB', 'name': 'United Kingdom', 'capital': 'London'},
                {'code': 'FR', 'name': 'France', 'capital': 'Paris'}
            ]
            
            for country_data in countries:
                if not db.query(Country).filter_by(code=country_data['code']).first():
                    country = Country(**country_data)
                    db.add(country)
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            raise

# Alias get_db as get_session for compatibility
get_session = get_db
