from sqlacodegen.codegen import CodeGenerator
from sqlalchemy import create_engine
import os

#one time set up script

# Get absolute path to db.db
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, 'db.db')
db_uri = f'sqlite:///{db_path}'

# Create engine and generate code
engine = create_engine(db_uri)
generator = CodeGenerator(engine)

# Write to file
output_path = os.path.join(current_dir, 'lib', 'models', 'generated_models.py')
with open(output_path, 'w') as f:
    f.write(generator.render())
