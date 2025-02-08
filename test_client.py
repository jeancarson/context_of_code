import requests
import json

BASE_URL = "http://localhost:5000"

def test_create_person():
    print("\nTesting CREATE person...")
    data = {
        "name": "John Doe",
        "dob": "1990-01-01"
    }
    response = requests.post(f"{BASE_URL}/people", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()

def test_get_all_persons():
    print("\nTesting GET all persons...")
    response = requests.get(f"{BASE_URL}/people")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

def test_get_person(person_id):
    print(f"\nTesting GET person {person_id}...")
    response = requests.get(f"{BASE_URL}/people/{person_id}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

def test_update_person(person_id):
    print(f"\nTesting UPDATE person {person_id}...")
    data = {
        "name": "John Smith",
        "dob": "1990-01-02"
    }
    response = requests.put(f"{BASE_URL}/people/{person_id}", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

def test_delete_person(person_id):
    print(f"\nTesting DELETE person {person_id}...")
    response = requests.delete(f"{BASE_URL}/people/{person_id}")
    print(f"Status Code: {response.status_code}")

def run_tests():
    # Create a person and get their ID
    created_person = test_create_person()
    person_id = created_person['id']

    # Test all other operations
    test_get_all_persons()
    test_get_person(person_id)
    test_update_person(person_id)
    test_get_person(person_id)  # Verify the update
    test_delete_person(person_id)
    test_get_person(person_id)  # Verify the deletion

if __name__ == "__main__":
    run_tests()
