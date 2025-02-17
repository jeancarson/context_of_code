from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from contextlib import contextmanager
from .models.generated_models import Base as GeneratedBase, Person
from .models.metrics_model import Metrics
from .models.visit_model import Visit
from .models.country_commits_model import CountryCommits
from .config import database

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
engine = create_engine(database.database_url)

# Create all tables
GeneratedBase.metadata.create_all(engine)
CountryCommits.metadata.create_all(engine)

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
    engine = create_engine('sqlite:///metrics.db')
    
    # Get metadata of existing tables
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # Drop old tables if they exist
    if 'search_trends' in metadata.tables:
        metadata.tables['search_trends'].drop(engine)
    if 'celebrity_searches' in metadata.tables:
        metadata.tables['celebrity_searches'].drop(engine)
    
    # Create all tables
    GeneratedBase.metadata.create_all(engine)
    CountryCommits.metadata.create_all(engine)
    return engine

def get_session():
    """Get a new database session"""
    engine = create_engine('sqlite:///metrics.db')
    Session = sessionmaker(bind=engine)
    return Session()
