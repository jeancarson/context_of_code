from typing import Dict, List, Optional
from .database import Person, get_db
from sqlalchemy import select, insert, update, delete, text

class PersonService:
    def __init__(self):
        self.db = next(get_db())

    def _to_api_format(self, db_result) -> dict:
        """Convert database result to API format"""
        if not db_result:
            return None
        return {
            'name': db_result[0],  # Name
            'dob': db_result[1],   # DOB
            'id': db_result[2]     # rowid
        }

    def create_person(self, name: str, dob: str) -> dict:
        # Insert the person
        stmt = insert(Person).values(Name=name, DOB=dob)
        result = self.db.execute(stmt)
        self.db.commit()

        # Get the last inserted ROWID using SQLite's last_insert_rowid()
        result = self.db.execute(text('SELECT last_insert_rowid() as id')).first()
        rowid = result[0]

        # Get the inserted record
        stmt = text('SELECT Name, DOB, rowid FROM Person WHERE rowid = :rowid')
        result = self.db.execute(stmt, {'rowid': rowid}).first()
        return self._to_api_format(result)

    def get_person(self, rowid: int) -> Optional[dict]:
        stmt = text('SELECT Name, DOB, rowid FROM Person WHERE rowid = :rowid')
        result = self.db.execute(stmt, {'rowid': rowid}).first()
        return self._to_api_format(result)

    def get_all_persons(self) -> List[dict]:
        stmt = text('SELECT Name, DOB, rowid FROM Person')
        results = self.db.execute(stmt).all()
        return [self._to_api_format(row) for row in results]

    def update_person(self, rowid: int, name: str, dob: str) -> Optional[dict]:
        stmt = text('UPDATE Person SET Name = :name, DOB = :dob WHERE rowid = :rowid')
        result = self.db.execute(stmt, {'name': name, 'dob': dob, 'rowid': rowid})
        self.db.commit()
        
        if result.rowcount > 0:
            stmt = text('SELECT Name, DOB, rowid FROM Person WHERE rowid = :rowid')
            result = self.db.execute(stmt, {'rowid': rowid}).first()
            return self._to_api_format(result)
        return None

    def delete_person(self, rowid: int) -> bool:
        # First verify the person exists
        stmt = text('SELECT 1 FROM Person WHERE rowid = :rowid')
        exists = self.db.execute(stmt, {'rowid': rowid}).first() is not None
        
        if exists:
            stmt = text('DELETE FROM Person WHERE rowid = :rowid')
            self.db.execute(stmt, {'rowid': rowid})
            self.db.commit()
            return True
        return False