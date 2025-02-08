import requests
import json
from typing import Optional, Dict, Any
from lib.constants import HTTPMethod, StatusCode, PersonField, ErrorMessage

class PersonClient:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        
    def _handle_response(self, response: requests.Response, expected_status: StatusCode) -> Dict[str, Any]:
        """Handle API response and validate status code"""
        if response.status_code != expected_status:
            error_msg = response.json().get('error', 'Unknown error') if response.content else 'No response body'
            raise ValueError(f"Expected status {expected_status}, got {response.status_code}. Error: {error_msg}")
        
        return response.json() if response.content else {}

    def create_person(self, name: str, dob: str) -> Dict[str, Any]:
        """Create a new person"""
        print("\nTesting CREATE person...")
        data = {
            PersonField.NAME.value: name,
            PersonField.DOB.value: dob
        }
        response = requests.post(
            f"{self.base_url}/people",
            json=data
        )
        result = self._handle_response(response, StatusCode.CREATED)
        print(f"Created person: {result}")
        return result

    def get_all_persons(self) -> Dict[str, Any]:
        """Get all persons"""
        print("\nTesting GET all persons...")
        response = requests.get(f"{self.base_url}/people")
        result = self._handle_response(response, StatusCode.OK)
        print(f"All persons: {result}")
        return result

    def get_person(self, person_id: int) -> Dict[str, Any]:
        """Get a specific person"""
        print(f"\nTesting GET person {person_id}...")
        response = requests.get(f"{self.base_url}/people/{person_id}")
        result = self._handle_response(response, StatusCode.OK)
        print(f"Person {person_id}: {result}")
        return result

    def update_person(self, person_id: int, name: Optional[str] = None, dob: Optional[str] = None) -> Dict[str, Any]:
        """Update a person"""
        print(f"\nTesting UPDATE person {person_id}...")
        data = {}
        if name is not None:
            data[PersonField.NAME.value] = name
        if dob is not None:
            data[PersonField.DOB.value] = dob
            
        response = requests.put(
            f"{self.base_url}/people/{person_id}",
            json=data
        )
        result = self._handle_response(response, StatusCode.OK)
        print(f"Updated person {person_id}: {result}")
        return result

    def delete_person(self, person_id: int) -> None:
        """Delete a person"""
        print(f"\nTesting DELETE person {person_id}...")
        response = requests.delete(f"{self.base_url}/people/{person_id}")
        self._handle_response(response, StatusCode.NO_CONTENT)
        print(f"Deleted person {person_id}")

def run_tests():
    """Run a complete test suite"""
    client = PersonClient()
    
    try:
        # Test creating a person
        person = client.create_person("John Doe", "1990-01-01")
        person_id = person[PersonField.ID.value]

        # Test getting all persons
        client.get_all_persons()

        # Test getting specific person
        client.get_person(person_id)

        # Test updating person
        client.update_person(person_id, name="John Smith", dob="1990-01-02")

        # Verify the update
        client.get_person(person_id)

        # Test deleting person
        client.delete_person(person_id)

        # Verify deletion (should raise an error)
        try:
            client.get_person(person_id)
        except ValueError as e:
            print(f"Successfully verified deletion: {e}")
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed: {str(e)}")

if __name__ == "__main__":
    run_tests()
