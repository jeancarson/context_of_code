from typing import Dict, List, Optional
from .database import Person, get_db

class PersonService:
    def __init__(self):
        self.db = next(get_db())

    def create_person(self, name: str, dob: str) -> dict:
        # Create new person
        person = Person(Name=name, DOB=dob)
        self.db.add(person)
        self.db.commit()
        return {
            'id': person.ROWID,
            'name': person.Name,
            'dob': person.DOB
        }

    def get_person(self, rowid: int) -> Optional[dict]:
        person = self.db.query(Person).filter(Person.ROWID == rowid).first()
        if not person:
            return None
        return {
            'id': person.ROWID,
            'name': person.Name,
            'dob': person.DOB
        }

    def get_all_persons(self) -> List[dict]:
        persons = self.db.query(Person).all()
        return [{
            'id': person.ROWID,
            'name': person.Name,
            'dob': person.DOB
        } for person in persons]

    def update_person(self, rowid: int, name: str, dob: str) -> Optional[dict]:
        person = self.db.query(Person).filter(Person.ROWID == rowid).first()
        if not person:
            return None
        
        person.Name = name
        person.DOB = dob
        self.db.commit()
        return {
            'id': person.ROWID,
            'name': person.Name,
            'dob': person.DOB
        }

    def delete_person(self, rowid: int) -> bool:
        person = self.db.query(Person).filter(Person.ROWID == rowid).first()
        if not person:
            return False
        
        self.db.delete(person)
        self.db.commit()
        return True