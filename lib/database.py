from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from contextlib import contextmanager
from .models.generated_models import Base, Person
from .config import database

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
engine = create_engine(database.database_url)

# Create all non existing tables, this is in theory not needed since we have the
#sqlacodegen command to generate the models direct from databse schema
#but may be useful in case we manually create models
#in short - does no harm to have here unnessesarily
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
