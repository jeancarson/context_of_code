from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from .models.generated_models import Base, Person

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
db_path = os.path.join(ROOT_DIR, 'db.db')
engine = create_engine(f'sqlite:///{db_path}')

# Create all tables
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
