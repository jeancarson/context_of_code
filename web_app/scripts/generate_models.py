"""
This script generates the models for the database.
Generated models are stored in the lib/models/generated_models.py file.

"""

from sqlacodegen.generators.declarative import generator
from sqlalchemy import create_engine
import os

# Get absolute path to db.db
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, 'db.db')
db_uri = f'sqlite:///{db_path}'

# Create engine and generate code
engine = create_engine(db_uri)
gen = generator.Generator(engine)
code = gen.generate()

# Write to file
output_path = os.path.join(current_dir, 'lib', 'models', 'generated_models.py')
with open(output_path, 'w') as f:
    f.write(code)
