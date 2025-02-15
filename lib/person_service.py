from typing import Dict, List, Optional
from .database import Person, get_db

class PersonService:
    def __init__(self):
        self.db = None
        with get_db() as session:
            self.db = session

    def create_person(self, name: str, dob: str) -> dict:
        with get_db() as session:
            # Create new person
            person = Person(Name=name, DOB=dob)
            session.add(person)
            session.commit()
            return {
                'id': person.ROWID,
                'name': person.Name,
                'dob': person.DOB
            }

    def get_person(self, rowid: int) -> Optional[dict]:
        with get_db() as session:
            person = session.query(Person).filter(Person.ROWID == rowid).first()
            if not person:
                return None
            return {
                'id': person.ROWID,
                'name': person.Name,
                'dob': person.DOB
            }

    def get_all_persons(self) -> List[dict]:
        with get_db() as session:
            persons = session.query(Person).all()
            return [{
                'id': person.ROWID,
                'name': person.Name,
                'dob': person.DOB
            } for person in persons]

    def update_person(self, rowid: int, name: str, dob: str) -> Optional[dict]:
        with get_db() as session:
            person = session.query(Person).filter(Person.ROWID == rowid).first()
            if not person:
                return None
            
            person.Name = name
            person.DOB = dob
            session.commit()
            return {
                'id': person.ROWID,
                'name': person.Name,
                'dob': person.DOB
            }

    def delete_person(self, rowid: int) -> bool:
        with get_db() as session:
            person = session.query(Person).filter(Person.ROWID == rowid).first()
            if not person:
                return False
            
            session.delete(person)
            session.commit()
            return True