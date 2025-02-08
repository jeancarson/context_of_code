from flask import jsonify, request, Response
from typing import Tuple, Union
from .constants import StatusCode, PersonField, ErrorMessage
from .person_service import PersonService, Person

class PersonHandler:
    def __init__(self):
        self._service = PersonService()

    def create_person(self) -> Tuple[Response, int]:
        if not request.is_json:
            return jsonify({"error": ErrorMessage.INVALID_CONTENT_TYPE.value}), StatusCode.BAD_REQUEST

        data = request.get_json()
        if not all(k in data for k in (PersonField.NAME.value, PersonField.DOB.value)):
            return jsonify({"error": ErrorMessage.MISSING_REQUIRED_FIELDS.value}), StatusCode.BAD_REQUEST

        person = self._service.create_person(
            name=data[PersonField.NAME.value],
            dob=data[PersonField.DOB.value]
        )
        return jsonify(person.to_dict()), StatusCode.CREATED

    def get_all_persons(self) -> Tuple[Response, int]:
        persons = self._service.get_all_persons()
        return jsonify([p.to_dict() for p in persons]), StatusCode.OK

    def get_person(self, person_id: int) -> Tuple[Response, int]:
        person = self._service.get_person(person_id)
        if person is None:
            return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
        return jsonify(person.to_dict()), StatusCode.OK

    def update_person(self, person_id: int) -> Tuple[Response, int]:
        if not request.is_json:
            return jsonify({"error": ErrorMessage.INVALID_CONTENT_TYPE.value}), StatusCode.BAD_REQUEST

        data = request.get_json()
        if not any(k in data for k in (PersonField.NAME.value, PersonField.DOB.value)):
            return jsonify({"error": ErrorMessage.MISSING_UPDATE_FIELDS.value}), StatusCode.BAD_REQUEST

        person = self._service.update_person(
            person_id=person_id,
            name=data.get(PersonField.NAME.value),
            dob=data.get(PersonField.DOB.value)
        )
        
        if person is None:
            return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
        return jsonify(person.to_dict()), StatusCode.OK

    def delete_person(self, person_id: int) -> Tuple[Response, int]:
        if not self._service.delete_person(person_id):
            return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
        return "", StatusCode.NO_CONTENT
