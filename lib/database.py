from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
import os

# Get the root directory of the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create engine and session
db_path = os.path.join(ROOT_DIR, 'db.db')
engine = create_engine(f'sqlite:///{db_path}')
SessionLocal = sessionmaker(bind=engine)

# Reflect the existing database
metadata = MetaData()
Person = Table('Person', metadata, autoload_with=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
