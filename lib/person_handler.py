from flask import jsonify, request, Response, make_response
from typing import Tuple, Union
from .constants import StatusCode, PersonField, ErrorMessage
from .person_service import PersonService

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
        return jsonify(person), StatusCode.CREATED

    def get_all_persons(self) -> Tuple[Response, int]:
        persons = self._service.get_all_persons()
        return jsonify(persons), StatusCode.OK

    def get_person(self, person_id: int) -> Tuple[Response, int]:
        person = self._service.get_person(person_id)
        if person is None:
            return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
        return jsonify(person), StatusCode.OK

    def update_person(self, person_id: int) -> Tuple[Response, int]:
        if not request.is_json:
            return jsonify({"error": ErrorMessage.INVALID_CONTENT_TYPE.value}), StatusCode.BAD_REQUEST

        data = request.get_json()
        if not all(k in data for k in (PersonField.NAME.value, PersonField.DOB.value)):
            return jsonify({"error": ErrorMessage.MISSING_REQUIRED_FIELDS.value}), StatusCode.BAD_REQUEST

        person = self._service.update_person(
            rowid=person_id,
            name=data[PersonField.NAME.value],
            dob=data[PersonField.DOB.value]
        )
        if person is None:
            return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
        return jsonify(person), StatusCode.OK

    def delete_person(self, person_id: int) -> Response:
        if self._service.delete_person(person_id):
            response = make_response('', StatusCode.NO_CONTENT)
            return response
        return jsonify({"error": ErrorMessage.PERSON_NOT_FOUND.value}), StatusCode.NOT_FOUND
