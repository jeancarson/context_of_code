from enum import Enum, auto

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

class StatusCode(int, Enum):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500

class ErrorMessage(str, Enum):
    INVALID_CONTENT_TYPE = "Content-Type must be application/json"
    MISSING_REQUIRED_FIELDS = "Missing required fields"
    MISSING_UPDATE_FIELDS = "At least one field (name or dob) is required"
