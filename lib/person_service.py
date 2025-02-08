from dataclasses import dataclass
from typing import Dict, List, Optional
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass
class Person:
    name: str
    dob: str
    id: Optional[int] = None

class PersonService:
    def __init__(self):
        self._persons: Dict[int, Person] = {}
        self._next_id: int = 1

    def create_person(self, name: str, dob: str) -> Person:
        person = Person(name=name, dob=dob, id=self._next_id)
        self._persons[self._next_id] = person
        self._next_id += 1
        return person

    def get_person(self, person_id: int) -> Optional[Person]:
        return self._persons.get(person_id)

    def get_all_persons(self) -> List[Person]:
        return list(self._persons.values())

    def update_person(self, person_id: int, name: Optional[str] = None, dob: Optional[str] = None) -> Optional[Person]:
        person = self._persons.get(person_id)
        if person is None:
            return None
        
        if name is not None:
            person.name = name
        if dob is not None:
            person.dob = dob
        
        return person

    def delete_person(self, person_id: int) -> bool:
        if person_id not in self._persons:
            return False
        del self._persons[person_id]
        return True
